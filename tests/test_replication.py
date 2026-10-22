"""
Checks the rules that keep the two PCs' copies of the databases the same:
which requests count as writes, how a write is made repeatable on the other PC,
and when a copy is skipped. No network is used; sending is replaced by a stub.

    python -m unittest tests.test_replication -v
"""

from __future__ import annotations
import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from integration import replication as rep  # noqa: E402

OP = rep.EXPLORER_PATH


class ReplicationRules(unittest.TestCase):

    def setUp(self):
        self.sent = []
        self._send = rep.send
        rep.send = lambda path, body, role, wait=rep.WAIT_SEC: self.sent.append((path, body, role)) or {"status": "copied"}
        rep._peer.clear()

    def tearDown(self):
        rep.send = self._send
        rep._peer.clear()

    def test_writes_and_reads(self):
        self.assertTrue(rep.is_write(OP, {"operation": "insert"}))
        self.assertTrue(rep.is_write(OP, {"operation": "FEDERATED_INSERT"}))
        self.assertFalse(rep.is_write(OP, {"operation": "VIEW"}))
        self.assertFalse(rep.is_write(OP, {"operation": "FEDERATED_VIEW"}))
        self.assertTrue(rep.is_write("/api/v1/uncertainty/apply", {}))
        self.assertTrue(rep.is_write("/api/v1/uncertainty/undo", {}))
        self.assertFalse(rep.is_write("/api/v1/uncertainty/match", {}))
        self.assertFalse(rep.is_write("/api/v1/uncertainty/train", {}))

    def test_a_write_from_the_dashboard_is_sent_on(self):
        body = {"db_id": "db3", "operation": "INSERT", "table": "products", "data": {"product_uid": "MED-X-1"}}
        res = rep.after_write({rep.HDR_PEER: "http://10.0.0.2:8012"}, OP, body, {"success": True}, role="pc1")
        self.assertEqual(res["replication"]["status"], "copied")
        self.assertEqual(self.sent[0][1]["data"], {"product_uid": "MED-X-1"})
        self.assertEqual(rep.peer_url("pc1"), "http://10.0.0.2:8012")

    def test_reads_failures_and_copies_are_not_sent(self):
        view = {"operation": "VIEW", "data": {}}
        insert = {"operation": "INSERT", "data": {}}
        rep.after_write({}, OP, view, {"success": True}, role="pc1")
        rep.after_write({}, OP, insert, {"success": False, "error": "duplicate"}, role="pc1")
        rep.after_write({rep.HDR_REPLICA: "someone-else"}, OP, insert, {"success": True}, role="pc2")
        self.assertEqual(self.sent, [])

    def test_generated_ids_travel_with_the_copy(self):
        fed = {"db_id": "all", "operation": "FEDERATED_INSERT", "data": {}}
        rep.after_write({}, OP, fed, {"success": True, "item_code": "MED-FED-1234"}, role="pc2")
        self.assertEqual(self.sent[-1][1]["data"]["item_code"], "MED-FED-1234")
        ban = {"db_id": "all", "operation": "FEDERATED_DELETE", "data": {"item_code": "MED-NAKALI-001"}}
        rep.after_write({}, OP, ban, {"success": True, "blacklist_id": "BLK-99"}, role="pc2")
        self.assertEqual(self.sent[-1][1]["data"]["blacklist_id"], "BLK-99")
        rep.after_write({}, "/api/v1/uncertainty/apply", {"mode": "auto"}, {"success": True, "run_id": "DQ-1"}, role="pc1")
        self.assertEqual(self.sent[-1][1], {"mode": "auto", "run_id": "DQ-1"})

    def test_same_files_are_never_copied_twice(self):
        self.assertTrue(rep.same_storage({rep.HDR_REPLICA: rep.STORAGE_ID}))
        self.assertFalse(rep.same_storage({rep.HDR_REPLICA: "another-laptop"}))
        self.assertFalse(rep.same_storage({}))

    def test_each_node_remembers_its_own_peer(self):
        rep.remember_peer({rep.HDR_PEER: "http://127.0.0.1:8012"}, "pc1")
        rep.remember_peer({rep.HDR_PEER: "http://127.0.0.1:8011/"}, "pc2")
        self.assertEqual(rep.peer_url("pc1"), "http://127.0.0.1:8012")
        self.assertEqual(rep.peer_url("pc2"), "http://127.0.0.1:8011")


if __name__ == "__main__":
    unittest.main()
