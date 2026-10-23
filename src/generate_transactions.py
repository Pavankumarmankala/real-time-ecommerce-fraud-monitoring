"""Synthetic e-commerce transaction generator.

Generates a realistic transaction stream with labelled fraud patterns
injected on top of legitimate behaviour, so the fraud rules can be
evaluated (precision / recall) against ground truth.

Fraud patterns injected:
  1. Velocity bursts      - many transactions from one customer in minutes
  2. Amount anomalies     - transactions far above the customer's normal spend
  3. Geo mismatches       - transaction country != customer's home country
  4. Device mismatches    - transaction on a device the customer never used
  5. Failed-payment retry - repeated failed attempts before a large charge
"""
import numpy as np
import pandas as pd

COUNTRIES = ["US", "CA", "GB", "DE", "IN", "AU"]
PAYMENT_METHODS = ["credit_card", "debit_card", "paypal", "apple_pay", "gift_card"]
MERCHANT_CATEGORIES = ["electronics", "apparel", "groceries", "travel", "digital_goods", "home"]


def generate(n_transactions: int = 100_000, n_customers: int = 2_000,
             days: int = 7, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-10-01 00:00:00")

    customers = pd.DataFrame({
        "customer_id": [f"CUST-{i:05d}" for i in range(n_customers)],
        "home_country": rng.choice(COUNTRIES, n_customers, p=[.62, .08, .08, .06, .10, .06]),
        "home_device": rng.choice(["mobile", "desktop", "tablet"], n_customers, p=[.55, .35, .10]),
        "avg_amount": np.round(rng.lognormal(mean=3.6, sigma=0.6, size=n_customers), 2),
    })
    cust = customers.set_index("customer_id")

    # ---- legitimate transactions -------------------------------------
    cust_ids = rng.choice(customers["customer_id"], n_transactions)
    base = cust.loc[cust_ids].reset_index()
    offsets_sec = np.sort(rng.integers(0, days * 86400, n_transactions))
    legit = pd.DataFrame({
        "transaction_id": [f"TXN-{i:07d}" for i in range(n_transactions)],
        "customer_id": cust_ids,
        "timestamp": start + pd.to_timedelta(offsets_sec, unit="s"),
        "amount": np.round(np.maximum(5, rng.normal(base["avg_amount"], base["avg_amount"] * 0.35)), 2),
        "country": base["home_country"].values,
        "device": base["home_device"].values,
        "payment_method": rng.choice(PAYMENT_METHODS, n_transactions, p=[.45, .25, .15, .10, .05]),
        "merchant_category": rng.choice(MERCHANT_CATEGORIES, n_transactions),
        "status": rng.choice(["approved", "failed"], n_transactions, p=[.97, .03]),
        "is_fraud_truth": 0,
        "fraud_pattern": "",
        # customer profile (account registration data, known in production
        # from the customer dimension — not inferred from the stream)
        "home_country_profile": base["home_country"].values,
        "home_device_profile": base["home_device"].values,
    })

    fraud_rows = []
    txn_counter = n_transactions

    def add_row(customer_id, ts, amount, country, device, status, pattern, payment="credit_card"):
        nonlocal txn_counter
        fraud_rows.append({
            "transaction_id": f"TXN-{txn_counter:07d}", "customer_id": customer_id,
            "timestamp": ts, "amount": round(float(amount), 2), "country": country,
            "device": device, "payment_method": payment,
            "merchant_category": "electronics", "status": status,
            "is_fraud_truth": 1, "fraud_pattern": pattern,
            "home_country_profile": cust.loc[customer_id, "home_country"],
            "home_device_profile": cust.loc[customer_id, "home_device"],
        })
        txn_counter += 1

    fraud_customers = rng.choice(customers["customer_id"], 220, replace=False)
    for cid in fraud_customers:
        home = cust.loc[cid]
        t0 = start + pd.Timedelta(seconds=int(rng.integers(0, days * 86400 - 7200)))
        pattern = rng.choice(["velocity", "amount_anomaly", "geo_mismatch",
                              "device_mismatch", "failed_retry"])
        if pattern == "velocity":
            for k in range(int(rng.integers(6, 10))):
                add_row(cid, t0 + pd.Timedelta(minutes=int(k * 1.5)),
                        home["avg_amount"] * rng.uniform(0.8, 1.4),
                        home["home_country"], home["home_device"], "approved", pattern)
        elif pattern == "amount_anomaly":
            add_row(cid, t0, home["avg_amount"] * rng.uniform(6, 12),
                    home["home_country"], home["home_device"], "approved", pattern)
        elif pattern == "geo_mismatch":
            foreign = rng.choice([c for c in COUNTRIES if c != home["home_country"]])
            add_row(cid, t0, home["avg_amount"] * rng.uniform(2, 5),
                    foreign, home["home_device"], "approved", pattern)
        elif pattern == "device_mismatch":
            other_device = "desktop" if home["home_device"] != "desktop" else "mobile"
            add_row(cid, t0, home["avg_amount"] * rng.uniform(2, 4),
                    home["home_country"], other_device, "approved", pattern)
        else:  # failed_retry
            for k in range(3):
                add_row(cid, t0 + pd.Timedelta(minutes=k * 7),
                        home["avg_amount"] * 3, home["home_country"],
                        home["home_device"], "failed", pattern)
            add_row(cid, t0 + pd.Timedelta(minutes=25),
                    home["avg_amount"] * rng.uniform(4, 7),
                    home["home_country"], home["home_device"], "approved", pattern)

    fraud = pd.DataFrame(fraud_rows)
    df = pd.concat([legit, fraud], ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    return df


if __name__ == "__main__":
    out = generate()
    print(out.shape)
    print(out["is_fraud_truth"].value_counts().to_dict())
