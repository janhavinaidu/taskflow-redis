import os
from workers.base_worker import BaseWorker
from task_queue.priority_queue import PriorityQueue
from task_queue.dead_letter_queue import DeadLetterQueue


class WorkerPool:
    def __init__(self, pq: PriorityQueue, dlq: DeadLetterQueue, event_bus=None):
        self.pq = pq
        self.dlq = dlq
        self.event_bus = event_bus
        self.workers: list[BaseWorker] = []
        self.num_workers = int(os.getenv("WORKER_COUNT", 4))

    def start(self):
        print(f"[WorkerPool] Starting {self.num_workers} workers...")
        for i in range(self.num_workers):
            worker_id = f"worker-{str(i+1).zfill(2)}"
            w = BaseWorker(worker_id, self.pq, self.dlq, self.event_bus)
            w.start()
            self.workers.append(w)
        print(f"[WorkerPool] All {self.num_workers} workers online")

    def stop(self):
        print("[WorkerPool] Shutting down...")
        for w in self.workers:
            w.stop()
        for w in self.workers:
            w.join(timeout=5)
        print("[WorkerPool] All workers stopped")

    def get_status(self) -> list[dict]:
        return [w.get_status() for w in self.workers]

    def active_count(self) -> int:
        return sum(1 for w in self.workers if w.current_task is not None)