import os
from flask import Flask
from app.config import config_by_name
from app.database.db_connection import close_db

def create_app(config_name=None):
    """Application factory for Railway Reservation System."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    # Register database connection teardown
    app.teardown_appcontext(close_db)

    # Register Blueprints
    from app.routes import api_bp, web_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)

    return app
