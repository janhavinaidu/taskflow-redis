import json
import uuid
from dataclasses import dataclass, field
from typing import Optional
from enum import IntEnum


class Priority(IntEnum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


PRIORITY_MAP = {
    "CRITICAL": Priority.CRITICAL,
    "HIGH": Priority.HIGH,
    "MEDIUM": Priority.MEDIUM,
    "LOW": Priority.LOW,
}


@dataclass
class Task:
    name: str
    task_type: str
    payload: dict
    priority: Priority
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "queued"
    retries: int = 0
    max_retries: int = 3
    ai_assigned: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "task_type": self.task_type,
            "payload": self.payload,
            "priority": int(self.priority),
            "priority_name": self.priority.name,
            "status": self.status,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "ai_assigned": self.ai_assigned,
            "error": self.error,
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def deserialize(cls, data: str) -> "Task":
        d = json.loads(data)
        return cls(
            task_id=d["task_id"],
            name=d["name"],
            task_type=d["task_type"],
            payload=d["payload"],
            priority=Priority(d["priority"]),
            status=d["status"],
            retries=d["retries"],
            max_retries=d["max_retries"],
            ai_assigned=d["ai_assigned"],
            error=d.get("error"),
        )