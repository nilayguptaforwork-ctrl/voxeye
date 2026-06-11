# Changelog

All notable changes to **voxeye** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] — unreleased

Initial release.

### Added
- `Observability.attach(session, ctx)` — three-line integration for LiveKit Agents:
  installs an OTLP `TracerProvider` (gzip + bearer auth) pointing at a self-hosted
  retina ingest service, resets a prior provider on pooled-worker reuse, resolves
  `call_id`/`agent_id`, introspects STT/LLM/TTS/VAD for provider+model, registers an
  async shutdown flush, and fires a fail-open lifecycle ping. Never raises into the
  user's hot path.
- `Redaction` — opt out of exporting sensitive data (model names, prompts, transcripts,
  tool I/O, or arbitrary attribute keys); filtered client-side before export.
- Typed package (`py.typed`, PEP 561).
