from dotenv import load_dotenv
import os

load_dotenv()

print("Sales folder:", os.getenv("SALES_DIR"))
print("MinIO endpoint:", os.getenv("MINIO_ENDPOINT"))
print("MinIO bucket:", os.getenv("MINIO_BUCKET"))
