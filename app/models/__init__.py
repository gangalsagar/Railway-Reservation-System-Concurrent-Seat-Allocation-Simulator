"""Data models for Railway Reservation System."""

from app.models.passenger import Passenger
from app.models.journey import Journey
from app.models.seat import Seat
from app.models.booking import Booking
from app.models.booking_request import BookingRequest

__all__ = [
    "Passenger",
    "Journey",
    "Seat",
    "Booking",
    "BookingRequest",
]
