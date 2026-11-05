# Railway Reservation System – Concurrent Seat Allocation Simulator

## 1. Project Overview
A full-stack railway reservation web application built with Python (Flask), SQLite, and HTML5/CSS3/JavaScript. The core objective of this prototype is to simulate and safely handle high-concurrency booking bursts (such as Indian Railways Tatkal window opens at 10:00 AM) where up to 50,000 users attempt to book within one minute, guaranteeing **zero double bookings**.

### Key Highlights
* **Process-Level Lock Synchronization**: Coordinate concurrent application threads using Python's `threading.Lock`.
* **Database ACID Transactions & Strict Constraints**: SQLite `BEGIN IMMEDIATE` transactions with conditional updates (`UPDATE seats SET status = 'BOOKED' WHERE seat_id = ? AND status = 'AVAILABLE'`) and partial unique indexes (`CREATE UNIQUE INDEX idx_confirmed_journey_seat ON bookings(journey_id, seat_id) WHERE booking_status = 'CONFIRMED'`).
* **Idempotency Protection**: Duplicate booking submissions with the same idempotency key are prevented from creating multiple allocations.
* **Modern Dashboard & Interactive Seating Map**: Visual seat status (Available, Selected, Booked), real-time booking history, and system telemetry metrics.

---

## 2. Technology Stack
* **Frontend**: HTML5, CSS3, JavaScript (ES6+, Fetch API)
* **Backend**: Python 3.10+, Flask
* **Database**: SQLite3 (foreign key enforcement enabled, partial unique indexes)
* **Concurrency**: `threading.Lock`, SQLite immediate transactions, conditional atomic updates
* **Testing**: PyTest, Thread-based Concurrency Simulator
* **DevOps**: Docker, Docker Compose, Jenkinsfile CI/CD Pipeline

---

## 3. Directory Structure
```
Railway-Reservation-System/
├── app/
│   ├── __init__.py           # Application factory
│   ├── routes.py             # Web routes & REST API endpoints
│   ├── config.py             # Environment configurations
│   ├── models/               # Data model definitions
│   │   ├── __init__.py
│   │   ├── passenger.py
│   │   ├── journey.py
│   │   ├── seat.py
│   │   └── booking.py
│   ├── services/             # Core business logic
│   │   ├── __init__.py
│   │   ├── booking_service.py
│   │   ├── seat_service.py
│   │   └── lock_manager.py
│   ├── database/             # Schema & connection handling
│   │   ├── __init__.py
│   │   ├── db_connection.py
│   │   ├── schema.sql
│   │   └── seed_data.py
│   ├── templates/            # Jinja2 HTML templates
│   │   ├── index.html
│   │   ├── seats.html
│   │   ├── booking.html
│   │   ├── confirmation.html
│   │   ├── history.html
│   │   └── admin.html
│   └── static/
│       ├── css/
│       │   └── style.css
│       ├── js/
│       │   └── script.js
│       └── images/
├── tests/                    # Automated PyTest test suite
│   ├── test_seats.py
│   ├── test_booking.py
│   ├── test_concurrency.py
│   ├── test_api.py
│   └── test_performance.py
├── docs/                     # Specifications & Design documents
│   ├── requirements.md
│   ├── system_design.md
│   └── detailed_design.md
├── run.py                    # Application entry point
├── requirements.txt          # Python dependencies
├── README.md
├── .gitignore
├── Dockerfile
├── docker-compose.yml
└── Jenkinsfile
```

---

## 4. Local Installation & Setup

### Prerequisites
* Python 3.10+ installed
* Git

### Step 1: Clone and Navigate
```bash
cd "sourcecode"
```

### Step 2: Create and Activate Virtual Environment
On Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Run the Application
```bash
python run.py
```
Open your browser and navigate to: `http://127.0.0.1:5000`

### Step 5: Run Automated Tests
```bash
pytest -v
```

---

## 5. Development Milestones Progress
- [x] **Milestone 1**: Environment and Project Structure (Scaffolding, dependencies, docs, Git repo)
- [x] **Milestone 2**: Database Implementation (Schema, foreign keys, partial unique constraints, connection management, seed data)
- [x] **Milestone 3**: Backend Models (Passenger, Journey, Seat, Booking domain entities)
- [x] **Milestone 4**: Flask APIs (REST endpoints for journeys, seats, bookings, admin metrics)
- [x] **Milestone 5**: Seat Allocation Functionality & Concurrency Control (LockManager, BookingService, thread race tests)
- [x] **Milestone 6**: Frontend Development (Responsive UI, seat selection, booking flow, admin telemetry)
- [ ] **Milestone 7**: Frontend-Backend Integration & Concurrency Verification (End-to-end integration and load testing)
- [ ] **Milestone 6**: Concurrency Control (Lock manager, thread coordination, duplicate prevention tests)
- [ ] **Milestone 7**: Frontend Development (Search, seat layout, booking modal, confirmation, history)
- [ ] **Milestone 8**: Frontend-Backend Integration (Fetch API integration, state management, error handling)
- [ ] **Milestone 9**: Administrative Dashboard (Real-time telemetry, latencies, requests/sec, error rate)
- [ ] **Milestone 10**: Application Execution & Verification (End-to-end load & concurrency verification)

