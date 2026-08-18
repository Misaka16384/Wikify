"""Server entry point and CLI runner for MAGI WebUI."""

from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path

from magi import __version__
from magi.ui.api import create_app, _get_static_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi ui",
        description="Launch the local MAGI WebUI dashboard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind the WebUI server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not automatically open the dashboard in default browser",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validation probe: verify app structure and exit cleanly with code 0",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code change (development mode)",
    )

    args = parser.parse_args(argv)

    if args.check:
        try:
            app = create_app()
            # Verify routes
            route_paths = [r.path for r in app.routes]
            assert "/api/status" in route_paths, "Missing /api/status route"
            assert "/api/kb" in route_paths, "Missing /api/kb route"
            assert "/api/jobs" in route_paths, "Missing /api/jobs route"
            static_dir = _get_static_dir()
            assert static_dir.is_dir(), f"Static directory does not exist: {static_dir}"
            assert (static_dir / "index.html").is_file(), "index.html missing from static directory"
            print(f"[OK] MAGI WebUI v{__version__} verified successfully.")
            return 0
        except Exception as exc:
            print(f"[FAIL] WebUI validation check failed: {exc}", file=sys.stderr)
            return 1

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required to run the WebUI. Please install uvicorn.", file=sys.stderr)
        return 1

    url = f"http://{args.host}:{args.port}"
    print(f"Starting MAGI WebUI v{__version__} at {url} ...")

    loopback = args.host in ("127.0.0.1", "localhost", "::1")
    if not loopback:
        print(
            f"WARNING: binding to {args.host} exposes the dashboard beyond this machine.\n"
            "         The API can trigger magi maintenance commands; only do this on a trusted network.",
            file=sys.stderr,
        )

    if not args.no_open:
        def _open_browser():
            time.sleep(1.0)
            try:
                webbrowser.open(url)
            except Exception:
                pass

        t = threading.Thread(target=_open_browser, daemon=True)
        t.start()

    try:
        if args.reload:
            uvicorn.run("magi.ui.api:create_app", host=args.host, port=args.port, reload=True, factory=True, log_level="info")
        else:
            app = create_app(extra_allowed_hosts=None if loopback else [args.host])
            uvicorn.run(app, host=args.host, port=args.port, log_level="info")
        return 0
    except KeyboardInterrupt:
        print("\nWebUI server stopped.")
        return 0
    except Exception as exc:
        print(f"WebUI server error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
