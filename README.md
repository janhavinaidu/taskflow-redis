# TaskFlow — Distributed Task Queue System

A production-grade background job processing system built with Python, Redis, and Flask. Implements priority scheduling, fault-tolerant retries, AI-powered task classification, and a real-time monitoring dashboard.

---

## Overview

TaskFlow is a distributed task queue that accepts jobs via a REST API, routes them through a Redis-backed priority queue, and processes them in parallel across a configurable worker pool. Failed tasks are automatically retried with exponential backoff and quarantined in a dead letter queue. An LLM-based classifier (Groq) automatically assigns task priority based on semantic understanding of the task description.

---

## Architecture

```
HTTP Request
     │
     ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Flask API  │────▶│  AI Classifier   │────▶│  Priority Queue │
│  (REST)     │     │  (Groq LLM)      │     │  (Redis Sorted  │
└─────────────┘     └──────────────────┘     │   Sets)         │
                     fallback on failure      └────────┬────────┘
                                                       │
                              ┌───────────────────────┤
                              │                       │
                    ┌─────────▼──────┐      ┌────────▼────────┐
                    │  Worker Pool   │      │  Dead Letter    │
                    │  (4 threads)   │      │  Queue (Redis)  │
                    │                │      │                 │
                    │  worker-01 ──▶ │      │  requeue /      │
                    │  worker-02 ──▶ │      │  discard        │
                    │  worker-03 ──▶ │      └─────────────────┘
                    │  worker-04 ──▶ │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │   SSE Stream   │
                    │  (Event Bus)   │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │   Dashboard    │
                    │  (Vanilla JS)  │
                    └────────────────┘
```

---

## Features

**Priority Scheduling** — Tasks are stored in Redis sorted sets scored by priority. CRITICAL tasks always dequeue before HIGH, MEDIUM, and LOW regardless of insertion order.

**Fault Tolerance** — Failed tasks are automatically retried up to 3 times with exponential backoff (2s, 4s, 8s). Tasks that exhaust all retries are moved to a dead letter queue instead of being silently dropped.

**AI Task Classification** — Incoming tasks are sent to Groq's LLM API which classifies their priority based on semantic understanding of the task description. If the API is unavailable, the system falls back to rule-based classification automatically.

**Concurrency** — A configurable pool of Python threads (default: 4, max: 8) independently pick up and process tasks from the shared Redis queue without stepping on each other.

**Real-time Observability** — An SSE-powered live dashboard shows queue depth per priority, worker status, task feed with filtering, event log stream, and dead letter queue management.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Core language | Python 3.11 | Worker logic, queue engine, retry system |
| Message broker | Redis 7 (sorted sets + hashes + lists) | Priority queue, task store, DLQ |
| AI classifier | Groq API (llama3-8b-8192) | Semantic task priority classification |
| Web framework | Flask | REST API and SSE stream |
| Containerisation | Docker + Docker Compose | Isolated Redis instance |
| Concurrency | Python threading | Parallel worker pool |
| Frontend | HTML + CSS + Vanilla JS | Live monitoring dashboard |
| Testing | pytest + pytest-mock | Unit and integration tests |

---

## Project Structure

```
taskflow-redis/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Environment config
│   ├── queue/
│   │   ├── task.py              # Task dataclass + serialisation
│   │   ├── priority_queue.py    # Redis sorted set queue engine
│   │   └── dead_letter_queue.py # DLQ — push, requeue, discard
│   ├── workers/
│   │   ├── worker_pool.py       # Spawns and manages worker threads
│   │   ├── base_worker.py       # Task pickup, retry, backoff logic
│   │   └── task_handlers.py     # Handlers for each task type
│   ├── ai/
│   │   └── classifier.py        # Groq LLM classifier + fallback
│   └── api/
│       ├── routes.py            # REST endpoints + frontend serving
│       ├── sse.py               # EventBus + SSE stream
│       └── dlq_routes.py        # DLQ management endpoints
├── frontend/
│   ├── index.html               # Dashboard UI
│   └── app.js                   # SSE client, polling, rendering
├── tests/
│   ├── test_queue.py            # Queue and DLQ unit tests
│   ├── test_worker.py           # Worker retry and concurrency tests
│   ├── test_classifier.py       # AI classifier + fallback tests
│   └── test_api.py              # API endpoint smoke tests
├── conftest.py                  # pytest path config
├── docker-compose.yml           # Redis container
├── requirements.txt
├── run.py                       # Entry point
└── .env
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Docker Desktop
- A free [Groq API key](https://console.groq.com)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/taskflow-redis.git
cd taskflow-redis

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Start Redis
docker-compose up -d
```

