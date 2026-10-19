import unittest

from fresh_tag.protocol import parse_qr, parse_telemetry


class ProtocolTests(unittest.TestCase):
    def test_parse_telemetry(self):
        packet = parse_telemetry("BOX01,3.75,123\x00")
        self.assertEqual(packet.box_id, "BOX01")
        self.assertAlmostEqual(packet.temperature_c, 3.75)
        self.assertEqual(packet.sequence, 123)

    def test_reject_bad_temperature(self):
        with self.assertRaises(ValueError):
            parse_telemetry("BOX01,999,1")

    def test_parse_qr(self):
        qr = parse_qr("SEAFOOD|FISH|BOX01|F001")
        self.assertEqual(qr.species_code, "FISH")
        self.assertEqual(qr.box_id, "BOX01")


if __name__ == "__main__":
    unittest.main()
