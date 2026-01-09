import sys


def _run_worker(argv: list[str]) -> None:
    from app import transcribe_worker

    raise SystemExit(transcribe_worker.main(argv, hard_exit=True))


def _run_app() -> None:
    from app import main as app_main

    raise SystemExit(app_main.main())


if __name__ == "__main__":
    if "--run-transcribe-worker" in sys.argv:
        worker_args = [arg for arg in sys.argv[1:] if arg != "--run-transcribe-worker"]
        _run_worker(worker_args)
    _run_app()
