# Real-Time E-Commerce Fraud & Transaction Monitoring

End-to-end data engineering project: a simulated real-time e-commerce
transaction stream is scored transaction-by-transaction by a fraud rule
engine, landed in a medallion pipeline (bronze / silver / gold), and
surfaced for monitoring and investigation in Power BI.

## Verified results (actual run, seed = 42)

| Metric | Value |
|---|---|
| Transactions processed | 100,670 |
| Customers / days covered | 2,000 / 7 |
| Revenue monitored | $4,483,271.74 |
| Labelled fraud transactions (injected) | 670 across 220 incidents |
| Flagged transactions | 421 (0.42%) — 33 high-risk, 388 medium-risk |
| Precision | 96.44% (406 TP / 15 FP) |
| Recall (per transaction) | 60.60% |
| Recall (per incident) | 99.55% (219 of 220 incidents detected) |
| Pipeline runtime | 3.72s (~27,000 txn/sec scored locally) |

Full numbers: `outputs/metrics.json`. Charts + HTML dashboard: `outputs/`.

## Fraud rules
Scored streaming-style, in timestamp order, per-customer rolling state only:
velocity (>=3 prior transactions in 10 min, +40), amount anomaly
(>4x rolling average, +35), geo mismatch vs customer profile (+30),
device mismatch vs customer profile (+25), failed-payment retry
(>=3 failures in prior hour, +35). Score >= 50 = high (block/alert),
25-49 = medium (review), <25 = low.

### Rule tuning log (this is the interesting part)
- **v1:** no single rule could reach the flag threshold — recall 25.1%,
  zero high-risk alerts. Rebalanced points and thresholds.
- **v2:** recall rose, but 92 of 105 false positives came from inferring a
  customer's "usual" country/device from their first transaction — an
  early fraud transaction poisoned the baseline and flagged later
  legitimate transactions.
- **v3 (current):** geo/device checks compare against the customer
  profile (account registration data in dim_customer, as in production).
  False positives fell 105 -> 15, precision reached 96.44%.

## Run it
```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run_pipeline.py     # generates, scores, aggregates, dashboards
.venv/bin/python -m pytest tests/    # 3 rule-engine tests
```

## Layout
- `src/generate_transactions.py` — synthetic stream + 5 injected fraud patterns, labelled for evaluation
- `src/fraud_rules.py` — streaming rule engine
- `src/pipeline.py` — bronze (raw Parquet) -> silver (validated, deduped, scored) -> gold aggregates
- `src/dashboard.py` — charts + HTML dashboard
- `sql/analytics_queries.sql` — 12 Athena/Redshift queries (hourly flag rate, revenue at risk, rule effectiveness, top-risk customers…)
- `powerbi/` — 3-page dashboard spec + DAX measures
- `docs/aws_architecture.md` — production mapping: Kinesis -> Firehose/S3 -> Lambda scoring -> Glue/Athena -> Redshift star schema -> Power BI, CloudWatch + IAM

## Resume bullets (verified — safe to use)
**Real-Time E-Commerce Fraud & Transaction Monitoring**
- Built a real-time fraud monitoring pipeline in Python (pandas, NumPy) processing 100,670 e-commerce transactions ($4.48M) across 2,000 customers, scoring each transaction in streaming order with 5 fraud rules (velocity, amount anomaly, geo/device mismatch, failed-payment retry) and tiering alerts into high/medium/low risk.
- Tuned the rule engine through three iterations, raising precision to 96.4% and detecting 219 of 220 fraud incidents (99.5% incident recall) by comparing geo/device signals against customer profile data instead of stream-inferred baselines, cutting false positives from 105 to 15.
- Designed a Medallion pipeline (raw Parquet -> scored silver -> gold aggregates) with 12 Athena/Redshift SQL queries and a Power BI monitoring spec (DAX measures for flag rate and revenue at risk), scoring ~27,000 transactions/second locally.
