import pytest

def test_homepage_rendering(client):
    """Test that the home page renders successfully with branding and search form."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "BharatRail Express" in html
    assert "Your next journey" in html
    assert "Search Journeys" in html
    assert 'id="search-source"' in html
    assert 'id="search-destination"' in html


def test_seats_page_rendering(client):
    """Test that the seat selection page renders with coach filters and layout container."""
    res = client.get("/seats/1")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Train Journey #1" in html
    assert "First AC (1A)" in html
    assert "2-Tier AC (2A)" in html
    assert "seats-grid" in html
    assert "Proceed to Passenger Details" in html


def test_booking_page_rendering(client):
    """Test that the booking page renders with passenger selector and idempotency field."""
    res = client.get("/booking?journey_id=1&seat_id=10&seat_number=A1-10&seat_type=2A")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Confirm seat allocation" in html
    assert 'id="passenger-select"' in html
    assert 'id="booking-idempotency-key"' in html
    assert "Confirm Booking Now" in html


def test_confirmation_page_confirmed(client):
    """Test that confirmation page renders ticket layout."""
    res = client.get("/confirmation?booking_id=1&status=confirmed")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "You're all set for your journey." in html
    assert 'id="ticket-seat"' in html
    assert "Print Ticket" in html


def test_confirmation_page_rejected(client):
    """Test that confirmation page properly renders rejection state."""
    res = client.get("/confirmation?status=rejected&seat_number=A1-01&journey_id=1")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "This seat is no longer available." in html
    assert 'id="rejected-seat-label"' in html
    assert "Select Another Seat" in html


def test_admin_dashboard_rendering(client):
    """Test that admin dashboard renders telemetry cards and data table."""
    res = client.get("/admin")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "System performance overview." in html
    assert "Confirmed Bookings" in html
    assert "Rejected Conflicts" in html
    assert "Average Latency" in html
    assert "P95 Latency" in html
    assert "Recent confirmed reservations" in html


def test_history_page_rendering(client):
    """Test that booking history page renders lookup form."""
    res = client.get("/history")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Every journey, in one place." in html
    assert 'id="history-passenger-select"' in html


def test_static_assets_served(client):
    """Test that CSS and JS static files are served with HTTP 200."""
    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == 200
    assert "BharatRail" in css_res.get_data(as_text=True) or "root" in css_res.get_data(as_text=True)

    js_res = client.get("/static/js/script.js")
    assert js_res.status_code == 200
    assert "searchJourneys" in js_res.get_data(as_text=True)

