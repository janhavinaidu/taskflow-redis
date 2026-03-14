import signal
import sys
from app import create_app

app, pool = create_app()


def shutdown(sig, frame):
    print("\n[run.py] Shutting down gracefully...")
    pool.stop()
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

if __name__ == "__main__":
    pool.start()
    print("[run.py] TaskFlow running on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)