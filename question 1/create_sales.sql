CREATE TABLE hive.default.sales (
    store_id VARCHAR,
    business_date DATE,
    bill_no VARCHAR,
    line_no BIGINT,
    product_code VARCHAR,
    qty BIGINT,
    unit_price DOUBLE,
    line_type VARCHAR,
    ts TIMESTAMP,
    source_file VARCHAR
)
WITH (
    format = 'PARQUET',
    external_location = 's3a://annapurna-sales/sales/'
);

