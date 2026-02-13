from __future__ import annotations

import os


def main() -> int:
    from app import backend_server

    try:
        backend_server.main()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return code
    except Exception:
        os._exit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
