import time
import threading
from task_queue.priority_queue import PriorityQueue
from task_queue.dead_letter_queue import DeadLetterQueue
from task_queue.task import Task
from workers.task_handlers import TASK_HANDLERS


class BaseWorker(threading.Thread):
    def __init__(self, worker_id: str, pq: PriorityQueue, dlq: DeadLetterQueue, event_bus=None):
        super().__init__(daemon=True)
        self.worker_id = worker_id
        self.pq = pq
        self.dlq = dlq
        self.event_bus = event_bus  # will wire up to SSE later
        self._stop_event = threading.Event()
        self.current_task = None

    def run(self):
        print(f"[{self.worker_id}] Started")
        while not self._stop_event.is_set():
            task = self.pq.dequeue()
            if task is None:
                time.sleep(0.5)  # no tasks, wait and poll again
                continue
            self.current_task = task
            self._process(task)
            self.current_task = None

    def stop(self):
        self._stop_event.set()

    def _process(self, task: Task):
        print(f"[{self.worker_id}] Processing '{task.name}' (priority: {task.priority.name})")
        self._emit("task_started", task)

        handler = TASK_HANDLERS.get(task.task_type)
        if not handler:
            task.error = f"No handler for task type: {task.task_type}"
            self.dlq.push(task)
            self._emit("task_failed", task)
            return

        try:
            result = handler(task.payload)
            task.status = "completed"
            task.error = None
            self.pq.update_task(task)
            print(f"[{self.worker_id}] Completed '{task.name}' → {result}")
            self._emit("task_completed", task)

        except Exception as e:
            task.error = str(e)
            task.retries += 1
            print(f"[{self.worker_id}] Failed '{task.name}' (attempt {task.retries}/{task.max_retries}): {e}")

            if task.retries < task.max_retries:
                self._retry(task)
            else:
                print(f"[{self.worker_id}] Exhausted retries for '{task.name}' → DLQ")
                self.dlq.push(task)
                self._emit("task_dead", task)

    def _retry(self, task: Task):
        """Exponential backoff before re-enqueuing."""
        backoff = 2 ** task.retries  # 2s, 4s, 8s
        print(f"[{self.worker_id}] Retrying '{task.name}' in {backoff}s (attempt {task.retries}/{task.max_retries})")
        task.status = "retrying"
        self.pq.update_task(task)
        self._emit("task_retrying", task)
        time.sleep(backoff)
        task.status = "queued"
        self.pq.enqueue(task)

    def _emit(self, event_type: str, task: Task):
        """Push event to SSE bus if available."""
        if self.event_bus:
            self.event_bus.publish(event_type, {
                "worker_id": self.worker_id,
                "task": task.to_dict(),
            })

    def get_status(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "status": "running" if self.current_task else "idle",
            "current_task": self.current_task.name if self.current_task else None,
        }