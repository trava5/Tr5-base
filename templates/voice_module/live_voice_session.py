"""Orchestrates one continuous voice turn-loop: listen, transcribe, ask,
speak, listen again — until stopped.

Listening and speaking are sequential, not simultaneous (open one input
stream, run it to completion, close it; then open one output stream, run
it to completion, close it) — a simple CLI microphone/speaker setup has no
echo cancellation, so streaming the mic while playback is active would let
the assistant hear itself. This mirrors how a person actually holds a
voice conversation: listen, think, speak, then listen again.

Depends only on the `AudioBackend`/`VoiceBridge` Protocols from
`audio_io.py`/`gemini_voice_bridge.py`, not their real implementations —
a test can supply fakes for both without touching hardware or the network
(PRINCIPLES.md P4).
"""

from __future__ import annotations

import threading
from typing import Callable, Iterator, Optional

from .audio_io import AudioBackend, AudioStream
from .gemini_voice_bridge import SPEAK_SAMPLE_RATE, TRANSCRIBE_SAMPLE_RATE, VoiceBridge

CHANNELS = 1
DEFAULT_CHUNK_SIZE = 1024


class LiveVoiceSession:
    """One `/voice` session for `chat_architect.py` (Tr5-base decision 4).

    `ask_callback` is the Architect's own `ClaudeThread`/`CodexThread.ask`
    — this class never talks to the reasoning model directly, only to
    `bridge` (Gemini, STT/TTS only) and `audio_backend` (the microphone
    and speakers).
    """

    def __init__(
        self,
        *,
        audio_backend: AudioBackend,
        bridge: VoiceBridge,
        ask_callback: Callable[[str], str],
        on_user_text: Optional[Callable[[str], None]] = None,
        on_assistant_text: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        self._audio = audio_backend
        self._bridge = bridge
        self._ask_callback = ask_callback
        self._on_user_text = on_user_text
        self._on_assistant_text = on_assistant_text
        self._on_error = on_error
        self._chunk_size = chunk_size
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            raise RuntimeError("Voice session is already running.")
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="LiveVoiceSession", daemon=True)
        self._thread.start()

    def stop(self, *, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        self._audio.terminate()

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self._run_one_turn()
        except Exception as error:  # noqa: BLE001 - reported, not swallowed silently
            if self._on_error is not None:
                self._on_error(error)
            else:
                raise

    def _run_one_turn(self) -> None:
        user_text = self._listen_and_transcribe()
        if not user_text or self._stop.is_set():
            return
        if self._on_user_text is not None:
            self._on_user_text(user_text)

        assistant_text = self._ask_callback(user_text)
        if self._on_assistant_text is not None:
            self._on_assistant_text(assistant_text)

        if assistant_text and not self._stop.is_set():
            self._speak(assistant_text)

    def _listen_and_transcribe(self) -> str:
        stream = self._audio.open_input_stream(
            rate=TRANSCRIBE_SAMPLE_RATE, channels=CHANNELS, chunk_size=self._chunk_size
        )
        try:
            return self._bridge.transcribe_turn(self._read_mic_chunks(stream), self._stop)
        finally:
            stream.stop_stream()
            stream.close()

    def _read_mic_chunks(self, stream: AudioStream) -> Iterator[bytes]:
        while not self._stop.is_set():
            yield stream.read(self._chunk_size, exception_on_overflow=False)

    def _speak(self, text: str) -> None:
        stream = self._audio.open_output_stream(rate=SPEAK_SAMPLE_RATE, channels=CHANNELS)
        try:
            for chunk in self._bridge.speak_text(text, self._stop):
                if self._stop.is_set():
                    break
                stream.write(chunk)
        finally:
            stream.stop_stream()
            stream.close()
