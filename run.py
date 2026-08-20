"""
Safe launcher script for Streamlit Instagram Tracker.
Automatically finds an available port and launches Streamlit cleanly.
"""

import sys
import os
import socket
import subprocess
import webbrowser

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def find_available_port(start_port: int = 8501) -> int:
    port = start_port
    while port < start_port + 50:
        if not is_port_in_use(port):
            return port
        port += 1
    return start_port

if __name__ == "__main__":
    port = find_available_port(8501)
    print(f"===================================================")
    print(f"   Demarrage du Tracker Instagram sur le port {port}")
    print(f"   URL : http://localhost:{port}")
    print(f"===================================================")
    
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        f"--server.port={port}",
        "--server.headless=false",
        "--browser.gatherUsageStats=false"
    ]
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nArret de l'application.")
