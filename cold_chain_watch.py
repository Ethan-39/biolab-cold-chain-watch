"""Rule-based monitoring demo for synthetic laboratory cold-storage telemetry."""

from __future__ import annotations

import csv
import json
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "telemetry.csv"
REPORT_PATH = ROOT / "results" / "report.json"
ALERTS_PATH = ROOT / "results" / "alerts.csv"
DASHBOARD_PATH = ROOT / "dashboard.html"
SEED = 39
DEMO_LOW_C = 2.0
DEMO_HIGH_C = 8.0
DAYS = 14
INTERVAL_MINUTES = 15


def generate_rows() -> list[dict[str, str]]:
    rng = random.Random(SEED)
    rows: list[dict[str, str]] = []
    start = date(2026, 10, 1)
    samples_per_day = 24 * 60 // INTERVAL_MINUTES
    for day_index in range(DAYS):
        day = start + timedelta(days=day_index)
        for slot in range(samples_per_day):
            hour = slot / 4
            timestamp = datetime.combine(day, datetime.min.time()) + timedelta(minutes=slot * INTERVAL_MINUTES)
            temp = 4.2 + 0.20 * math.sin(2 * math.pi * hour / 24) + rng.uniform(-0.13, 0.13)
            energy = 0.069 + rng.uniform(-0.004, 0.004)
            event = "normal"
            if day_index == 9 and 9 <= hour < 13:
                temp = 9.4 + rng.uniform(-0.15, 0.15)
                event = "temperature_excursion"
            if day_index == 11 and 1 <= hour < 2:
                event = "missing_telemetry"
            if day_index == 12 and 14 <= hour < 18:
                energy = 0.0
                elapsed_hours = hour - 14
                temp = 4.8 + elapsed_hours * 0.85 + rng.uniform(-0.08, 0.08)
                event = "power_interruption"
            split = "train" if day_index < 7 else "test"
            rows.append({
                "timestamp": timestamp.isoformat(timespec="minutes"),
                "device_id": "cooler-01",
                "split": split,
                "temperature_c": "" if event == "missing_telemetry" else f"{temp:.2f}",
                "energy_kwh_15min": "" if event == "missing_telemetry" else f"{energy:.4f}",
                "event_label": event,
            })
    return rows


def robust_power_limits(training_rows: list[dict[str, str]]) -> tuple[float, float, float]:
    samples = [float(row["energy_kwh_15min"]) for row in training_rows if row["energy_kwh_15min"]]
    center = median(samples)
    mad = median([abs(value - center) for value in samples])
    scale = max(1.4826 * mad, 0.002)
    return center, center - 4.5 * scale, center + 4.5 * scale


def detect_alerts(rows: list[dict[str, str]], training_rows: list[dict[str, str]]) -> list[tuple[dict[str, str], list[str]]]:
    _, power_low, power_high = robust_power_limits(training_rows)
    alerts: list[tuple[dict[str, str], list[str]]] = []
    for row in rows:
        codes: list[str] = []
        if not row["temperature_c"] or not row["energy_kwh_15min"]:
            codes.append("missing_reading")
        if row["temperature_c"]:
            temp = float(row["temperature_c"])
            if temp < DEMO_LOW_C or temp > DEMO_HIGH_C:
                codes.append("temperature_outside_demo_band")
        if row["energy_kwh_15min"]:
            energy = float(row["energy_kwh_15min"])
            if energy < power_low or energy > power_high:
                codes.append("energy_usage_outlier")
        if codes:
            alerts.append((row, codes))
    return alerts


def classification_metrics(actual: list[bool], predicted: list[bool]) -> dict[str, float | int]:
    tp = sum(a and p for a, p in zip(actual, predicted))
    fp = sum((not a) and p for a, p in zip(actual, predicted))
    fn = sum(a and (not p) for a, p in zip(actual, predicted))
    tn = sum((not a) and (not p) for a, p in zip(actual, predicted))
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": round(tp / (tp + fp), 3) if tp + fp else 0.0,
        "recall": round(tp / (tp + fn), 3) if tp + fn else 0.0,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def render_dashboard(report: dict, chart_data: dict, alert_rows: list[dict]) -> None:
    template = (ROOT / "dashboard_template.html").read_text(encoding="utf-8")
    html = template.replace("__REPORT__", json.dumps(report, ensure_ascii=True))
    html = html.replace("__CHART_DATA__", json.dumps(chart_data, ensure_ascii=True))
    html = html.replace("__ALERTS__", json.dumps(alert_rows, ensure_ascii=True))
    DASHBOARD_PATH.write_text(html, encoding="utf-8")


def run() -> dict:
    rows = generate_rows()
    write_csv(DATA_PATH, rows)
    training = [row for row in rows if row["split"] == "train"]
    testing = [row for row in rows if row["split"] == "test"]
    alerts = detect_alerts(rows, training)
    alert_lookup = {row["timestamp"]: codes for row, codes in alerts}
    truth = [row["event_label"] != "normal" for row in testing]
    predicted = [row["timestamp"] in alert_lookup for row in testing]
    metrics = classification_metrics(truth, predicted)
    report = {
        "project": "BioLab Cold-Chain Watch",
        "data_type": "synthetic teaching telemetry; not connected to equipment",
        "seed": SEED,
        "device_count": 1,
        "interval_minutes": INTERVAL_MINUTES,
        "train_days": 7,
        "test_days": 7,
        "demo_temperature_band_c": [DEMO_LOW_C, DEMO_HIGH_C],
        "rule_count": 3,
        "test_point_metrics": metrics,
        "alert_counts": {
            code: sum(code in codes and row["split"] == "test" for row, codes in alerts)
            for code in ("missing_reading", "temperature_outside_demo_band", "energy_usage_outlier")
        },
        "limitations": [
            "Temperature band is a demo placeholder, not a laboratory or equipment safety specification.",
            "All telemetry and labelled events are generated by this project.",
            "Alerts only request human inspection; the software cannot control devices or assess sample viability.",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    alert_export = [
        {"timestamp": row["timestamp"], "device_id": row["device_id"], "split": row["split"], "alert_codes": ";".join(codes), "operator_prompt": "Manually verify sensor and equipment status."}
        for row, codes in alerts
    ]
    write_csv(ALERTS_PATH, alert_export)
    daily: dict[str, dict[str, float]] = {}
    for row in testing:
        day = row["timestamp"][:10]
        bucket = daily.setdefault(day, {"energy": 0.0, "count": 0.0})
        if row["energy_kwh_15min"]:
            bucket["energy"] += float(row["energy_kwh_15min"])
            bucket["count"] += 1
    chart_data = {
        "timestamps": [row["timestamp"] for row in testing],
        "temperature": [float(row["temperature_c"]) if row["temperature_c"] else None for row in testing],
        "events": [row["event_label"] for row in testing],
        "daily": [{"day": day, "energy": round(values["energy"], 3)} for day, values in daily.items()],
    }
    render_dashboard(report, chart_data, [item for item in alert_export if item["split"] == "test"])
    return report


if __name__ == "__main__":
    result = run()
    metrics = result["test_point_metrics"]
    print(f"Test point recall: {metrics['recall']:.3f}; precision: {metrics['precision']:.3f}")
    print(f"Dashboard: {DASHBOARD_PATH}")
