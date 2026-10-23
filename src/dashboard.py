"""Builds chart PNGs and a self-contained HTML dashboard from gold data."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "data" / "gold"; OUT = ROOT / "outputs"; CHARTS = OUT / "charts"


def build():
    CHARTS.mkdir(parents=True, exist_ok=True)
    hourly = pd.read_csv(GOLD / "hourly_summary.csv", parse_dates=["event_hour"])
    country = pd.read_csv(GOLD / "risk_by_country.csv")
    alerts = pd.read_csv(GOLD / "alerts.csv")
    metrics = json.loads((OUT / "metrics.json").read_text())

    plt.figure(figsize=(11, 3.5))
    plt.plot(hourly.event_hour, hourly.transactions, label="Transactions")
    plt.plot(hourly.event_hour, hourly.flagged, label="Flagged")
    plt.legend(); plt.title("Hourly transaction volume vs flagged"); plt.tight_layout()
    plt.savefig(CHARTS / "hourly_volume.png", dpi=150); plt.close()

    reasons = alerts.alert_reasons.fillna("").str.split(",").explode()
    reasons = reasons[reasons != ""].value_counts()
    plt.figure(figsize=(7, 3.5))
    reasons.plot(kind="bar"); plt.title("Alerts by rule"); plt.tight_layout()
    plt.savefig(CHARTS / "alerts_by_rule.png", dpi=150); plt.close()

    country["flag_rate"] = 100 * country.flagged / country.transactions
    plt.figure(figsize=(7, 3.5))
    country.sort_values("flag_rate").plot(x="country", y="flag_rate", kind="barh", legend=False)
    plt.title("Flag rate by country (%)"); plt.tight_layout()
    plt.savefig(CHARTS / "flag_rate_by_country.png", dpi=150); plt.close()

    cards = "".join(f"<div class='card'><h3>{k.replace('_',' ').title()}</h3><p>{v}</p></div>"
                    for k, v in metrics.items())
    html = f"""<!doctype html><html><head><meta charset='utf-8'>
<title>Real-Time E-Commerce Fraud & Transaction Monitoring</title>
<style>body{{font-family:Arial,sans-serif;margin:24px;background:#f7f7f9}}
.card{{display:inline-block;background:#fff;border:1px solid #ddd;border-radius:8px;
padding:12px 16px;margin:6px;min-width:170px}} img{{max-width:100%;background:#fff;
border:1px solid #ddd;border-radius:8px;margin:8px 0}}</style></head><body>
<h1>Real-Time E-Commerce Fraud &amp; Transaction Monitoring</h1>{cards}
<h2>Hourly volume</h2><img src='charts/hourly_volume.png'>
<h2>Alerts by rule</h2><img src='charts/alerts_by_rule.png'>
<h2>Flag rate by country</h2><img src='charts/flag_rate_by_country.png'>
</body></html>"""
    (OUT / "dashboard.html").write_text(html)
    print("dashboard + 3 charts written to", OUT)


if __name__ == "__main__":
    build()
