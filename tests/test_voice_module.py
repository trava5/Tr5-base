from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from typing import Iterable, Iterator

import pytest

from templates.voice_module.audio_io import PyAudioBackend
from templates.voice_module.gemini_voice_bridge import GeminiVoiceBridge, VoiceBridgeConfig
from templates.voice_module.live_voice_session import LiveVoiceSession


# ---------------------------------------------------------------------------
# Real deferred-import checks (PRINCIPLES.md P2). Neither call below reaches
# real audio hardware or a real network request — constructing `pyaudio.
# PyAudio()` succeeds even with zero devices present, and constructing
# `genai.Client(api_key=...)` is purely local (no request is made until a
# real API call is issued) — so both are safe to exercise for real here.
# ---------------------------------------------------------------------------


def test_pyaudio_backend_real_import_and_lifecycle() -> None:
    backend = PyAudioBackend()
    try:
        assert backend is not None
    finally:
        backend.terminate()


def test_gemini_voice_bridge_real_import_and_construction() -> None:
    bridge = GeminiVoiceBridge(
        VoiceBridgeConfig(api_key="fake-test-key-not-real", live_model="models/fake")
    )
    assert bridge is not None


# ---------------------------------------------------------------------------
# Fakes for orchestration tests (PRINCIPLES.md P4) — no real hardware or
# network reachable from here.
# ---------------------------------------------------------------------------


