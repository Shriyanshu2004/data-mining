from pathlib import Path
from datetime import datetime, timezone
import csv
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

SALES_DIR = Path(os.environ["SALES_DIR"])

def read_sales_file(path: Path) -> pd.DataFrame:
    store_id = path.name.split("_")[1]

    if store_id <= "S05":
        delimiter = ","
        encoding = "utf-8-sig"
        df = pd.read_csv(path, sep=delimiter, encoding=encoding, dtype=str)
        df = df.rename(columns={
            "product_code": "product_code",
            "qty": "qty",
            "unit_price": "unit_price",
            "line_type": "line_type",
            "ts": "ts",
        })
        df["ts"] = pd.to_datetime(df["ts"], format="%Y-%m-%dT%H:%M:%S")

    elif store_id <= "S09":
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str)
        df = df.rename(columns={
            "item_code": "product_code",
            "quantity": "qty",
            "rate": "unit_price",
            "type": "line_type",
            "txn_time": "ts",
        })
        df["ts"] = pd.to_datetime(df["ts"], format="%d-%m-%Y %H:%M:%S")

    else:
        df = pd.read_csv(path, sep=",", encoding="utf-8-sig", dtype=str)
        df["ts"] = pd.to_numeric(df["ts"], errors="raise")
        df["ts"] = pd.to_datetime(df["ts"], unit="s", utc=True)

    for column in ["qty", "unit_price", "line_no"]:
        df[column] = pd.to_numeric(df[column], errors="raise")

    df["source_file"] = path.name
    df["store_id"] = store_id

    return df

sample_files = [
    sorted(SALES_DIR.glob("SALES_S01_*.csv"))[0],
    sorted(SALES_DIR.glob("SALES_S06_*.csv"))[0],
    sorted(SALES_DIR.glob("SALES_S10_*.csv"))[0],
]

for path in sample_files:
    df = read_sales_file(path)
    print(f"\nFile: {path.name}")
    print(f"Rows read: {len(df)}")
    print("Columns:", list(df.columns))
    print(df[["bill_no", "line_no", "product_code", "qty", "unit_price", "line_type", "ts"]].head(2).to_string(index=False))
