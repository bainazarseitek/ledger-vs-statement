"""Host CLI: python -m recon.cli <command>. Host runs write only to $RAW_DATASET (raw_dev from the Makefile)."""
import argparse
import json
import logging
import os
from datetime import UTC, date, datetime, timedelta


def guarded(run_date):
    """check_run_date runs before anything is generated, fetched or loaded."""
    from recon.config import load_env
    from recon.load import check_run_date

    env = load_env()
    check_run_date(run_date, env.world_start, datetime.now(UTC).date())
    return env


def show(label, value):
    print(f"{label}: {json.dumps(value, sort_keys=True)}")


def bq_setup(args):
    from recon.bq import host_client
    from recon.load import ensure_tables

    client = host_client()
    for dataset in ("raw", "raw_dev"):
        ensure_tables(client, dataset)
        print(f"ok: {dataset} has payment_events, settlement_lines, fx_rates")


def generate(args):
    from recon.generator import emit

    env = guarded(args.date)
    show("generate", emit(env.seed, env.world_start, args.date, env.landing_dir))


def fetch(args):
    from recon.fx import fetch_nbk

    env = guarded(args.date)
    show("fetch", fetch_nbk(args.date, env.landing_dir))


def load(args, client=None):
    from recon.bq import host_client
    from recon.load import TABLES, load_day

    env = guarded(args.date)
    client = client or host_client()
    dataset = os.environ["RAW_DATASET"]
    for table in TABLES:
        show(f"load {dataset}", load_day(client, dataset, table, args.date, env.landing_dir))


def day(args, client=None):
    """Generate, fetch FX, then load the 3 tables: the same order as the DAG."""
    from recon.bq import host_client

    guarded(args.date)
    print(f"run date {args.date}")
    generate(args)
    fetch(args)
    load(args, client or host_client())


def days(args):
    from recon.bq import host_client

    if args.to_date < args.from_date:
        raise SystemExit(f"--to {args.to_date} is before --from {args.from_date}")
    client = host_client()
    d = args.from_date
    while d <= args.to_date:                              # oldest first; the loop lives in Python, not in shell
        day(argparse.Namespace(date=d), client)
        d += timedelta(days=1)


def main():
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(prog="recon.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bq-setup", help="create raw and raw_dev and their 3 tables if missing").set_defaults(func=bq_setup)
    for name, func, text in (("generate", generate, "write the synthetic landing files for one arrival day"),
                             ("fetch", fetch, "land the real NBK rates for one run date, once"),
                             ("load", load, "load the 3 raw tables of one arrival day into $RAW_DATASET"),
                             ("day", day, "generate, fetch and load one arrival day")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--date", required=True, type=date.fromisoformat, help="run date, YYYY-MM-DD (UTC)")
        p.set_defaults(func=func)
    p = sub.add_parser("days", help="run day for every date from --from to --to, oldest first")
    p.add_argument("--from", dest="from_date", required=True, type=date.fromisoformat)
    p.add_argument("--to", dest="to_date", required=True, type=date.fromisoformat)
    p.set_defaults(func=days)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
