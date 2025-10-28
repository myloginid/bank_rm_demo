from __future__ import annotations

import os

from flask import Flask, render_template

from anonymization import anonymization_bp
from productivity import productivity_bp


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.secret_key = "rm-productivity-demo"  # Replace with a secure key in production.
    app.config.setdefault("MAX_CONTENT_LENGTH", 5 * 1024 * 1024)

    app.register_blueprint(productivity_bp, url_prefix="/productivity")
    app.register_blueprint(anonymization_bp, url_prefix="/anonymization")

    @app.route("/")
    def home():
        return render_template("combined.html")

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("CDSW_APP_PORT", "8080"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host="127.0.0.1", port=port, debug=debug)
