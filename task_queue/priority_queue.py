import redis
from typing import Optional
from task_queue.task import Task, Priority


QUEUE_KEY = "taskflow:queue"
TASK_STORE_KEY = "taskflow:tasks"


class PriorityQueue:
    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client

    def enqueue(self, task: Task) -> bool:
        """Add task to sorted set using priority as score. Lower score = higher priority."""
        try:
            # Store full task data in hash
            self.r.hset(TASK_STORE_KEY, task.task_id, task.serialize())
            # Add to sorted set — score is priority value (CRITICAL=1 always first)
            self.r.zadd(QUEUE_KEY, {task.task_id: int(task.priority)})
            return True
        except Exception as e:
            print(f"[PriorityQueue] enqueue failed: {e}")
            return False

    def dequeue(self) -> Optional[Task]:
        """Atomically pop the highest priority task (lowest score)."""
        try:
            while True:
                results = self.r.zrange(QUEUE_KEY, 0, 0)
                if not results:
                    return None
                
                task_id = results[0]
                if isinstance(task_id, bytes):
                    task_id = task_id.decode()

                # Atomically attempt to remove the item we just selected
                removed = self.r.zrem(QUEUE_KEY, task_id)
                if removed:
                    raw = self.r.hget(TASK_STORE_KEY, task_id)
                    if not raw:
                        return None

                    task = Task.deserialize(raw)
                    task.status = "running"
                    # Update status in store
                    self.r.hset(TASK_STORE_KEY, task_id, task.serialize())
                    return task
                # If removed is 0, someone else got there first. 
                # Since we loop, we try again automatically.
        except Exception as e:
            print(f"[PriorityQueue] dequeue failed: {e}")
            return None

    def update_task(self, task: Task):
        """Update task data in the hash store."""
        self.r.hset(TASK_STORE_KEY, task.task_id, task.serialize())

    def get_all_tasks(self) -> list[dict]:
        """Return all tasks for the dashboard."""
        all_raw = self.r.hvals(TASK_STORE_KEY)
        tasks = []
        for raw in all_raw:
            try:
                task = Task.deserialize(raw)
                tasks.append(task.to_dict())
            except Exception:
                continue
        return tasks

    def get_queue_depth(self) -> dict:
        """Return count of queued tasks per priority."""
        depths = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        queued_ids = self.r.zrange(QUEUE_KEY, 0, -1, withscores=True)
        for _, score in queued_ids:
            priority = Priority(int(score))
            depths[priority.name] += 1
        return depths

    def queue_size(self) -> int:
        return self.r.zcard(QUEUE_KEY)