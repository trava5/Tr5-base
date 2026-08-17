"""`/voice` command support for `chat_architect.py` (Tr5-base decision 4).

`templates/voice_module/` is a standalone, copyable package (see its own
README.md) — this module is one *user* of it, wiring it into the
framework's single entry point. A project cloned from this template can
separately copy `templates/voice_module/` into `project/` for its own
product's voice feature, entirely decoupled from this file.

Gemini here is used purely for speech-to-text/text-to-speech duty; the
Architect is still reached through its own Codex/Claude Agent SDK thread
(`agents/agent.py`) via `ask_callback` — voice never bypasses it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from templates.voice_module.audio_io import PyAudioBackend
from templates.voice_module.gemini_voice_bridge import GeminiVoiceBridge, VoiceBridgeConfig
from templates.voice_module.live_voice_session import LiveVoiceSession

DEFAULT_LIVE_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"


@dataclass(frozen=True)
class VoiceConfig:
    api_key: str
    live_model: str

    @classmethod
    def load(cls) -> "VoiceConfig":
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "Missing GEMINI_API_KEY in .env. /voice needs its own, "
                "separate Gemini connection for speech-to-text/text-to-speech "
                "duty only (Tr5-base decision 4) — it does not reuse the "
                "architect's own Codex/Claude thread, and does not start "
                "without its own credential."
            )
        live_model = os.environ.get("GEMINI_LIVE_MODEL", "").strip() or DEFAULT_LIVE_MODEL
        return cls(api_key=api_key, live_model=live_model)


def start_voice_session(
    ask_callback: Callable[[str], str],
    *,
    on_error: Callable[[Exception], None] | None = None,
) -> LiveVoiceSession:
    """Builds and starts a real `LiveVoiceSession` wired to `ask_callback`.

    Raises `RuntimeError` with a clear message (via `VoiceConfig.load`) if
    `GEMINI_API_KEY` is not configured, instead of a bare error deep inside
    the SDK once a session is already partway open.
    """
    config = VoiceConfig.load()
    bridge = GeminiVoiceBridge(VoiceBridgeConfig(api_key=config.api_key, live_model=config.live_model))
    audio = PyAudioBackend()
    session = LiveVoiceSession(
        audio_backend=audio,
        bridge=bridge,
        ask_callback=ask_callback,
        on_user_text=lambda text: print(f"\nYou (voice): {text}"),
        on_assistant_text=lambda text: print(f"\nArchitect (voice):\n{text}\n"),
        on_error=on_error,
    )
    session.start()
    return session
