from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()
sales_dir = Path(os.environ["SALES_DIR"])

original = sales_dir / "SALES_S01_20241112.csv"
resend = sales_dir / "SALES_S01_20241112__R1.csv"

a = pd.read_csv(original, dtype=str, encoding="utf-8-sig")
b = pd.read_csv(resend, dtype=str, encoding="utf-8-sig")

key = ["bill_no", "line_no"]
payload = ["product_code", "qty", "unit_price", "line_type", "ts"]

a["line_no"] = a["line_no"].astype(str)
b["line_no"] = b["line_no"].astype(str)

merged = a.merge(
    b,
    on=key,
    how="inner",
    suffixes=("_original", "_resend")
)

print("Original rows:", len(a))
print("Resend rows:", len(b))
print("Shared line keys:", len(merged))

conflict_mask = False
for col in payload:
    conflict_mask = conflict_mask | (
        merged[f"{col}_original"].fillna("") !=
        merged[f"{col}_resend"].fillna("")
    )

print("Shared keys with different payload:", int(conflict_mask.sum()))
print("Original lines absent from resend:", len(a) - len(merged))
print("Resend lines absent from original:", len(b) - len(merged))
