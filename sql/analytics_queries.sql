-- Real-Time E-Commerce Fraud & Transaction Monitoring
-- Dialect: Amazon Athena / Redshift (standard SQL). Source: silver layer
-- Table: transactions_scored (one row per scored transaction)

-- 1. Hourly transaction volume and flag rate
SELECT date_trunc('hour', timestamp) AS event_hour,
       COUNT(*) AS transactions,
       SUM(is_flagged) AS flagged,
       ROUND(100.0 * SUM(is_flagged) / COUNT(*), 2) AS flag_rate_pct
FROM transactions_scored GROUP BY 1 ORDER BY 1;

-- 2. Daily fraud summary with revenue at risk
SELECT CAST(timestamp AS DATE) AS event_date,
       COUNT(*) AS transactions, SUM(is_flagged) AS flagged,
       SUM(CASE WHEN risk_tier = 'high' THEN amount ELSE 0 END) AS revenue_at_risk
FROM transactions_scored GROUP BY 1 ORDER BY 1;

-- 3. Flag rate by country
SELECT country, COUNT(*) AS transactions, SUM(is_flagged) AS flagged,
       ROUND(100.0 * SUM(is_flagged) / COUNT(*), 2) AS flag_rate_pct
FROM transactions_scored GROUP BY 1 ORDER BY flag_rate_pct DESC;

-- 4. Flag rate by payment method
SELECT payment_method, COUNT(*) AS transactions, SUM(is_flagged) AS flagged,
       ROUND(100.0 * SUM(is_flagged) / COUNT(*), 2) AS flag_rate_pct
FROM transactions_scored GROUP BY 1 ORDER BY flag_rate_pct DESC;

-- 5. Alert reasons breakdown (one alert can carry several rules)
SELECT alert_reasons, COUNT(*) AS alerts
FROM transactions_scored WHERE is_flagged = 1
GROUP BY 1 ORDER BY alerts DESC;

-- 6. Highest-risk customers (top 50 by high-risk transactions)
SELECT customer_id, COUNT(*) AS transactions,
       SUM(CASE WHEN risk_tier = 'high' THEN 1 ELSE 0 END) AS high_risk_txns,
       SUM(amount) AS total_amount, MAX(risk_score) AS max_risk_score
FROM transactions_scored GROUP BY 1
HAVING SUM(CASE WHEN risk_tier = 'high' THEN 1 ELSE 0 END) > 0
ORDER BY high_risk_txns DESC LIMIT 50;

-- 7. Velocity suspects: customers with bursts in a 10-minute window
SELECT customer_id, CAST(timestamp AS DATE) AS event_date,
       COUNT(*) AS txns, SUM(amount) AS burst_amount
FROM transactions_scored
WHERE alert_reasons LIKE '%velocity%'
GROUP BY 1, 2 ORDER BY txns DESC LIMIT 50;

-- 8. Amount anomalies: flagged amount vs customer average
SELECT customer_id, transaction_id, amount, risk_score, alert_reasons
FROM transactions_scored
WHERE alert_reasons LIKE '%amount_anomaly%'
ORDER BY amount DESC LIMIT 50;

-- 9. Failed-payment retry chains
SELECT customer_id, COUNT(*) AS failed_attempts
FROM transactions_scored
WHERE status = 'failed'
GROUP BY 1 HAVING COUNT(*) >= 3 ORDER BY failed_attempts DESC;

-- 10. Risk tier distribution
SELECT risk_tier, COUNT(*) AS transactions,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct,
       SUM(amount) AS amount_at_tier
FROM transactions_scored GROUP BY 1 ORDER BY 2 DESC;

-- 11. Merchant category risk
SELECT merchant_category, COUNT(*) AS transactions, SUM(is_flagged) AS flagged,
       ROUND(100.0 * SUM(is_flagged) / COUNT(*), 2) AS flag_rate_pct
FROM transactions_scored GROUP BY 1 ORDER BY flag_rate_pct DESC;

-- 12. Rule effectiveness vs labelled ground truth (evaluation only)
SELECT SUM(CASE WHEN is_flagged = 1 AND is_fraud_truth = 1 THEN 1 ELSE 0 END) AS true_positives,
       SUM(CASE WHEN is_flagged = 1 AND is_fraud_truth = 0 THEN 1 ELSE 0 END) AS false_positives,
       SUM(CASE WHEN is_flagged = 0 AND is_fraud_truth = 1 THEN 1 ELSE 0 END) AS false_negatives
FROM transactions_scored;
