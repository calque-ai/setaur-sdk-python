# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-10-20

### Added

- `setaur.init()` now validates the credentials file before connecting. Passing the edge-to-cloud file (`<robotKey>-cloud.creds`) raises a `ValueError` that names the file and points to `<robotKey>-nats.creds`; a file with no credentials, or credentials past their expiry, is also rejected with a clear message instead of an opaque NATS auth error.

### Changed

- Documented the `url` parameter of `setaur.init()` and the `SETAUR_NATS_URL` environment variable in the README, including how to change only the port.

### Fixed

- Shutdown could hang: if a message and the shutdown signal were both queued while a publish was in flight, the signal was consumed as a message. `close()` then waited out its 5-second timeout and the NATS connection was never closed.
- `close()` and `shutdown()` after a burst that filled the publish queue always timed out, because the shutdown signal could not be queued on a full queue. It now waits for space.
- `close()` called a second time is now a no-op.
- The client's event loop is now closed when its background thread exits, instead of leaking the loop and its sockets on every `init()`/`shutdown()` cycle. Publishing or flushing on an already-closed client drops the message (and `flush()` returns `False`) instead of raising.

## [0.2.1] - 2026-07-13

### Changed

- Documented `EventSourceType.STATE_MACHINE` — use this source type to feed the state machine timeline visualizer in the Setaur platform. Events appear in both the state timeline (Gantt-style bar chart) and the standard event timeline.
- Fixed README: removed `SourceType.STATE_MACHINE` from the sensor source types table; this value only exists on `EventSourceType`, not `SourceType`.

## [0.2.0] - 2026-07-06

### Added

- `setaur.install_logging_handler()` - attach a handler to the Python `logging` module so every log record is forwarded to setaur-edge as a structured `LogMessage`. Source file, line, and function name are captured automatically.
- `setaur.set_log_context(**kwargs)` - set process-global fields injected into every log record. `firmware_version` and `component` are routed to top-level `LogMessage` fields; all other keys (e.g. `mission_id`, `zone`) are forwarded as `attrs`.
- `setaur.clear_log_context()` - remove all log context fields.
- Active span context (`trace_id`, `span_id`) is injected into log records automatically when logging inside a `setaur.span()` block.
- `SetaurLogHandler` is exported for advanced use (manual attach, subclassing).

## [0.1.2] - 2026-06-24

- Fix: NATS credentials key corrected from `credentials` to `user_credentials` in connector options.
- Fix: Added `nkeys` extra to `nats-py` dependency so NATS credentials auth works without a manual install step.

## [0.1.1] - 2026-06-24

- `setaur.init()` now accepts an optional `url` parameter to set the NATS server address. Falls back to the `SETAUR_NATS_URL` environment variable, then `nats://localhost:4222`.

## [0.1.0] - 2026-06-23

Initial release. Includes:

- `setaur.sensor()` - publish high-rate sensor streams (IMU, lidar, encoders, etc.)
- `setaur.event()` / `info()` / `warning()` / `error()` / `critical()` - structured events with severity levels and typed attrs
- `setaur.span()` - timed operations with automatic distributed trace propagation
- `setaur.get_tracer()` - component-scoped handle to avoid repeating `source_id`
- `setaur.get_active_trace_id()` - log correlation helper
- Automatic nested span context propagation (no manual ID wiring)
- `py.typed` marker for full type-checker support
