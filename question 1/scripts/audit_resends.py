from pathlib import Path
import os
import re
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
sales_dir = Path(os.environ["SALES_DIR"])

def read_normalized(path):
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        header = f.readline()

    sep = ";" if header.count(";") > header.count(",") else ","
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", sep=sep)
    df.columns = [c.strip().lstrip("\ufeff") for c in df.columns]

    rename = {
        "item_code": "product_code",
        "quantity": "qty",
        "rate": "unit_price",
        "type": "line_type",
        "txn_time": "ts",
    }
    df = df.rename(columns=rename)

    required = [
        "bill_no", "line_no", "product_code",
        "qty", "unit_price", "line_type", "ts"
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}")

    return df[required].fillna("")

results = []

for resend_path in sorted(sales_dir.glob("*__R*.csv")):
    original_name = re.sub(r"__R\d+(?=\.csv$)", "", resend_path.name)
    original_path = sales_dir / original_name

    if not original_path.exists():
        results.append({"resend": resend_path.name, "status": "ORIGINAL_MISSING"})
        continue

    try:
        original = read_normalized(original_path)
        resend = read_normalized(resend_path)

        key = ["bill_no", "line_no"]
        payload = ["product_code", "qty", "unit_price", "line_type", "ts"]

        original_dups = int(original.duplicated(key, keep=False).sum())
        resend_dups = int(resend.duplicated(key, keep=False).sum())

        merged = original.merge(
            resend, on=key, how="outer",
            suffixes=("_original", "_resend"),
            indicator=True,
            validate="one_to_one"
        )

        shared = merged[merged["_merge"] == "both"]
        conflicts = 0
        for col in payload:
            conflicts += int((
                shared[f"{col}_original"] != shared[f"{col}_resend"]
            ).any(axis=0))

        results.append({
            "resend": resend_path.name,
            "status": "OK",
            "original_rows": len(original),
            "resend_rows": len(resend),
            "shared_keys": len(shared),
            "resend_only_keys": int((merged["_merge"] == "right_only").sum()),
            "original_only_keys": int((merged["_merge"] == "left_only").sum()),
            "original_duplicate_key_rows": original_dups,
            "resend_duplicate_key_rows": resend_dups,
            "payload_conflicting_columns": conflicts,
        })

    except Exception as e:
        results.append({
            "resend": resend_path.name,
            "status": "ERROR",
            "error": str(e),
        })

report = pd.DataFrame(results)
report.to_csv("reports/resend_audit.csv", index=False)

print("Resend files audited:", len(report))
print("\nStatuses:")
print(report["status"].value_counts().to_string())

print("\nPartial resends:")
if "original_only_keys" in report.columns:
    print(report.loc[
        report["original_only_keys"].fillna(0) > 0,
        ["resend", "original_rows", "resend_rows",
         "original_only_keys", "payload_conflicting_columns"]
    ].to_string(index=False))

print("\nResends with new keys or payload conflicts:")
if "resend_only_keys" in report.columns:
    print(report.loc[
        (report["resend_only_keys"].fillna(0) > 0) |
        (report["payload_conflicting_columns"].fillna(0) > 0),
        ["resend", "resend_only_keys", "payload_conflicting_columns"]
    ].to_string(index=False))

print("\nDuplicate-key cases:")
if "original_duplicate_key_rows" in report.columns:
    print(report.loc[
        (report["original_duplicate_key_rows"].fillna(0) > 0) |
        (report["resend_duplicate_key_rows"].fillna(0) > 0),
        ["resend", "original_duplicate_key_rows", "resend_duplicate_key_rows"]
    ].to_string(index=False))
