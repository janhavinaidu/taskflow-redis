import redis
from flask import Flask
from app.config import Config
from task_queue.priority_queue import PriorityQueue
from task_queue.dead_letter_queue import DeadLetterQueue
from workers.worker_pool import WorkerPool
from ai.classifier import AIClassifier
from app.api.sse import EventBus, create_sse_blueprint
from app.api.routes import create_main_blueprint, create_dlq_blueprint


def create_app() -> tuple:
    app = Flask(__name__)

    # Redis connection
    r = redis.Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB,
        decode_responses=True,
    )

    # Core components
    pq = PriorityQueue(r)
    dlq = DeadLetterQueue(r)
    event_bus = EventBus()
    classifier = AIClassifier()
    pool = WorkerPool(pq, dlq, event_bus)

    # Register blueprints
    app.register_blueprint(create_main_blueprint(pq, dlq, pool, classifier))
    app.register_blueprint(create_dlq_blueprint(pq, dlq))
    app.register_blueprint(create_sse_blueprint(event_bus))

    return app, pool