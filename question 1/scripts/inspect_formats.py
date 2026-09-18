from pathlib import Path
from dotenv import load_dotenv
import csv
import os

load_dotenv()

sales_dir = Path(os.environ["SALES_DIR"])

for store in ["S01", "S06", "S10"]:
    files = sorted(sales_dir.glob(f"SALES_{store}_*.csv"))

    if not files:
        print(f"{store}: No CSV files found")
        continue

    file_path = files[0]

    with file_path.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)

        delimiter = ";" if store == "S06" else ","
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader, [])

    print(f"\nStore group: {store}")
    print(f"Sample file: {file_path.name}")
    print(f"Delimiter: {delimiter!r}")
    print(f"Header: {header}")
