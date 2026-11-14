"""Start the local research API and dashboard together; never enable live mode."""

import os
import secrets
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from types import FrameType

import httpx


def _available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def launch_dashboard(host: str = "127.0.0.1", port: int = 8501, open_browser: bool = True) -> int:
    if host not in {"127.0.0.1", "0.0.0.0"} or not 1 <= port <= 65535:
        raise ValueError("invalid dashboard host or port")
    environment = dict(os.environ)
    environment["PM_MODE"] = "offline_demo"
    environment["PM_LIVE_TRADING_ENABLED"] = "false"
    environment["PM_CONTROL_TOKEN"] = environment.get("PM_CONTROL_TOKEN") or secrets.token_urlsafe(
        32
    )
    environment["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    api_port = _available_port()
    environment["PM_API_URL"] = f"http://127.0.0.1:{api_port}"
    processes: list[subprocess.Popen[bytes]] = []
    previous = signal.getsignal(signal.SIGTERM)

    def stop_signal(signum: int, frame: FrameType | None) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_signal)
    try:
        api = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.api.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
            ],
            env=environment,
        )
        processes.append(api)
        with httpx.Client(timeout=1, trust_env=False) as client:
            for _ in range(100):
                if api.poll() is not None:
                    raise RuntimeError("API process exited; see its log above")
                try:
                    if client.get(environment["PM_API_URL"] + "/health/ready").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("API readiness timed out")
        dashboard_file = Path(__file__).resolve().parent / "dashboard" / "main.py"
        ui = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(dashboard_file),
                "--server.address",
                host,
                "--server.port",
                str(port),
                "--server.headless",
                "true",
            ],
            env=environment,
        )
        processes.append(ui)
        url = f"http://127.0.0.1:{port}"
        with httpx.Client(timeout=1, trust_env=False) as client:
            for _ in range(100):
                if ui.poll() is not None:
                    raise RuntimeError("Dashboard process exited; see its log above")
                try:
                    if client.get(url + "/_stcore/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Dashboard readiness timed out")
        print(f"Dashboard ready: {url} | SYNTHETIC ONLY | Ctrl+C stops both processes", flush=True)
        if open_browser:
            webbrowser.open(url)
        while all(process.poll() is None for process in processes):
            time.sleep(0.2)
        return next((process.returncode for process in processes if process.returncode), 1)
    except KeyboardInterrupt:
        return 0
    finally:
        for process in reversed(processes):
            _stop(process)
        signal.signal(signal.SIGTERM, previous)
