# Changelog

All notable changes to this project will be documented in this file.

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
