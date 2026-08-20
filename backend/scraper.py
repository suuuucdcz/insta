"""
Scraper module for Instagram Follower Tracker.
Configured with ULTRA-SAFE mode, long human-like randomized delays, and rate-limiting protections.
"""

import time
import random
import requests
from typing import Dict, Any, List, Optional, Tuple, Callable
from backend.auth import get_authenticated_headers
from backend.database import add_target, save_snapshot

# Ultra-safe human delay settings
SAFE_DELAY_MIN = 4.5
SAFE_DELAY_MAX = 9.0
BATCH_PAUSE_EVERY_N_PAGES = 3
BATCH_PAUSE_DURATION = (8.0, 15.0)


def get_user_info(username: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Fetches basic profile info for a given Instagram username.
    """
    clean_username = username.strip().lstrip("@").lower()
    headers, cookies = get_authenticated_headers()
    
    if not cookies or "sessionid" not in cookies:
        return False, None, "Vous n'êtes pas connecté à Instagram. Veuillez vous connecter dans les paramètres."
        
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={clean_username}"
    
    # Safe sleep before profile query
    time.sleep(random.uniform(1.5, 3.0))
    
    try:
        resp = requests.get(url, headers=headers, cookies=cookies, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            user = data.get("data", {}).get("user")
            if not user:
                return False, None, f"Compte @{clean_username} introuvable."
                
            profile_info = {
                "id": str(user.get("id")),
                "username": user.get("username"),
                "full_name": user.get("full_name", ""),
                "profile_pic_url": user.get("profile_pic_url", ""),
                "follower_count": user.get("edge_followed_by", {}).get("count", 0),
                "following_count": user.get("edge_follow", {}).get("count", 0),
                "is_private": user.get("is_private", False),
                "is_verified": user.get("is_verified", False),
                "biography": user.get("biography", "")
            }
            return True, profile_info, "Succès"
        elif resp.status_code == 404:
            return False, None, f"Le compte @{clean_username} n'existe pas ou est introuvable."
        elif resp.status_code in (401, 403):
            return False, None, "Session expirée. Veuillez vous reconnecter dans l'application."
        elif resp.status_code == 429:
            return False, None, "Limite de requêtes atteinte (Rate limit). Veuillez patienter quelques minutes."
        else:
            return False, None, f"Instagram a répondu avec le statut {resp.status_code}."
    except Exception as e:
        return False, None, f"Erreur réseau : {str(e)}"


def get_user_followers(
    user_id: str,
    target_count: int = 0,
    delay_range: Tuple[float, float] = (SAFE_DELAY_MIN, SAFE_DELAY_MAX),
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Fetches the full followers list with long human delays to avoid bot detection.
    """
    headers, cookies = get_authenticated_headers()
    followers = []
    max_id = None
    page = 1
    
    while True:
        url = f"https://www.instagram.com/api/v1/friendships/{user_id}/followers/?count=50&search_surface=follow_list_page"
        if max_id:
            url += f"&max_id={max_id}"
            
        try:
            # Human pause before each request
            sleep_time = random.uniform(*delay_range)
            time.sleep(sleep_time)
            
            resp = requests.get(url, headers=headers, cookies=cookies, timeout=25)
            if resp.status_code != 200:
                if resp.status_code == 429:
                    return False, followers, "Instagram limite les requêtes (429). Pause requise."
                if resp.status_code == 400 and "checkpoint" in resp.text:
                    return False, followers, "Instagram demande une validation de sécurité."
                return False, followers, f"Erreur lors de la récupération (Code {resp.status_code})."
                
            data = resp.json()
            users = data.get("users", [])
            for u in users:
                followers.append({
                    "id": str(u.get("pk") or u.get("id")),
                    "username": u.get("username", "").lower(),
                    "full_name": u.get("full_name", ""),
                    "profile_pic_url": u.get("profile_pic_url", ""),
                    "is_verified": u.get("is_verified", False),
                    "is_private": u.get("is_private", False),
                    "has_anonymous_profile_picture": u.get("has_anonymous_profile_picture", False)
                })
                
            if progress_callback:
                progress_callback("abonnés (mode sécurisé)", len(followers), target_count)
                
            max_id = data.get("next_max_id")
            if not max_id or not users:
                break
                
            # Extra long rest every few pages
            if page % BATCH_PAUSE_EVERY_N_PAGES == 0:
                time.sleep(random.uniform(*BATCH_PAUSE_DURATION))
                
            page += 1
            
        except Exception as e:
            return False, followers, f"Erreur inattendue : {str(e)}"
            
    return True, followers, "Succès"


def get_user_following(
    user_id: str,
    target_count: int = 0,
    delay_range: Tuple[float, float] = (SAFE_DELAY_MIN, SAFE_DELAY_MAX),
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Fetches following list with long human delays.
    """
    headers, cookies = get_authenticated_headers()
    following = []
    max_id = None
    page = 1
    
    while True:
        url = f"https://www.instagram.com/api/v1/friendships/{user_id}/following/?count=50"
        if max_id:
            url += f"&max_id={max_id}"
            
        try:
            # Human pause
            sleep_time = random.uniform(*delay_range)
            time.sleep(sleep_time)
            
            resp = requests.get(url, headers=headers, cookies=cookies, timeout=25)
            if resp.status_code != 200:
                if resp.status_code == 429:
                    return False, following, "Instagram limite les requêtes (429)."
                if resp.status_code == 400 and "checkpoint" in resp.text:
                    return False, following, "Instagram demande une validation de sécurité."
                return False, following, f"Erreur récupération abonnements (Code {resp.status_code})."
                
            data = resp.json()
            users = data.get("users", [])
            for u in users:
                following.append({
                    "id": str(u.get("pk") or u.get("id")),
                    "username": u.get("username", "").lower(),
                    "full_name": u.get("full_name", ""),
                    "profile_pic_url": u.get("profile_pic_url", ""),
                    "is_verified": u.get("is_verified", False),
                    "is_private": u.get("is_private", False),
                    "has_anonymous_profile_picture": u.get("has_anonymous_profile_picture", False)
                })
                
            if progress_callback:
                progress_callback("abonnements (mode sécurisé)", len(following), target_count)
                
            max_id = data.get("next_max_id")
            if not max_id or not users:
                break
                
            if page % BATCH_PAUSE_EVERY_N_PAGES == 0:
                time.sleep(random.uniform(*BATCH_PAUSE_DURATION))
                
            page += 1
            
        except Exception as e:
            return False, following, f"Erreur inattendue : {str(e)}"
            
    return True, following, "Succès"


def scan_target(
    username: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> Dict[str, Any]:
    """
    Performs a full ultra-safe scan of a target account with human pauses.
    """
    clean_username = username.strip().lstrip("@").lower()
    
    # Step 1: User info
    success, info, msg = get_user_info(clean_username)
    if not success or not info:
        return {"success": False, "message": msg, "target": clean_username}
        
    user_id = info["id"]
    follower_count = info["follower_count"]
    following_count = info["following_count"]
    
    add_target(
        username=clean_username,
        full_name=info["full_name"],
        profile_pic_url=info["profile_pic_url"],
        is_private=info["is_private"]
    )
    
    # Safe break before followers
    time.sleep(random.uniform(3.0, 5.0))
    
    # Step 2: Fetch followers
    if progress_callback:
        progress_callback("status", 0, follower_count)
    ok_f, followers, msg_f = get_user_followers(user_id, target_count=follower_count, progress_callback=progress_callback)
    if not ok_f and not followers:
        return {"success": False, "message": f"Followers: {msg_f}", "target": clean_username}
        
    # Safe break between followers & following
    time.sleep(random.uniform(4.0, 7.0))
    
    # Step 3: Fetch following
    ok_fl, following, msg_fl = get_user_following(user_id, target_count=following_count, progress_callback=progress_callback)
    if not ok_fl and not following:
        return {"success": False, "message": f"Following: {msg_fl}", "target": clean_username}
        
    # Step 4: Save Snapshot & compute Diffs
    snapshot_id, diffs = save_snapshot(
        target_username=clean_username,
        follower_count=len(followers) or follower_count,
        following_count=len(following) or following_count,
        followers_list=followers,
        following_list=following
    )
    
    return {
        "success": True,
        "message": f"Scan sécurisé terminé pour @{clean_username} !",
        "target": clean_username,
        "snapshot_id": snapshot_id,
        "follower_count": len(followers),
        "following_count": len(following),
        "diffs": diffs,
        "profile": info
    }
