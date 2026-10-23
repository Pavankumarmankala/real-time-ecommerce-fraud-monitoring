# AWS Production Architecture

This repo runs locally with a simulated stream. The production mapping
uses only services already in Pavan's stack (plus Kinesis as the
streaming front door):

| Layer (local)              | AWS service                                   |
|----------------------------|-----------------------------------------------|
| Simulated transaction feed | Amazon Kinesis Data Streams                   |
| Bronze landing             | Kinesis Data Firehose -> S3 (raw, partitioned by date/hour) |
| Validation + rule scoring  | AWS Lambda (same logic as `src/fraud_rules.py`) |
| Silver storage             | S3 Parquet, registered in AWS Glue Data Catalog |
| Analytics queries          | Amazon Athena (see `sql/analytics_queries.sql`) |
| Gold / serving             | Amazon Redshift star schema (fact_transactions, dim_customer, dim_device, fact_alerts) |
| Monitoring                 | CloudWatch (pipeline errors, alert-volume alarms) + Power BI dashboard |
| Access control             | IAM role-based access, no credentials in code  |

## Star schema (gold)
- **fact_transactions**: transaction_id, customer_key, device_key, timestamp,
  amount, payment_method, status, risk_score, risk_tier, is_flagged
- **fact_alerts**: transaction_id, customer_key, alert_reasons, risk_score, created_at
- **dim_customer**: customer_id, home_country, home_device, avg_amount
- **dim_calendar**: date, hour, day_of_week

## Alert flow
risk_tier = high -> alert written to fact_alerts, CloudWatch alarm on
hourly high-risk count, case appears on Power BI Page 2 (Risk Investigation)
for analyst review. Medium tier is review-only, low tier is approved silently.
