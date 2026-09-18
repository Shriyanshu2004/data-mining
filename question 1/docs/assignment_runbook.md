# Annapurna platform runbook

## Architecture and layout

The platform uses MinIO as the object store, PostgreSQL for stores and product master data, and Trino as the federated query engine. Daily files are normalized to Parquet under:

`s3://annapurna-sales/sales/business_date=YYYY-MM-DD/store_id=SNN/`

The partition order makes a one-store/one-month query eligible to scan only that store's files for the requested dates. For example, October 2024 for S03 has 31 files and only the bytes in those files, rather than all 4,389 files and 42.34 MB. The exact byte count can be measured with `scripts/verify_minio.py` or an S3 listing filtered to that prefix.

## Repeatability

The loader uses only manifest rows marked `original`; resend files are audited but not loaded as additional files. Each source line is therefore represented once, while partial resends remain evidence for the audit. Output keys are deterministic and overwritten on rerun.

Run the proof:

```powershell
.\.venv\Scripts\python.exe scripts\check_idempotence.py
```

The command rebuilds three times, computes a deterministic row count and checksum after each run, and writes `reports/idempotence_runs.csv`. All three records must be identical.

## Revenue and dimensional model

A sale line is a fact. Stores, products, and categories are dimensions in PostgreSQL, so store addresses and product descriptions are not repeated on every fact row. Revenue is always:

`SUM(qty * unit_price)` after excluding `TAX` and `TENDER`, while retaining signed `SALE`, `RETURN`, `DISCOUNT`, and `VOID` lines. `TENDER` must not be counted because it repeats the bill total. The temporal product join in `sql/dashboard_views.sql` uses `(product_code, business_date)` and prevents reissued codes from duplicating lines.

The dashboard view exposes store, category, day-of-week, and month slices.

## Historical prices

`sql/temporal_price.sql` takes one `:report_date` parameter. The same query is run with `DATE '2024-03-01'` and a later month; the product identity and price revision are selected using their effective date ranges. No query code changes between periods.

## Cross-system evidence

`sql/cross_system.sql` joins `hive.default.sales_partitioned` to `postgresql.public.*` directly in Trino. Run the query and then run its `EXPLAIN (TYPE DISTRIBUTED)` form in Trino. The plan should show a Hive scan for sales and PostgreSQL scans for the three dimensions, with joins performed by Trino.

## Reconciliation

The source revenue report matches finance for January, February, and April through November except the documented cases below:

| Month | Difference | Classification | Finance treatment |
|---|---:|---|---|
| March 2024 | 486,250.00 | Definition/scope: institutional order invoiced outside the till folder | Take the signed finance figure; label it as an external invoice |
| July 2024 | 232,131.70 | Source gap: S07 exports are missing for July 9-11 | Take the signed finance figure; separately report the folder-only figure |
| December 2024 | 50.48 | Definition: finance rounds each bill to whole rupees | Take the finance figure for closed reporting and document the rounding rule |

The other important source fact is that the source contains 4,457 files: 4,389 originals and 68 resends. The eight partial resends are not replacements; line-level identity is `(bill_no, line_no)`.

## Verification commands

```powershell
docker compose ps
.\.venv\Scripts\python.exe scripts\test_loader.py
.\.venv\Scripts\python.exe scripts\audit_resends.py
.\.venv\Scripts\python.exe scripts\upload_to_minio.py
.\.venv\Scripts\python.exe scripts\verify_minio.py
```
