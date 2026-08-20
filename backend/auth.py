"""
Authentication module for Instagram Follower Tracker.
Manages Brave/Chrome browser sessions, manual login, and robust challenge handling.
"""

import json
import os
import time
import requests
from typing import Dict, Any, Optional, Tuple
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
BROWSER_PROFILE_DIR = os.path.join(DATA_DIR, "browser_profile")
SESSION_FILE = os.path.join(DATA_DIR, "session.json")

DEFAULT_IG_APP_ID = "936619743392459"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def get_saved_session() -> Optional[Dict[str, Any]]:
    """Loads saved session information from session.json or Streamlit Cloud Secrets."""
    # 1. Try Streamlit Cloud Secrets (if running on cloud)
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "sessionid" in st.secrets:
            sid = st.secrets["sessionid"]
            uid = st.secrets.get("ds_user_id", "8205680658")
            csrf = st.secrets.get("csrftoken", "")
            return {
                "logged_in_user_id": uid,
                "logged_in_username": st.secrets.get("username", "mathis_dryy"),
                "user_agent": DEFAULT_USER_AGENT,
                "app_id": DEFAULT_IG_APP_ID,
                "cookies": {
                    "sessionid": sid,
                    "ds_user_id": uid,
                    "csrftoken": csrf,
                },
                "updated_at": "Streamlit Cloud Secrets"
            }
    except Exception:
        pass

    # 2. Local session.json file
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_session(session_data: Dict[str, Any]) -> None:
    """Saves session info and cookies to session.json."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2)


def get_browser_executable_path() -> Optional[str]:
    """Detects Brave or Chrome browser executable if installed on Windows."""
    possible_paths = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return p
    return None


def is_session_valid() -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Checks if the currently saved session can make authenticated requests to Instagram API.
    Returns: (is_valid, username_or_error, profile_data)
    """
    session_data = get_saved_session()
    if not session_data or "cookies" not in session_data:
        return False, "Aucune session enregistrée. Veuillez vous connecter.", None
    
    cookies = session_data.get("cookies", {})
    if "sessionid" not in cookies:
        return False, "Jeton de session (sessionid) manquant.", None
        
    headers = {
        "User-Agent": session_data.get("user_agent", DEFAULT_USER_AGENT),
        "X-IG-App-ID": session_data.get("app_id", DEFAULT_IG_APP_ID),
        "X-CSRFToken": cookies.get("csrftoken", ""),
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "*/*",
        "Referer": "https://www.instagram.com/",
    }
    
    stored_username = session_data.get("logged_in_username", "")
    
    # Check if Instagram is in challenge/checkpoint state
    url_test = "https://www.instagram.com/api/v1/users/web_profile_info/?username=instagram"
    try:
        resp = requests.get(url_test, headers=headers, cookies=cookies, timeout=8)
        if resp.status_code == 200:
            display_name = stored_username if (stored_username and not stored_username.startswith("user_")) else "mathis_dryy"
            return True, display_name, None
        elif resp.status_code == 429:
            # 429 is temporary rate limit on test endpoint, session is still valid!
            display_name = stored_username if stored_username else "mathis_dryy"
            return True, f"{display_name} (Actif)", None
        elif resp.status_code == 400 and "checkpoint" in resp.text:
            return False, "Validation requise par Instagram. Ouvrez Brave pour valider le message.", None
        elif resp.status_code in (401, 403):
            return False, "Session expirée. Veuillez vous reconnecter.", None
        else:
            display_name = stored_username if stored_username else "mathis_dryy"
            return True, display_name, None
    except Exception:
        # Network timeout on cloud test shouldn't block user
        display_name = stored_username if stored_username else "mathis_dryy"
        return True, display_name, None


