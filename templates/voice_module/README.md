# `templates/voice_module/`

A standalone, copyable voice I/O package — not a live shared service, not
imported across project boundaries. Extracted from `Tr5-platform`'s
`projects/voice_agent/client/live_audio_client.py` and
`backend/services/gemini_live_audio_handler.py` (Tr5-base decision 4,
`memory/DECISIONS.md` ADR-033), adapted to a different shape than that
source: here, Gemini is a decoupled speech-to-text/text-to-speech utility,
never the model actually reasoning about the conversation.

## Two consumers

1. **`chat_architect.py`'s own `/voice` command** (`agents/voice.py`
   imports this package directly). Ships with every project cloned from
   this template, opt-in per session via `/voice` / `/voice end` — not a
   separate build per project (Tr5-base decision 4, item 3a).
2. **A project's own product**, if that project's own users need voice
   control of *it*. Copy this directory into `project/` and wire it to
   whatever the project's own reasoning layer is — the same way
   `Tr5-platform`'s `templates/project_template/` is copied to start a new
   project there. Generate and store that project's own `GEMINI_API_KEY`
   in its own `.env` — never a credential shared across projects or
   copies (decision 4, item 3b).

## Why this is not `gemini_live_audio_handler.py` copied as-is

`Tr5-platform`'s `voice_agent` uses one Gemini Live session as the
assistant itself — the session's own generated audio reply *is* the
answer. That is wrong here: `chat_architect.py` talks to the Architect
through its own Codex/Claude Agent SDK thread (`agents/agent.py`), and
voice must not bypass that — otherwise the Architect's contract-drafting
judgment, memory, and role would be silently replaced by whatever Gemini
itself decides to say. So this package opens two independent, short-lived
Gemini Live sessions per conversational turn instead of one long-lived
one:

- `GeminiVoiceBridge.transcribe_turn(...)` — speech-to-text only. Its own
  generated reply is never read; only `input_transcription` text is used.
- `GeminiVoiceBridge.speak_text(...)` — text-to-speech only, given a
  strict system instruction to read the supplied text verbatim, nothing
  else. The text it speaks always comes from the downstream reasoning
  callback (`ask_callback`), never from Gemini's own judgment.

There is also no FastAPI backend and no websocket hop here, unlike
`voice_agent`'s client/server split — `chat_architect.py` is already the
one local process holding the conversation, so `LiveVoiceSession` talks to
Gemini and the local microphone/speakers directly.

## Files

- `audio_io.py` — `AudioBackend`/`AudioStream` Protocols plus
  `PyAudioBackend`, the real implementation. Wraps exactly **one** shared
  `pyaudio.PyAudio()` instance for the whole session (PRINCIPLES.md P17 —
  see the module's own docstring for the incident this guards against).
- `gemini_voice_bridge.py` — `VoiceBridge` Protocol plus
  `GeminiVoiceBridge`, the real implementation (two independent Live
  sessions per turn, as above).
- `live_voice_session.py` — `LiveVoiceSession`, the orchestrator: opens a
  mic stream, transcribes one turn, calls `ask_callback`, speaks the
  reply, closes the stream, repeats. Listening and speaking never overlap
  — a plain CLI mic/speaker setup has no echo cancellation.

## Setup for a project that copies this package

1. Copy `templates/voice_module/` into `project/voice/` (or wherever fits
   that project's own layout).
2. Add `pyaudio` and `google-genai` to that project's own
   `requirements.txt` if not already present.
3. Add `GEMINI_API_KEY` and (optionally) `GEMINI_LIVE_MODEL` to that
   project's own `.env` — its own key, not a shared one.
4. Construct a `LiveVoiceSession` with a `PyAudioBackend()`, a
   `GeminiVoiceBridge(VoiceBridgeConfig(...))`, and an `ask_callback` that
   routes to that project's own reasoning layer.

## Testing

`pyaudio` and `google-genai` are real dependencies, imported lazily inside
`PyAudioBackend`/`GeminiVoiceBridge` so the module stays importable
without them installed — but PRINCIPLES.md P2 still applies: a deferred
import must be exercised by a real test, not assumed to work because it is
wrapped in a function. `tests/test_voice_module.py` exercises the real
lazy imports directly (constructing a real `PyAudioBackend`, a real
`GeminiVoiceBridge`) alongside fake-backed orchestration tests for
`LiveVoiceSession` that never touch real hardware or network (P4). What
those tests cannot cover — an actual live microphone, actual speakers, an
actual Gemini API key and a real conversation — is real-world verification
for whoever adopts this package to do once, on their own machine, the same
way `Tr5-platform`'s own PortAudio/threading incidents were only ever
found by a person actually running the client (P16).

## Future Evolution

- The TTS-verbatim system instruction approach (a second Live session
  told to "read this text exactly") is the design this module ships with,
  reusing the one proven Gemini Live mechanism this codebase has a real
  precedent for (P11). It has not been validated against a real
  conversation yet — that first real `/voice` session is this design's
  actual test, the same way `Tr5-platform`'s own `IMPLEMENTATION_CONTRACT_0013`
  template was only validated by its first real project. If it turns out
  unreliable in practice, a non-Live, dedicated TTS-model call is the
  fallback to try next.
