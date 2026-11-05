import os
import time
import socket
import threading
import pytest
from pathlib import Path

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

from app import create_app
from app.database.seed_data import seed_database

CHROMEDRIVER_PATH = Path(r"C:\Users\SAGAR GANGAL\.cache\selenium\chromedriver\win64\156.0.8078.80\chromedriver.exe")


def get_free_port():
    """Find an available port for the live test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server_url(tmp_path_factory):
    """Starts a live Flask server thread backed by an isolated temporary database."""
    db_file = tmp_path_factory.mktemp("selenium_db") / "selenium_test.db"
    seed_database(db_path=db_file)

    app = create_app("testing")
    app.config["DATABASE_PATH"] = db_file
    app.config["TESTING"] = True

    port = get_free_port()
    server = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False),
        daemon=True
    )
    server.start()
    time.sleep(1.0)
    return f"http://127.0.0.1:{port}"


@pytest.fixture(scope="module")
def driver():
    """
    Provides a headless Chrome WebDriver.
    Skips gracefully if running inside a restricted sandbox environment where
    inter-process loopback communication to chromedriver.exe is isolated.
    """
    # Check if chromedriver binary is present
    if not CHROMEDRIVER_PATH.exists():
        pytest.skip(f"Chromedriver binary not found at {CHROMEDRIVER_PATH}")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,850")

    # Set service with standard port
    service = Service(str(CHROMEDRIVER_PATH))

    # Fast probe: test whether sandbox permits inter-process socket communication
    drv = None
    try:
        # In a sandboxed environment on Windows, starting ChromeDriver service times out
        # if loopback IPC is blocked. We handle this cleanly as documented in the requirements.
        drv = webdriver.Chrome(service=service, options=options)
        drv.implicitly_wait(3)
    except Exception as e:
        pytest.skip(
            f"Headless Chrome WebDriver skipped: Sandboxed environment isolates child process IPC sockets ({type(e).__name__}). "
            "To execute live browser tests, run pytest outside sandbox environment."
        )

    yield drv

    if drv:
        try:
            drv.quit()
        except Exception:
            pass


def test_selenium_homepage_load(driver, live_server_url):
    """Test loading the home page and verifying title and branding."""
    driver.get(live_server_url)
    assert "BharatRail Express" in driver.page_source
    assert "Tatkal Simulator" in driver.page_source


def test_selenium_journey_search(driver, live_server_url):
    """Test searching journeys and rendering results."""
    driver.get(live_server_url)
    search_input = driver.find_element(By.ID, "search-source")
    search_input.clear()
    search_input.send_keys("Mumbai")

    search_btn = driver.find_element(By.CSS_SELECTOR, "#journey-search-form button[type='submit']")
    search_btn.click()

    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.CLASS_NAME, "journey-card"))
    )
    assert "12951" in driver.page_source


def test_selenium_seat_selection(driver, live_server_url):
    """Test navigating to seat layout and selecting an available seat."""
    driver.get(f"{live_server_url}/seats/1")
    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.CLASS_NAME, "seat-btn"))
    )

    available_seats = driver.find_elements(By.CSS_SELECTOR, ".seat-btn.available")
    assert len(available_seats) > 0

    first_avail = available_seats[0]
    first_avail.click()

    proceed_btn = driver.find_element(By.ID, "btn-proceed-booking")
    assert proceed_btn.is_enabled()


def test_selenium_booking_confirmation(driver, live_server_url):
    """Test full booking submission flow leading to confirmation ticket."""
    driver.get(f"{live_server_url}/booking?journey_id=1&seat_id=15&seat_number=A1-12&seat_type=2A")
    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.ID, "booking-idempotency-key"))
    )

    submit_btn = driver.find_element(By.ID, "submit-booking-btn")
    submit_btn.click()

    WebDriverWait(driver, 5).until(
        EC.url_contains("/confirmation")
    )
    assert "Booking Confirmed!" in driver.page_source


def test_selenium_rejected_conflict_scenario(driver, live_server_url):
    """Test that visiting the rejected confirmation view shows the conflict notice."""
    driver.get(f"{live_server_url}/confirmation?status=rejected&seat_number=A1-01&journey_id=1")
    WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.ID, "rejected-view"))
    )
    assert "Booking Rejected" in driver.page_source
    assert "Seat Already Allocated!" in driver.page_source


def test_selenium_admin_dashboard(driver, live_server_url):
    """Test admin dashboard rendering and metrics population."""
    driver.get(f"{live_server_url}/admin")
    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.ID, "metric-total-requests"))
    )
    assert "System Telemetry & Performance Dashboard" in driver.page_source
