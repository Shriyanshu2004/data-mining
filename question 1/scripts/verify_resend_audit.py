import pandas as pd

df = pd.read_csv("reports/resend_audit.csv")

print("Total resend files:", len(df))
print("Audit errors:", int((df["status"] != "OK").sum()))
print("Partial resends:", int((df["original_only_keys"] > 0).sum()))
print("Full-key matches:", int((df["original_only_keys"] == 0).sum()))
print("Resend-only keys:", int(df["resend_only_keys"].sum()))
print("Payload conflict columns:", int(df["payload_conflicting_columns"].sum()))
print("Duplicate-key rows in originals:", int(df["original_duplicate_key_rows"].sum()))
print("Duplicate-key rows in resends:", int(df["resend_duplicate_key_rows"].sum()))
