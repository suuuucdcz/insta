"""
Database module for Instagram Follower Tracker.
Handles SQLite storage for targets, snapshots, followers, following, and diff events,
with chronological position tracking and risk signals.
"""

import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "tracker.db")


@contextmanager
def get_db(db_path: str = DB_PATH):
    """Context manager that opens, commits and always closes the SQLite connection."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str = DB_PATH) -> None:
    """Initialize SQLite tables if they do not exist."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        
        # Targets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT,
                profile_pic_url TEXT,
                is_private INTEGER DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_username TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                follower_count INTEGER DEFAULT 0,
                following_count INTEGER DEFAULT 0
            )
        """)
        
        # Followers per snapshot with list_order (1 = top / most recent)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS snapshot_followers (
                snapshot_id INTEGER NOT NULL,
                target_username TEXT NOT NULL,
                user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                full_name TEXT,
                profile_pic_url TEXT,
                is_verified INTEGER DEFAULT 0,
                is_private INTEGER DEFAULT 0,
                list_order INTEGER DEFAULT 0,
                has_default_avatar INTEGER DEFAULT 0,
                PRIMARY KEY (snapshot_id, user_id),
                FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
            )
        """)
        
        # Following per snapshot with list_order (1 = top / most recent follow)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS snapshot_following (
                snapshot_id INTEGER NOT NULL,
                target_username TEXT NOT NULL,
                user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                full_name TEXT,
                profile_pic_url TEXT,
                is_verified INTEGER DEFAULT 0,
                is_private INTEGER DEFAULT 0,
                list_order INTEGER DEFAULT 0,
                has_default_avatar INTEGER DEFAULT 0,
                PRIMARY KEY (snapshot_id, user_id),
                FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
            )
        """)
        
        # Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_username TEXT NOT NULL,
                snapshot_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,
                user_id TEXT,
                username TEXT NOT NULL,
                full_name TEXT,
                profile_pic_url TEXT,
                list_order INTEGER DEFAULT 0,
                FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE SET NULL
            )
        """)
        
        # Add columns if migrating from existing DB
        try:
            cursor.execute("ALTER TABLE snapshot_followers ADD COLUMN list_order INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE snapshot_followers ADD COLUMN has_default_avatar INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE snapshot_following ADD COLUMN list_order INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE snapshot_following ADD COLUMN has_default_avatar INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE events ADD COLUMN list_order INTEGER DEFAULT 0;")
        except Exception:
            pass
            
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_target ON snapshots(target_username, timestamp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_followers_snap ON snapshot_followers(snapshot_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_following_snap ON snapshot_following(snapshot_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_target ON events(target_username, timestamp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);")


def add_target(username: str, full_name: str = "", profile_pic_url: str = "", is_private: bool = False, db_path: str = DB_PATH) -> bool:
    clean_username = username.strip().lstrip("@").lower()
    if not clean_username:
        return False
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO targets (username, full_name, profile_pic_url, is_private)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                full_name=excluded.full_name,
                profile_pic_url=excluded.profile_pic_url,
                is_private=excluded.is_private
        """, (clean_username, full_name, profile_pic_url, 1 if is_private else 0))
    return True


def remove_target(username: str, db_path: str = DB_PATH) -> None:
    clean_username = username.strip().lstrip("@").lower()
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM targets WHERE username = ?", (clean_username,))


def get_targets(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM targets ORDER BY id ASC")
        return [dict(row) for row in cursor.fetchall()]


def get_snapshots(target_username: Optional[str] = None, limit: int = 50, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        if target_username:
            clean = target_username.strip().lstrip("@").lower()
            cursor.execute("SELECT * FROM snapshots WHERE target_username = ? ORDER BY timestamp DESC LIMIT ?", (clean, limit))
        else:
            cursor.execute("SELECT * FROM snapshots ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_latest_snapshot(target_username: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    clean_username = target_username.strip().lstrip("@").lower()
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM snapshots 
            WHERE target_username = ? 
            ORDER BY timestamp DESC, id DESC 
            LIMIT 1
        """, (clean_username,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_snapshot_followers(snapshot_id: int, order_by_recent: bool = True, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    order_clause = "list_order ASC" if order_by_recent else "username ASC"
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT * FROM snapshot_followers 
            WHERE snapshot_id = ?
            ORDER BY {order_clause}
        """, (snapshot_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_snapshot_following(snapshot_id: int, order_by_recent: bool = True, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    order_clause = "list_order ASC" if order_by_recent else "username ASC"
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT * FROM snapshot_following 
            WHERE snapshot_id = ?
            ORDER BY {order_clause}
        """, (snapshot_id,))
        return [dict(row) for row in cursor.fetchall()]


def save_snapshot(
    target_username: str,
    follower_count: int,
    following_count: int,
    followers_list: List[Dict[str, Any]],
    following_list: List[Dict[str, Any]],
    db_path: str = DB_PATH
) -> Tuple[int, Dict[str, List[Dict[str, Any]]]]:
    clean_username = target_username.strip().lstrip("@").lower()
    diffs = {
        "new_followers": [],
        "unfollowers": [],
        "new_followings": [],
        "unfollowed": []
    }
    
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Get latest prior snapshot ID
        cursor.execute("""
            SELECT id FROM snapshots 
            WHERE target_username = ? 
            ORDER BY id DESC LIMIT 1
        """, (clean_username,))
        prev_row = cursor.fetchone()
        prev_snapshot_id = prev_row["id"] if prev_row else None
        
        # 2. Insert new snapshot
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO snapshots (target_username, timestamp, follower_count, following_count)
            VALUES (?, ?, ?, ?)
        """, (clean_username, now_str, follower_count, following_count))
        snapshot_id = cursor.lastrowid
        
        # 3. Insert current followers with list_order
        follower_rows = [
            (
                snapshot_id,
                clean_username,
                str(u.get("id") or u.get("pk") or u.get("user_id") or u.get("username")),
                u.get("username", "").lower(),
                u.get("full_name", ""),
                u.get("profile_pic_url", ""),
                1 if u.get("is_verified") else 0,
                1 if u.get("is_private") else 0,
                idx + 1,
                1 if (not u.get("profile_pic_url") or "44884218_345707102882519" in u.get("profile_pic_url", "") or "default_avatar" in u.get("profile_pic_url", "") or u.get("has_anonymous_profile_picture")) else 0
            )
            for idx, u in enumerate(followers_list)
        ]
        cursor.executemany("""
            INSERT OR REPLACE INTO snapshot_followers 
            (snapshot_id, target_username, user_id, username, full_name, profile_pic_url, is_verified, is_private, list_order, has_default_avatar)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, follower_rows)
        
        # 4. Insert current following with list_order (1 = most recent follow)
        following_rows = [
            (
                snapshot_id,
                clean_username,
                str(u.get("id") or u.get("pk") or u.get("user_id") or u.get("username")),
                u.get("username", "").lower(),
                u.get("full_name", ""),
                u.get("profile_pic_url", ""),
                1 if u.get("is_verified") else 0,
                1 if u.get("is_private") else 0,
                idx + 1,
                1 if (not u.get("profile_pic_url") or "44884218_345707102882519" in u.get("profile_pic_url", "") or "default_avatar" in u.get("profile_pic_url", "") or u.get("has_anonymous_profile_picture")) else 0
            )
            for idx, u in enumerate(following_list)
        ]
        cursor.executemany("""
            INSERT OR REPLACE INTO snapshot_following 
            (snapshot_id, target_username, user_id, username, full_name, profile_pic_url, is_verified, is_private, list_order, has_default_avatar)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, following_rows)
        
        # 5. Calculate Diffs if there was a previous snapshot
        if prev_snapshot_id:
            cursor.execute("SELECT user_id, username, full_name, profile_pic_url, list_order FROM snapshot_followers WHERE snapshot_id = ?", (prev_snapshot_id,))
            prev_followers = {row["user_id"]: dict(row) for row in cursor.fetchall()}
            
            curr_followers = {row[2]: {"user_id": row[2], "username": row[3], "full_name": row[4], "profile_pic_url": row[5], "list_order": row[8]} for row in follower_rows}
            
            cursor.execute("SELECT user_id, username, full_name, profile_pic_url, list_order FROM snapshot_following WHERE snapshot_id = ?", (prev_snapshot_id,))
            prev_following = {row["user_id"]: dict(row) for row in cursor.fetchall()}
            
            curr_following = {row[2]: {"user_id": row[2], "username": row[3], "full_name": row[4], "profile_pic_url": row[5], "list_order": row[8]} for row in following_rows}
            
            # A. New Followers
            for uid, data in curr_followers.items():
                if uid not in prev_followers:
                    diffs["new_followers"].append(data)
                    cursor.execute("""
                        INSERT INTO events (target_username, snapshot_id, timestamp, event_type, user_id, username, full_name, profile_pic_url, list_order)
                        VALUES (?, ?, ?, 'NEW_FOLLOWER', ?, ?, ?, ?, ?)
                    """, (clean_username, snapshot_id, now_str, data["user_id"], data["username"], data["full_name"], data["profile_pic_url"], data.get("list_order", 0)))
                    
            # B. Unfollowers
            for uid, data in prev_followers.items():
                if uid not in curr_followers:
                    diffs["unfollowers"].append(data)
                    cursor.execute("""
                        INSERT INTO events (target_username, snapshot_id, timestamp, event_type, user_id, username, full_name, profile_pic_url, list_order)
                        VALUES (?, ?, ?, 'UNFOLLOWED_BY', ?, ?, ?, ?, ?)
                    """, (clean_username, snapshot_id, now_str, data["user_id"], data["username"], data["full_name"], data["profile_pic_url"], data.get("list_order", 0)))
            
            # C. New Followings
            for uid, data in curr_following.items():
                if uid not in prev_following:
                    diffs["new_followings"].append(data)
                    cursor.execute("""
                        INSERT INTO events (target_username, snapshot_id, timestamp, event_type, user_id, username, full_name, profile_pic_url, list_order)
                        VALUES (?, ?, ?, 'NEW_FOLLOWING', ?, ?, ?, ?, ?)
                    """, (clean_username, snapshot_id, now_str, data["user_id"], data["username"], data["full_name"], data["profile_pic_url"], data.get("list_order", 0)))
                    
            # D. Unfollowed
            for uid, data in prev_following.items():
                if uid not in curr_following:
                    diffs["unfollowed"].append(data)
                    cursor.execute("""
                        INSERT INTO events (target_username, snapshot_id, timestamp, event_type, user_id, username, full_name, profile_pic_url, list_order)
                        VALUES (?, ?, ?, 'UNFOLLOWED', ?, ?, ?, ?, ?)
                    """, (clean_username, snapshot_id, now_str, data["user_id"], data["username"], data["full_name"], data["profile_pic_url"], data.get("list_order", 0)))
                    
    return snapshot_id, diffs


def get_events(
    target_username: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
    db_path: str = DB_PATH
) -> List[Dict[str, Any]]:
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM events WHERE 1=1"
        params = []
        
        if target_username:
            clean = target_username.strip().lstrip("@").lower()
            query += " AND target_username = ?"
            params.append(clean)
            
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
            
        query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_history_stats(target_username: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    clean = target_username.strip().lstrip("@").lower()
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, target_username, timestamp, follower_count, following_count
            FROM snapshots
            WHERE target_username = ?
            ORDER BY timestamp ASC
        """, (clean,))
        return [dict(row) for row in cursor.fetchall()]
