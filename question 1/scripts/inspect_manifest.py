import pandas as pd

manifest = pd.read_csv("data/reference/file_manifest.csv")

print("Manifest rows:", len(manifest))
print("\nFile kinds:")
print(manifest["kind"].value_counts().to_string())

print("\nStores:")
print(manifest["store_id"].value_counts().sort_index().to_string())

print("\nMissing values:")
print(manifest.isna().sum().to_string())

print("\nDuplicate filenames:", int(manifest["file"].duplicated().sum()))
print("Total expected source rows:", int(manifest["rows"].sum()))
