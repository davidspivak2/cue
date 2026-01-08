import sys

from app import main as app_main
from app import transcribe_worker


if __name__ == "__main__":
    if "--run-transcribe-worker" in sys.argv:
        argv = [arg for arg in sys.argv[1:] if arg != "--run-transcribe-worker"]
        raise SystemExit(transcribe_worker.main(argv))
    raise SystemExit(app_main.main())
