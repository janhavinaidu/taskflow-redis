import time
import pytest
import redis
from unittest.mock import patch, MagicMock
from task_queue.task import Task, Priority
from task_queue.priority_queue import PriorityQueue
from task_queue.dead_letter_queue import DeadLetterQueue
from workers.base_worker import BaseWorker


@pytest.fixture
def r():
    client = redis.Redis(host="localhost", port=6379, db=2)
    yield client
    client.flushdb()


@pytest.fixture
def pq(r):
    return PriorityQueue(r)


@pytest.fixture
def dlq(r):
    return DeadLetterQueue(r)


@pytest.fixture
def worker(pq, dlq):
    return BaseWorker("worker-test", pq, dlq)


def make_task(task_type="payment", priority=Priority.MEDIUM):
    return Task(
        name=f"Test {task_type}",
        task_type=task_type,
        payload={"amount": 50, "filename": "test.jpg", "report_type": "monthly", "recipients": 10},
        priority=priority,
    )


# --- Handler resolution ---

def test_unknown_task_type_goes_to_dlq(worker, pq, dlq):
    task = Task(name="Unknown", task_type="nonexistent", payload={}, priority=Priority.LOW)
    pq.enqueue(task)
    t = pq.dequeue()
    worker._process(t)
    assert dlq.size() == 1


# --- Retry logic ---

def test_task_retried_on_failure(worker, pq, dlq):
    task = make_task()
    pq.enqueue(task)
    t = pq.dequeue()

    with patch.dict("workers.base_worker.TASK_HANDLERS", {"payment": MagicMock(side_effect=Exception("timeout"))}):
        with patch("workers.base_worker.BaseWorker._retry") as mock_retry:
            worker._process(t)
            mock_retry.assert_called_once()


def test_task_goes_to_dlq_after_max_retries(worker, pq, dlq):
    task = make_task()
    task.retries = 2          # already at max_retries - 1
    task.max_retries = 3
    pq.enqueue(task)
    t = pq.dequeue()

    with patch.dict("workers.base_worker.TASK_HANDLERS", {"payment": MagicMock(side_effect=Exception("fatal"))}):
        worker._process(t)

    assert dlq.size() == 1


# --- Successful processing ---

def test_task_completes_successfully(worker, pq, dlq):
    task = make_task()
    pq.enqueue(task)
    t = pq.dequeue()

    with patch.dict("workers.base_worker.TASK_HANDLERS", {"payment": MagicMock(return_value={"status": "confirmed"})}):
        worker._process(t)

    assert dlq.size() == 0
    all_tasks = pq.get_all_tasks()
    completed = [t for t in all_tasks if t["status"] == "completed"]
    assert len(completed) == 1


# --- Worker status ---

def test_worker_status_idle(worker):
    status = worker.get_status()
    assert status["status"] == "idle"
    assert status["current_task"] is None


# --- Worker pool ---

def test_worker_pool_starts_and_stops(pq, dlq):
    from workers.worker_pool import WorkerPool
    pool = WorkerPool(pq, dlq)
    pool.start()
    time.sleep(0.3)
    statuses = pool.get_status()
    assert len(statuses) == 4
    pool.stop()