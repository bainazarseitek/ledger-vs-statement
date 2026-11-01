"""Host CLI: python -m recon.cli <command>."""
import argparse
import json
from datetime import date


def bq_setup(args):
    from recon.bq import host_client
    from recon.load import ensure_tables

    client = host_client()
    for dataset in ("raw", "raw_dev"):
        ensure_tables(client, dataset)
        print(f"ok: {dataset} has payment_events, settlement_lines, fx_rates")


def generate(args):
    from recon.config import load_env
    from recon.generator import emit

    env = load_env()
    print(json.dumps(emit(env.seed, env.world_start, args.date, env.landing_dir), sort_keys=True))


def main():
    parser = argparse.ArgumentParser(prog="recon.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bq-setup", help="create raw and raw_dev and their 3 tables if missing").set_defaults(func=bq_setup)
    gen = sub.add_parser("generate", help="write the synthetic landing files for one arrival day")
    gen.add_argument("--date", required=True, type=date.fromisoformat, help="run date, YYYY-MM-DD (UTC)")
    gen.set_defaults(func=generate)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
