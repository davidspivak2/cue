from __future__ import annotations

import os


def main() -> int:
    from app import qt_worker_runner

    try:
        return qt_worker_runner.main()
    except Exception:
        os._exit(1)


if __name__ == "__main__":
    raise SystemExit(main())
