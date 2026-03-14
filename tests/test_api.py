import pytest
import redis
from unittest.mock import patch
from app import create_app
from task_queue.task import Priority


@pytest.fixture
def client():
    with patch("app.config.Config.REDIS_DB", 3):
        app, pool = create_app()
        app.config["TESTING"] = True
        r = redis.Redis(host="localhost", port=6379, db=3)
        r.flushdb()
        with app.test_client() as c:
            yield c
        r.flushdb()


# --- Task submission ---

def test_submit_task_success(client):
    res = client.post("/tasks", json={
        "name": "Payment confirmation",
        "task_type": "payment",
        "payload": {"amount": 200},
        "priority": "CRITICAL"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["task"]["task_type"] == "payment"
    assert data["task"]["priority_name"] == "CRITICAL"
    assert data["task"]["ai_assigned"] is False


def test_submit_task_missing_fields(client):
    res = client.post("/tasks", json={"name": "incomplete"})
    assert res.status_code == 400


def test_submit_task_invalid_type(client):
    res = client.post("/tasks", json={
        "name": "Bad task",
        "task_type": "nonexistent",
        "payload": {}
    })
    assert res.status_code == 400


def test_submit_task_ai_assigned(client):
    with patch("ai.classifier.AIClassifier.classify",
               return_value=(Priority.HIGH, True)):
        res = client.post("/tasks", json={
            "name": "Image resize job",
            "task_type": "image",
            "payload": {"filename": "photo.jpg"}
        })
    assert res.status_code == 201
    assert res.get_json()["task"]["ai_assigned"] is True


# --- Task listing ---

def test_list_tasks_empty(client):
    res = client.get("/tasks")
    assert res.status_code == 200
    assert res.get_json()["count"] == 0


def test_list_tasks_after_submit(client):
    client.post("/tasks", json={
        "name": "Report generation",
        "task_type": "report",
        "payload": {"report_type": "monthly"},
        "priority": "MEDIUM"
    })
    res = client.get("/tasks")
    assert res.get_json()["count"] == 1


# --- Status endpoint ---

def test_status_endpoint(client):
    res = client.get("/status")
    assert res.status_code == 200
    data = res.get_json()
    assert "queue_depth" in data
    assert "workers" in data
    assert "dlq_size" in data


# --- DLQ endpoints ---

def test_dlq_empty(client):
    res = client.get("/dlq")
    assert res.status_code == 200
    assert res.get_json()["count"] == 0


def test_dlq_discard_all(client):
    res = client.delete("/dlq")
    assert res.status_code == 200