from pathlib import Path
import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

endpoint = os.environ["MINIO_ENDPOINT"]
bucket = os.environ["MINIO_BUCKET"]
access_key = os.environ["MINIO_ACCESS_KEY"]
secret_key = os.environ["MINIO_SECRET_KEY"]

root = Path("data/processed/sales")

s3 = boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    region_name="us-east-1",
)

try:
    s3.head_bucket(Bucket=bucket)
except ClientError as exc:
    print(f"Cannot access bucket '{bucket}': {exc}")
    raise SystemExit(1)

files = list(root.rglob("*.parquet"))
uploaded = 0
failed = []

for file in files:
    key = "sales/" + file.relative_to(root).as_posix()
    try:
        s3.upload_file(str(file), bucket, key)
        uploaded += 1
        if uploaded % 500 == 0:
            print(f"Uploaded {uploaded}/{len(files)} files")
    except Exception as exc:
        failed.append(f"{key}: {exc}")

print("\n=== MINIO UPLOAD SUMMARY ===")
print("Bucket:", bucket)
print("Files found:", len(files))
print("Files uploaded:", uploaded)
print("Failures:", len(failed))

for error in failed[:20]:
    print("ERROR:", error)

if uploaded == len(files) and not failed:
    print("UPLOAD COMPLETE")
