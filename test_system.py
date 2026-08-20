"""
Unit and integration test script for Instagram Tracker SQLite engine & analytics.
"""

import os
import sys
import unittest
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.database import (
    init_db,
    add_target,
    get_targets,
    remove_target,
    save_snapshot,
    get_latest_snapshot,
    get_snapshot_followers,
    get_snapshot_following,
    get_events,
    get_history_stats
)
from backend.analytics import (
    get_account_summary,
    get_cross_account_analysis,
    to_dataframe,
    events_to_dataframe
)

TEST_DB = os.path.join(BASE_DIR, "data", "test_tracker.db")


class TestInstagramTracker(unittest.TestCase):
    def setUp(self):
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except Exception:
                pass
        init_db(TEST_DB)

    def tearDown(self):
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except Exception:
                pass

    def test_database_and_diffs(self):
        # 1. Add targets
        add_target("alice_main", full_name="Alice Main", db_path=TEST_DB)
        add_target("alice_priv", full_name="Alice Private", db_path=TEST_DB)
        
        targets = get_targets(TEST_DB)
        self.assertEqual(len(targets), 2)
        self.assertEqual(targets[0]["username"], "alice_main")
        
        # 2. Snapshot 1 for alice_main
        followers_s1 = [
            {"id": "1", "username": "user1", "full_name": "User One"},
            {"id": "2", "username": "user2", "full_name": "User Two"},
            {"id": "3", "username": "user3", "full_name": "User Three"},
        ]
        following_s1 = [
            {"id": "1", "username": "user1", "full_name": "User One"},
            {"id": "4", "username": "user4", "full_name": "User Four"},
        ]
        
        s1_id, diffs1 = save_snapshot(
            target_username="alice_main",
            follower_count=3,
            following_count=2,
            followers_list=followers_s1,
            following_list=following_s1,
            db_path=TEST_DB
        )
        self.assertEqual(s1_id, 1)
        self.assertEqual(len(diffs1["new_followers"]), 0) # first snapshot, no diffs
        
        # 3. Snapshot 2 for alice_main (user2 unfollowed, user5 followed)
        followers_s2 = [
            {"id": "1", "username": "user1", "full_name": "User One"},
            {"id": "3", "username": "user3", "full_name": "User Three"},
            {"id": "5", "username": "user5", "full_name": "User Five"}, # NEW
        ]
        following_s2 = [
            {"id": "1", "username": "user1", "full_name": "User One"},
            {"id": "6", "username": "user6", "full_name": "User Six"}, # NEW FOLLOWING (unfollowed user4)
        ]
        
        s2_id, diffs2 = save_snapshot(
            target_username="alice_main",
            follower_count=3,
            following_count=2,
            followers_list=followers_s2,
            following_list=following_s2,
            db_path=TEST_DB
        )
        self.assertEqual(s2_id, 2)
        self.assertEqual(len(diffs2["new_followers"]), 1)
        self.assertEqual(diffs2["new_followers"][0]["username"], "user5")
        self.assertEqual(len(diffs2["unfollowers"]), 1)
        self.assertEqual(diffs2["unfollowers"][0]["username"], "user2")
        self.assertEqual(len(diffs2["new_followings"]), 1)
        self.assertEqual(diffs2["new_followings"][0]["username"], "user6")
        self.assertEqual(len(diffs2["unfollowed"]), 1)
        self.assertEqual(diffs2["unfollowed"][0]["username"], "user4")
        
        # Check recorded events
        events = get_events(target_username="alice_main", db_path=TEST_DB)
        self.assertEqual(len(events), 4)

    def test_cross_account_analytics(self):
        # Setup snapshot for account A
        save_snapshot(
            target_username="account_a",
            follower_count=2,
            following_count=1,
            followers_list=[
                {"id": "10", "username": "common_friend"},
                {"id": "11", "username": "only_a_friend"},
            ],
            following_list=[{"id": "20", "username": "vip"}],
            db_path=TEST_DB
        )
        
        # Setup snapshot for account B
        save_snapshot(
            target_username="account_b",
            follower_count=2,
            following_count=1,
            followers_list=[
                {"id": "10", "username": "common_friend"},
                {"id": "12", "username": "only_b_friend"},
            ],
            following_list=[{"id": "20", "username": "vip"}],
            db_path=TEST_DB
        )
        
        cross = get_cross_account_analysis("account_a", "account_b", db_path=TEST_DB)
        self.assertIsNotNone(cross)
        self.assertEqual(cross["count_common_followers"], 1)
        self.assertEqual(cross["common_followers"][0]["username"], "common_friend")
        self.assertEqual(cross["count_exclusive_followers_a"], 1)
        self.assertEqual(cross["exclusive_followers_a"][0]["username"], "only_a_friend")
        self.assertEqual(cross["count_exclusive_followers_b"], 1)
        self.assertEqual(cross["exclusive_followers_b"][0]["username"], "only_b_friend")
        self.assertEqual(cross["count_common_following"], 1)
        
        # Test DataFrame conversions
        df_com = to_dataframe(cross["common_followers"])
        self.assertEqual(len(df_com), 1)
        
        events = get_events(db_path=TEST_DB)
        df_ev = events_to_dataframe(events)
        self.assertIsInstance(df_ev, pd.DataFrame)


if __name__ == "__main__":
    unittest.main()
