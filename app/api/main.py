import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse

from app.cli import demo, paper_report
from app.config import Settings, load_settings
from app.domain.models import Model, Opportunity
from app.storage.database import Database
from app.venues.mock import MockVenue


class Health(Model):
    status: str
    mode: str
    live_ready: bool = False


class ControlResult(Model):
    status: str


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or load_settings()
    db = Database(cfg.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db.initialize()
        yield
        db.engine.dispose()

    app = FastAPI(title="Prediction-market research", version="0.1.0", lifespan=lifespan)

    def authorize(authorization: Annotated[str | None, Header()] = None) -> None:
        expected = cfg.control_token
        if not expected or not secrets.compare_digest(authorization or "", "Bearer " + expected):
            raise HTTPException(status_code=401, detail="valid control bearer token required")

    @app.get("/health/live", response_model=Health)
    def health() -> Health:
        return Health(status="ok", mode=cfg.mode)

    @app.get("/health/ready", response_model=Health)
    def ready() -> Health:
        try:
            db.records("audit")
        except Exception:
            raise HTTPException(status_code=503, detail="storage unavailable") from None
        if cfg.mode != "offline_demo":
            raise HTTPException(status_code=503, detail="requested mode not implemented")
        return Health(status="offline_research_ready", mode=cfg.mode)

    @app.get("/markets")
    def markets() -> list[dict[str, Any]]:
        return [MockVenue().fixture()[0].model_dump(mode="json")]

    @app.get("/books")
    def books() -> list[dict[str, Any]]:
        return [b.model_dump(mode="json") for b in MockVenue().fixture()[1:3]]

    @app.get("/opportunities", response_model=list[Opportunity])
    def opportunities() -> list[Opportunity]:
        return [demo()]

    @app.get("/mappings")
    def mappings() -> list[dict[str, Any]]:
        return db.records("mapping")

    @app.get("/orders")
    def orders() -> list[dict[str, Any]]:
        return db.records("paper_run")

    @app.get("/positions")
    def positions() -> list[dict[str, str]]:
        return db.positions()

    @app.get("/risk")
    def risk() -> dict[str, Any]:
        return {
            "mode": cfg.mode,
            "kill_switch": db.killed(),
            "live_ready": False,
            "armed": False,
            "eligibility": "UNVERIFIED",
            "credentials": "UNVERIFIED",
            "scope": "All displayed books and opportunities are fixed synthetic fixtures",
        }

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> str:
        return "pm_live_ready 0\npm_kill_switch " + str(int(db.killed())) + "\n"

    @app.get("/reports")
    def reports() -> list[dict[str, Any]]:
        return db.records("paper_run")

    @app.post("/controls/kill", dependencies=[Depends(authorize)], response_model=ControlResult)
    def kill() -> ControlResult:
        db.activate_kill("local-operator")
        return ControlResult(status="HALTED; no live orders exist; positions not liquidated")

    @app.post("/controls/paper/start", dependencies=[Depends(authorize)])
    def paper_start() -> dict[str, Any]:
        if cfg.mode != "offline_demo":
            raise HTTPException(409, "only offline synthetic paper mode is implemented")
        report = paper_report(settings=cfg)
        with db.transaction() as session:
            from app.domain.models import utcnow
            from app.storage.database import Record, SystemState

            state = session.get(SystemState, "kill")
            if state and state.value == "true":
                raise HTTPException(409, "kill switch active")
            session.add(
                Record(
                    kind="paper_run",
                    key=str(uuid4()),
                    payload=report,
                    created_at=utcnow().isoformat(),
                )
            )
            session.add(
                Record(
                    kind="audit",
                    key=str(uuid4()),
                    payload={"action": "paper_start", "actor": "local-operator"},
                    created_at=utcnow().isoformat(),
                )
            )
        return report

    @app.post("/controls/live/arm", dependencies=[Depends(authorize)])
    def arm() -> None:
        raise HTTPException(409, "LIVE_DISABLED: M3-M6 requirements unverified")

    return app
