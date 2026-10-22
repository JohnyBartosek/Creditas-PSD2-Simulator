"""PSD2 Simulator Reflex application."""

import atexit
import os
import socket
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import reflex as rx
from reflex.config import get_config

from psd2_app.state import AppState
from psd2_app.views import app_page

app = rx.App()
app.add_page(app_page, route="/", title="PSD2 TPP Simulator", on_load=AppState.boot)


def _listen_port() -> int:
    """Port the running server is bound to, including an auto-incremented one."""
    if "--port" in sys.argv:
        try:
            return int(sys.argv[sys.argv.index("--port") + 1])
        except (IndexError, ValueError):
            pass
    config = get_config()
    return int(config.frontend_port or config.backend_port or 3000)


def _open_browser_when_ready() -> None:
    """Open the app in the default browser once the server accepts connections."""
    port = _listen_port()
    lock_path = Path(tempfile.gettempdir()) / f"psd2-simulator-{port}.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            if time.time() - lock_path.stat().st_mtime < 30:
                return
            lock_path.unlink()
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except OSError:
            return
    os.close(fd)
    atexit.register(lambda: lock_path.unlink(missing_ok=True))

    url = f"http://localhost:{port}/"
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.4):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.25)


threading.Thread(target=_open_browser_when_ready, name="open-browser", daemon=True).start()
