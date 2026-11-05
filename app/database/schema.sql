-- Railway Reservation System - Database Schema
-- Milestone 2: Schema Definition with Foreign Keys & Partial Unique Constraints

-- Enforce Foreign Key Integrity
PRAGMA foreign_keys = ON;

-- 1. PASSENGERS TABLE
CREATE TABLE IF NOT EXISTS passengers (
    passenger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    passenger_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. JOURNEYS TABLE
CREATE TABLE IF NOT EXISTS journeys (
    journey_id INTEGER PRIMARY KEY AUTOINCREMENT,
    train_number TEXT NOT NULL,
    source TEXT NOT NULL,
    destination TEXT NOT NULL,
    journey_date TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_train_date UNIQUE (train_number, journey_date)
);

-- 3. SEATS TABLE
CREATE TABLE IF NOT EXISTS seats (
    seat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id INTEGER NOT NULL,
    seat_number TEXT NOT NULL,
    seat_type TEXT NOT NULL CHECK(seat_type IN ('1A', '2A', '3A', 'SL', 'CC', '2S')),
    status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK(status IN ('AVAILABLE', 'BOOKED')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (journey_id) REFERENCES journeys(journey_id) ON DELETE CASCADE,
    CONSTRAINT uk_journey_seat UNIQUE (journey_id, seat_number)
);

-- 4. BOOKINGS TABLE
CREATE TABLE IF NOT EXISTS bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    passenger_id INTEGER NOT NULL,
    seat_id INTEGER NOT NULL,
    journey_id INTEGER NOT NULL,
    booking_status TEXT NOT NULL CHECK(booking_status IN ('CONFIRMED', 'CANCELLED', 'REJECTED')),
    booking_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    idempotency_key TEXT UNIQUE NOT NULL,
    FOREIGN KEY (passenger_id) REFERENCES passengers(passenger_id) ON DELETE RESTRICT,
    FOREIGN KEY (seat_id) REFERENCES seats(seat_id) ON DELETE RESTRICT,
    FOREIGN KEY (journey_id) REFERENCES journeys(journey_id) ON DELETE RESTRICT
);

-- 5. BOOKING_REQUESTS TABLE (Telemetry & Audit)
CREATE TABLE IF NOT EXISTS booking_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    passenger_id INTEGER,
    journey_id INTEGER,
    seat_id INTEGER,
    request_status TEXT NOT NULL CHECK(request_status IN ('SUCCESS', 'REJECTED', 'ERROR')),
    request_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processing_time_ms REAL NOT NULL,
    FOREIGN KEY (passenger_id) REFERENCES passengers(passenger_id) ON DELETE SET NULL,
    FOREIGN KEY (journey_id) REFERENCES journeys(journey_id) ON DELETE SET NULL,
    FOREIGN KEY (seat_id) REFERENCES seats(seat_id) ON DELETE SET NULL
);

-- CRITICAL REQUIREMENT: Partial Unique Index
-- Prevents more than one CONFIRMED booking for the same journey_id and seat_id
CREATE UNIQUE INDEX IF NOT EXISTS idx_confirmed_journey_seat
ON bookings (journey_id, seat_id)
WHERE booking_status = 'CONFIRMED';

-- Performance Optimization Indexes
CREATE INDEX IF NOT EXISTS idx_seats_journey_status
ON seats (journey_id, status);

CREATE INDEX IF NOT EXISTS idx_journeys_search
ON journeys (source, destination, journey_date);

CREATE INDEX IF NOT EXISTS idx_bookings_passenger
ON bookings (passenger_id);

CREATE INDEX IF NOT EXISTS idx_booking_requests_journey
ON booking_requests (journey_id);
