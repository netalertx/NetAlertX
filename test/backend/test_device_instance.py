"""
Unit tests for server/models/device_instance.py's DeviceInstance model methods.

Covers:
  - DeviceInstance.getAllByName()
  - DeviceInstance.getByMac()
  - DeviceInstance.getAllByMacs()
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db_test_helpers import make_db, make_device_dict, insert_device_from_dict


class TestGetAllByName(unittest.TestCase):
    """devName has no column-level collation (unlike devMac), so getAllByName()
    must apply COLLATE NOCASE itself, and must return every match rather than
    just one - callers (e.g. the dockerdisc plugin's resolve_host_mac()) rely
    on the full set to detect an ambiguous (multiple-match) name."""

    def setUp(self):
        self.conn = make_db()
        devices = [
            make_device_dict("aa:bb:cc:dd:ee:01", devName="docker-host-1"),
            make_device_dict("aa:bb:cc:dd:ee:02", devName="Docker-Host-1"),
            make_device_dict("aa:bb:cc:dd:ee:03", devName="other-host"),
        ]
        for d in devices:
            insert_device_from_dict(self.conn, d)
        self.conn.commit()

    def _instance(self):
        from models.device_instance import DeviceInstance
        inst = DeviceInstance()

        def _fetchall(q, p=()):
            rows = self.conn.execute(q, p).fetchall()
            return [dict(r) for r in rows]
        inst._fetchall = _fetchall
        return inst

    def test_case_insensitive_match_returns_all_ambiguous_rows(self):
        inst = self._instance()
        results = inst.getAllByName("docker-host-1")
        macs = {r["devMac"] for r in results}
        self.assertEqual(macs, {"aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:02"})

    def test_case_insensitive_match_different_case_query(self):
        inst = self._instance()
        results = inst.getAllByName("OTHER-HOST")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["devMac"], "aa:bb:cc:dd:ee:03")

    def test_no_match_returns_empty_list(self):
        inst = self._instance()
        results = inst.getAllByName("does-not-exist")
        self.assertEqual(results, [])


class TestGetByMac(unittest.TestCase):
    """devMac is declared COLLATE NOCASE at the column level (unlike
    devName), so getByMac() relies on the schema rather than applying its
    own COLLATE clause - this exercises that guarantee against a real
    SQLite connection, not a mock."""

    def setUp(self):
        self.conn = make_db()
        insert_device_from_dict(self.conn, make_device_dict("aa:bb:cc:dd:ee:ff"))
        self.conn.commit()

    def _instance(self):
        from models.device_instance import DeviceInstance
        inst = DeviceInstance()

        def _fetchone(q, p=()):
            row = self.conn.execute(q, p).fetchone()
            return dict(row) if row else None
        inst._fetchone = _fetchone
        return inst

    def test_case_insensitive_match(self):
        inst = self._instance()
        result = inst.getByMac("AA:BB:CC:DD:EE:FF")
        self.assertIsNotNone(result)
        self.assertEqual(result["devMac"], "aa:bb:cc:dd:ee:ff")

    def test_no_match_returns_none(self):
        inst = self._instance()
        self.assertIsNone(inst.getByMac("00:00:00:00:00:00"))


class TestGetAllByMacs(unittest.TestCase):
    """One query for a batch of MACs - added for callers (e.g. WIFICANARY's
    known-device-turned-rogue check) that would otherwise call getByMac()
    once per item in a loop, one DB round-trip each."""

    def setUp(self):
        self.conn = make_db()
        insert_device_from_dict(self.conn, make_device_dict("aa:bb:cc:dd:ee:01", devName="host-1"))
        insert_device_from_dict(self.conn, make_device_dict("aa:bb:cc:dd:ee:02", devName="host-2"))
        self.conn.commit()

    def _instance(self):
        from models.device_instance import DeviceInstance
        inst = DeviceInstance()

        def _fetchall(q, p=()):
            rows = self.conn.execute(q, p).fetchall()
            return [dict(r) for r in rows]
        inst._fetchall = _fetchall
        return inst

    def test_returns_dict_keyed_by_lowercased_mac(self):
        inst = self._instance()
        result = inst.getAllByMacs(["AA:BB:CC:DD:EE:01", "aa:bb:cc:dd:ee:02"])
        self.assertEqual(set(result.keys()), {"aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:02"})
        self.assertEqual(result["aa:bb:cc:dd:ee:01"]["devName"], "host-1")

    def test_unmatched_mac_simply_absent_from_result(self):
        inst = self._instance()
        result = inst.getAllByMacs(["aa:bb:cc:dd:ee:01", "00:00:00:00:00:00"])
        self.assertEqual(set(result.keys()), {"aa:bb:cc:dd:ee:01"})

    def test_duplicate_macs_collapsed_to_one_query_param(self):
        inst = self._instance()
        result = inst.getAllByMacs(["aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:01"])
        self.assertEqual(set(result.keys()), {"aa:bb:cc:dd:ee:01"})

    def test_empty_input_returns_empty_dict_without_querying(self):
        inst = self._instance()
        inst._fetchall = lambda q, p=(): (_ for _ in ()).throw(AssertionError("should not query"))
        self.assertEqual(inst.getAllByMacs([]), {})

    def test_blank_entries_are_filtered_out(self):
        inst = self._instance()
        result = inst.getAllByMacs(["aa:bb:cc:dd:ee:01", "", None])
        self.assertEqual(set(result.keys()), {"aa:bb:cc:dd:ee:01"})


if __name__ == "__main__":
    unittest.main()
