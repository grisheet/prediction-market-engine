import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config import Settings, load_settings
from app.execution.state import ExecutionState
from app.risk.gates import require_live
from app.storage.database import Database
from app.venues.base import UnsupportedCapability
from app.venues.kalshi import KalshiVenue


def database(tmp_path):
    db = Database("sqlite:///" + str(tmp_path / "engine.db"))
    db.initialize()
    return db


def test_concurrent_reservations_and_restart(tmp_path):
    db = database(tmp_path)

    def reserve(i):
        try:
            db.reserve(str(i), "event", D("7"), D("10"), D("10"))
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(reserve, range(2))) == 1
    with pytest.raises(ValueError):
        db.release("0", reconciled=False)
    db.activate_kill("test")
    other = Database(db.engine.url.render_as_string())
    assert other.killed()
    with pytest.raises(ValueError, match="KILL_SWITCH"):
        other.reserve("new", "event", D("1"), D("10"), D("10"))


def test_fill_dedup_and_cash(tmp_path):
    db = database(tmp_path)
    args = ("fill1", "mock", "market", "YES", D("2"), D("0.8"), D("0.01"))
    assert db.apply_fill(*args)
    assert not db.apply_fill(*args)
    assert db.positions()[0]["quantity"] == "2"
    assert db.records("cash_ledger")[0]["delta"] == "-0.81"
    with pytest.raises(ValueError, match="conflicting"):
        db.apply_fill(*args[:-1], D("0.02"))


def test_api_controls_and_restart(tmp_path):
    cfg = Settings(database_url="sqlite:///" + str(tmp_path / "api.db"), control_token="test-token")
    auth = {"Authorization": "Bearer test-token"}
    with TestClient(create_app(cfg)) as c:
        assert c.get("/health/ready").status_code == 200
        for path in (
            "markets",
            "books",
            "mappings",
            "opportunities",
            "orders",
            "positions",
            "risk",
            "metrics",
            "reports",
        ):
            assert c.get("/" + path).status_code == 200
        assert c.post("/controls/kill").status_code == 401
        assert c.post("/controls/paper/start", headers=auth).status_code == 200
        assert c.post("/controls/live/arm", headers=auth).status_code == 409
        assert c.post("/controls/kill", headers=auth).status_code == 200
        assert c.post("/controls/paper/start", headers=auth).status_code == 409
        assert "test-token" not in c.get("/openapi.json").text
    with TestClient(create_app(cfg)) as c:
        assert c.get("/risk").json()["kill_switch"] is True


def test_config_environment_override(monkeypatch):
    monkeypatch.setenv("PM_MIN_NET_PROFIT_USD", "1.50")
    assert load_settings("config/default.yaml").min_net_profit_usd == D("1.50")


def test_live_always_fails_closed():
    with pytest.raises(UnsupportedCapability):
        require_live(Settings(mode="live", live_trading_enabled=True))


async def test_real_connector_no_fake_success():
    with pytest.raises(UnsupportedCapability):
        await KalshiVenue().place_order({})


def test_transitions():
    s = ExecutionState()
    with pytest.raises(ValueError):
        s.advance("PAIRED")
    for state in ("VALIDATING", "RESERVED", "SUBMITTING", "UNKNOWN", "MANUAL_REVIEW"):
        s = s.advance(state)
    assert s.state == "MANUAL_REVIEW"


def test_cli_contract(tmp_path):
    env = dict(os.environ, PYTHONPATH=".", PM_DATABASE_URL="sqlite:///" + str(tmp_path / "cli.db"))

    def run(*args):
        return subprocess.run(
            [sys.executable, "-c", "from app.cli import main; main()", *args],
            capture_output=True,
            text=True,
            env=env,
        )

    demo = run("demo")
    assert demo.returncode == 0
    assert D(json.loads(demo.stdout)["net_profit"]) == D("0.4")
    assert run("paper", "--config", "config/default.yaml").returncode == 0
    replay = run("replay", "--recording", "fixtures/replay.json", "--seed", "42")
    assert replay.returncode == 0
    record = run("record", "--venue", "kalshi", "--duration-seconds", "1")
    assert record.returncode == 2 and "UNVERIFIED" in record.stderr


def test_migration_schema_matches_models(tmp_path):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from app.storage.database import Base

    cfg = Config("alembic.ini")
    url = "sqlite:///" + str(tmp_path / "migration.db")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    db = Database(url)
    assert set(inspect(db.engine).get_table_names()) == set(Base.metadata.tables) | {
        "alembic_version"
    }
    db.reserve("r", "e", D("1"), D("2"), D("2"))
    command.downgrade(cfg, "base")
    assert inspect(db.engine).get_table_names() == ["alembic_version"]


def test_storage_rollback_and_readiness(tmp_path):
    from sqlalchemy import text

    from app.storage.database import Record

    db = database(tmp_path)
    with pytest.raises(RuntimeError):
        with db.transaction() as session:
            session.add(Record(kind="audit", key="rolledback", payload={}, created_at="test"))
            raise RuntimeError("injected write failure")
    assert db.records("audit") == []
    cfg = Settings(database_url=db.engine.url.render_as_string())
    with TestClient(create_app(cfg)) as client:
        with db.engine.begin() as connection:
            connection.execute(text("DROP TABLE records"))
        assert client.get("/health/ready").status_code == 503


def test_unimplemented_mode_readiness_and_paper_fail_closed(tmp_path):
    cfg = Settings(
        mode="live",
        live_trading_enabled=True,
        control_token="test",
        database_url="sqlite:///" + str(tmp_path / "live.db"),
    )
    with TestClient(create_app(cfg)) as client:
        assert client.get("/health/ready").status_code == 503
        auth = {"Authorization": "Bearer test"}
        assert client.post("/controls/paper/start", headers=auth).status_code == 409
        assert client.post("/controls/live/arm", headers=auth).status_code == 409


def test_empty_token_disables_controls(tmp_path):
    cfg = Settings(database_url="sqlite:///" + str(tmp_path / "auth.db"))
    with TestClient(create_app(cfg)) as c:
        for path in ("/controls/paper/start", "/controls/kill", "/controls/live/arm"):
            assert c.post(path, headers={"Authorization": "Bearer "}).status_code == 401
            assert c.get(path).status_code == 405


def test_reservation_idempotency_and_reconciled_release(tmp_path):
    db = database(tmp_path)
    db.reserve("r", "event", D("7"), D("10"), D("10"))
    db.reserve("r", "event", D("7"), D("10"), D("10"))
    with pytest.raises(ValueError, match="conflict"):
        db.reserve("r", "event", D("8"), D("10"), D("10"))
    db.release("r", reconciled=True)
    db.reserve("new", "event", D("10"), D("10"), D("10"))
