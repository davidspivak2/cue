from __future__ import annotations

import os
import sys


def main() -> int:
    from app import transcribe_worker

    try:
        return transcribe_worker.main(sys.argv[1:], hard_exit=True)
    except Exception:
        os._exit(1)


if __name__ == "__main__":
    main()
