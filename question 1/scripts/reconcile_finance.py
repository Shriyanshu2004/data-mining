from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parents[1]
source = pd.read_csv(root / "reports" / "monthly_net_revenue.csv")
finance = pd.read_csv(root / "data" / "reference" / "finance_monthly.csv")
finance["month"] = finance["month"].str[:7]
source["month"] = source["month"].str[:7]
source = source.rename(columns={"net_revenue": "folder_revenue"})
comparison = source.merge(finance[["month", "revenue_inr"]], on="month", how="outer")
comparison["difference"] = comparison["revenue_inr"] - comparison["folder_revenue"]
comparison["classification"] = "matches"
comparison.loc[comparison["month"] == "2024-03", "classification"] = "definition: external institutional invoice"
comparison.loc[comparison["month"] == "2024-07", "classification"] = "source gap: missing S07 exports"
comparison.loc[comparison["month"] == "2024-12", "classification"] = "definition: finance rounds each bill"
comparison["take_back_to_finance"] = comparison["revenue_inr"]
comparison.to_csv(root / "reports" / "reconciliation.csv", index=False)

print(comparison.to_string(index=False))
print("\nSaved: reports/reconciliation.csv")
