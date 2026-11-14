import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def test_dashboard_launcher_readiness_safety_and_cleanup(tmp_path: Path) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    log_path = tmp_path / "launcher.log"
    env = dict(
        os.environ,
        PM_DATABASE_URL="sqlite:///" + str(tmp_path / "launcher.db"),
        PM_CONTROL_TOKEN="launcher-test-token",
        PM_MODE="live",
        PM_LIVE_TRADING_ENABLED="true",
    )
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from app.cli import main; main()",
                "dashboard",
                "--no-browser",
                "--port",
                str(port),
            ],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    api_port = None
    try:
        with httpx.Client(timeout=1, trust_env=False) as client:
            for _ in range(200):
                text = log_path.read_text()
                assert process.poll() is None, text
                match = re.search(r"Uvicorn running on http://127\.0\.0\.1:(\d+)", text)
                if match:
                    api_port = int(match.group(1))
                if "Dashboard ready:" in text:
                    break
                time.sleep(0.1)
            else:
                raise AssertionError(log_path.read_text())
            assert api_port is not None
            api = f"http://127.0.0.1:{api_port}"
            assert client.get(f"http://127.0.0.1:{port}/_stcore/health").status_code == 200
            risk = client.get(api + "/risk").json()
            assert risk["mode"] == "offline_demo" and risk["live_ready"] is False
            response = client.post(
                api + "/controls/paper/start",
                headers={"Authorization": "Bearer launcher-test-token"},
            )
            assert response.status_code == 200
            assert "launcher-test-token" not in log_path.read_text()
    finally:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    assert process.returncode == 0
    with httpx.Client(timeout=1, trust_env=False) as client:
        for child_port in (api_port, port):
            try:
                client.get(f"http://127.0.0.1:{child_port}/health/live")
            except httpx.ConnectError:
                continue
            raise AssertionError("launcher left a child server running")
