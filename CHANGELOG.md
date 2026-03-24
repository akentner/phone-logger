# Changelog

## 0.3.0 - 2026-03-24

### Breaking Changes
- `since` field renamed to `last_changed` in `LineState` — affects MQTT line/trunk state payloads, Webhook payloads, and REST API responses

### Features
- **Combined MqttAdapter** (`src/adapters/mqtt.py`) replaces separate `mqtt_sub` and `mqtt_pub` adapters — single connection, unified lifecycle
- **Trunk state MQTT topic** (`{prefix}/trunk/{id}/state`) now includes `last_changed` timestamp
- **`last_changed` timestamp** set on all FSM transitions (RING, CALL, TALKING, FINISHED, MISSED, NOT_REACHED, IDLE) — previously only set on RING/CALL
- **HA MQTT Discovery**: `object_id` field added to all discovery payloads — entity IDs in Home Assistant are now stable and ID-based, independent of label changes
- **PBX caller/called device**, MSN resolver and cursor pagination (from 0.2.0)

### Fixes
- Trunk status remained `busy` after call end when multiple lines shared a trunk — now correctly transitions to `idle` once all lines are idle

### Refactoring
- `mqtt_sub.py` and `mqtt_pub.py` removed; replaced by `src/adapters/mqtt.py`

## 0.1.1 - 2026-03-20

### Features
- **Dark mode** support via CSS `prefers-color-scheme`

### Fixes
- FastAPI lifespan handler corrected (callable now accepts `app` parameter)

### Refactoring
- `LineConfig` removed — line count is now derived directly from configured trunks
- Translations are no longer reloaded on PBX auto-refresh polling

### Documentation
- Added `AGENTS.md` (English)
- Fixed ASCII art alignment in README

## 0.1.0 - Initial Release

### Features

- **Fritz!Box Callmonitor** integration via direct TCP connection
- **Phone number resolution** from multiple sources:
  - Local contacts (JSON file, SQLite)
  - tellows.de (with spam score detection)
  - dasTelefonbuch.de
  - klartelefonbuch.de
- **Call aggregation** with full lifecycle tracking (ringing, answered, missed, finished)
- **PBX state management** with per-line FSM (finite state machine)
- **Anonymous call handling** (withheld numbers passed through without resolver lookup)
- **Web interface** with:
  - Aggregated call history with resolved names and MSN display
  - Raw event log
  - Contact management
  - Resolver cache management
  - Live PBX status
- **Webhook output** with configurable event filters and full LineState payload
- **MQTT output** with per-line state topics (retained, change-only)
- **REST API** for integration and manual triggering
- **Home Assistant ingress** support
- **Multi-architecture** Docker builds (amd64, aarch64, armv7, armhf, i386)
