-- Dashboard semantic layer. Dimensions stay in PostgreSQL; sales stays in the lake.
-- The temporal product join prevents reissued product codes from duplicating lines.

CREATE OR REPLACE VIEW hive.default.sales_enriched AS
SELECT
    s.store_id,
    st.store_name,
    s.business_date,
    day_of_week(s.business_date) AS day_of_week,
    s.bill_no,
    s.line_no,
    p.product_sk,
    p.product_code,
    p.product_name,
    c.category_id,
    c.category_name,
    s.qty,
    s.unit_price,
    s.line_type,
    s.qty * s.unit_price AS signed_line_revenue
FROM hive.default.sales_partitioned s
JOIN postgresql.public.stores st
  ON st.store_id = s.store_id
JOIN postgresql.public.products p
  ON p.product_code = s.product_code
 AND s.business_date >= p.valid_from
 AND s.business_date < p.valid_to
JOIN postgresql.public.product_categories c
  ON c.category_id = p.category_id;

-- Use this view for every dashboard revenue measure.
SELECT
    store_id,
    category_name,
    day_of_week,
    date_trunc('month', business_date) AS month,
    round(sum(signed_line_revenue), 2) AS net_revenue
FROM hive.default.sales_enriched
WHERE upper(line_type) NOT IN ('TAX', 'TENDER')
GROUP BY store_id, category_name, day_of_week, date_trunc('month', business_date);
