import os
import boto3
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["MINIO_ENDPOINT"],
    aws_access_key_id=os.environ["MINIO_ACCESS_KEY"],
    aws_secret_access_key=os.environ["MINIO_SECRET_KEY"],
    region_name="us-east-1",
)

bucket = os.environ["MINIO_BUCKET"]
paginator = s3.get_paginator("list_objects_v2")

count = 0
total_bytes = 0

for page in paginator.paginate(Bucket=bucket):
    for obj in page.get("Contents", []):
        if obj["Key"].endswith(".parquet"):
            count += 1
            total_bytes += obj["Size"]

print("Bucket:", bucket)
print("Parquet objects:", count)
print("Total size (MB):", round(total_bytes / (1024 * 1024), 2))
print("Expected objects: 4389")
print("Verification:", "PASSED" if count == 4389 else "CHECK REQUIRED")
