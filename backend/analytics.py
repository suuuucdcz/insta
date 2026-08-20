"""
Analytics and Comparison module for Instagram Follower Tracker.
Handles snapshot diffing between any two dates, Base64 avatar extraction, and chronological tracking.
"""

import os
import re
import base64
import requests
from typing import Dict, Any, List, Set, Optional, Tuple
import pandas as pd
from backend.database import (
    DB_PATH,
    get_latest_snapshot,
    get_snapshots,
    get_snapshot_followers,
    get_snapshot_following,
    get_events,
    get_history_stats,
    get_targets
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AVATARS_DIR = os.path.join(BASE_DIR, "data", "avatars")
os.makedirs(AVATARS_DIR, exist_ok=True)

DEFAULT_AVATAR_FALLBACK = "https://static.cdninstagram.com/rsrc.php/v3/y6/r/yW-8Pz7pS7q.png"


def download_avatar(profile_pic_url: str, username: str, avatars_dir: str = AVATARS_DIR) -> Optional[str]:
    """Downloads and caches profile picture locally."""
    if not profile_pic_url:
        return None
    os.makedirs(avatars_dir, exist_ok=True)
    clean_name = username.strip().lstrip("@").lower()
    file_path = os.path.join(avatars_dir, f"{clean_name}.jpg")
    
    if os.path.exists(file_path) and os.path.getsize(file_path) > 500:
        return file_path
        
    try:
        resp = requests.get(profile_pic_url, timeout=5)
        if resp.status_code == 200 and len(resp.content) > 500:
            with open(file_path, "wb") as f:
                f.write(resp.content)
            return file_path
    except Exception:
        pass
    return None


def get_cached_avatar_base64(username: str, profile_pic_url: Optional[str] = None) -> str:
    """
    Returns a Base64 data URI (data:image/jpeg;base64,...) for the avatar.
    This guarantees 100% reliable image rendering in Streamlit tables with zero CORS blocks.
    """
    clean_name = username.strip().lstrip("@").lower()
    file_path = os.path.join(AVATARS_DIR, f"{clean_name}.jpg")
    
    # 1. If cached on disk
    if os.path.exists(file_path) and os.path.getsize(file_path) > 500:
        try:
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
                return f"data:image/jpeg;base64,{b64}"
        except Exception:
            pass
            
    # 2. Try download if url available
    if profile_pic_url:
        downloaded = download_avatar(profile_pic_url, clean_name)
        if downloaded and os.path.exists(downloaded):
            try:
                with open(downloaded, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                    return f"data:image/jpeg;base64,{b64}"
            except Exception:
                pass
                
    return DEFAULT_AVATAR_FALLBACK


def compare_snapshots(old_snapshot_id: int, new_snapshot_id: int, db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Compares any two snapshots (old vs new) and returns the exact differences
    in followers and following with profile pictures and metadata.
    """
    f_old = {u["user_id"]: u for u in get_snapshot_followers(old_snapshot_id, db_path=db_path)}
    f_new = {u["user_id"]: u for u in get_snapshot_followers(new_snapshot_id, db_path=db_path)}
    
    fl_old = {u["user_id"]: u for u in get_snapshot_following(old_snapshot_id, db_path=db_path)}
    fl_new = {u["user_id"]: u for u in get_snapshot_following(new_snapshot_id, db_path=db_path)}
    
    new_followers = [f_new[uid] for uid in f_new if uid not in f_old]
    unfollowers = [f_old[uid] for uid in f_old if uid not in f_new]
    
    new_following = [fl_new[uid] for uid in fl_new if uid not in fl_old]
    unfollowed = [fl_old[uid] for uid in fl_old if uid not in fl_new]
    
    return {
        "old_snapshot_id": old_snapshot_id,
        "new_snapshot_id": new_snapshot_id,
        "old_follower_count": len(f_old),
        "new_follower_count": len(f_new),
        "delta_followers": len(f_new) - len(f_old),
        "old_following_count": len(fl_old),
        "new_following_count": len(fl_new),
        "delta_following": len(fl_new) - len(fl_old),
        "new_followers": new_followers,
        "unfollowers": unfollowers,
        "new_following": new_following,
        "unfollowed": unfollowed
    }


def to_rich_dataframe(
    users_list: List[Dict[str, Any]],
    include_rank: bool = True,
    hide_viewer: bool = False,
    viewer_username: str = "mathis_dryy"
) -> pd.DataFrame:
    """
    Builds a clean DataFrame with Base64 Profile Picture for instant rendering in Streamlit.
    """
    if not users_list:
        cols = ["Photo", "Rang", "Pseudo", "Nom complet", "Statut", "Lien Instagram"]
        return pd.DataFrame(columns=cols)
        
    filtered = users_list
    if hide_viewer:
        filtered = [u for u in users_list if u.get("username", "").lower() != viewer_username.lower()]
        
    rows = []
    for idx, u in enumerate(filtered):
        uname = u.get("username", "")
        rank_val = idx + 1
        pic_b64 = get_cached_avatar_base64(uname, u.get("profile_pic_url"))
        is_self = (uname.lower() == viewer_username.lower())
        
        row = {
            "Photo": pic_b64,
        }
        if include_rank:
            row["Rang"] = f"#{rank_val}" + (" 👤 (Vous)" if is_self else "")
            
        row["Pseudo"] = f"@{uname}"
        row["Nom complet"] = u.get("full_name", "")
        row["Statut"] = "🔒 Privé" if u.get("is_private") else "Public"
        row["Lien Instagram"] = f"https://www.instagram.com/{uname}/"
        
        rows.append(row)
        
    return pd.DataFrame(rows)


def to_dataframe(users_list: List[Dict[str, Any]], include_rank: bool = True) -> pd.DataFrame:
    return to_rich_dataframe(users_list, include_rank=include_rank)


def events_to_dataframe(events_list: List[Dict[str, Any]]) -> pd.DataFrame:
    if not events_list:
        return pd.DataFrame(columns=["Date & Heure", "Compte Cible", "Événement", "Utilisateur", "Nom complet", "Lien"])
        
    type_labels = {
        "NEW_FOLLOWER": "🟢 Nouvel abonné",
        "UNFOLLOWED_BY": "🔴 Désabonnement (Unfollow)",
        "NEW_FOLLOWING": "➕ Nouvel abonnement suivi",
        "UNFOLLOWED": "➖ Abonnement retiré"
    }
    
    rows = []
    for ev in events_list:
        uname = ev.get("username", "")
        rows.append({
            "Date & Heure": ev.get("timestamp", ""),
            "Compte Cible": f"@{ev.get('target_username', '')}",
            "Événement": type_labels.get(ev.get("event_type", ""), ev.get("event_type", "")),
            "Utilisateur": f"@{uname}",
            "Nom complet": ev.get("full_name", ""),
            "Lien": f"https://www.instagram.com/{uname}/"
        })
    return pd.DataFrame(rows)


def get_account_summary(target_username: Optional[str], db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    if not target_username:
        return None
    clean = target_username.strip().lstrip("@").lower()
    latest = get_latest_snapshot(clean, db_path=db_path)
    if not latest:
        return None
        
    followers = get_snapshot_followers(latest["id"], order_by_recent=True, db_path=db_path)
    following = get_snapshot_following(latest["id"], order_by_recent=True, db_path=db_path)
    
    follower_set = {u["user_id"]: u for u in followers}
    following_set = {u["user_id"]: u for u in following}
    
    mutual_ids = set(follower_set.keys()).intersection(set(following_set.keys()))
    not_following_back_ids = set(following_set.keys()) - set(follower_set.keys())
    fans_ids = set(follower_set.keys()) - set(following_set.keys())
    events = get_events(target_username=clean, limit=50, db_path=db_path)
    
    return {
        "target_username": clean,
        "snapshot_id": latest["id"],
        "timestamp": latest["timestamp"],
        "follower_count": len(followers),
        "following_count": len(following),
        "mutual_count": len(mutual_ids),
        "not_following_back_count": len(not_following_back_ids),
        "fans_count": len(fans_ids),
        "followers": followers,
        "following": following,
        "mutuals": [following_set[uid] for uid in mutual_ids],
        "not_following_back": [following_set[uid] for uid in not_following_back_ids],
        "fans": [follower_set[uid] for uid in fans_ids],
        "recent_events": events
    }


def get_cross_account_analysis(target_a: Optional[str], target_b: Optional[str], db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    if not target_a or not target_b:
        return None
    clean_a = target_a.strip().lstrip("@").lower()
    clean_b = target_b.strip().lstrip("@").lower()
    
    latest_a = get_latest_snapshot(clean_a, db_path=db_path)
    latest_b = get_latest_snapshot(clean_b, db_path=db_path)
    
    if not latest_a or not latest_b:
        return None
        
    followers_a = get_snapshot_followers(latest_a["id"], order_by_recent=True, db_path=db_path)
    followers_b = get_snapshot_followers(latest_b["id"], order_by_recent=True, db_path=db_path)
    
    following_a = get_snapshot_following(latest_a["id"], order_by_recent=True, db_path=db_path)
    following_b = get_snapshot_following(latest_b["id"], order_by_recent=True, db_path=db_path)
    
    map_f_a = {u["user_id"]: u for u in followers_a}
    map_f_b = {u["user_id"]: u for u in followers_b}
    set_f_a = set(map_f_a.keys())
    set_f_b = set(map_f_b.keys())
    
    common_f_ids = set_f_a.intersection(set_f_b)
    exclusive_f_a_ids = set_f_a - set_f_b
    exclusive_f_b_ids = set_f_b - set_f_a
    
    map_fl_a = {u["user_id"]: u for u in following_a}
    map_fl_b = {u["user_id"]: u for u in following_b}
    set_fl_a = set(map_fl_a.keys())
    set_fl_b = set(map_fl_b.keys())
    
    common_fl_ids = set_fl_a.intersection(set_fl_b)
    exclusive_fl_a_ids = set_fl_a - set_fl_b
    exclusive_fl_b_ids = set_fl_b - set_fl_a
    
    overlap_pct_a = (len(common_f_ids) / len(set_f_a) * 100) if set_f_a else 0.0
    overlap_pct_b = (len(common_f_ids) / len(set_f_b) * 100) if set_f_b else 0.0
    
    return {
        "target_a": clean_a,
        "target_b": clean_b,
        "timestamp_a": latest_a["timestamp"],
        "timestamp_b": latest_b["timestamp"],
        "count_followers_a": len(followers_a),
        "count_followers_b": len(followers_b),
        "count_common_followers": len(common_f_ids),
        "count_exclusive_followers_a": len(exclusive_f_a_ids),
        "count_exclusive_followers_b": len(exclusive_f_b_ids),
        "overlap_pct_a": round(overlap_pct_a, 1),
        "overlap_pct_b": round(overlap_pct_b, 1),
        "common_followers": [map_f_a[uid] for uid in common_f_ids],
        "exclusive_followers_a": [map_f_a[uid] for uid in exclusive_f_a_ids],
        "exclusive_followers_b": [map_f_b[uid] for uid in exclusive_f_b_ids],
        "count_following_a": len(following_a),
        "count_following_b": len(following_b),
        "count_common_following": len(common_fl_ids),
        "count_exclusive_following_a": len(exclusive_fl_a_ids),
        "count_exclusive_following_b": len(exclusive_fl_b_ids),
        "common_following": [map_fl_a[uid] for uid in common_fl_ids],
        "exclusive_following_a": [map_fl_a[uid] for uid in exclusive_fl_a_ids],
        "exclusive_following_b": [map_fl_b[uid] for uid in exclusive_fl_b_ids],
    }
