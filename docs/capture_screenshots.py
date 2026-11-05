import os
import sys
import time
import subprocess
import threading
from pathlib import Path

# Add project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import create_app
from app.database.seed_data import seed_database

CHROME_BIN = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
if not CHROME_BIN.exists():
    CHROME_BIN = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

OUTPUT_DIR = ROOT / "docs" / "screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def capture_url(url, output_file, wait_sec=1.5):
    cmd = [
        str(CHROME_BIN),
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size=1280,850",
        f"--screenshot={output_file}",
        url
    ]
    subprocess.run(cmd, check=True)
    print(f"Captured: {output_file.name}")

def main():
    # Ensure seed database exists
    seed_database()

    app = create_app("development")
    
    server_thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=5099, debug=False, use_reloader=False),
        daemon=True
    )
    server_thread.start()
    time.sleep(1.5)

    base = "http://127.0.0.1:5099"

    capture_url(f"{base}/", OUTPUT_DIR / "01_home_search.png")
    capture_url(f"{base}/seats/1", OUTPUT_DIR / "02_seat_selection.png")
    capture_url(f"{base}/booking?journey_id=1&seat_id=10&seat_number=A1-10&seat_type=2A", OUTPUT_DIR / "03_booking_form.png")
    capture_url(f"{base}/confirmation?booking_id=1&status=confirmed", OUTPUT_DIR / "04_confirmation_ticket.png")
    capture_url(f"{base}/confirmation?status=rejected&seat_number=A1-01&journey_id=1", OUTPUT_DIR / "05_rejection_conflict.png")
    capture_url(f"{base}/admin", OUTPUT_DIR / "06_admin_dashboard.png")

    print("All screenshots captured successfully!")

if __name__ == "__main__":
    main()
