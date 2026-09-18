-- Run the same query with only :report_date changed.
-- March uses March's product identity and effective price revision.

WITH report_period AS (
  SELECT DATE '2024-03-01' AS report_date
), products_as_of_period AS (
    SELECT p.*
    FROM postgresql.public.products p
    CROSS JOIN report_period r
    WHERE r.report_date >= p.valid_from
      AND r.report_date < p.valid_to
), prices_as_of_period AS (
    SELECT pr.*
    FROM postgresql.public.price_revisions pr
    CROSS JOIN report_period r
    WHERE r.report_date >= pr.effective_from
      AND r.report_date < pr.effective_to
)
SELECT
    s.product_code,
    p.product_sk,
    p.product_name,
    pr.selling_price AS authoritative_selling_price,
    sum(s.qty) AS units,
    round(sum(s.qty * pr.selling_price), 2) AS revenue_at_period_price
FROM hive.default.sales_partitioned s
JOIN products_as_of_period p
  ON p.product_code = s.product_code
JOIN prices_as_of_period pr
  ON pr.product_sk = p.product_sk
CROSS JOIN report_period r
WHERE s.business_date >= r.report_date
  AND s.business_date < date_add('month', 1, r.report_date)
  AND upper(s.line_type) NOT IN ('TAX', 'TENDER')
GROUP BY s.product_code, p.product_sk, p.product_name, pr.selling_price
ORDER BY revenue_at_period_price DESC;

-- Examples:
-- For the second run, change only the report_period literal to DATE '2024-11-01'.
