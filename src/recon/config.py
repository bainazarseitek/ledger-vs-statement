"""Load world.toml, dbt/seeds/mids.csv and the environment into frozen dataclasses."""
import csv
import os
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

WORLD_FILE = Path(__file__).parent / "world.toml"
MIDS_FILE = Path(__file__).resolve().parents[2] / "dbt" / "seeds" / "mids.csv"
INT_COLUMNS = ("statement_utc_offset_hours", "max_settlement_lag_days", "fee_bps", "fee_fixed_minor",
               "fee_tol_bps", "fee_tol_min_minor")


@dataclass(frozen=True)
class Mid:
    """One merchant account: the contract terms both the merchant and the PSP know."""
    mid: str
    psp: str
    currency: str
    statement_utc_offset_hours: int
    max_settlement_lag_days: int
    fee_bps: int
    fee_fixed_minor: int
    fee_tol_bps: int
    fee_tol_min_minor: int

    @property
    def tag(self) -> str:
        return self.currency.lower()


@dataclass(frozen=True)
class World:
    """Everything finance does not know: volumes, timing, defects, noise."""
    generator_version: str
    lookback_days: int
    statement_grace_days: int
    mean_per_day: dict
    jitter_pct: int
    plan_order: tuple
    plan_weight_pct: tuple
    price_minor: dict
    local_hour_weights: tuple
    webhooks: dict
    settlement: dict
    defects: dict
    fee_noise: dict
    mids: tuple


@dataclass(frozen=True)
class Env:
    seed: int
    world_start: date
    landing_dir: Path


def load_mids(path=MIDS_FILE) -> tuple:
    with open(path, newline="") as f:
        return tuple(Mid(**{k: int(v) if k in INT_COLUMNS else v for k, v in row.items()})
                     for row in csv.DictReader(f))


def load_world(path=WORLD_FILE, mids_path=MIDS_FILE) -> World:
    doc = tomllib.loads(Path(path).read_text())
    plans = doc["plans"]
    world = World(
        generator_version=doc["generator_version"],
        lookback_days=doc["lookback_days"],
        statement_grace_days=doc["statement_grace_days"],
        mean_per_day=dict(doc["volume"]["mean_per_day"]),
        jitter_pct=doc["volume"]["jitter_pct"],
        plan_order=tuple(plans["order"]),
        plan_weight_pct=tuple(plans["weight_pct"]),
        price_minor={cur: tuple(prices) for cur, prices in plans["price_minor"].items()},
        local_hour_weights=tuple(doc["time"]["local_hour_weights"]),
        webhooks=dict(doc["webhooks"]),
        settlement=dict(doc["settlement"]),
        defects=dict(doc["defects"]),
        fee_noise=dict(doc["fee_noise"]),
        mids=load_mids(mids_path),
    )
    check(world)
    return world


def check(w: World) -> None:
    """Fail loudly at load time instead of producing a subtly wrong world."""
    problems = []
    if len(w.local_hour_weights) != 24:
        problems.append("time.local_hour_weights needs 24 values")
    if not (len(w.plan_order) == len(w.plan_weight_pct) == len(w.price_minor.get("USD", ()))
            == len(w.price_minor.get("KZT", ()))):
        problems.append("plans.order, plans.weight_pct and every price list need the same length")
    if sum(w.plan_weight_pct) != 100:
        problems.append("plans.weight_pct must sum to 100")
    tags = [m.tag for m in w.mids]
    if len(set(tags)) != len(tags):
        problems.append("two merchant accounts would get the same id tag")
    for m in w.mids:
        if m.currency not in w.price_minor:
            problems.append(f"no price list for {m.currency}")
        if m.mid not in w.mean_per_day:
            problems.append(f"no volume.mean_per_day for {m.mid}")
    if problems:
        raise ValueError("world.toml or mids.csv is invalid: " + "; ".join(problems))


def load_env() -> Env:
    """Only the CLI and the DAG read the environment. Generator functions take these as arguments."""
    return Env(
        seed=int(os.environ["RECON_SEED"]),
        world_start=date.fromisoformat(os.environ["RECON_WORLD_START"]),
        landing_dir=Path(os.environ["RECON_LANDING_DIR"]),
    )
