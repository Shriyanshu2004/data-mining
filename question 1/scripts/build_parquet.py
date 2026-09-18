from pathlib import Path
import os
import re
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

SALES_DIR = Path(os.environ["SALES_DIR"])
OUTPUT_DIR = Path("data/processed/sales")
MANIFEST_PATH = Path("data/reference/file_manifest.csv")

manifest = pd.read_csv(MANIFEST_PATH, dtype={"store_id": str})
manifest = manifest[manifest["kind"] == "original"].copy()

def read_sales_file(path: Path, store_id: str, business_date: str) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
        df = df.rename(columns={
            "item_code": "product_code",
            "quantity": "qty",
            "rate": "unit_price",
            "type": "line_type",
            "txn_time": "ts",
        })
        ts = pd.to_datetime(df["ts"], errors="raise", utc=True)
    elif store_id <= "S05":
        df = pd.read_csv(path, sep=",", encoding="utf-8-sig", dtype=str)
        ts = pd.to_datetime(
            df["ts"], format="%Y-%m-%dT%H:%M:%S", errors="raise"
        ).dt.tz_localize("Asia/Kolkata").dt.tz_convert("UTC")

    elif store_id <= "S09":
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str)
        df = df.rename(columns={
            "item_code": "product_code",
            "quantity": "qty",
            "rate": "unit_price",
            "type": "line_type",
            "txn_time": "ts",
        })
        ts = pd.to_datetime(
            df["ts"], format="%d-%m-%Y %H:%M:%S", errors="raise"
        ).dt.tz_localize("Asia/Kolkata").dt.tz_convert("UTC")

    else:
        df = pd.read_csv(path, sep=",", encoding="utf-8-sig", dtype=str)
        epoch = pd.to_numeric(df["ts"], errors="raise")
        ts = pd.to_datetime(epoch, unit="s", utc=True)

    for column in ["qty", "unit_price", "line_no"]:
        df[column] = pd.to_numeric(df[column], errors="raise")

    df["ts"] = ts.dt.tz_convert("UTC").dt.tz_localize(None)
    df["store_id"] = store_id
    df["business_date"] = pd.to_datetime(business_date).date()
    df["source_file"] = path.name

    columns = [
        "store_id", "business_date", "bill_no", "line_no",
        "product_code", "qty", "unit_price", "line_type",
        "ts", "source_file"
    ]

    return df[columns]

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    processed_files = 0
    errors = []

    for row in manifest.itertuples(index=False):
        source_path = SALES_DIR / row.file

        match = re.search(r"SALES_(S\d{2})_(\d{8})", row.file)
        if not match:
            errors.append(f"Unexpected filename: {row.file}")
            continue

        store_id = match.group(1)
        business_date = pd.to_datetime(match.group(2), format="%Y%m%d").date()

        try:
            df = read_sales_file(source_path, store_id, str(business_date))

            if len(df) != int(row.rows):
                errors.append(
                    f"Row mismatch {row.file}: expected {row.rows}, got {len(df)}"
                )
                continue

            output_path = (
                OUTPUT_DIR
                / f"business_date={business_date}"
                / f"store_id={store_id}"
                / f"{Path(row.file).stem}.parquet"
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = output_path.with_name(output_path.name + ".tmp")
            df.to_parquet(temporary_path, index=False, compression="snappy")
            os.replace(temporary_path, output_path)

            total_rows += len(df)
            processed_files += 1

        except Exception as exc:
            errors.append(f"{row.file}: {exc}")

        if processed_files and processed_files % 500 == 0:
            print(f"Processed {processed_files} files; {total_rows:,} rows")

    print("\n=== PARQUET BUILD SUMMARY ===")
    print("Original files in manifest:", len(manifest))
    print("Files successfully processed:", processed_files)
    print("Rows written:", total_rows)
    print("Errors:", len(errors))
    print("Output directory:", OUTPUT_DIR.resolve())

    for error in errors[:30]:
        print("ERROR:", error)

    if len(errors) > 30:
        print(f"... plus {len(errors) - 30} more errors")

if __name__ == "__main__":
    main()

