#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if uv run --no-sync python -c 'import httpx; r=httpx.get("http://127.0.0.1:8501/_stcore/health", timeout=1); r.raise_for_status()' >/dev/null 2>&1; then
  echo 'Dashboard already running. Open port 8501 in the Codespaces Ports tab.'
  exit 0
fi
nohup uv run --no-sync pm-engine dashboard --host 0.0.0.0 --no-browser > /tmp/pm-engine-dashboard.log 2>&1 < /dev/null &
uv run --no-sync python - <<'CHECK'
import time
import httpx
for _ in range(150):
    try:
        r = httpx.get("http://127.0.0.1:8501/_stcore/health", timeout=1)
        if r.status_code == 200:
            print("Ready. Open the private dashboard using port 8501 in the Ports tab.")
            break
    except httpx.HTTPError:
        pass
    time.sleep(0.2)
else:
    raise SystemExit("Startup failed. Read /tmp/pm-engine-dashboard.log for details.")
CHECK
