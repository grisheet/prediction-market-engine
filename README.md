# Prediction-market research engine

A working Python 3.12 offline research repository, not a live trading system. Every supplied
market, recording, fee schedule and profit example is **SYNTHETIC**. Real adapters fail closed.

## Website: setup, results and working demo

Open **https://grisheet.github.io/prediction-market-engine/**. No installation or terminal is
needed to use the website. It teaches setup, displays the original synthetic Python report
files, and provides a functioning browser calculator and paper simulation.

The website's demo uses the vendored decimal.js 10.6.0 library for exact decimal arithmetic.
It supports a USD, unit-payout binary pair, whole contracts, USD 0.01 price ticks, ask depth,
per-level rounded synthetic fees, conservative sizing, risk limits and failed-leg scenarios.
Financial values export as strings. Inputs stay in memory in the current browser tab; there
is no trading account connection or server process. Terms and Privacy are linked in the footer.

The original Python application remains the complete research interface for API, SQLite
records, replay and broader domain models. Open it in Codespaces using the instructions below.
The website does not claim that GitHub Pages runs Python or Streamlit. Codespaces execution
remains distinct from the website and is subject to your GitHub plan.

For contributors: `npm ci --ignore-scripts`, `npm test`, and `npm run check` validate the
website without a Python server. The repository's existing GitHub Pages configuration publishes
main from the repository root. `index.html` is the website entry point and `.nojekyll` preserves
its assets as ordinary files. No separate website build or custom hosting account is required.

## Run the full Python application in GitHub Codespaces

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/grisheet/prediction-market-engine?quickstart=1)

Click **Open in GitHub Codespaces**, then **Create codespace**. GitHub installs dependencies
and starts the app. When ready, open **Ports**, find **8501 / Prediction Market Dashboard**,
and click its **Open in Browser** icon. Keep the port private. Sign in to the GitHub account
that owns or can access this private repository. No venue credentials are required.

This runs the actual Python API and Streamlit dashboard. The launcher generates a temporary
control token shared only between its child processes, allowing the synthetic paper and kill
buttons to work. Live trading stays disabled. Codespaces usage depends on your GitHub plan;
stop the codespace when finished.

If startup needs repeating, use the Codespaces terminal:

```bash
bash scripts/start-codespace.sh
```

## Run on your computer

Install Python 3.12 and Git first. On macOS/Linux:

```bash
git clone https://github.com/grisheet/prediction-market-engine.git
cd prediction-market-engine
python3.12 -m pip install uv==0.13.6
uv sync --frozen
uv run pm-engine dashboard
```

On Windows PowerShell:

```powershell
git clone https://github.com/grisheet/prediction-market-engine.git
cd prediction-market-engine
py -3.12 -m pip install uv==0.13.6
uv sync --frozen
uv run pm-engine dashboard
```

Your browser opens http://127.0.0.1:8501 after both services become ready. Ctrl+C stops both.
If that port is occupied, use `uv run pm-engine dashboard --port 8502`. Sign in to GitHub for
cloning this private repository. Installation downloads dependencies. Once installed, the
synthetic app works offline. All financial JSON values are strings.

For the spec's arithmetic example, `uv run pm-engine demo` reports 20 paired units, USD 19.40
acquisition, USD 0.20 synthetic fees and USD 0.40 potential surplus. This example explicitly
raises order/unmatched limits and sets adverse reserve to zero. Default risk settings can
correctly reject it. It is not a live market signal or realized profit.

## Research commands

```bash
uv run pm-engine replay --recording fixtures/replay.json --seed 42
uv run pm-engine paper --config config/default.yaml
uv run pm-engine init-db
uv run pm-engine api
```

`paper` validates the configured risk limits, persists its run and audit record, and honors
the persistent kill switch. The conservative defaults reject the synthetic signal: its
maximum unmatched-leg budget prevents enough size from meeting the profit threshold.
A NO_TRADE report is an expected research result. Replay is read-only research and does not
constitute permission to submit orders. It accepts only the synthetic recording schema.

For a second terminal:

```bash
uv run streamlit run app/dashboard/main.py
```

API binds to 127.0.0.1:8000; Streamlit shows fixed fixtures, readiness, opportunities and run
reports. Streamlit may listen on non-loopback interfaces by its own default; for a strictly
local launch use `uv run streamlit run app/dashboard/main.py --server.address 127.0.0.1`.
Financial JSON values are strings. Read OpenAPI at http://127.0.0.1:8000/docs.

Control endpoints require a matching `PM_CONTROL_TOKEN` bearer token. Empty tokens disable
controls. Set a random token in the environment of both processes; do not put it in the browser
URL or source code. The dashboard sends the token from its server to the API. No cookie auth,
CORS permissions or browser-executed trading keys exist. New paper runs and kill activation
write audit events. Arming always returns HTTP 409, including with valid authentication.

Supported configuration overrides use the `PM_` prefix, for example
`PM_MIN_NET_PROFIT_USD=0.50`. Environment values override YAML. `.env` is not loaded automatically.
`.env.example` contains empty placeholders only. No real venue credentials are consumed.

`uv run pm-engine record --venue kalshi --duration-seconds 300` returns exit code 2 and an
explicit UNVERIFIED error. It makes no network request. Real discovery, fee APIs, authenticated
streams and order APIs require later verified integrations.

## Storage and Docker

SQLite uses exact decimal strings and transactional `BEGIN IMMEDIATE` reservations. API
startup and `init-db` create the research schema. For migration-managed databases instead:

```bash
uv run alembic upgrade head
```

Do not initialize a database with both methods: `create_all` does not stamp Alembic revisions.
The migration command targets `alembic.ini`; the application uses `PM_DATABASE_URL`.
PostgreSQL transactions deliberately reject use until concurrency tests validate that backend.

```bash
docker compose up --build
```

Docker publishes API port 8000 only on host loopback and persists SQLite in a named volume.
The image uses a locked dependency install. Docker execution has not been validated here.

## Scope and evidence

See [verification](docs/VERIFICATION.md), [architecture](docs/ARCHITECTURE.md),
[API verification](docs/API_VERIFICATION.md), [data dictionary](docs/DATA_DICTIONARY.md),
[fees](docs/FEES.md), [matching](docs/MATCHING.md), [runbooks](docs/RUNBOOKS.md), and
[limitations and readiness](docs/LIMITATIONS.md).

M0 and M1 are the primary deliverable. M2 and M4 contain tested foundations, not completed
milestones. No live connectivity, live readiness, PostgreSQL compatibility, container smoke
result, screenshot, historical backtest, actual order acknowledgment or real profit is claimed.
