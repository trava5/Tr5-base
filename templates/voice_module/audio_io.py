"""Microphone/speaker audio I/O, isolated behind a small Protocol.

`PyAudioBackend` wraps exactly **one** shared `pyaudio.PyAudio()` instance
for every stream it opens, whether that stream is later read from a send
thread or written to from a receive thread. Creating a second, independent
`pyaudio.PyAudio()` instance while another thread already has an active
stream is a documented source of a hard access violation on Windows during
PortAudio host API initialization — this is exactly PRINCIPLES.md P17
(native/hardware library instances often need to be shared across threads,
not created per-thread), extracted from `Tr5-platform`'s own
`client/live_audio_client.py` incident (see its `_send_microphone_audio`/
`_receive_and_play` docstrings) and `pyaudio_diagnostic.py`. Do not
construct a second `PyAudioBackend` (or a second raw `pyaudio.PyAudio()`)
anywhere in a single voice session — pass the one instance around instead.

`pyaudio` is imported lazily, inside `PyAudioBackend.__init__`, not at
module level — this keeps `audio_io.py` importable (and its Protocols
usable for type-checking/fakes) even in an environment without the
PortAudio system library installed. PRINCIPLES.md P2 ("verify deferred
imports too") applies: a deferred import still needs to be exercised by a
real test, not assumed to work just because it is wrapped in a function —
see `tests/test_voice_module.py::test_pyaudio_backend_real_import_and_lifecycle`.
"""

from __future__ import annotations

from typing import Protocol


class AudioStream(Protocol):
    """Shared surface both an input (mic) and output (speaker) stream need.

    A real `pyaudio.Stream` already satisfies this Protocol structurally —
    no adapter class is needed for the real backend.
    """

    def read(self, num_frames: int, exception_on_overflow: bool = ...) -> bytes: ...

    def write(self, data: bytes) -> None: ...

    def stop_stream(self) -> None: ...

    def close(self) -> None: ...


class AudioBackend(Protocol):
    """What `LiveVoiceSession` needs from an audio backend.

    Deliberately narrow — only what a voice session actually calls — so a
    test fake can implement it without touching real hardware, per
    PRINCIPLES.md P4 (verification isolated from real external systems
    must be structurally tied to that isolation, not just instructed).
    """

    def open_input_stream(self, *, rate: int, channels: int, chunk_size: int) -> AudioStream: ...

    def open_output_stream(self, *, rate: int, channels: int) -> AudioStream: ...

    def terminate(self) -> None: ...


class PyAudioBackend:
    """Real backend: one shared `pyaudio.PyAudio()` instance (P17)."""

    def __init__(self) -> None:
        import pyaudio  # deferred — see module docstring

        self._pyaudio_module = pyaudio
        self._audio = pyaudio.PyAudio()

    def open_input_stream(self, *, rate: int, channels: int, chunk_size: int) -> AudioStream:
        return self._audio.open(
            format=self._pyaudio_module.paInt16,
            channels=channels,
            rate=rate,
            input=True,
            frames_per_buffer=chunk_size,
        )

    def open_output_stream(self, *, rate: int, channels: int) -> AudioStream:
        return self._audio.open(
            format=self._pyaudio_module.paInt16,
            channels=channels,
            rate=rate,
            output=True,
        )

    def terminate(self) -> None:
        self._audio.terminate()
