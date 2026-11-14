import argparse
import json
from decimal import Decimal
from pathlib import Path

from app.config import Settings, load_settings
from app.domain.models import Opportunity
from app.execution.paper import PaperBroker, PaperOrder, ReplayEvent, ReplayRecording
from app.pricing.engine import evaluate
from app.storage.database import Database
from app.venues.mock import MockVenue


def demo() -> Opportunity:
    market, yes, no, fee = MockVenue().fixture()
    # Disable the uncertainty reserve ONLY to reproduce the spec's synthetic arithmetic example.
    settings = Settings(
        adverse_movement_reserve_per_share_usd=Decimal("0"),
        max_order_cost_usd=Decimal("20"),
        max_unmatched_cost_usd=Decimal("20"),
    )
    return evaluate(market, market, yes, no, fee, fee, settings, 0, (Decimal("50"), Decimal("50")))


def paper_report(seed: int = 42, settings: Settings | None = None) -> dict[str, object]:
    market, yes, no, fee = MockVenue().fixture()
    cfg = settings or Settings(
        adverse_movement_reserve_per_share_usd=Decimal("0"),
        max_order_cost_usd=Decimal("20"),
        max_unmatched_cost_usd=Decimal("20"),
    )
    signal = evaluate(market, market, yes, no, fee, fee, cfg, 0, (Decimal("50"), Decimal("50")))
    if signal.status != "EVALUABLE":
        return {
            "result_label": "SYNTHETIC",
            "seed": seed,
            "orders": [],
            "signal": signal.model_dump(mode="json"),
            "status": "NO_TRADE",
        }
    broker = PaperBroker(
        [ReplayEvent(at_ms=0, book=yes, fee=fee), ReplayEvent(at_ms=0, book=no, fee=fee)], seed=seed
    )
    results = [
        broker.submit(
            PaperOrder(
                order_id=f"synthetic-{outcome}",
                venue=market.venue,
                market_id=market.market_id,
                outcome=outcome,
                signal_ms=0,
                quantity=signal.quantity,
                price_cap=next(leg.worst_price for leg in signal.legs if leg.outcome == outcome),
            )
        )
        for outcome in ("YES", "NO")
    ]
    paired = min(r.filled_quantity for r in results)
    cost = sum((r.cost + r.fee for r in results), Decimal("0"))
    return {
        "result_label": "SYNTHETIC",
        "seed": seed,
        "signal": signal.model_dump(mode="json"),
        "orders": [r.model_dump(mode="json") for r in results],
        "paired_quantity": str(paired),
        "cash_spent_usd": str(cost),
        "unmatched_quantity": str(abs(results[0].filled_quantity - results[1].filled_quantity)),
        "potential_settlement_surplus_usd": str(paired - cost),
        "realized_trading_pnl_usd": "0",
        "settlement_status": "PENDING",
        "limitation": "Synthetic taker simulation; no real participant order flow.",
    }


def main() -> None:
    import logging

    from app.observability.events import Event, emit

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    emit(Event.STARTUP)
    parser = argparse.ArgumentParser(description="Offline-first prediction-market research")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    init = sub.add_parser("init-db")
    init.add_argument("--config")
    paper = sub.add_parser("paper")
    paper.add_argument("--config")
    replay = sub.add_parser("replay")
    replay.add_argument("--recording", required=True)
    replay.add_argument("--seed", type=int, default=42)
    record = sub.add_parser("record")
    record.add_argument("--venue", choices=["kalshi", "polymarket"], required=True)
    record.add_argument("--duration-seconds", type=int, default=300)
    sub.add_parser("api")
    dashboard = sub.add_parser("dashboard", help="start the synthetic dashboard and API together")
    dashboard.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1")
    dashboard.add_argument("--port", type=int, default=8501)
    dashboard.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.command == "demo":
        print(demo().model_dump_json(indent=2))
    elif args.command == "init-db":
        db = Database(load_settings(args.config).database_url)
        db.initialize()
        print("SQLite research schema initialized")
    elif args.command == "paper":
        settings = load_settings(args.config)
        if settings.mode != "offline_demo":
            parser.exit(2, "Only synthetic offline paper runs are implemented.\n")
        from uuid import uuid4

        from app.domain.models import utcnow
        from app.storage.database import Record, SystemState

        db = Database(settings.database_url)
        db.initialize()
        with db.transaction() as session:
            state = session.get(SystemState, "kill")
            if state and state.value == "true":
                parser.exit(2, "KILL_SWITCH: new paper runs blocked.\n")
            report = paper_report(settings=settings)
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
                    payload={"action": "paper_start", "actor": "local-cli"},
                    created_at=utcnow().isoformat(),
                )
            )
        print(json.dumps(report, indent=2))
    elif args.command == "replay":
        from pydantic import ValidationError

        try:
            recording = ReplayRecording.model_validate_json(Path(args.recording).read_text())
        except (OSError, ValidationError):
            parser.exit(2, "Invalid recording: version 1 SYNTHETIC schema required.\n")
        broker = PaperBroker(list(recording.events), args.seed)
        results = [broker.submit(order) for order in recording.orders]
        print(
            json.dumps(
                {
                    "result_label": "SYNTHETIC",
                    "seed": args.seed,
                    "orders": [r.model_dump(mode="json") for r in results],
                },
                indent=2,
            )
        )
    elif args.command == "record":
        parser.exit(2, "UNVERIFIED: real venue recording is disabled; no network request made.\n")
    elif args.command == "dashboard":
        from app.launcher import launch_dashboard

        try:
            code = launch_dashboard(args.host, args.port, open_browser=not args.no_browser)
        except (ValueError, RuntimeError) as error:
            parser.exit(2, str(error) + "\n")
        if code:
            parser.exit(code)
    elif args.command == "api":
        import uvicorn

        uvicorn.run("app.api.main:create_app", factory=True, host="127.0.0.1", port=8000)
