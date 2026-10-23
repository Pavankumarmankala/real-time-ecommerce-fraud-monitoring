"""Streaming fraud rule engine.

Scores transactions one at a time, in timestamp order, keeping only
per-customer rolling state (the same shape a Kinesis/Lambda or
Kafka Streams job would keep). No future information is used.

Rules (points, tuned v2 — v1 thresholds gave 25.1% recall and no
high-risk alerts at all, because no single rule could reach the
flagging threshold; each strong signal now flags on its own and
combined signals escalate to high):
  velocity         >=3 prior transactions in 10 minutes      +40
  amount_anomaly   amount > 4x customer's rolling average    +35
  geo_mismatch     country != customer's usual country       +30
  device_mismatch  device != customer's usual device         +25
  failed_retry     >=3 failed attempts in the prior hour     +35

Risk tiers:  score >= 50 -> high (block + alert)
             25-49       -> medium (manual review)
             < 25        -> low (approve)
"""
from collections import defaultdict, deque
import pandas as pd


def score_transactions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("timestamp").reset_index(drop=True)
    history_ts = defaultdict(deque)      # customer -> deque[timestamp]
    history_amt = defaultdict(list)      # customer -> list[amount] (capped)
    failed_ts = defaultdict(deque)       # customer -> deque[timestamp of failures]
    usual_country, usual_device = {}, {}

    scores, reasons_col, tiers = [], [], []
    for row in df.itertuples(index=False):
        cid, ts = row.customer_id, row.timestamp
        score, reasons = 0, []

        # velocity: count this customer's transactions in the last 10 min
        dq = history_ts[cid]
        while dq and (ts - dq[0]).total_seconds() > 600:
            dq.popleft()
        if len(dq) >= 3:
            score += 40; reasons.append("velocity")
        dq.append(ts)

        # amount anomaly vs rolling average (needs >=3 prior transactions)
        amts = history_amt[cid]
        if len(amts) >= 3 and row.amount > 4 * (sum(amts) / len(amts)):
            score += 35; reasons.append("amount_anomaly")
        amts.append(row.amount)
        if len(amts) > 50:
            amts.pop(0)

        # geo / device mismatch vs the customer PROFILE (account
        # registration data in dim_customer). v2 inferred "usual" from the
        # first transaction seen, so an early fraud transaction poisoned
        # the baseline and flagged the customer's later legitimate
        # transactions — 92 of v2's 105 false positives came from this.
        profile_country = getattr(row, "home_country_profile", None)
        profile_device = getattr(row, "home_device_profile", None)
        if profile_country is not None and str(profile_country) != "nan":
            if row.country != profile_country:
                score += 30; reasons.append("geo_mismatch")
            if row.device != profile_device:
                score += 25; reasons.append("device_mismatch")
        elif cid not in usual_country:
            usual_country[cid], usual_device[cid] = row.country, row.device
        else:
            if row.country != usual_country[cid]:
                score += 30; reasons.append("geo_mismatch")
            if row.device != usual_device[cid]:
                score += 25; reasons.append("device_mismatch")

        # repeated failed payments in the prior hour
        fq = failed_ts[cid]
        while fq and (ts - fq[0]).total_seconds() > 3600:
            fq.popleft()
        if len(fq) >= 3:
            score += 35; reasons.append("failed_retry")
        if row.status == "failed":
            fq.append(ts)

        scores.append(score)
        reasons_col.append(",".join(reasons))
        tiers.append("high" if score >= 50 else "medium" if score >= 25 else "low")

    df["risk_score"] = scores
    df["alert_reasons"] = reasons_col
    df["risk_tier"] = tiers
    df["is_flagged"] = (df["risk_tier"] != "low").astype(int)
    return df
