# Build Plan

## App Summary
- Name: eagleio-platform-interface
- Type: processor
- Description: Bidirectional bridge between the Doover tag system and Eagle.io's REST API, allowing other Doover apps to publish and receive configurable data to/from Eagle.io parameters.

## External Integration
- Service: Eagle.io (IoT data management platform by Bentley Systems)
- Documentation: https://docs.eagle.io/en/latest/api/index.html
- Authentication: API key via `X-Api-Key` HTTP header
- Base URL: `https://api.eagle.io/api/v1/`
- Rate Limits: 350 requests per 5-minute window per IP address

## Data Flow

### Outbound (Doover -> Eagle.io)
- **Trigger**: `on_message_create` - other Doover apps update tags (via `tag_values` channel or custom channels)
- **Processing**: Read incoming tag data from subscribed channels, map tag names to Eagle.io node IDs using configuration, send values to Eagle.io via REST API
- **Output**: HTTP PUT to Eagle.io `/api/v1/nodes/:id/historic/data/value` to set parameter current values

### Inbound (Eagle.io -> Doover)
- **Trigger**: `on_schedule` - periodic polling of Eagle.io parameters
- **Processing**: Read configured Eagle.io parameters via REST API GET, compare with cached values, update Doover tags with new data
- **Output**: Doover tags updated via `set_tag()` so other apps can read them with `get_tag()`

### Data Flow Diagram
```
Other Doover Apps                    Eagle.io Platform
      |                                     |
      | set_tag() / publish                 |
      v                                     |
 [Doover Channels]                          |
      |                                     |
      | on_message_create                   |
      v                                     |
 +---------------------------------+        |
 | eagleio-platform-interface      |        |
 |                                 |  PUT   |
 |  Outbound: tag -> Eagle.io     |------->|
 |                                 |        |
 |  Inbound: Eagle.io -> tag      |<-------|
 |                (on_schedule)    |  GET   |
 +---------------------------------+        |
      |                                     |
      | set_tag()                           |
      v                                     |
 [Doover Tags]                              |
      |                                     |
      | get_tag()                           |
      v                                     |
 Other Doover Apps                          |
```

## Configuration Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `api_key` | String | yes | - | Eagle.io API key for authentication |
| `base_url` | String | no | `https://api.eagle.io/api/v1` | Eagle.io API base URL |
| `poll_enabled` | Boolean | no | `true` | Enable scheduled polling of Eagle.io parameters |
| `outbound_enabled` | Boolean | no | `true` | Enable pushing tag updates to Eagle.io |
| `tag_mappings` | Array of Object | yes | - | List of tag-to-parameter mappings (see below) |
| `subscription` | ManySubscriptionConfig | yes | - | Channel subscriptions for receiving tag updates |
| `schedule` | ScheduleConfig | no | `rate(5 minutes)` | Polling interval for inbound data from Eagle.io |

### Tag Mapping Object Schema

Each element in `tag_mappings` defines a bidirectional or unidirectional mapping:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `tag_name` | String | yes | - | Doover tag name to read/write |
| `eagleio_node_id` | String | yes | - | Eagle.io parameter node ID (24-char alphanumeric or @customId) |
| `direction` | Enum | no | `both` | Data sync direction: `to_eagleio`, `from_eagleio`, or `both` |
| `source_app_key` | Application | no | - | Doover app key to read the tag from (for outbound). If not set, reads from own tags |

### Subscriptions
- Channel pattern: `tag_values` (to detect tag updates from other apps)
- Additional user-configured channels as needed
- Message types: tag value updates from subscribed devices/apps

### Schedule
- Interval: Configurable via `ScheduleConfig`, default `rate(5 minutes)`
- Purpose: Poll Eagle.io API for current parameter values and sync to Doover tags (inbound direction)

## Event Handlers

| Handler | Trigger | Description |
|---------|---------|-------------|
| `setup` | Invocation start | Initialize HTTP session, validate API key, load cached state from tags |
| `on_message_create` | Channel message (tag update) | Detect tag value changes from subscribed channels, push updated values to mapped Eagle.io parameters |
| `on_schedule` | Configurable interval | Poll Eagle.io for current values of all `from_eagleio` and `both` direction mappings, update corresponding Doover tags |
| `close` | Invocation end | Clean up HTTP session |

## Tags (Output)

