import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cold_chain_watch as project


class ColdChainWatchTests(unittest.TestCase):
    def test_generated_demo_is_reproducible_and_labeled(self):
        first = project.generate_rows()
        self.assertEqual(first, project.generate_rows())
        self.assertEqual(len(first), 14 * 24 * 4)
        self.assertEqual(sum(row["event_label"] == "temperature_excursion" for row in first), 16)
        self.assertEqual(sum(row["event_label"] == "missing_telemetry" for row in first), 4)
        self.assertEqual(sum(row["event_label"] == "power_interruption" for row in first), 16)

    def test_rules_detect_all_injected_test_events(self):
        rows = project.generate_rows()
        training = [row for row in rows if row["split"] == "train"]
        testing = [row for row in rows if row["split"] == "test"]
        alerts = {row["timestamp"]: set(codes) for row, codes in project.detect_alerts(rows, training)}
        for row in testing:
            if row["event_label"] == "temperature_excursion":
                self.assertIn("temperature_outside_demo_band", alerts[row["timestamp"]])
            elif row["event_label"] == "missing_telemetry":
                self.assertIn("missing_reading", alerts[row["timestamp"]])
            elif row["event_label"] == "power_interruption":
                self.assertIn("energy_usage_outlier", alerts[row["timestamp"]])

    def test_run_reports_perfect_fixed_scenario_recall_without_claiming_real_data(self):
        report = project.run()
        self.assertEqual(report["test_point_metrics"]["recall"], 1.0)
        self.assertIn("synthetic", report["data_type"])
        self.assertEqual(report["test_point_metrics"]["false_positive"], 0)


if __name__ == "__main__":
    unittest.main()
