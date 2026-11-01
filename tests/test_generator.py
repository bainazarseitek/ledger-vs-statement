"""Generator tests: determinism, arrival rules, schema and planted-class counts. No .env, no BigQuery."""
import hashlib
import json
import re
import tomllib
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from recon.generator import emit, payments_for_day, world

SEED = 20261101
WORLD_START = date(2026, 10, 4)
REPO = Path(__file__).resolve().parents[1]
SCHEMAS = REPO / "src" / "recon" / "schemas"
GOLDEN = "7bae06c071d0f45b8322c64a63c58ed4c2a0e8a660dedf4ac013e8cacc8917ac"   # generator 1.0.0, run date 2026-10-09
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\+00:00$")


def day(i):
    return WORLD_START + timedelta(days=i)


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def day_files(landing, run_date):
    r = run_date.isoformat()
    files = [landing / f"payment_events/arrival_date={r}/part-000.ndjson"]
    files += [landing / f"settlement_lines/arrival_date={r}/mid={m.mid}.ndjson" for m in world().mids]
    files.append(landing / f"_truth/booking_date={r}.ndjson")
    return sorted(files)


def combined_hash(landing, run_date):
    text = "".join(f"{p.relative_to(landing).as_posix()} {hashlib.sha256(p.read_bytes()).hexdigest()}\n"
                   for p in day_files(landing, run_date))
    return hashlib.sha256(text.encode()).hexdigest()


def booked(first_days):
    """Every payment booked in the first `first_days` days, for every MID."""
    return [p for i in range(first_days) for m in world().mids for p in payments_for_day(SEED, WORLD_START, day(i), m)]


@pytest.fixture
def landing(tmp_path):
    return tmp_path / "landing"


def test_golden_hash(landing):
    emit(SEED, WORLD_START, day(5), landing)                       # 2026-10-09
    assert combined_hash(landing, day(5)) == GOLDEN


def test_rerun_is_byte_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    emit(SEED, WORLD_START, day(5), a)
    emit(SEED, WORLD_START, day(5), b)
    for pa, pb in zip(day_files(a, day(5)), day_files(b, day(5)), strict=True):
        assert pa.read_bytes() == pb.read_bytes(), pa.name


def test_other_seed_differs(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    emit(SEED, WORLD_START, day(5), a)
    emit(SEED + 1, WORLD_START, day(5), b)
    assert combined_hash(a, day(5)) != combined_hash(b, day(5))


def test_rows_belong_to_their_run(landing):
    for i in range(10):
        r = day(i)
        emit(SEED, WORLD_START, r, landing)
        for path in day_files(landing, r):
            rel = path.relative_to(landing).as_posix()
            for row in read_rows(path):
                if rel.startswith("payment_events/"):
                    assert row["_arrival_date"] == r.isoformat()
                    assert row["delivered_ts"].startswith(r.isoformat())
                    assert row["_source_file"] == rel
                elif rel.startswith("settlement_lines/"):
                    assert row["_arrival_date"] == r.isoformat()
                    assert row["statement_id"].endswith(f"{r:%Y%m%d}")
                    assert rel.endswith(f"mid={row['mid']}.ndjson")
                    assert row["_source_file"] == rel


def test_each_row_in_exactly_one_file(landing):
    lines, deliveries = {}, []
    for i in range(15):
        emit(SEED, WORLD_START, day(i), landing)
        for path in day_files(landing, day(i)):
            rel = path.relative_to(landing).as_posix()
            for row in read_rows(path):
                if rel.startswith("settlement_lines/"):
                    lines[row["payment_id"]] = lines.get(row["payment_id"], 0) + 1
                elif rel.startswith("payment_events/"):
                    deliveries.append(row)
    delivered = {row["payment_id"] for row in deliveries}
    for p in booked(10):
        t = p["truth"]
        if "D2" in t["planted"]:
            assert t["payment_id"] not in lines
        else:
            assert lines.get(t["payment_id"]) == 1, t["payment_id"]
        if "D3" in t["planted"]:
            assert t["payment_id"] not in delivered
    ids = [row["delivery_id"] for row in deliveries]
    assert len(ids) == len(set(ids))


def test_lookback_is_enough():
    assert 3 <= world().lookback_days
    for p in booked(10):
        b = date.fromisoformat(p["truth"]["booking_date"])
        arrivals = [row["_arrival_date"] for row in p["deliveries"]]
        if p["line"]:
            arrivals.append(p["line"]["_arrival_date"])
        for a in arrivals:
            assert b <= date.fromisoformat(a) <= b + timedelta(days=3), p["truth"]["payment_id"]


def check_value(field, value):
    if value is None:
        assert field["mode"] != "REQUIRED", field["name"]
        return
    kind = field["type"]
    if kind == "STRING":
        assert isinstance(value, str)
    elif kind == "INT64":
        assert isinstance(value, int) and not isinstance(value, bool)
    elif kind == "BOOL":
        assert isinstance(value, bool)
    elif kind == "DATE":
        assert DATE_RE.match(value)
    elif kind == "TIMESTAMP":
        assert TS_RE.match(value)
    else:
        raise AssertionError(f"unexpected type {kind}")


def test_rows_match_schema(landing):
    emit(SEED, WORLD_START, day(5), landing)
    schemas = {name: json.loads((SCHEMAS / f"{name}.json").read_text())["fields"]
               for name in ("payment_events", "settlement_lines")}
    for path in day_files(landing, day(5)):
        table = path.relative_to(landing).parts[0]
        if table not in schemas:
            continue
        fields = schemas[table]
        for row in read_rows(path):
            assert set(row) == {f["name"] for f in fields}
            for f in fields:
                check_value(f, row[f["name"]])


def within(count, expected):
    return 0.25 * expected <= count <= 3 * expected


def test_class_counts_within_loose_bounds():
    payments = booked(7)
    planted = [set(p["truth"]["planted"]) for p in payments]
    with_events = [p for p in payments if p["deliveries"]]
    settled = [p for p in payments if p["line"]]
    without_d5 = [p for p in settled if "D5" not in p["truth"]["planted"]]
    d = world().defects
    n = len(payments)
    assert within(sum("D2" in s for s in planted), n * d["missing_in_statement_bp"] / 10000)
    assert within(sum("D3" in s for s in planted), n * d["missing_in_ledger_bp"] / 10000)
    assert within(sum("D4" in s for s in planted), n * d["amount_mismatch_bp"] / 10000)
    assert within(sum("D1" in set(p["truth"]["planted"]) for p in with_events),
                  len(with_events) * world().webhooks["redelivery_bp"] / 10000)
    assert within(sum("D5" in set(p["truth"]["planted"]) for p in settled),
                  len(settled) * d["fee_overcharge_bp"] / 10000)
    assert within(sum(p["truth"]["fee_noise"] == "spike" for p in without_d5),
                  len(without_d5) * world().fee_noise["spike_bp"] / 10000)


def test_grace_days_match_dbt():
    world_toml = tomllib.loads((REPO / "src" / "recon" / "world.toml").read_text())
    project = yaml.safe_load((REPO / "dbt" / "dbt_project.yml").read_text())
    assert world_toml["statement_grace_days"] == project["vars"]["statement_grace_days"]
