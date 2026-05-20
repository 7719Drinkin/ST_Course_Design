"""Flask application factory and shared error handling."""

from __future__ import annotations

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import BadRequest, HTTPException

from backend.config import Config
from backend.routes.aut import aut_bp
from backend.routes.design import design_bp
from backend.routes.review import review_bp


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    CORS(app, origins=config_object.CORS_ORIGINS)

    app.register_blueprint(design_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(aut_bp)

    @app.get("/health")
    def health() -> tuple[dict[str, str], int]:
        return {"status": "ok"}, 200

    @app.errorhandler(BadRequest)
    def handle_bad_request(exc: BadRequest):
        return jsonify({"error": "bad_request", "message": exc.description}), 400

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        return jsonify({"error": exc.name, "message": exc.description}), exc.code or 500

    @app.errorhandler(Exception)
    def handle_uncaught_exception(exc: Exception):
        app.logger.exception("Unhandled backend error", exc_info=exc)
        return jsonify({"error": "internal_server_error", "message": "Unexpected backend error"}), 500

    return app
