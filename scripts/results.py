"""N1, N2 and N3 with the context to reproduce them, written to docs/evidence/<UTC date>/summary.json.

N1 comes from compare.json (the rerun proof), N2 from <marts>.fct_recon_daily, docs/testing.md and a dbt
run_results.json, N3 from fx_report.json when it exists. Every number in the README comes from this file.
"""
import argparse
import glob
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

# The S8.2 procedure: the reprocessed logical dates and the one older day cleared out of order.
PROOF = {"reprocess_from": "2026-10-26", "reprocess_to": "2026-11-01", "reprocess_days": 7, "cleared_day": "2026-10-14"}
N2_SQL = """select count(*) as mid_days,
       sum(abs(unexplained_minor)) as abs_unexplained_minor,
       countif(unexplained_minor != 0) as days_not_closing,
       min(recon_date) as first_day,
       max(recon_date) as last_day,
       max(as_of_date) as as_of_date
from `{project}.{marts}.fct_recon_daily`"""


def mutation_counts(path="docs/testing.md"):
    """K of K from the mutation-check table: rows whose last cell says caught or missed."""
    caught = total = 0
    for line in Path(path).read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and cells[0].isdigit() and cells[-1].lower() in ("caught", "missed"):
            total += 1
            caught += cells[-1].lower() == "caught"
    return caught, total


def decomposition_status(run_results):
    """Status of assert_recon_decomposition_closes in the dbt build that made the current marts."""
    path = run_results or max(glob.glob("runs/dbt/*/target/run_results.json"), key=os.path.getmtime)
    doc = json.loads(Path(path).read_text())
    statuses = [r["status"] for r in doc["results"] if r["unique_id"].endswith(".assert_recon_decomposition_closes")]
    return (statuses[0] if statuses else "not run"), path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marts-dataset", default="analytics")
    parser.add_argument("--run-results", help="default: the newest runs/dbt/*/target/run_results.json")
    args = parser.parse_args()
    from recon.bq import host_client, query, rows
    from recon.config import load_env

    client, env = host_client(), load_env()
    today = datetime.now(UTC).date()
    evidence = Path(f"docs/evidence/{today.isoformat()}")

    n2_row = rows(query(client, N2_SQL.format(project=client.project, marts=args.marts_dataset), use_cache=False))[0]
    caught, total = mutation_counts()
    status, rr_path = decomposition_status(args.run_results)
    n2 = {"M_mid_days": n2_row["mid_days"], "U_abs_unexplained_minor": n2_row["abs_unexplained_minor"],
          "days_not_closing": n2_row["days_not_closing"], "first_day": n2_row["first_day"].isoformat(),
          "last_day": n2_row["last_day"].isoformat(), "as_of_date": n2_row["as_of_date"].isoformat(),
          "assert_recon_decomposition_closes": status, "run_results": rr_path,
          "K_caught": caught, "K_total": total,
          "claim_allowed": n2_row["abs_unexplained_minor"] == 0 and status == "pass"}

    compare_path = evidence / "compare.json"
    n1 = None
    if compare_path.exists():
        c = json.loads(compare_path.read_text())
        n1 = {"D_reprocessed_days": PROOF["reprocess_days"], **PROOF, "P_identical": c["groups_identical"],
              "P_total": c["groups_before"], "R_rows": c["rows"], "as_of_before": c["as_of_before"],
              "as_of_after": c["as_of_after"], "identical": c["identical"], "summary": c["summary"],
              "source": str(compare_path)}

    fx_path = evidence / "fx_report.json"
    n3 = json.loads(fx_path.read_text()).get("n3") if fx_path.exists() else None

    doc = {"date": today.isoformat(), "written_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(sep=" "),
           "git_sha": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip(),
           "seed": env.seed, "world_start": env.world_start.isoformat(),
           "window": {"first_day": n2["first_day"], "last_day": n2["last_day"]}, "as_of_date": n2["as_of_date"],
           "marts_dataset": args.marts_dataset, "synthetic": "N1 and N2 are measured on synthetic payments",
           "real": "N3 is measured on real NBK rates", "N1": n1, "N2": n2, "N3": n3}
    evidence.mkdir(parents=True, exist_ok=True)
    out = evidence / "summary.json"
    out.write_text(re.sub(re.escape(client.project), "<project>", json.dumps(doc, indent=2, sort_keys=True)) + "\n")
    print(f"N1: {n1['summary'] if n1 else 'no compare.json yet'}")
    print(f"N2: {n2['M_mid_days']} MID-days, {n2['U_abs_unexplained_minor']} minor units unexplained, "
          f"decomposition {status}, mutations {caught} of {total} caught")
    print(f"N3: {'present' if n3 else 'not measured yet'} -> {out}")


if __name__ == "__main__":
    main()
