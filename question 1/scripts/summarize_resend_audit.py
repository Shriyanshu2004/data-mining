import pandas as pd

df = pd.read_csv("reports/resend_audit.csv")

print("Resend status counts:")
print(df["status"].value_counts().to_string())

print("\nResend types:")
print("Full-key matches:", int((df["resend_only_keys"] == 0).sum()))
print("Partial resends:", int((df["original_only_keys"] > 0).sum()))
print("Resends with new keys:", int((df["resend_only_keys"] > 0).sum()))
print("Originals with duplicate keys:", int((df["original_duplicate_key_rows"] > 0).sum()))
print("Resends with duplicate keys:", int((df["resend_duplicate_key_rows"] > 0).sum()))

print("\nPartial resend files:")
partial = df[df["original_only_keys"] > 0]
print(partial[[
    "resend", "original_rows", "resend_rows",
    "shared_keys", "original_only_keys"
]].to_string(index=False))

print("\nFiles with new keys:")
new_keys = df[df["resend_only_keys"] > 0]
print(new_keys[[
    "resend", "original_rows", "resend_rows",
    "resend_only_keys"
]].to_string(index=False))
