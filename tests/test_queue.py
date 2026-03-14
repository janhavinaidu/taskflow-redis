import pytest
import redis
from task_queue.task import Task, Priority
from task_queue.priority_queue import PriorityQueue
from task_queue.dead_letter_queue import DeadLetterQueue


@pytest.fixture
def r():
    client = redis.Redis(host="localhost", port=6379, db=1)  # db=1 keeps tests isolated
    yield client
    client.flushdb()  # clean up after each test


@pytest.fixture
def pq(r):
    return PriorityQueue(r)


@pytest.fixture
def dlq(r):
    return DeadLetterQueue(r)


def make_task(name="Test task", task_type="payment", priority=Priority.MEDIUM):
    return Task(
        name=name,
        task_type=task_type,
        payload={"amount": 100},
        priority=priority,
    )


# --- Task serialisation ---

def test_task_serialise_deserialise():
    task = make_task()
    restored = Task.deserialize(task.serialize())
    assert restored.task_id == task.task_id
    assert restored.priority == task.priority
    assert restored.name == task.name


# --- Priority queue ---

def test_enqueue_and_dequeue(pq):
    task = make_task()
    pq.enqueue(task)
    result = pq.dequeue()
    assert result is not None
    assert result.task_id == task.task_id


def test_priority_order_respected(pq):
    """CRITICAL should always come out before LOW regardless of insert order."""
    low = make_task("Low task", priority=Priority.LOW)
    critical = make_task("Critical task", priority=Priority.CRITICAL)
    medium = make_task("Medium task", priority=Priority.MEDIUM)

    pq.enqueue(low)
    pq.enqueue(critical)
    pq.enqueue(medium)

    first = pq.dequeue()
    second = pq.dequeue()
    third = pq.dequeue()

    assert first.priority == Priority.CRITICAL
    assert second.priority == Priority.MEDIUM
    assert third.priority == Priority.LOW


def test_dequeue_empty_returns_none(pq):
    assert pq.dequeue() is None


def test_queue_size(pq):
    pq.enqueue(make_task("t1"))
    pq.enqueue(make_task("t2"))
    assert pq.queue_size() == 2


def test_queue_depth_by_priority(pq):
    pq.enqueue(make_task(priority=Priority.CRITICAL))
    pq.enqueue(make_task(priority=Priority.CRITICAL))
    pq.enqueue(make_task(priority=Priority.LOW))
    depths = pq.get_queue_depth()
    assert depths["CRITICAL"] == 2
    assert depths["LOW"] == 1


# --- Dead letter queue ---

def test_push_to_dlq(pq, dlq):
    task = make_task()
    pq.enqueue(task)
    t = pq.dequeue()
    dlq.push(t)
    assert dlq.size() == 1


def test_requeue_from_dlq(pq, dlq):
    task = make_task()
    pq.enqueue(task)
    t = pq.dequeue()
    dlq.push(t)
    dlq.requeue(t.task_id)
    assert dlq.size() == 0
    assert pq.queue_size() == 1


def test_discard_from_dlq(pq, dlq):
    task = make_task()
    pq.enqueue(task)
    t = pq.dequeue()
    dlq.push(t)
    dlq.discard(t.task_id)
    assert dlq.size() == 0


def test_requeue_all(pq, dlq):
    for i in range(3):
        t = make_task(f"task {i}")
        pq.enqueue(t)
        popped = pq.dequeue()
        dlq.push(popped)
    dlq.requeue_all()
    assert dlq.size() == 0
    assert pq.queue_size() == 3