| Tag Name | Type | Description |
|----------|------|-------------|
| `last_sync_time` | string (ISO8601) | Timestamp of the last successful sync operation |
| `last_sync_direction` | string | Direction of last sync: `inbound` or `outbound` |
| `last_error` | string/null | Last error message, null if no errors |
| `sync_stats` | object | Counts of successful/failed syncs: `{inbound_ok, inbound_fail, outbound_ok, outbound_fail}` |
| `eagleio_values` | object | Cached current values from Eagle.io keyed by node ID |
| `connection_status` | string | Current connection status to Eagle.io API: `connected`, `error`, `unknown` |

In addition, for each inbound mapping, the processor writes a tag with the configured `tag_name` containing the value retrieved from Eagle.io.

## UI Elements
N/A - has_ui is false

## Documentation Chunks

### Required Chunks
- `config-schema.md` - Configuration types and patterns (Boolean, String, Enum, Array, Object, Application)
- `cloud-handler.md` - Handler entry point, Application class, event handler signatures
- `cloud-project.md` - Project structure, build.sh, deployment package, pyproject.toml setup
- `processor-features.md` - ManySubscriptionConfig, ScheduleConfig, connection status, UI management

### Recommended Chunks
- `tags-channels.md` - Tag get/set patterns, channel publishing, inter-agent communication (critical for this app since it bridges tags to an external system)

### Discovery Keywords
subscription, schedule, rate, tag, set_tag, get_tag, channel, publish, api_key, connection, ping_connection, ManySubscriptionConfig, ScheduleConfig

## Implementation Notes

### Entry Point Conversion
- The current `__init__.py` uses `pydoover.docker.run_app` (device app pattern). This MUST be converted to the cloud processor pattern using `pydoover.cloud.processor.run_app` with a `handler()` function.
- The current `application.py` inherits from `pydoover.docker.Application`. This MUST be changed to `pydoover.cloud.processor.Application`.
- Remove `app_state.py` (StateMachine pattern is for device apps, not serverless processors). Use tags for state persistence instead.
- Remove `transitions` dependency from `pyproject.toml`.

### HTTP Client for Eagle.io API
- Use `aiohttp` (already in dev dependencies) or Python's built-in `urllib.request` for making HTTP calls to Eagle.io.
- Since this runs in Lambda (serverless), prefer lightweight HTTP. The `requests` library can be added as a production dependency, or use `urllib.request` to avoid extra dependencies.
- All Eagle.io API calls require the `X-Api-Key` header and `Content-Type: application/json`.

### Eagle.io API Patterns

**Reading a parameter's current value:**
```
GET /api/v1/nodes/{node_id}?attr=currentValue
Headers: X-Api-Key: {api_key}
Response: {"currentValue": {"value": 28.5, "time": "2024-01-01T00:00:00Z", "quality": 0}}
```

**Setting a parameter's current value:**
```
PUT /api/v1/nodes/{node_id}/historic/data/value
Headers: X-Api-Key: {api_key}, Content-Type: application/json
Body: {"value": 28.5}
Response: 202 Accepted
```

**Reading historic data (multiple nodes):**
```
GET /api/v1/historic?params={id1},{id2}&startTime={iso}&endTime={iso}
Headers: X-Api-Key: {api_key}
Response: JTS format document
```

### Error Handling
- Handle 429 (rate limit) responses with backoff; log and set `last_error` tag
- Handle 401 (auth failure) by setting `connection_status` tag to `error`
- Handle network errors gracefully; processor is serverless so errors should be logged to tags for visibility
- All operations should be idempotent (messages may be delivered multiple times)

### State Persistence
- Since this is a serverless processor, ALL state must be persisted via tags
- Cache Eagle.io values in `eagleio_values` tag to detect changes and avoid unnecessary API calls
- Track sync statistics in `sync_stats` tag

### External Packages
- `requests` or `urllib3` - for Eagle.io HTTP API calls (evaluate whether `urllib.request` from stdlib is sufficient to minimize Lambda package size)
- Remove `transitions` (device app dependency, not needed for processor)

### Key Design Decisions
1. **Bidirectional sync with configurable direction per mapping** - Each tag mapping can be outbound-only, inbound-only, or both
2. **Schedule-based inbound polling** - Eagle.io does not push data; we must poll on a schedule
3. **Channel-triggered outbound** - When other apps update tags, the message triggers an outbound sync to Eagle.io
4. **Source app key support** - Outbound mappings can read tags from specific other apps, not just the processor's own tags
5. **Rate limit awareness** - With 350 requests per 5 minutes, batch operations where possible and track remaining quota