class FakeAudioStream:
    def __init__(self, chunks: list[bytes] | None = None) -> None:
        self._chunks = list(chunks or [])
        self.written: list[bytes] = []
        self.closed = False
        self.stopped = False

    def read(self, num_frames: int, exception_on_overflow: bool = False) -> bytes:
        if self._chunks:
            return self._chunks.pop(0)
        return b"\x00" * num_frames

    def write(self, data: bytes) -> None:
        self.written.append(data)

    def stop_stream(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True


class FakeAudioBackend:
    def __init__(self) -> None:
        self.input_streams: list[FakeAudioStream] = []
        self.output_streams: list[FakeAudioStream] = []
        self.terminated = False

    def open_input_stream(self, *, rate: int, channels: int, chunk_size: int) -> FakeAudioStream:
        stream = FakeAudioStream()
        self.input_streams.append(stream)
        return stream

    def open_output_stream(self, *, rate: int, channels: int) -> FakeAudioStream:
        stream = FakeAudioStream()
        self.output_streams.append(stream)
        return stream

    def terminate(self) -> None:
        self.terminated = True


class FakeVoiceBridge:
    """Scripted bridge: returns each entry of `turns` in order, one per
    `transcribe_turn` call, then sets `stop` once exhausted so a session
    under test ends on its own instead of needing a hard timeout."""

    def __init__(self, turns: list[str]) -> None:
        self._turns = list(turns)
        self.spoken: list[str] = []

    def transcribe_turn(self, audio_chunks: Iterable[bytes], stop: threading.Event) -> str:
        for _ in audio_chunks:
            break  # draining mirrors what the real bridge does with a real generator
        if not self._turns:
            stop.set()
            return ""
        return self._turns.pop(0)

    def speak_text(self, text: str, stop: threading.Event) -> Iterator[bytes]:
        self.spoken.append(text)
        yield b"chunk-1"
        yield b"chunk-2"


class BlockingBridge:
    """Bridge whose `transcribe_turn` blocks until `stop` is set — a
    session using this stays "running" indefinitely, without relying on
    any real wall-clock pacing to simulate "still listening"."""

    def __init__(self) -> None:
        self.transcribe_calls = 0

    def transcribe_turn(self, audio_chunks: Iterable[bytes], stop: threading.Event) -> str:
        self.transcribe_calls += 1
        stop.wait()
        return ""

    def speak_text(self, text: str, stop: threading.Event) -> Iterator[bytes]:
        yield b""


def _wait_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met within timeout")


def test_live_voice_session_runs_a_full_turn_end_to_end() -> None:
    audio = FakeAudioBackend()
    bridge = FakeVoiceBridge(turns=["hello architect"])
    asked: list[str] = []

    def ask_callback(text: str) -> str:
        asked.append(text)
        return "hello back"

    session = LiveVoiceSession(audio_backend=audio, bridge=bridge, ask_callback=ask_callback)
    session.start()
    try:
        _wait_until(lambda: bridge.spoken == ["hello back"])
    finally:
        session.stop()

    assert asked == ["hello architect"]
    assert audio.output_streams[0].written == [b"chunk-1", b"chunk-2"]
    assert audio.terminated


def test_live_voice_session_skips_ask_and_speak_on_empty_transcript() -> None:
    audio = FakeAudioBackend()
    bridge = FakeVoiceBridge(turns=["", "second turn"])
    asked: list[str] = []
    session = LiveVoiceSession(
        audio_backend=audio,
        bridge=bridge,
        ask_callback=lambda text: asked.append(text) or "reply",
    )
    session.start()
    try:
        _wait_until(lambda: asked == ["second turn"])
    finally:
        session.stop()

    assert asked == ["second turn"]
    assert bridge.spoken == ["reply"]


def test_live_voice_session_stop_is_idempotent_and_terminates_audio_once() -> None:
    audio = FakeAudioBackend()
    bridge = BlockingBridge()
    session = LiveVoiceSession(audio_backend=audio, bridge=bridge, ask_callback=lambda text: "reply")
    session.start()
    _wait_until(lambda: bridge.transcribe_calls >= 1)

    session.stop()
    assert audio.terminated
    assert not session.is_running

    session.stop()  # must not raise the second time


def test_live_voice_session_starting_twice_raises() -> None:
    audio = FakeAudioBackend()
    bridge = BlockingBridge()
    session = LiveVoiceSession(audio_backend=audio, bridge=bridge, ask_callback=lambda text: "reply")
    session.start()
    try:
        _wait_until(lambda: bridge.transcribe_calls >= 1)
        with pytest.raises(RuntimeError):
            session.start()
    finally:
        session.stop()


def test_live_voice_session_reports_errors_via_on_error_instead_of_crashing_silently() -> None:
    audio = FakeAudioBackend()

    class ExplodingBridge:
        def transcribe_turn(self, audio_chunks, stop):
            raise RuntimeError("boom")

        def speak_text(self, text, stop):
            yield b""

    errors: list[Exception] = []
    session = LiveVoiceSession(
        audio_backend=audio,
        bridge=ExplodingBridge(),
        ask_callback=lambda text: "unused",
        on_error=lambda error: errors.append(error),
    )
    session.start()
    try:
        _wait_until(lambda: len(errors) == 1)
    finally:
        session.stop()

    assert isinstance(errors[0], RuntimeError)


# ---------------------------------------------------------------------------
# Regression test for the event-loop-blocking fix in
# `GeminiVoiceBridge._transcribe_turn_async` (see its own comment).
# ---------------------------------------------------------------------------


class _FakeLiveSession:
    def __init__(self, events: list[object]) -> None:
        self._events = events
        self.sent: list[bytes] = []

    async def send_realtime_input(self, *, audio) -> None:
        self.sent.append(audio.data)

    async def receive(self):
        for event in self._events:
            yield event


class _FakeLiveConnectContext:
    def __init__(self, session: _FakeLiveSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeLiveSession:
        return self._session

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


def test_gemini_voice_bridge_transcribe_reads_mic_chunks_off_the_event_loop_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard for `_transcribe_turn_async()`'s `_send()`: each
    mic-chunk `next()` call must run on a worker thread (`asyncio.
    to_thread`), never directly on the event loop's own thread (the thread
    that calls `bridge.transcribe_turn()`, since `asyncio.run()` drives the
    loop on the calling thread, not a new one). A real microphone read
    blocks for as long as one chunk takes to arrive; running that call
    directly on the event loop thread would stall delivery of
    `turn_complete` for that same duration, on every single chunk sent
    during an utterance, not just once — PRINCIPLES.md P16's concern about
    a fake's *pacing*, tested here more precisely via thread identity
    rather than a wall-clock timing threshold (which chunk pacing under a
    real microphone would make correct but easy to make flaky here).
    """
    events = [
        SimpleNamespace(
            server_content=SimpleNamespace(
                input_transcription=SimpleNamespace(text="hi"), turn_complete=False
            )
        ),
        SimpleNamespace(
            server_content=SimpleNamespace(input_transcription=None, turn_complete=True)
        ),
    ]
    session = _FakeLiveSession(events)
    bridge = GeminiVoiceBridge(
        VoiceBridgeConfig(api_key="fake-test-key-not-real", live_model="models/fake")
    )
    monkeypatch.setattr(
        bridge._client.aio.live, "connect", lambda **kwargs: _FakeLiveConnectContext(session)
    )

    calling_thread = threading.current_thread()
    read_threads: list[threading.Thread] = []

    def _mic_chunks() -> Iterator[bytes]:
        while True:
            read_threads.append(threading.current_thread())
            yield b"chunk"

    text = bridge.transcribe_turn(_mic_chunks(), threading.Event())

    assert text == "hi"
    assert read_threads, "the mic generator was never read from"
    assert all(thread is not calling_thread for thread in read_threads)