### Configuration

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_key_here
WORKER_COUNT=4
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
DEBUG=true
```

### Run

```bash
python run.py
```

Open your browser at `http://localhost:5000`

---

## API Reference

### Submit a task

```http
POST /tasks
Content-Type: application/json

{
  "name": "Payment confirmation",
  "task_type": "payment",
  "payload": { "amount": 500 },
  "priority": "CRITICAL"       // optional — omit for AI classification
}
```

Response:
```json
{
  "message": "Task enqueued",
  "task": {
    "task_id": "uuid",
    "name": "Payment confirmation",
    "priority_name": "CRITICAL",
    "ai_assigned": false,
    "status": "queued"
  }
}
```

### List all tasks

```http
GET /tasks
```

### System status

```http
GET /status
```

Returns queue depth per priority, worker statuses, active worker count, and DLQ size.

### Dead letter queue

```http
GET    /dlq               # list failed tasks
POST   /dlq/requeue       # requeue all failed tasks
POST   /dlq/requeue/:id   # requeue a specific task
DELETE /dlq               # discard all failed tasks
DELETE /dlq/:id           # discard a specific task
```

### SSE stream

```http
GET /events
```

Real-time event stream. Events: `task_started`, `task_completed`, `task_retrying`, `task_failed`, `task_dead`.

---

## Supported Task Types

| Type | Simulates | Default Priority |
|---|---|---|
| `payment` | Payment gateway confirmation | CRITICAL |
| `image` | Image resize / processing | HIGH |
| `report` | PDF report generation | MEDIUM |
| `digest` | Bulk email / weekly newsletter | LOW |

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific phase
pytest tests/test_queue.py -v
pytest tests/test_worker.py -v
pytest tests/test_classifier.py -v
pytest tests/test_api.py -v
```

All 23 tests pass across 4 test modules covering queue logic, worker retry behaviour, AI classifier fallback, and API endpoints.

---

## Design Decisions

**Why Redis sorted sets for the priority queue?**
Redis `ZADD` and `ZPOPMIN` are atomic O(log N) operations. Using the priority value as the score means the highest-priority task is always at the front without any application-level sorting. This is the same pattern used by production systems like Sidekiq.

**Why threads over processes or Celery?**
Task handlers are I/O bound — they wait on network calls, not CPU. Python threads are appropriate here because the GIL only penalises CPU-bound work. Processes would add IPC overhead for no benefit. Celery was deliberately avoided to demonstrate understanding of the underlying primitives Celery abstracts away.

**Why SSE over WebSockets?**
The dashboard is read-only — it only needs server-to-client streaming. SSE is purpose-built for this, has lower overhead than WebSockets, and is supported natively by Flask without additional libraries.

**Why exponential backoff?**
Linear retries can hammer a failing downstream service and worsen its recovery. Exponential backoff (2s, 4s, 8s) gives dependent services time to recover between attempts.

**Why a dead letter queue instead of permanent deletion?**
Silent failure is the worst kind of failure in a production system. The DLQ preserves failed tasks with their error context so an operator can inspect, fix, and requeue them rather than losing the work permanently.

---

## Dashboard

The monitoring dashboard provides:

- **Overview** — live metrics (tasks processed, queue depth, success rate, DLQ size), worker pool status, queue depth by priority, recent task feed, SSE event log
- **Task Feed** — full task list with filtering by status (queued, running, completed, failed, retrying) and priority
- **Submit Task** — manual task submission form with optional AI priority classification
- **Dead Letter Queue** — view failed tasks with error messages, requeue or discard individually or in bulk
- **Event Logs** — full real-time SSE stream with colour-coded log levels

---

## License

MIT
