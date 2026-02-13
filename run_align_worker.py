from __future__ import annotations

import os
import sys


def main() -> int:
    from app import align_worker

    try:
        return align_worker.main(sys.argv[1:])
    except Exception:
        os._exit(1)


if __name__ == "__main__":
    raise SystemExit(main())
