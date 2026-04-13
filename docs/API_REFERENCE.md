# H2Track Web Console API Reference

**Last Updated:** 2026-04-06
**Base URL:** `http://<host>:18080`
**Content-Type:** `application/json`

---

## Table of Contents

1. [Authentication](#authentication)
2. [Simulation Control](#simulation-control)
3. [Metrics & Monitoring](#metrics--monitoring)
4. [Logs](#logs)
5. [LLM Assistant](#llm-assistant)
6. [Diagnostics & Reports](#diagnostics--reports)
7. [Fleet Operations](#fleet-operations)
8. [WebSocket Endpoints](#websocket-endpoints)
9. [Error Handling](#error-handling)

---

## Authentication

The API supports optional API key authentication. Authentication is **automatically disabled** when no API key is configured.

### Configuration

Set the `H2TRACK_API_KEY` environment variable to enable authentication:

```bash
export H2TRACK_API_KEY="your-secret-key"
```

### Request Format

When authentication is enabled, include the API key in the request header:

```
X-API-Key: your-secret-key
```

### Authentication Behavior

| State | Behavior |
|-------|----------|
| `H2TRACK_API_KEY` not set | All endpoints are publicly accessible |
| `H2TRACK_API_KEY` set | Protected endpoints require valid `X-API-Key` header |

### Protected Endpoints

The following endpoints require authentication when enabled:
- `POST /api/sim/start`
- `POST /api/sim/stop`
- `POST /api/llm/*` (all LLM endpoints)
- `POST /api/diag/export`
- `POST /api/report/export`
- All Fleet API write operations

### Error Response

```json
{
  "detail": "Invalid API key"
}
```

**Status Code:** `403 Forbidden`

---

## Simulation Control

### POST /api/sim/start

Start a simulation with the specified launch profile.

**Authentication:** Required (if enabled)

#### Request

```json
{
  "scene": "warehouse",
  "use_gaden": "true",
  "use_slam": "true",
  "use_rviz": "true",
  "headless": "false"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `scene` | string | `"warehouse"` | Scene name (`warehouse` or `baseline`) |
| `use_gaden` | string | `"true"` | Use GADEN gas simulation (`"true"` or `"false"`) |
| `use_slam` | string | `"true"` | Enable SLAM mapping (`"true"` or `"false"`) |
| `use_rviz` | string | `"true"` | Launch RViz visualization (`"true"` or `"false"`) |
| `headless` | string | `"false"` | Run without GUI (`"true"` or `"false"`) |

#### Success Response

**Status Code:** `202 Accepted`

```json
{
  "ok": true,
  "message": "simulation started"
}
```

#### Error Responses

| Status Code | Description |
|-------------|-------------|
| `400` | Invalid JSON payload |
| `403` | Invalid API key (if auth enabled) |
| `409` | Simulation already running or starting |

```json
{
  "detail": "simulation already running"
}
```

---

### POST /api/sim/stop

Stop the currently running simulation.

**Authentication:** Required (if enabled)

#### Request

No request body required.

#### Success Response

**Status Code:** `202 Accepted`

```json
{
  "ok": true,
  "message": "stop signal sent"
}
```

#### Error Responses

| Status Code | Description |
|-------------|-------------|
| `403` | Invalid API key (if auth enabled) |
| `409` | Simulation is not running |

```json
{
  "detail": "simulation is not running"
}
```

---

### GET /api/sim/status

Get the current simulation status.

**Authentication:** Not required

#### Request

No parameters.

#### Response

**Status Code:** `200 OK`

```json
{
  "state": "running",
  "pid": 12345,
  "last_error": "",
  "latest_log_id": 42,
  "launch_profile": {
    "scene": "warehouse",
    "use_gaden": "true",
    "use_slam": "true",
    "use_rviz": "true",
    "headless": "false"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `state` | string | Current state: `idle`, `starting`, `running`, `stopping`, `error` |
| `pid` | number \| null | Process ID of running simulation, or null |
| `last_error` | string | Last error message, empty if none |
| `latest_log_id` | number | ID of the most recent log entry |
| `launch_profile` | object | Current launch profile configuration |

---

## Metrics & Monitoring

### GET /api/metrics/recent

Get a snapshot of recent metrics including gas concentration, robot mode, navigation stats, and topic health.

**Authentication:** Not required

#### Query Parameters

| Parameter | Type | Default | Constraints | Description |
|-----------|------|---------|-------------|-------------|
| `limit` | integer | `120` | 1-2000 | Maximum history entries to return |

#### Response

**Status Code:** `200 OK`

```json
{
  "phase": {
    "current": "RUNNING",
    "started_at": "2026-04-06T12:00:00.000000+00:00",
    "timeline": [
      {
        "phase": "INIT",
        "start_ts": "2026-04-06T11:55:00.000000+00:00",
        "end_ts": "2026-04-06T11:55:30.000000+00:00",
        "duration_ms": 30000,
        "reason": "init"
      }
    ]
  },
  "mode": {
    "current": "SEEK_TRACK",
    "history": [
      {"timestamp": "2026-04-06T12:00:00.000000+00:00", "value": "PATROL"},
      {"timestamp": "2026-04-06T12:01:00.000000+00:00", "value": "SEEK_TRACK"}
    ]
  },
  "gas": {
    "current": 2.45,
    "history": [
      {"timestamp": "2026-04-06T12:00:00.000000+00:00", "value": 1.23},
      {"timestamp": "2026-04-06T12:00:01.000000+00:00", "value": 2.45}
    ],
    "raw_current": 2.50,
    "raw_history": [],
    "signal_status": "active",
    "signal_reason": "GADEN gas readings are active"
  },
  "source_found": {
    "current": false
  },
  "nav": {
    "goal_succeeded": 15,
    "failed_to_make_progress": 0,
    "goal_canceled": 2,
    "mean_goal_time_sec": 12.5,
    "current_goal_age_sec": 5.2,
    "goal_durations_sec": [10.2, 15.3, 12.1]
  },
  "topic_health": {
    "/gas_concentration": {
      "status": "ok",
      "hz": 10.5,
      "stale_sec": 0.1,
      "last_value": 2.45,
      "threshold_sec": 2.5
    },
    "/robot_mode": {
      "status": "ok",
      "hz": 1.2,
      "stale_sec": 0.8,
      "last_value": "SEEK_TRACK",
      "threshold_sec": 20.0
    }
  },
  "node_health": {
    "updated_at": "2026-04-06T12:00:00.000000+00:00",
    "nodes": [
      {
        "name": "/mission_manager_node",
        "up": true,
        "status": "up",
        "restart_count": 0,
        "last_seen": "2026-04-06T12:00:00.000000+00:00",
        "last_error": ""
      }
    ]
  },
  "launch_profile": {
    "scene": "warehouse",
    "use_gaden": "true",
    "use_slam": "true",
    "use_rviz": "true",
    "headless": "false"
  },
  "mission_thresholds": {
    "enter_threshold": 0.65,
    "exit_threshold": 0.4,
    "source_threshold": 3.4
  },
  "updated_at": "2026-04-06T12:00:00.000000+00:00"
}
```

---

### GET /api/health/nodes

Get node health status for all monitored ROS nodes.

**Authentication:** Not required

#### Response

**Status Code:** `200 OK`

```json
{
  "updated_at": "2026-04-06T12:00:00.000000+00:00",
  "nodes": [
    {
      "name": "/mission_manager_node",
      "up": true,
      "status": "up",
      "restart_count": 0,
      "last_seen": "2026-04-06T12:00:00.000000+00:00",
      "last_error": ""
    },
    {
      "name": "/controller_server",
      "up": true,
      "status": "up",
      "restart_count": 0,
      "last_seen": "2026-04-06T12:00:00.000000+00:00",
      "last_error": ""
    },
    {
      "name": "/gaden_adapter_node",
      "up": false,
      "status": "down",
      "restart_count": 1,
      "last_seen": "2026-04-06T11:55:00.000000+00:00",
      "last_error": "not discovered"
    }
  ]
}
```

---

### GET /metrics

Prometheus metrics endpoint for external monitoring systems.

**Authentication:** Not required

#### Response

**Status Code:** `200 OK`

**Content-Type:** `text/plain; version=0.0.4; charset=utf-8`

```
# HELP h2track_gas_concentration Current gas concentration
# TYPE h2track_gas_concentration gauge
h2track_gas_concentration 2.45

# HELP h2track_nav_goals_total Total navigation goals
# TYPE h2track_nav_goals_total counter
h2track_nav_goals_total{status="succeeded"} 15
h2track_nav_goals_total{status="canceled"} 2
h2track_nav_goals_total{status="failed"} 0
```

#### Error Response

**Status Code:** `503 Service Unavailable`

```json
{
  "detail": "prometheus_client not installed. Install with: pip install prometheus_client"
}
```

---

## Logs

### GET /api/logs/recent

Get recent log entries from the simulation.

**Authentication:** Not required

#### Query Parameters

| Parameter | Type | Default | Constraints | Description |
|-----------|------|---------|-------------|-------------|
| `limit` | integer | `200` | 1-2000 | Maximum log entries to return |

#### Response

**Status Code:** `200 OK`

```json
{
  "logs": [
    {
      "id": 42,
      "timestamp": "2026-04-06T12:00:00.000000+00:00",
      "source": "sim",
      "line": "[INFO] [mission_manager_node]: Mode transition: PATROL -> SEEK_TRACK"
    },
    {
      "id": 41,
      "timestamp": "2026-04-06T11:59:59.000000+00:00",
      "source": "control",
      "line": "launching: ros2 launch h2track_sim demo.launch.py"
    }
  ],
  "latest_id": 42
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | number | Unique log entry ID (monotonically increasing) |
| `timestamp` | string | ISO 8601 timestamp |
| `source` | string | Log source: `system`, `sim`, `control`, `demo_prep` |
| `line` | string | Log content |

---

### GET /api/logs/stream

Stream logs via Server-Sent Events (SSE).

**Authentication:** Not required

#### Query Parameters

| Parameter | Type | Default | Constraints | Description |
|-----------|------|---------|-------------|-------------|
| `after_id` | integer | `0` | >= 0 | Only stream logs with ID greater than this value |

#### Response

**Content-Type:** `text/event-stream`

```
id: 42
event: log
data: {"id":42,"timestamp":"2026-04-06T12:00:00.000000+00:00","source":"sim","line":"[INFO] Mode transition: PATROL -> SEEK_TRACK"}

id: 43
event: log
data: {"id":43,"timestamp":"2026-04-06T12:00:01.000000+00:00","source":"sim","line":"[INFO] Gas concentration: 2.45"}

event: ping
data: {}
```

#### Event Types

| Event | Description |
|-------|-------------|
| `log` | New log entry with JSON payload |
| `ping` | Keep-alive ping (sent when no new logs) |

---

## LLM Assistant

### GET /api/llm/profiles

List all LLM profiles with masked API keys.

**Authentication:** Not required

#### Response

**Status Code:** `200 OK`

```json
{
  "active_profile_id": "550e8400-e29b-41d4-a716-446655440000",
  "profiles": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "OpenAI GPT-4",
      "base_url": "https://api.openai.com/v1",
      "model": "gpt-4",
      "protocol": "chat",
      "timeout_sec": 60.0,
      "has_api_key": true,
      "api_key_preview": "***sk-a",
      "created_at": "2026-04-01T00:00:00.000000+00:00",
      "updated_at": "2026-04-06T12:00:00.000000+00:00"
    }
  ],
  "path": "/home/user/.config/h2track/llm_profiles.json"
}
```

---

### POST /api/llm/profiles

Create or update an LLM profile.

**Authentication:** Required (if enabled)

#### Request

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "OpenAI GPT-4",
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-your-api-key",
  "model": "gpt-4",
  "protocol": "chat",
  "timeout_sec": 60.0,
  "headers": {},
  "set_active": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | No | Profile ID (auto-generated if omitted) |
| `name` | string | No | Profile display name |
| `base_url` | string | Yes | API base URL |
| `api_key` | string | Yes | API key for authentication |
| `model` | string | Yes | Model identifier |
| `protocol` | string | No | Protocol: `chat`, `responses`, or `dual` (default: `chat`) |
| `timeout_sec` | number | No | Request timeout in seconds (default: 60.0) |
| `headers` | object | No | Additional headers to include |
| `set_active` | boolean | No | Set as active profile after saving |

#### Response

**Status Code:** `202 Accepted`

```json
{
  "ok": true,
  "profile": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "OpenAI GPT-4",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4",
    "protocol": "chat",
    "timeout_sec": 60.0,
    "has_api_key": true,
    "api_key_preview": "***sk-a"
  }
}
```

#### Error Responses

| Status Code | Description |
|-------------|-------------|
| `400` | Missing required field |

```json
{
  "detail": "base_url is required"
}
```

---

### POST /api/llm/profiles/{profile_id}/activate

Activate a specific LLM profile.

**Authentication:** Required (if enabled)

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `profile_id` | string | UUID of the profile to activate |

#### Response

**Status Code:** `202 Accepted`

```json
{
  "ok": true,
  "active_profile_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Error Response

**Status Code:** `404 Not Found`

```json
{
  "detail": "profile not found"
}
```

---

### POST /api/llm/profiles/{profile_id}/check

Check connectivity for an LLM profile by making a test API call.

**Authentication:** Required (if enabled)

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `profile_id` | string | UUID of the profile to check |

#### Response

**Status Code:** `200 OK`

```json
{
  "ok": true,
  "protocol_used": "chat",
  "preview": "OK"
}
```

#### Error Responses

| Status Code | Description |
|-------------|-------------|
| `404` | Profile not found |
| `500` | API call failed |

---

### DELETE /api/llm/profiles/{profile_id}

Delete an LLM profile.

**Authentication:** Required (if enabled)

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `profile_id` | string | UUID of the profile to delete |

#### Response

**Status Code:** `202 Accepted`

```json
{
  "ok": true
}
```

#### Error Response

**Status Code:** `404 Not Found`

```json
{
  "detail": "profile not found"
}
```

---

### POST /api/llm/chat

Send a chat message to the LLM and receive analysis and suggested actions.

**Authentication:** Required (if enabled)

#### Request

```json
{
  "profile_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Analyze the current gas tracking performance and suggest improvements",
  "include_context": true,
  "log_limit": 1000,
  "report_limit": 3
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `profile_id` | string | No | Active profile | Profile ID to use |
| `message` | string | Yes | - | User message |
| `include_context` | boolean | No | `true` | Include simulation context |
| `log_limit` | integer | No | `1000` | Max log entries in context |
| `report_limit` | integer | No | `3` | Max reports in context |

#### Response

**Status Code:** `200 OK`

```json
{
  "ok": true,
  "analysis": "The gas tracking is performing well. The robot has successfully transitioned from PATROL to SEEK_TRACK mode when gas concentration exceeded the enter_threshold of 0.65. Current concentration is 2.45, approaching the source_threshold of 3.4.",
  "actions": [
    {
      "type": "console_action",
      "title": "Check GADEN Status",
      "risk_level": "low",
      "payload": {
        "action": "check_gaden_status"
      }
    },
    {
      "type": "shell_command",
      "title": "List Active Nodes",
      "risk_level": "low",
      "payload": {
        "command": "ros2 node list"
      }
    }
  ],
  "protocol_used": "chat",
  "profile_id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "gpt-4",
  "timestamp": "2026-04-06T12:00:00.000000+00:00"
}
```

#### Action Types

| Type | Description | Risk Levels |
|------|-------------|-------------|
| `console_action` | Built-in simulation action | `low`, `medium`, `high` |
| `shell_command` | Execute shell command | `low`, `medium`, `high` |
| `code_evolve` | Code modification action | `high` |

#### Error Responses

| Status Code | Description |
|-------------|-------------|
| `400` | Message is required |
| `500` | LLM API call failed |

---

### POST /api/llm/action/execute

Execute an action suggested by the LLM.

**Authentication:** Required (if enabled)

#### Request

```json
{
  "action": {
    "type": "shell_command",
    "title": "List Active Nodes",
    "risk_level": "low",
    "payload": {
      "command": "ros2 node list"
    }
  }
}
```

#### Response

**Status Code:** `202 Accepted` (success) or `409 Conflict` (action failed)

```json
{
  "ok": true,
  "message": "Action executed successfully",
  "output": "/mission_manager_node\n/controller_server\n/planner_server"
}
```

#### Error Response

**Status Code:** `400 Bad Request`

```json
{
  "detail": "action object is required"
}
```

---

### POST /api/llm/loop/run-once

Run a single LLM autonomous loop iteration (chat + optional auto-execute).

**Authentication:** Required (if enabled)

#### Request

```json
{
  "objective": "Analyze current system and suggest executable optimization actions",
  "auto_execute": true,
  "allow_code_evolve": false,
  "profile_id": "550e8400-e29b-41d4-a716-446655440000",
  "include_context": true,
  "log_limit": 1000,
  "report_limit": 3
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `objective` | string | No | `"Analyze current system..."` | Objective for the LLM |
| `auto_execute` | boolean | No | `true` | Execute suggested actions automatically |
| `allow_code_evolve` | boolean | No | `false` | Allow `code_evolve` actions |
| `profile_id` | string | No | Active profile | Profile ID to use |
| `include_context` | boolean | No | `true` | Include simulation context |
| `log_limit` | integer | No | `1000` | Max log entries in context |
| `report_limit` | integer | No | `3` | Max reports in context |

#### Response

**Status Code:** `202 Accepted`

```json
{
  "ok": true,
  "chat": {
    "ok": true,
    "analysis": "...",
    "actions": [...]
  },
  "executed": [
    {
      "action": {
        "type": "shell_command",
        "title": "List Active Nodes",
        "risk_level": "low",
        "payload": {"command": "ros2 node list"}
      },
      "result": {
        "ok": true,
        "output": "/mission_manager_node\n/controller_server"
      }
    }
  ]
}
```

---

### GET /api/llm/history

Get LLM chat history.

**Authentication:** Not required

#### Query Parameters

| Parameter | Type | Default | Constraints | Description |
|-----------|------|---------|-------------|-------------|
| `limit` | integer | `50` | 1-500 | Maximum entries to return |

#### Response

**Status Code:** `200 OK`

```json
{
  "rows": [
    {
      "timestamp": "2026-04-06T12:00:00.000000+00:00",
      "profile_id": "550e8400-e29b-41d4-a716-446655440000",
      "model": "gpt-4",
      "message": "Analyze current performance",
      "analysis": "The system is performing well...",
      "actions": [...]
    }
  ]
}
```

---

### GET /api/llm/audit

Get LLM action audit log.

**Authentication:** Not required

#### Query Parameters

| Parameter | Type | Default | Constraints | Description |
|-----------|------|---------|-------------|-------------|
| `limit` | integer | `100` | 1-1000 | Maximum entries to return |

#### Response

**Status Code:** `200 OK`

```json
{
  "rows": [
    {
      "timestamp": "2026-04-06T12:00:00.000000+00:00",
      "title": "List Active Nodes",
      "type": "shell_command",
      "risk_level": "low",
      "payload": {"command": "ros2 node list"},
      "result": {
        "ok": true,
        "output": "/mission_manager_node\n/controller_server"
      }
    }
  ]
}
```

---

## Diagnostics & Reports

### POST /api/diag/export

Export diagnostics to a zip file.

**Authentication:** Required (if enabled)

#### Response

**Status Code:** `202 Accepted`

```json
{
  "ok": true,
  "path": "/home/user/h2track-xian/artifacts/diag/h2track_diag_warehouse_20260406_120000.zip"
}
```

#### Export Contents

The zip file contains:
- `summary.json` - Status and metrics summary
- `logs.jsonl` - Recent log entries in JSON Lines format

#### Error Response

**Status Code:** `500 Internal Server Error`

```json
{
  "detail": "diagnostic export failed: <error message>"
}
```

---

### POST /api/report/export

Export a run report as JSON and Markdown files.

**Authentication:** Required (if enabled)

#### Response

**Status Code:** `202 Accepted`

```json
{
  "ok": true,
  "json_path": "/home/user/h2track-xian/artifacts/reports/h2track_run_report_warehouse_20260406_120000.json",
  "markdown_path": "/home/user/h2track-xian/artifacts/reports/h2track_run_report_warehouse_20260406_120000.md"
}
```

---

## Fleet Operations

Fleet API endpoints are only available when multi-robot support is enabled.

### GET /api/fleet/overview

Get fleet summary with per-robot status.

**Authentication:** Not required

#### Response

**Status Code:** `200 OK`

```json
{
  "total_robots": 3,
  "active_count": 2,
  "idle_count": 1,
  "robots": [
    {
      "robot_id": "robot_001",
      "status": "active",
      "mode": "SEEK_TRACK",
      "gas_concentration": 2.45,
      "position": {"x": 3.5, "y": -2.1}
    }
  ]
}
```

---

### GET /api/fleet/metrics

Get aggregate fleet metrics.

**Authentication:** Not required

#### Response

**Status Code:** `200 OK`

```json
{
  "total_distance_m": 1250.5,
  "total_nav_successes": 45,
  "total_nav_failures": 2,
  "average_gas_concentration": 1.85
}
```

---

### GET /api/fleet/history

Get historical fleet data.

**Authentication:** Not required

#### Query Parameters

| Parameter | Type | Default | Constraints | Description |
|-----------|------|---------|-------------|-------------|
| `limit` | integer | `100` | 1-1000 | Maximum entries to return |

#### Response

**Status Code:** `200 OK`

```json
{
  "snapshots": [
    {
      "timestamp": "2026-04-06T12:00:00.000000+00:00",
      "total_robots": 3,
      "active_count": 2,
      "metrics": {...}
    }
  ]
}
```

---

### POST /api/fleet/record-navigation-success/{robot_id}

Record a successful navigation for a robot.

**Authentication:** Required (if enabled)

#### Response

**Status Code:** `202 Accepted`

```json
{
  "ok": true,
  "robot_id": "robot_001"
}
```

---

### POST /api/fleet/record-navigation-failure/{robot_id}

Record a failed navigation for a robot.

**Authentication:** Required (if enabled)

#### Response

**Status Code:** `202 Accepted`

```json
{
  "ok": true,
  "robot_id": "robot_001"
}
```

---

### POST /api/fleet/record-distance/{robot_id}

Record distance traveled for a robot.

**Authentication:** Required (if enabled)

#### Request

```json
{
  "distance_m": 15.5
}
```

#### Response

**Status Code:** `202 Accepted`

```json
{
  "ok": true,
  "robot_id": "robot_001",
  "distance_m": 15.5
}
```

---

### POST /api/fleet/record-snapshot

Record a historical snapshot of the fleet state.

**Authentication:** Required (if enabled)

#### Response

**Status Code:** `202 Accepted`

```json
{
  "ok": true
}
```

---

## WebSocket Endpoints

### WebSocket /ws

Real-time metrics streaming at 1 Hz.

**Protocol:** WebSocket

#### Connection

```javascript
const ws = new WebSocket('ws://localhost:18080/ws');
```

#### Server Messages

**Metrics Update** (sent every 1 second when not paused)

```json
{
  "type": "metrics",
  "data": {
    "phase": {...},
    "mode": {...},
    "gas": {...},
    "nav": {...}
  },
  "timestamp": "2026-04-06T12:00:00.000000+00:00"
}
```

**Status Update** (sent in response to commands)

```json
{
  "type": "status",
  "paused": true,
  "timestamp": "2026-04-06T12:00:00.000000+00:00"
}
```

#### Client Commands

| Command | Format | Description |
|---------|--------|-------------|
| Pause | `{"action": "pause"}` or `"pause"` | Pause metrics stream |
| Resume | `{"action": "resume"}` or `"resume"` | Resume metrics stream |
| Subscribe | `{"action": "subscribe", "topic": "gas"}` or `"subscribe:gas"` | Subscribe to specific topic |
| Unsubscribe | `{"action": "unsubscribe", "topic": "gas"}` or `"unsubscribe:gas"` | Unsubscribe from topic |

#### Example Usage

```javascript
const ws = new WebSocket('ws://localhost:18080/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'metrics') {
    console.log('Gas concentration:', data.data.gas.current);
  }
};

// Pause stream
ws.send(JSON.stringify({action: 'pause'}));

// Resume stream
ws.send(JSON.stringify({action: 'resume'}));

// Subscribe to specific topic
ws.send(JSON.stringify({action: 'subscribe', topic: 'gas'}));
```

---

### WebSocket /ws/heatmap

Real-time heatmap visualization streaming at 2 Hz.

**Protocol:** WebSocket

#### Connection

```javascript
const ws = new WebSocket('ws://localhost:18080/ws/heatmap');
```

#### Server Messages

**Heatmap Update** (sent every 0.5 seconds when data available)

```json
{
  "type": "heatmap_update",
  "timestamp": "2026-04-06T12:00:00.000000+00:00",
  "grid": {
    "resolution": 0.5,
    "origin": [-7.5, -10.8, 0.0],
    "dimensions": [30, 22, 5],
    "data": "base64_encoded_float32_array"
  },
  "particles": {
    "positions": [[3.5, -2.1], [3.6, -2.0], [3.4, -2.2]],
    "weights": [0.85, 0.82, 0.78]
  },
  "estimate": {
    "position": [3.6, -3.04],
    "confidence": 0.85
  }
}
```

#### Message Fields

| Field | Type | Description |
|-------|------|-------------|
| `grid.resolution` | number | Grid cell size in meters |
| `grid.origin` | array | Grid origin point [x, y, z] |
| `grid.dimensions` | array | Grid dimensions [nx, ny, nz] |
| `grid.data` | string | Base64-encoded float32 concentration values |
| `particles.positions` | array | Array of [x, y] particle positions |
| `particles.weights` | array | Array of particle weights |
| `estimate.position` | array | Estimated source position [x, y] |
| `estimate.confidence` | number | Confidence value [0, 1] |

#### Client Commands

Same as `/ws` endpoint: `pause`, `resume`, `subscribe:topic`, `unsubscribe:topic`

---

## Error Handling

### Standard Error Response Format

All error responses follow this format:

```json
{
  "detail": "Error message describing the issue"
}
```

### HTTP Status Codes

| Status Code | Description |
|-------------|-------------|
| `200` | Success |
| `202` | Accepted (async operation started) |
| `400` | Bad Request - Invalid parameters or payload |
| `403` | Forbidden - Invalid or missing API key |
| `404` | Not Found - Resource does not exist |
| `409` | Conflict - Operation cannot be performed in current state |
| `500` | Internal Server Error - Unexpected error |
| `503` | Service Unavailable - Required dependency not available |

### Common Error Examples

**Invalid JSON (400)**

```json
{
  "detail": "invalid JSON payload: Expecting value: line 1 column 1 (char 0)"
}
```

**Missing Required Field (400)**

```json
{
  "detail": "message is required"
}
```

**Invalid API Key (403)**

```json
{
  "detail": "Invalid API key"
}
```

**Resource Not Found (404)**

```json
{
  "detail": "profile not found"
}
```

**Conflict (409)**

```json
{
  "detail": "simulation already running"
}
```

**Internal Error (500)**

```json
{
  "detail": "llm chat failed: connection timeout"
}
```

---

## UI Metadata

### GET /api/ui/meta

Get UI mode metadata (static bundle vs legacy inline).

**Authentication:** Not required

#### Response

**Status Code:** `200 OK`

```json
{
  "mode": "static_bundle",
  "bundle_ready": true,
  "bundle_path": "/path/to/static_console"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `mode` | string | `static_bundle` or `legacy_inline` |
| `bundle_ready` | boolean | Whether static bundle is available |
| `bundle_path` | string \| null | Path to static bundle directory |

---

## Appendix: Launch Profile Values

### Boolean Parameter Values

Boolean parameters (`use_gaden`, `use_slam`, `use_rviz`, `headless`) accept the following string values:

| True | False |
|------|-------|
| `"true"` | `"false"` |
| `"1"` | `"0"` |
| `"yes"` | `"no"` |
| `"on"` | `"off"` |

### Available Scenes

| Scene | Description |
|-------|-------------|
| `warehouse` | Default warehouse environment |
| `baseline` | Baseline test environment |

---

## Appendix: Robot Modes

| Mode | Description |
|------|-------------|
| `PATROL` | Navigating patrol waypoints |
| `SEEK_CONFIRM` | Verifying gas detection |
| `SEEK_TRACK` | Tracking gas toward source |
| `SOURCE_FOUND` | Source location identified |

---

## Appendix: Simulation States

| State | Description |
|-------|-------------|
| `idle` | No simulation running |
| `starting` | Simulation is launching |
| `running` | Simulation is active |
| `stopping` | Simulation is shutting down |
| `error` | Simulation encountered an error |
