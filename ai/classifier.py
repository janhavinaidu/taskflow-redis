import os
import json
from groq import Groq
from task_queue.task import Priority, PRIORITY_MAP


SYSTEM_PROMPT = """You are a task priority classifier for a job queue system.

Given a task name and type, classify its priority as one of:
- CRITICAL: payment processing, security, authentication, data loss prevention
- HIGH: user-facing operations, file processing, invoices, time-sensitive jobs
- MEDIUM: report generation, data sync, notifications
- LOW: bulk emails, digests, cleanup, analytics, non-urgent batch jobs

Respond ONLY with valid JSON in this exact format, nothing else:
{"priority": "CRITICAL", "reason": "one sentence explanation"}"""


class AIClassifier:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        self.enabled = bool(api_key)
        self.client = Groq(api_key=api_key) if self.enabled else None

    def classify(self, task_name: str, task_type: str) -> tuple[Priority, bool]:
        """
        Returns (Priority, ai_assigned).
        Falls back to rule-based default if API fails or is disabled.
        """
        if not self.enabled:
            return self._fallback(task_type), False

        try:
            response = self.client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Task name: {task_name}\nTask type: {task_type}"}
                ],
                max_tokens=60,
                temperature=0,
            )

            raw = response.choices[0].message.content.strip()
            data = json.loads(raw)
            priority_str = data.get("priority", "").upper()

            if priority_str not in PRIORITY_MAP:
                raise ValueError(f"Invalid priority returned: {priority_str}")

            print(f"[AIClassifier] '{task_name}' → {priority_str} ({data.get('reason', '')})")
            return PRIORITY_MAP[priority_str], True

        except Exception as e:
            print(f"[AIClassifier] API failed, using fallback: {e}")
            return self._fallback(task_type), False

    def _fallback(self, task_type: str) -> Priority:
        """Rule-based fallback when API is unavailable."""
        rules = {
            "payment":  Priority.CRITICAL,
            "image":    Priority.HIGH,
            "report":   Priority.MEDIUM,
            "digest":   Priority.LOW,
        }
        priority = rules.get(task_type, Priority.MEDIUM)
        print(f"[AIClassifier] Fallback → {priority.name} for type '{task_type}'")
        return priority