def login_with_tokens(sessionid: str, ds_user_id: str, csrftoken: str = "", username: str = "") -> Tuple[bool, str]:
    """
    Allows direct authentication by pasting Instagram session tokens.
    Ideal for cloud deployment (Streamlit Cloud, Render) where no headful browser is available.
    """
    clean_sid = sessionid.strip()
    clean_uid = ds_user_id.strip()
    clean_csrf = csrftoken.strip()
    
    if not clean_sid or len(clean_sid) < 15:
        return False, "Le jeton 'sessionid' semble incomplet ou invalide."
        
    if not clean_uid:
        if "%3A" in clean_sid:
            clean_uid = clean_sid.split("%3A")[0]
        elif ":" in clean_sid:
            clean_uid = clean_sid.split(":")[0]
        else:
            clean_uid = "8205680658"
            
    resolved_uname = username.strip().lstrip("@") or "mathis_dryy"
    
    cookies = {
        "sessionid": clean_sid,
        "ds_user_id": clean_uid,
        "csrftoken": clean_csrf or "missing",
    }
    
    session_payload = {
        "logged_in_user_id": clean_uid,
        "logged_in_username": resolved_uname,
        "user_agent": DEFAULT_USER_AGENT,
        "app_id": DEFAULT_IG_APP_ID,
        "cookies": cookies,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    save_session(session_payload)
    return True, f"Connexion validée avec succès pour @{resolved_uname} !"


def login_with_browser(timeout_seconds: int = 240) -> Dict[str, Any]:
    """
    Opens Brave in headful mode and keeps it open until the user reaches the main Instagram feed
    and passes any security/scraping confirmation prompt.
    """
    os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    
    result = {"success": False, "message": "Connexion interrompue ou expirée."}
    
    with sync_playwright() as p:
        launch_kwargs = {
            "user_data_dir": BROWSER_PROFILE_DIR,
            "headless": False,
            "viewport": {"width": 1280, "height": 850},
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        }
        
        brave_or_chrome = get_browser_executable_path()
        if brave_or_chrome:
            launch_kwargs["executable_path"] = brave_or_chrome
            
        context = p.chromium.launch_persistent_context(**launch_kwargs)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        
        start_time = time.time()
        logged_in = False
        captured_cookies = {}
        user_id = ""
        
        # Wait until user logs in AND clears any challenge/warning
        while time.time() - start_time < timeout_seconds:
            try:
                # Check if browser is still open
                if not context.pages or page.is_closed():
                    break
                    
                current_url = page.url.lower()
                cookies_list = context.cookies()
                cookies_dict = {c["name"]: c["value"] for c in cookies_list if "instagram.com" in c.get("domain", "")}
                
                # Check if user has sessionid and is NOT on login or challenge page
                has_session = "sessionid" in cookies_dict and "ds_user_id" in cookies_dict
                not_on_barrier = (
                    "accounts/login" not in current_url and
                    "challenge" not in current_url and
                    "scraping_warning" not in current_url and
                    "two_factor" not in current_url
                )
                
                if has_session and not_on_barrier:
                    user_id = cookies_dict.get("ds_user_id", "")
                    logged_in = True
                    captured_cookies = cookies_dict
                    break
            except Exception:
                pass
                
            time.sleep(2)
            
        if logged_in:
            time.sleep(2)
            ua = page.evaluate("navigator.userAgent")
            
            # Save session
            session_payload = {
                "logged_in_user_id": user_id,
                "logged_in_username": "mathis_dryy",
                "user_agent": ua or DEFAULT_USER_AGENT,
                "app_id": DEFAULT_IG_APP_ID,
                "cookies": captured_cookies,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            save_session(session_payload)
            result = {
                "success": True,
                "message": "Connexion et validation réussies !",
                "user_id": user_id,
                "username": "mathis_dryy"
            }
        else:
            result = {
                "success": False,
                "message": "Délai dépassé ou fenêtre fermée avant la validation complète."
            }
            
        try:
            context.close()
        except Exception:
            pass
            
    return result


def get_authenticated_headers() -> Tuple[Dict[str, str], Dict[str, str]]:
    """Returns (headers_dict, cookies_dict) for requests."""
    session_data = get_saved_session() or {}
    cookies = session_data.get("cookies", {})
    headers = {
        "User-Agent": session_data.get("user_agent", DEFAULT_USER_AGENT),
        "X-IG-App-ID": session_data.get("app_id", DEFAULT_IG_APP_ID),
        "X-CSRFToken": cookies.get("csrftoken", ""),
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "*/*",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.instagram.com/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    return headers, cookies
