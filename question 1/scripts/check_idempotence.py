from pathlib import Path
import csv
import hashlib
import os
import subprocess
import sys

import duckdb
from dotenv import load_dotenv

load_dotenv()
root = Path(__file__).resolve().parents[1]
output = root / "data" / "processed" / "sales" / "**" / "*.parquet"
report_path = root / "reports" / "idempotence_runs.csv"


def snapshot():
    connection = duckdb.connect()
    query = f"""
        SELECT COUNT(*) AS row_count,
               md5(string_agg(
                   concat_ws('|', store_id, CAST(business_date AS VARCHAR), bill_no,
                             CAST(line_no AS VARCHAR), product_code, CAST(qty AS VARCHAR),
                             CAST(unit_price AS VARCHAR), line_type, CAST(ts AS VARCHAR)),
                   '|' ORDER BY store_id, business_date, bill_no, line_no
               )) AS checksum
        FROM read_parquet('{output.as_posix()}', union_by_name=true)
    """
    row_count, checksum = connection.execute(query).fetchone()
    connection.close()
    return int(row_count), checksum


runs = []
for run_number in range(1, 4):
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "build_parquet.py")],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    row_count, checksum = snapshot()
    runs.append({"run": run_number, "row_count": row_count, "checksum": checksum})
    print(f"run={run_number} row_count={row_count} checksum={checksum}")

if len({(run["row_count"], run["checksum"]) for run in runs}) != 1:
    raise SystemExit("IDEMPOTENCE FAILED")

with report_path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=["run", "row_count", "checksum"])
    writer.writeheader()
    writer.writerows(runs)

print(f"IDEMPOTENCE PASSED; report={report_path.relative_to(root)}")
