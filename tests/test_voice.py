from __future__ import annotations

import pytest

import agents.voice as voice


def test_voice_config_load_raises_a_clear_error_without_gemini_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_LIVE_MODEL", raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        voice.VoiceConfig.load()

    assert "GEMINI_API_KEY" in str(excinfo.value)


def test_voice_config_load_uses_default_live_model_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-key-not-real")
    monkeypatch.delenv("GEMINI_LIVE_MODEL", raising=False)

    config = voice.VoiceConfig.load()

    assert config.api_key == "fake-test-key-not-real"
    assert config.live_model == voice.DEFAULT_LIVE_MODEL


def test_voice_config_load_honors_explicit_live_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-key-not-real")
    monkeypatch.setenv("GEMINI_LIVE_MODEL", "models/custom-live")

    config = voice.VoiceConfig.load()

    assert config.live_model == "models/custom-live"


def test_start_voice_session_raises_before_touching_audio_hardware_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No GEMINI_API_KEY set — start_voice_session must fail fast on
    # VoiceConfig.load() and never reach PyAudioBackend()/GeminiVoiceBridge()
    # at all (verified below by making both raise if constructed).
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def _fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("must not be constructed without GEMINI_API_KEY")

    monkeypatch.setattr(voice, "PyAudioBackend", _fail)
    monkeypatch.setattr(voice, "GeminiVoiceBridge", _fail)

    with pytest.raises(RuntimeError):
        voice.start_voice_session(lambda text: "unused")


def test_start_voice_session_wires_ask_callback_into_a_live_voice_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-key-not-real")

    created: dict[str, object] = {}

    class FakeAudioBackend:
        def terminate(self) -> None:
            pass

    class FakeBridge:
        def __init__(self, config: object) -> None:
            created["bridge_config"] = config

    class FakeSession:
        def __init__(self, **kwargs: object) -> None:
            created.update(kwargs)
            self.started = False

        def start(self) -> None:
            self.started = True

    monkeypatch.setattr(voice, "PyAudioBackend", FakeAudioBackend)
    monkeypatch.setattr(voice, "GeminiVoiceBridge", FakeBridge)
    monkeypatch.setattr(voice, "LiveVoiceSession", FakeSession)

    def ask_callback(text: str) -> str:
        return "reply"

    session = voice.start_voice_session(ask_callback)

    assert session.started is True
    assert created["ask_callback"] is ask_callback
    assert isinstance(created["audio_backend"], FakeAudioBackend)
    assert isinstance(created["bridge"], FakeBridge)
