-- Trino federation query: no staging or copy between systems.
-- Sales is read through Hive/MinIO; dimensions are read through PostgreSQL.

SELECT
    s.store_id,
    st.store_name,
    c.category_name,
    date_trunc('month', s.business_date) AS month,
    round(sum(s.qty * s.unit_price), 2) AS net_revenue
FROM hive.default.sales_partitioned s
JOIN postgresql.public.stores st
  ON st.store_id = s.store_id
JOIN postgresql.public.products p
  ON p.product_code = s.product_code
 AND s.business_date >= p.valid_from
 AND s.business_date < p.valid_to
JOIN postgresql.public.product_categories c
  ON c.category_id = p.category_id
WHERE upper(s.line_type) NOT IN ('TAX', 'TENDER')
GROUP BY s.store_id, st.store_name, c.category_name, date_trunc('month', s.business_date)
ORDER BY month, s.store_id, c.category_name;

-- Evidence command in Trino CLI:
-- EXPLAIN (TYPE DISTRIBUTED) <the SELECT above>;
-- The plan must show HiveScan for sales_partitioned and PostgreSQL scans for
-- stores, products, and product_categories, followed by distributed joins.
