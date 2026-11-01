"""Host CLI: python -m recon.cli <command>."""
import argparse

from recon.bq import host_client
from recon.load import ensure_tables


def bq_setup(args):
    client = host_client()
    for dataset in ("raw", "raw_dev"):
        ensure_tables(client, dataset)
        print(f"ok: {dataset} has payment_events, settlement_lines, fx_rates")


def main():
    parser = argparse.ArgumentParser(prog="recon.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bq-setup", help="create raw and raw_dev and their 3 tables if missing").set_defaults(func=bq_setup)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
