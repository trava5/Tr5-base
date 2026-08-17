"""Gemini Live API used purely for speech-to-text / text-to-speech duty.

Tr5-base decision 4 / ADR-033: `chat_architect.py` talks to the Architect
through its own Codex/Claude Agent SDK thread (`agents/agent.py`) — Gemini
is never the one reasoning about the conversation here. This bridge opens
two independent, short-lived Gemini Live sessions per voice turn: one that
transcribes microphone audio to text (`transcribe_turn`), and one that
speaks a given piece of text back verbatim (`speak_text`). Neither session's
own generated reply is ever used as the assistant's answer — the answer
always comes from `LiveVoiceSession`'s `ask_callback` (the Architect).

This intentionally does not reuse `Tr5-platform`'s
`backend/services/gemini_live_audio_handler.py` pattern of "one Live
session IS the assistant" — that pattern is right for `voice_agent`, where
Gemini itself is the conversational agent, but wrong here, where Gemini is
a decoupled STT/TTS utility only. What *is* reused, because it is a proven
mechanism (PRINCIPLES.md P11): reading `input_transcription`/
`output_transcription`/`turn_complete` events off `session.receive()`, and
the "call `session.receive()` again for every turn, for as long as the
connection stays open" pattern documented in that same source file.

Also unlike `voice_agent`: there is no FastAPI backend and no websocket
hop in `chat_architect.py` — the local process talks to Gemini directly.
`google.genai` is imported lazily inside `GeminiVoiceBridge.__init__`, not
at module level, for the same reason `audio_io.py` defers `pyaudio` (stays
importable without the dependency installed; PRINCIPLES.md P2 — a deferred
import is still exercised by a real test, not exempted from one — see
`tests/test_voice_module.py::test_gemini_voice_bridge_real_import_and_construction`).
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Iterable, Iterator, Protocol

TRANSCRIBE_SAMPLE_RATE = 16000
SPEAK_SAMPLE_RATE = 24000
AUDIO_INPUT_MIME_TYPE = "audio/pcm;rate=16000"

# Instructs the TTS session to act as a verbatim reader, not a second
# conversational partner — the whole point of decoupling STT/TTS from the
# Architect's own reasoning is defeated if this session improvises instead
# of reading exactly what it is given.
_SPEAK_SYSTEM_INSTRUCTION = (
    "You are a text-to-speech engine. Speak the following text aloud "
    "exactly as given, with no additions, no commentary, no changes, and "
    "no follow-up questions."
)


@dataclass(frozen=True)
class VoiceBridgeConfig:
    api_key: str
    live_model: str


class VoiceBridge(Protocol):
    """What `LiveVoiceSession` needs from a Gemini STT/TTS bridge.

    A test fake implements this without any real network access, per
    PRINCIPLES.md P4.
    """

    def transcribe_turn(self, audio_chunks: Iterable[bytes], stop: threading.Event) -> str: ...

    def speak_text(self, text: str, stop: threading.Event) -> Iterator[bytes]: ...


class GeminiVoiceBridge:
    """Real backend: two independent, on-demand Gemini Live sessions."""

    def __init__(self, config: VoiceBridgeConfig) -> None:
        from google import genai  # deferred — see module docstring

        self._genai = genai
        self._config = config
        self._client = genai.Client(api_key=config.api_key)

    def transcribe_turn(self, audio_chunks: Iterable[bytes], stop: threading.Event) -> str:
        return asyncio.run(self._transcribe_turn_async(audio_chunks, stop))

    async def _transcribe_turn_async(
        self, audio_chunks: Iterable[bytes], stop: threading.Event
    ) -> str:
        from google.genai import types

        config = types.LiveConnectConfig(
            response_modalities=["TEXT"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )
        fragments: list[str] = []
        async with self._client.aio.live.connect(
            model=self._config.live_model, config=config
        ) as session:

            async def _send() -> None:
                # `audio_chunks` is a plain synchronous iterable — each
                # `next()` call blocks on a real microphone read
                # (`stream.read()` in `live_voice_session.py`). Calling
                # `next()` directly inside this coroutine would block the
                # single-threaded event loop for the duration of that
                # hardware read, starving `_receive()` below and delaying
                # delivery of `turn_complete` — the same class of timing
                # bug PRINCIPLES.md P16 warns about (a fake with an
                # instant `next()` would never expose this; a real
                # microphone's natural pacing would). Offload each
                # `next()` call to a worker thread instead, so the loop
                # stays free to run `_receive()` concurrently.
                iterator = iter(audio_chunks)
                while not stop.is_set():
                    chunk = await asyncio.to_thread(next, iterator, None)
                    if chunk is None or stop.is_set():
                        return
                    await session.send_realtime_input(
                        audio=types.Blob(data=chunk, mime_type=AUDIO_INPUT_MIME_TYPE)
                    )

            async def _receive() -> None:
                async for message in session.receive():
                    content = message.server_content
                    if content is None:
                        continue
                    if content.input_transcription and content.input_transcription.text:
                        fragments.append(content.input_transcription.text)
                    if content.turn_complete:
                        return

            send_task = asyncio.create_task(_send())
            receive_task = asyncio.create_task(_receive())
            done, pending = await asyncio.wait(
                {send_task, receive_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            for task in done:
                task.result()
        return "".join(fragments).strip()

    def speak_text(self, text: str, stop: threading.Event) -> Iterator[bytes]:
        return iter(asyncio.run(self._speak_text_async(text, stop)))

    async def _speak_text_async(self, text: str, stop: threading.Event) -> list[bytes]:
        from google.genai import types

        config = types.LiveConnectConfig(
            system_instruction=_SPEAK_SYSTEM_INSTRUCTION,
            response_modalities=["AUDIO"],
        )
        chunks: list[bytes] = []
        async with self._client.aio.live.connect(
            model=self._config.live_model, config=config
        ) as session:
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=text)]),
                turn_complete=True,
            )
            async for message in session.receive():
                if stop.is_set():
                    break
                content = message.server_content
                if content is None:
                    continue
                if content.model_turn and content.model_turn.parts:
                    for part in content.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            chunks.append(part.inline_data.data)
                if content.turn_complete:
                    break
        return chunks
