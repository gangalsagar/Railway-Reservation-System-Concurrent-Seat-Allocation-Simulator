import os
from flask import Flask
from app.config import config_by_name

def create_app(config_name=None):
    """Application factory for Railway Reservation System."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    # Blueprints and routes will be registered here as milestones progress
    with app.app_context():
        # Ensure database tables exist if needed
        pass

    return app
