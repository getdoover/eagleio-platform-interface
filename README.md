# Eagle.io Platform Interface

<img src="https://raw.githubusercontent.com/getdoover/eagleio-platform-interface/main/assets/icon.png" alt="App Icon" style="max-width: 100px;">

**Allows other Doover apps to publish/receive configurable information to/from Eagle.io via the Doover tag system**

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/getdoover/eagleio-platform-interface)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/getdoover/eagleio-platform-interface/blob/main/LICENSE)

[Getting Started](#getting-started) | [Configuration](#configuration) | [Developer](https://github.com/getdoover/eagleio-platform-interface/blob/main/DEVELOPMENT.md) | [Need Help?](#need-help)

<br/>

## Overview

The Eagle.io Platform Interface is a Doover cloud processor that provides bidirectional data synchronization between the Doover platform and [Eagle.io](https://eagle.io), a cloud-based environmental monitoring and data management system. It bridges the two platforms by mapping Doover tags to Eagle.io parameter nodes, enabling seamless data flow in either or both directions.

This processor operates as a serverless, event-driven application running on AWS Lambda. It listens for tag update messages on subscribed Doover channels to push values outbound to Eagle.io, and runs on a configurable schedule to poll Eagle.io for inbound parameter values. All synchronization activity, connection health, and error state are tracked through Doover tags, giving full visibility into the integration status.

Whether you need to send sensor readings from Doover to Eagle.io dashboards, pull Eagle.io parameter values into Doover for use by other applications, or maintain a two-way sync, this processor handles it with configurable per-tag direction control and cross-application tag reading.

### Features

- **Bidirectional sync** -- push Doover tag values to Eagle.io and/or pull Eagle.io parameter values into Doover, with per-mapping direction control (`to_eagleio`, `from_eagleio`, `both`)
- **Flexible tag mappings** -- map any number of Doover tags to Eagle.io parameter nodes using node IDs or `@customId` references
- **Cross-application tag reading** -- read tags from other Doover applications for outbound sync via the `source_app_key` option
- **Scheduled inbound polling** -- configurable schedule to periodically fetch current values from Eagle.io
- **Event-driven outbound sync** -- automatically pushes values when tag updates arrive on subscribed channels
- **Connection health monitoring** -- validates the API key on startup and exposes connection status, last error, and cumulative sync statistics as tags
- **Error resilience** -- handles HTTP 401 (auth failure), 429 (rate limiting), network errors, and JSON parse errors gracefully with per-operation error reporting
- **Lightweight Lambda deployment** -- uses Python standard library `urllib` for HTTP, requiring no additional packages beyond `pydoover`

<br/>

## Getting Started

### Prerequisites

1. **Eagle.io account** -- You need an active Eagle.io account with API access enabled
2. **Eagle.io API key** -- Generate an API key from your Eagle.io account settings (Account > API Keys)
3. **Eagle.io parameter node IDs** -- Identify the node IDs for the parameters you want to synchronize. These are 24-character alphanumeric strings visible in the Eagle.io workspace, or custom IDs prefixed with `@`
4. **Doover platform access** -- A Doover agent with permissions to install cloud processor applications

### Installation

Install the application onto your Doover agent using the Doover CLI or the Doover platform UI:

```bash
doover app install eagleio-platform-interface --agent <agent-id>
```

### Quick Start

1. Install the processor on your Doover agent
2. Open the app configuration and enter your **Eagle.io API Key**
3. Add at least one **Tag Mapping** with a Doover tag name and the corresponding Eagle.io node ID
4. Set the **Direction** for each mapping (`to_eagleio`, `from_eagleio`, or `both`)
5. Configure the **Subscription** to the Doover channel(s) carrying tag updates (for outbound sync)
6. Set a **Schedule** for inbound polling (e.g., every 5 minutes)
7. Save the configuration -- the processor will validate the API key and begin synchronizing

<br/>

## Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| **API Key** | Eagle.io API key for authentication. Obtain from your Eagle.io account settings. | *Required* |
| **Base URL** | Eagle.io API base URL. Only change if using a non-standard Eagle.io endpoint. | `https://api.eagle.io/api/v1` |
| **Poll Enabled** | Enable scheduled polling of Eagle.io parameters (inbound sync). Set to `false` to disable inbound data flow. | `true` |
| **Outbound Enabled** | Enable pushing tag updates to Eagle.io (outbound sync). Set to `false` to disable outbound data flow. | `true` |
| **Tag Mappings** | List of tag-to-Eagle.io parameter mappings. Each mapping defines a Doover tag, an Eagle.io node ID, a sync direction, and an optional source app. See details below. | *Required* |
| **Subscription** | A list of Doover channels to subscribe to. The processor triggers outbound sync when messages arrive on these channels. | *Required* |
| **Schedule** | A schedule definition for inbound polling. Controls how often the processor fetches values from Eagle.io. | *Required* |

### Tag Mapping Fields

Each entry in the **Tag Mappings** array has the following fields:

| Field | Description | Default |
|-------|-------------|---------|
| **Tag Name** | The Doover tag name to read from or write to. For inbound sync, this tag will be created/updated with the Eagle.io value. | *Required* |
| **Eagle.io Node ID** | The Eagle.io parameter node ID. Use the 24-character alphanumeric ID or a `@customId` reference. | *Required* |
| **Direction** | Data sync direction: `to_eagleio` (outbound only), `from_eagleio` (inbound only), or `both` (bidirectional). | `both` |
| **Source App Key** | For outbound sync, optionally read the tag from another Doover application's namespace instead of the processor's own tags. Leave empty to use the processor's own tags. | `null` |

### Example Configuration

```json
{
  "api_key": "your-eagleio-api-key-here",
  "base_url": "https://api.eagle.io/api/v1",
  "poll_enabled": true,
  "outbound_enabled": true,
  "tag_mappings": [
    {
      "tag_name": "temperature",
      "eagle.io_node_id": "5f3a7b2c1d4e6f8a9b0c1d2e",
      "direction": "from_eagleio"
    },
    {
      "tag_name": "setpoint",
      "eagle.io_node_id": "6a4b8c3d2e5f7g0h1i2j3k4l",
      "direction": "to_eagleio",
      "source_app_key": "my-controller-app"
    },
    {
      "tag_name": "flow_rate",
      "eagle.io_node_id": "@site1-flow",
      "direction": "both"
    }
  ],
  "dv_proc_subscriptions": ["my-data-channel"],
  "dv_proc_schedules": "every 5 minutes"
}
```

<br/>

## Tags

This processor exposes the following status and data tags:

| Tag | Description |
|-----|-------------|
| **connection_status** | Current Eagle.io API connection state: `connected` or `error`. Updated on startup and when authentication issues are detected. |
| **last_sync_time** | ISO 8601 timestamp of the most recent sync operation (inbound or outbound). |
| **last_sync_direction** | Direction of the most recent sync: `inbound` or `outbound`. |
| **last_error** | Description of the most recent error, or `null` if the last operation was successful. Covers auth failures, rate limits, network errors, and partial sync failures. |
| **sync_stats** | Cumulative sync statistics object with counters: `inbound_ok`, `inbound_fail`, `outbound_ok`, `outbound_fail`. Persisted across invocations. |
| **eagleio_values** | Cached Eagle.io parameter values from the most recent inbound poll. Keyed by node ID, each entry contains `value`, `time`, and `quality`. |
| **\<tag_name\>** | Dynamic tags created by inbound sync. For each mapping with direction `from_eagleio` or `both`, a tag matching the configured **Tag Name** is created/updated with the current Eagle.io parameter value. |

<br/>

## How It Works

1. **Startup and validation** -- When the processor is invoked, it reads the configuration, parses tag mappings, loads persisted sync statistics, and validates the Eagle.io API key by making a lightweight request. Connection status is reported via the `connection_status` tag.

2. **Outbound sync (on_message_create)** -- When a message arrives on a subscribed Doover channel, the processor filters tag mappings to those with direction `to_eagleio` or `both`. For each mapping, it resolves the tag value from the message data, the processor's own tags, or another app's namespace (via `source_app_key`). It then sends a PUT request to the Eagle.io Historic Data API to set the parameter value.

3. **Inbound sync (on_schedule)** -- On each scheduled invocation, the processor filters tag mappings to those with direction `from_eagleio` or `both`. For each mapping, it sends a GET request to the Eagle.io Nodes API to retrieve the parameter's current value (including timestamp and quality). The value is written to the corresponding Doover tag, and the full result is cached in the `eagleio_values` tag.

4. **Error handling** -- All Eagle.io API calls are wrapped with error handling for HTTP 401 (authentication failure), HTTP 429 (rate limiting), network connectivity errors, and JSON decode errors. Errors are logged and reported via the `last_error` tag without halting the sync of other mappings.

5. **Status reporting** -- After each sync operation, the processor updates `last_sync_time`, `last_sync_direction`, and `sync_stats` with cumulative success/failure counts. If all operations in a sync cycle succeed, `last_error` is cleared to `null`.

<br/>

## Integrations

This cloud processor works with:

- **Eagle.io** -- Bentley Systems' cloud-based environmental monitoring and data management platform. The processor communicates with the Eagle.io REST API (v1) using API key authentication to read and write parameter node values.
- **Doover tag system** -- Reads and writes tags within the Doover platform, enabling other Doover applications to produce data for Eagle.io or consume data from Eagle.io without needing direct API access.
- **Other Doover applications** -- Via the `source_app_key` configuration, this processor can read tags from any other application installed on the same Doover agent, acting as a bridge between those apps and Eagle.io.

<br/>

## Need Help?

- Email: support@doover.com
- [Doover Documentation](https://docs.doover.com)
- [App Developer Documentation](https://github.com/getdoover/eagleio-platform-interface/blob/main/DEVELOPMENT.md)

<br/>

## Version History

### v0.1.0 (Current)
- Initial release
- Bidirectional Eagle.io data synchronization (inbound polling and outbound push)
- Configurable tag-to-node mappings with per-mapping direction control
- Cross-application tag reading via source app key
- Connection health monitoring and error reporting via Doover tags
- Cumulative sync statistics tracking
- Support for Eagle.io node IDs and @customId references

<br/>

## License

This app is licensed under the [Apache License 2.0](https://github.com/getdoover/eagleio-platform-interface/blob/main/LICENSE).
