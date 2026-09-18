from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()
sales_dir = Path(os.environ["SALES_DIR"])

for name in [
    "SALES_S01_20241112.csv",
    "SALES_S06_20241108.csv",
    "SALES_S10_20241108.csv",
]:
    path = sales_dir / name
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        print(f"{name}: {f.readline().strip()}")
