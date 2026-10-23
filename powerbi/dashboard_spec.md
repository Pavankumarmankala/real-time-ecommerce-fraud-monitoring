# Power BI Dashboard — Real-Time Fraud & Transaction Monitoring

Data source: gold layer CSVs (or Athena/Redshift views of the silver table)
in `data/gold/` — hourly_summary, daily_summary, risk_by_country,
risk_by_payment_method, alerts. Model: alerts fact linked to a calendar
table on timestamp; country / payment_method as slicer dimensions.

## Page 1 — Executive Monitoring
- KPI cards: Total Transactions, Flagged Transactions, Flag Rate %,
  High-Risk Transactions, Revenue at Risk (sum of high-risk amounts)
- Line chart: transactions and flagged transactions by hour
- Bar chart: alerts by rule (alert_reasons)
- Slicers: date, country, payment method, risk tier

## Page 2 — Risk Investigation
- Table: alerts (transaction, customer, amount, risk score, reasons),
  conditional formatting on risk_score
- Barh chart: flag rate % by country
- Bar chart: flag rate % by payment method
- Top-50 highest-risk customers table

## Page 3 — Rule Performance
- KPI cards: Precision %, Recall % (vs labelled ground truth, evaluation only)
- Stacked bar: risk tier distribution by day
- Table: false positives for rule tuning review
