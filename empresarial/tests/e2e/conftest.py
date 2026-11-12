import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn


@pytest.fixture(scope="session", autouse=True)
def live_server():
    """Garantiza que el servidor FastAPI esté corriendo en 127.0.0.1:8000 durante la sesión de pruebas E2E."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    is_open = sock.connect_ex(("127.0.0.1", 8000)) == 0
    sock.close()

    if not is_open:
        from app.main import create_app

        test_app = create_app()
        config = uvicorn.Config(test_app, host="127.0.0.1", port=8000, log_level="error")
        server = uvicorn.Server(config)
        t = threading.Thread(target=server.run, daemon=True)
        t.start()
        time.sleep(1.5)
        yield
        server.should_exit = True
    else:
        yield
