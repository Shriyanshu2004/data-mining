from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()
sales_dir = Path(os.environ["SALES_DIR"])

files = [
    sales_dir / "SALES_S01_20241112.csv",
    sales_dir / "SALES_S01_20241112__R1.csv",
]

for file in files:
    df = pd.read_csv(file, dtype=str, encoding="utf-8-sig")
    duplicates = df.duplicated(["bill_no", "line_no"], keep=False)

    print(f"\nFile: {file.name}")
    print("Rows:", len(df))
    print("Duplicate-key rows:", int(duplicates.sum()))

    if duplicates.any():
        print(df.loc[duplicates, ["bill_no", "line_no"]].sort_values(
            ["bill_no", "line_no"]
        ).to_string(index=False))
