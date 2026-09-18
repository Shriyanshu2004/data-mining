CREATE TABLE hive.default.sales_partitioned (
    bill_no VARCHAR,
    line_no BIGINT,
    product_code VARCHAR,
    qty BIGINT,
    unit_price DOUBLE,
    line_type VARCHAR,
    ts TIMESTAMP,
    source_file VARCHAR,
    business_date DATE,
    store_id VARCHAR
)
WITH (
    format = 'PARQUET',
    external_location = 's3a://annapurna-sales/sales/',
    partitioned_by = ARRAY['business_date', 'store_id']
);
