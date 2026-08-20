"""
Automated background scheduler for Instagram Follower Tracker.
Executes scheduled scans at safe intervals (e.g. twice a day) with natural delays.
"""

import time
import os
import sys
import threading
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.database import get_targets
from backend.scraper import scan_target

_SCHEDULER_THREAD = None
_IS_RUNNING = False


def run_scheduled_job():
    """Runs a single safe scan cycle for all configured targets."""
    targets = get_targets()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⏰ Lancement du scan automatique programmé...")
    for t in targets:
        try:
            uname = t["username"]
            res = scan_target(uname)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Scan auto @{uname} terminé: {res.get('success')}")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Erreur scan auto @{t.get('username')}: {e}")
        time.sleep(10) # 10s pause between accounts


def _scheduler_loop(interval_hours: float = 12.0):
    global _IS_RUNNING
    _IS_RUNNING = True
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🟢 Planificateur automatique actif (toutes les {interval_hours} heures)")
    
    interval_seconds = int(interval_hours * 3600)
    while _IS_RUNNING:
        time.sleep(interval_seconds)
        if _IS_RUNNING:
            run_scheduled_job()


def start_scheduler(interval_hours: float = 12.0) -> bool:
    global _SCHEDULER_THREAD, _IS_RUNNING
    if _IS_RUNNING and _SCHEDULER_THREAD and _SCHEDULER_THREAD.is_alive():
        return True
    _SCHEDULER_THREAD = threading.Thread(target=_scheduler_loop, args=(interval_hours,), daemon=True)
    _SCHEDULER_THREAD.start()
    return True


def stop_scheduler():
    global _IS_RUNNING
    _IS_RUNNING = False


def is_scheduler_active() -> bool:
    global _IS_RUNNING, _SCHEDULER_THREAD
    return _IS_RUNNING and _SCHEDULER_THREAD is not None and _SCHEDULER_THREAD.is_alive()
