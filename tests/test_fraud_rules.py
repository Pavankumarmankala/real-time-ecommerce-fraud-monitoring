import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from fraud_rules import score_transactions


def _df(rows):
    return pd.DataFrame(rows, columns=["transaction_id", "customer_id", "timestamp",
                                       "amount", "country", "device", "payment_method",
                                       "merchant_category", "status",
                                       "is_fraud_truth", "fraud_pattern"])


def test_clean_transaction_is_low():
    df = _df([("T1", "C1", pd.Timestamp("2026-10-01 10:00"), 50, "US", "mobile",
               "credit_card", "apparel", "approved", 0, "")])
    out = score_transactions(df)
    assert out.iloc[0].risk_tier == "low" and out.iloc[0].is_flagged == 0


def test_velocity_burst_is_flagged():
    rows = [("T%d" % i, "C1", pd.Timestamp("2026-10-01 10:00") + pd.Timedelta(minutes=i),
             50, "US", "mobile", "credit_card", "apparel", "approved", 0, "") for i in range(7)]
    out = score_transactions(_df(rows))
    assert out.iloc[-1].is_flagged == 1 and "velocity" in out.iloc[-1].alert_reasons


def test_geo_and_device_mismatch_scores():
    rows = [("T1", "C1", pd.Timestamp("2026-10-01 10:00"), 50, "US", "mobile",
             "credit_card", "apparel", "approved", 0, ""),
            ("T2", "C1", pd.Timestamp("2026-10-01 11:00"), 60, "DE", "desktop",
             "credit_card", "apparel", "approved", 0, "")]
    out = score_transactions(_df(rows))
    assert out.iloc[1].risk_score == 55 and out.iloc[1].risk_tier == "high"
