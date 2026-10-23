"""Medallion pipeline: bronze (raw) -> silver (scored) -> gold (aggregates).

Locally this reads/writes Parquet + CSV. In AWS the same layers map to:
  bronze = S3 raw (Kinesis Firehose landing), silver = S3 Parquet scored
  by Lambda, gold = Redshift tables / Athena views feeding Power BI.
"""
import json, time
from pathlib import Path
import pandas as pd
from generate_transactions import generate
from fraud_rules import score_transactions

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"; OUT = ROOT / "outputs"


def run(n_transactions: int = 100_000) -> dict:
    t_start = time.time()
    for layer in ["bronze", "silver", "gold"]:
        (DATA / layer).mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)

    # BRONZE - raw simulated stream landing, partitioned by date
    raw = generate(n_transactions=n_transactions)
    raw["event_date"] = raw["timestamp"].dt.date.astype(str)
    raw.to_parquet(DATA / "bronze" / "transactions_raw.parquet", index=False)
    raw.to_csv(DATA / "bronze" / "transactions_raw.csv", index=False)

    # SILVER - validate, dedupe, score
    silver = raw.drop_duplicates(subset=["transaction_id"]).copy()
    silver = silver[silver["amount"] > 0]
    silver = score_transactions(silver.drop(columns=["event_date"]))
    silver["event_date"] = silver["timestamp"].dt.date.astype(str)
    silver.to_parquet(DATA / "silver" / "transactions_scored.parquet", index=False)
    silver.to_csv(DATA / "silver" / "transactions_scored.csv", index=False)

    # GOLD - aggregates for BI
    silver["event_hour"] = silver["timestamp"].dt.floor("h")
    gold = {
        "hourly_summary": silver.groupby("event_hour").agg(
            transactions=("transaction_id", "count"), flagged=("is_flagged", "sum"),
            fraud_truth=("is_fraud_truth", "sum"), revenue=("amount", "sum")).reset_index(),
        "daily_summary": silver.groupby("event_date").agg(
            transactions=("transaction_id", "count"), flagged=("is_flagged", "sum"),
            fraud_truth=("is_fraud_truth", "sum"), revenue=("amount", "sum")).reset_index(),
        "risk_by_country": silver.groupby("country").agg(
            transactions=("transaction_id", "count"), flagged=("is_flagged", "sum"),
            fraud_truth=("is_fraud_truth", "sum")).reset_index(),
        "risk_by_payment_method": silver.groupby("payment_method").agg(
            transactions=("transaction_id", "count"), flagged=("is_flagged", "sum"),
            fraud_truth=("is_fraud_truth", "sum")).reset_index(),
        "alerts": silver[silver["is_flagged"] == 1][
            ["transaction_id", "customer_id", "timestamp", "amount", "country",
             "device", "payment_method", "risk_score", "risk_tier",
             "alert_reasons", "is_fraud_truth"]],
    }
    for name, frame in gold.items():
        frame.to_csv(DATA / "gold" / f"{name}.csv", index=False)

    # Evaluation vs ground truth (flagged = predicted fraud)
    tp = int(((silver.is_flagged == 1) & (silver.is_fraud_truth == 1)).sum())
    fp = int(((silver.is_flagged == 1) & (silver.is_fraud_truth == 0)).sum())
    fn = int(((silver.is_flagged == 0) & (silver.is_fraud_truth == 1)).sum())
    # Incident-level detection: a fraud incident (one customer's injected
    # pattern) counts as detected if ANY of its transactions is flagged.
    # This matters because e.g. a velocity burst's first transactions are
    # indistinguishable from legitimate ones by design.
    fraud_only = silver[silver.is_fraud_truth == 1]
    incidents = fraud_only.groupby(["customer_id", "fraud_pattern"])["is_flagged"].max()
    elapsed = round(time.time() - t_start, 2)
    metrics = {
        "fraud_incidents_truth": int(len(incidents)),
        "fraud_incidents_detected": int(incidents.sum()),
        "incident_recall_pct": round(100 * float(incidents.mean()), 2) if len(incidents) else 0,
        "transactions_processed": int(len(silver)),
        "customers": int(silver.customer_id.nunique()),
        "days_covered": int(silver.event_date.nunique()),
        "total_revenue_monitored": round(float(silver.amount.sum()), 2),
        "fraud_transactions_truth": int(silver.is_fraud_truth.sum()),
        "flagged_transactions": int(silver.is_flagged.sum()),
        "flagged_rate_pct": round(100 * silver.is_flagged.mean(), 2),
        "high_risk_transactions": int((silver.risk_tier == "high").sum()),
        "medium_risk_transactions": int((silver.risk_tier == "medium").sum()),
        "precision_pct": round(100 * tp / (tp + fp), 2) if tp + fp else 0,
        "recall_pct": round(100 * tp / (tp + fn), 2) if tp + fn else 0,
        "true_positives": tp, "false_positives": fp, "false_negatives": fn,
        "pipeline_runtime_seconds": elapsed,
        "throughput_txn_per_sec": round(len(silver) / elapsed, 1),
    }
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    run()
