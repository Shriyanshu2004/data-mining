from pathlib import Path
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
sales_dir = Path(os.environ["SALES_DIR"])

def read_file(path):
    store = path.name.split("_")[1]

    if store <= "S05":
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
        df = df.rename(columns={"qty": "qty", "unit_price": "unit_price"})
    elif store <= "S09":
        df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8-sig")
        df = df.rename(columns={
            "item_code": "product_code",
            "quantity": "qty",
            "rate": "unit_price",
            "type": "line_type",
        })
    else:
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")

    return df

resends = sorted(
    p for p in sales_dir.glob("*.csv")
    if "__R" in p.stem
)

for path in resends[:5]:
    original_name = path.stem.split("__R")[0] + path.suffix
    original = sales_dir / original_name

    print(f"\nResend: {path.name}")
    print(f"Original exists: {original.exists()}")

    if not original.exists():
        continue

    a = read_file(original)
    b = read_file(path)

    print(f"Original rows: {len(a)}")
    print(f"Resend rows:   {len(b)}")
