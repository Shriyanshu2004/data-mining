from pathlib import Path
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
sales_dir = Path(os.environ["SALES_DIR"])

manifest = pd.read_csv("data/reference/file_manifest.csv", dtype={"store_id": str})
manifest = manifest[manifest["kind"] == "original"].copy()

def read_sales_file(path: Path, store_id: str) -> pd.DataFrame:
    if store_id <= "S05":
        df = pd.read_csv(path, sep=",", encoding="utf-8-sig", dtype=str)
        df["ts"] = pd.to_datetime(
            df["ts"], format="%Y-%m-%dT%H:%M:%S", errors="raise"
        )

    elif store_id <= "S09":
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str)
        df = df.rename(columns={
            "item_code": "product_code",
            "quantity": "qty",
            "rate": "unit_price",
            "type": "line_type",
            "txn_time": "ts",
        })
        df["ts"] = pd.to_datetime(
            df["ts"], format="%d-%m-%Y %H:%M:%S", errors="raise"
        )

    else:
        df = pd.read_csv(path, sep=",", encoding="utf-8-sig", dtype=str)
        df["ts"] = pd.to_numeric(df["ts"], errors="raise")
        df["ts"] = pd.to_datetime(df["ts"], unit="s", utc=True)

    for column in ["qty", "unit_price", "line_no"]:
        df[column] = pd.to_numeric(df[column], errors="raise")

    df["source_file"] = path.name
    df["store_id"] = store_id
    return df

checked = 0
total_rows = 0
errors = []

for row in manifest.itertuples(index=False):
    path = sales_dir / row.file

    if not path.exists():
        errors.append(f"MISSING FILE: {row.file}")
        continue

    try:
        df = read_sales_file(path, row.store_id)
        actual_rows = len(df)
        expected_rows = int(row.rows)

        if actual_rows != expected_rows:
            errors.append(
                f"ROW COUNT MISMATCH: {row.file}: "
                f"expected {expected_rows}, got {actual_rows}"
            )
        else:
            checked += 1
            total_rows += actual_rows

    except Exception as exc:
        errors.append(f"READ ERROR: {row.file}: {exc}")

print("Original manifest files:", len(manifest))
print("Files read with matching row counts:", checked)
print("Rows read and validated:", total_rows)
print("Errors:", len(errors))

for error in errors[:30]:
    print(error)

if len(errors) > 30:
    print(f"... and {len(errors) - 30} more errors")
