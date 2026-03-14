from flask import Blueprint, request, jsonify
from task_queue.task import Task, Priority, PRIORITY_MAP
from task_queue.priority_queue import PriorityQueue
from task_queue.dead_letter_queue import DeadLetterQueue
from workers.worker_pool import WorkerPool
from ai.classifier import AIClassifier
import os
from flask import send_from_directory

def create_main_blueprint(pq: PriorityQueue, dlq: DeadLetterQueue,
                           pool: WorkerPool, classifier: AIClassifier):
    bp = Blueprint("main", __name__)

    # --- Task submission ---

    @bp.route("/tasks", methods=["POST"])
    def submit_task():
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON body"}), 400

        name = data.get("name")
        task_type = data.get("task_type")
        payload = data.get("payload", {})
        manual_priority = data.get("priority")  # optional override

        if not name or not task_type:
            return jsonify({"error": "name and task_type are required"}), 400

        if task_type not in ["payment", "image", "report", "digest"]:
            return jsonify({"error": f"Unknown task_type: {task_type}"}), 400

        # AI classify or use manual override
        if manual_priority and manual_priority.upper() in PRIORITY_MAP:
            priority = PRIORITY_MAP[manual_priority.upper()]
            ai_assigned = False
        else:
            priority, ai_assigned = classifier.classify(name, task_type)

        task = Task(
            name=name,
            task_type=task_type,
            payload=payload,
            priority=priority,
            ai_assigned=ai_assigned,
        )

        success = pq.enqueue(task)
        if not success:
            return jsonify({"error": "Failed to enqueue task"}), 500

        return jsonify({
            "message": "Task enqueued",
            "task": task.to_dict(),
        }), 201

    # --- Task listing ---

    @bp.route("/tasks", methods=["GET"])
    def list_tasks():
        tasks = pq.get_all_tasks()
        return jsonify({"tasks": tasks, "count": len(tasks)}), 200

    # --- System status ---

    @bp.route("/status", methods=["GET"])
    def status():
        return jsonify({
            "queue_depth": pq.get_queue_depth(),
            "queue_size": pq.queue_size(),
            "workers": pool.get_status(),
            "active_workers": pool.active_count(),
            "dlq_size": dlq.size(),
        }), 200
    @bp.route("/")
    def index():
        frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
        return send_from_directory(frontend_path, "index.html")

    @bp.route("/<path:filename>")
    def static_files(filename):
        frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
        return send_from_directory(frontend_path, filename)

    return bp
   

def create_dlq_blueprint(pq: PriorityQueue, dlq: DeadLetterQueue):
    bp = Blueprint("dlq", __name__)

    @bp.route("/dlq", methods=["GET"])
    def list_dlq():
        tasks = dlq.get_all()
        return jsonify({"tasks": tasks, "count": len(tasks)}), 200

    @bp.route("/dlq/requeue/<task_id>", methods=["POST"])
    def requeue_one(task_id):
        success = dlq.requeue(task_id)
        if not success:
            return jsonify({"error": "Task not found"}), 404
        return jsonify({"message": f"Task {task_id} requeued"}), 200

    @bp.route("/dlq/requeue", methods=["POST"])
    def requeue_all():
        count = dlq.requeue_all()
        return jsonify({"message": f"Requeued {count} tasks"}), 200

    @bp.route("/dlq/<task_id>", methods=["DELETE"])
    def discard_one(task_id):
        dlq.discard(task_id)
        return jsonify({"message": f"Task {task_id} discarded"}), 200

    @bp.route("/dlq", methods=["DELETE"])
    def discard_all():
        count = dlq.discard_all()
        return jsonify({"message": f"Discarded {count} tasks"}), 200

    return bp