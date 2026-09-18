-- Annapurna Stores: sales analytics
-- Source: processed Parquet files via DuckDB view `sales`

-- 1. Overall dataset profile
SELECT
    COUNT(*) AS total_lines,
    COUNT(DISTINCT store_id) AS stores,
    COUNT(DISTINCT business_date) AS business_days,
    COUNT(DISTINCT bill_no) AS distinct_bill_numbers,
    MIN(business_date) AS first_business_date,
    MAX(business_date) AS last_business_date
FROM sales;

-- 2. Line types and counts
SELECT line_type, COUNT(*) AS line_count
FROM sales
GROUP BY line_type
ORDER BY line_type;

-- 3. Monthly net revenue by store.
-- Revenue is qty * unit_price; excludes TAX and TENDER.
-- SALE, RETURN, DISCOUNT, and VOID remain signed as stored.
SELECT
    store_id,
    DATE_TRUNC('month', business_date)::DATE AS month,
    ROUND(SUM(qty * unit_price), 2) AS net_revenue
FROM sales
WHERE UPPER(line_type) NOT IN ('TAX', 'TENDER')
GROUP BY store_id, month
ORDER BY month, store_id;

-- 4. Daily net revenue
SELECT
    business_date,
    store_id,
    ROUND(SUM(qty * unit_price), 2) AS net_revenue
FROM sales
WHERE UPPER(line_type) NOT IN ('TAX', 'TENDER')
GROUP BY business_date, store_id
ORDER BY business_date, store_id;

-- 5. Top products by net revenue
SELECT
    product_code,
    ROUND(SUM(qty * unit_price), 2) AS net_revenue,
    SUM(qty) AS net_quantity
FROM sales
WHERE UPPER(line_type) NOT IN ('TAX', 'TENDER')
GROUP BY product_code
ORDER BY net_revenue DESC
LIMIT 20;
