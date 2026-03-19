# Phone Logger

A Home Assistant add-on that monitors incoming and outgoing phone calls via Fritz!Box Callmonitor, resolves caller names from multiple sources, and provides a web-based call history.

## Prerequisites

- A Fritz!Box router with Callmonitor enabled
- To enable Callmonitor: dial `#96*5*` from any phone connected to the Fritz!Box

## Installation

1. Add this repository to your Home Assistant instance:
   **Settings > Add-ons > Add-on Store > ... (top right) > Repositories**
2. Enter the repository URL: `https://github.com/akentner/phone-logger`
3. Install the "Phone Logger" add-on
4. Configure the add-on (see below)
5. Start the add-on
6. Open the Web UI via the sidebar

## Configuration

### Basic Settings

| Option | Default | Description |
|--------|---------|-------------|
| `log_level` | `INFO` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |
| `phone_country_code` | `49` | Country code without + or 00 |
| `phone_local_area_code` | _(empty)_ | Local area code without leading 0. **Required** for resolving short local numbers. |
| `fritz_host` | `192.168.178.1` | Fritz!Box IP address or hostname |
| `fritz_port` | `1012` | Fritz!Box Callmonitor port |

### Input Adapters

Call events can be received from multiple sources:

- **fritz** - Direct TCP connection to Fritz!Box Callmonitor (primary)
- **rest** - REST API for manual trigger/testing
- **mqtt** - Subscribe to call events from an MQTT broker

### Resolver Adapters

Phone numbers are resolved to names using these sources (in order):

1. **json_file** - Local contacts file (`contacts.json`)
2. **sqlite** - Previously resolved numbers (local database)
3. **tellows** - tellows.de reverse lookup (with spam score)
4. **dastelefon** - dasTelefonbuch.de reverse lookup
5. **klartelbuch** - klartelefonbuch.de reverse lookup

### Output Adapters

Call events and resolved data are sent to:

- **call_log** - SQLite database (always recommended)
- **webhook** - HTTP POST to configurable URLs (e.g. Home Assistant automations)
- **mqtt** - Publish to MQTT broker with per-line state topics

### Webhooks

Configure one or more webhook URLs to receive call event notifications.
Each webhook can filter which events to receive:

- Raw events: `ring`, `call`, `connect`, `disconnect`
- Line states: `state:talking`, `state:finished`, `state:missed`, `state:notReached`, `state:idle`

### MQTT

When MQTT output is enabled, events are published to:

- `{prefix}/event` - All events
- `{prefix}/event/{type}` - Filtered by event type
- `{prefix}/line/{id}/state` - Per-line state (retained, only on change)

## Web Interface

The add-on provides an ingress-based web interface with:

- **Call History** - Aggregated calls with status, duration, and resolved names
- **Raw Events** - Individual call events for debugging
- **Contacts** - Manage local contacts
- **Cache** - View and manage the resolver cache
- **PBX Status** - Live line and trunk status

## Fritz!Box Setup

1. **Enable Callmonitor**: Pick up a phone connected to your Fritz!Box and dial `#96*5*`. You will hear a confirmation tone.
2. **Verify**: The add-on will connect to port 1012 on your Fritz!Box. Check the add-on logs for "Connected to Fritz!Box".
3. **Firewall**: Ensure your Home Assistant host can reach the Fritz!Box on TCP port 1012.

## Support

- [GitHub Issues](https://github.com/akentner/phone-logger/issues)
- [GitHub Repository](https://github.com/akentner/phone-logger)
