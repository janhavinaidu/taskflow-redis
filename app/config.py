import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    WORKER_COUNT = int(os.getenv("WORKER_COUNT", 4))
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"

    @classmethod
    def redis_url(cls) -> str:
        return f"redis://{cls.REDIS_HOST}:{cls.REDIS_PORT}/{cls.REDIS_DB}"