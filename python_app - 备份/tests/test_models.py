import unittest
from datetime import datetime, timedelta, timezone

from fresh_tag.models import FreshnessStore, aging_factor
from fresh_tag.protocol import parse_qr, parse_telemetry
from fresh_tag.simulator import demo_reading, demo_temperature


class ModelTests(unittest.TestCase):
    def test_demo_temperature_holds_each_stage_for_ten_seconds(self):
        self.assertEqual(demo_temperature(0), 4.0)
        self.assertEqual(demo_temperature(9.9), 4.0)
        self.assertEqual(demo_temperature(10), 14.0)
        self.assertEqual(demo_temperature(19.9), 14.0)
        self.assertEqual(demo_temperature(20), 24.0)
        self.assertEqual(demo_temperature(29.9), 24.0)
        self.assertEqual(demo_temperature(30), 34.0)
        self.assertEqual(demo_temperature(120), 34.0)
        self.assertEqual(demo_reading(0, 1.5), 5.0)
        self.assertEqual(demo_reading(12, -3), 13.0)
        self.assertEqual(demo_reading(25, 0.4), 24.4)

    def test_q10(self):
        self.assertAlmostEqual(aging_factor(4), 1.0)
        self.assertAlmostEqual(aging_factor(14), 2.0)

    def test_one_hour_at_14c_counts_as_two(self):
        store = FreshnessStore()
        item = store.register(parse_qr("SEAFOOD|FISH|BOX01|F001"))
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        store.ingest(parse_telemetry("BOX01,14,1"), start)
        # 无线间隔上限为 10 秒，用 time_scale=360 模拟一小时真实时间。
        store.ingest(parse_telemetry("BOX01,14,2"), start + timedelta(seconds=10), time_scale=360)
        self.assertAlmostEqual(item.equivalent_age_hours, 2.0, places=5)
        self.assertAlmostEqual(item.overtemp_degree_minutes, 600.0, places=5)

    def test_demo_restarts_sequence_after_live_packets(self):
        store = FreshnessStore()
        item = store.register(parse_qr("SEAFOOD|SHRIMP|BOX01|S001"))
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        store.ingest(parse_telemetry("BOX01,28,80"), start)
        store.begin_demo("BOX01", start)
        store.ingest(parse_telemetry("BOX01,3.5,0"), start, time_scale=1200)
        store.ingest(parse_telemetry("BOX01,3.5,1"), start + timedelta(seconds=1), time_scale=1200)
        self.assertAlmostEqual(store.boxes["BOX01"].temperature_c, 3.5)
        self.assertGreater(item.equivalent_age_hours, 0.3)
        self.assertLess(item.equivalent_age_hours, 0.4)

    def test_duplicate_packet_does_not_age_twice(self):
        store = FreshnessStore()
        item = store.register(parse_qr("SEAFOOD|FISH|BOX01|F001"))
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        store.ingest(parse_telemetry("BOX01,4,1"), start)
        store.ingest(parse_telemetry("BOX01,4,1"), start + timedelta(seconds=2))
        self.assertEqual(item.equivalent_age_hours, 0)


if __name__ == "__main__":
    unittest.main()
