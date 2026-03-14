import redis
from task_queue.task import Task

DLQ_KEY = "taskflow:dlq"
TASK_STORE_KEY = "taskflow:tasks"
QUEUE_KEY = "taskflow:queue"


class DeadLetterQueue:
    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client

    def push(self, task: Task):
        """Move a permanently failed task into the DLQ."""
        task.status = "failed"
        self.r.hset(TASK_STORE_KEY, task.task_id, task.serialize())
        self.r.lpush(DLQ_KEY, task.task_id)
        print(f"[DLQ] Task {task.task_id} ({task.name}) moved to dead letter queue")

    def get_all(self) -> list[dict]:
        """Return all tasks currently in the DLQ."""
        task_ids = self.r.lrange(DLQ_KEY, 0, -1)
        tasks = []
        for tid in task_ids:
            if isinstance(tid, bytes):
                tid = tid.decode()
            raw = self.r.hget(TASK_STORE_KEY, tid)
            if raw:
                tasks.append(Task.deserialize(raw).to_dict())
        return tasks

    def requeue(self, task_id: str) -> bool:
        """Push a DLQ task back into the priority queue."""
        raw = self.r.hget(TASK_STORE_KEY, task_id)
        if not raw:
            return False
        task = Task.deserialize(raw)
        task.status = "queued"
        task.retries = 0
        task.error = None
        self.r.hset(TASK_STORE_KEY, task_id, task.serialize())
        self.r.zadd(QUEUE_KEY, {task_id: int(task.priority)})
        self.r.lrem(DLQ_KEY, 0, task_id)
        print(f"[DLQ] Task {task_id} requeued")
        return True

    def requeue_all(self) -> int:
        """Requeue every task in the DLQ. Returns count requeued."""
        task_ids = self.r.lrange(DLQ_KEY, 0, -1)
        count = 0
        for tid in task_ids:
            if isinstance(tid, bytes):
                tid = tid.decode()
            if self.requeue(tid):
                count += 1
        return count

    def discard(self, task_id: str) -> bool:
        """Permanently delete a task from DLQ and task store."""
        self.r.lrem(DLQ_KEY, 0, task_id)
        self.r.hdel(TASK_STORE_KEY, task_id)
        return True

    def discard_all(self) -> int:
        """Clear the entire DLQ."""
        task_ids = self.r.lrange(DLQ_KEY, 0, -1)
        count = len(task_ids)
        for tid in task_ids:
            if isinstance(tid, bytes):
                tid = tid.decode()
            self.r.hdel(TASK_STORE_KEY, tid)
        self.r.delete(DLQ_KEY)
        return count

    def size(self) -> int:
        return self.r.llen(DLQ_KEY)