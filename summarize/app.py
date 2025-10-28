from __future__ import annotations

from flask import Blueprint, flash, render_template, request

from .services import SummarizationClient, SummarizationError


summarize_bp = Blueprint("summarize", __name__, template_folder="templates")
client = SummarizationClient()


@summarize_bp.route("/", methods=["GET", "POST"])
def index():
    summary = ""
    original = ""
    if request.method == "POST":
        original = request.form.get("text_input", "").strip()
        try:
            summary = client.summarize(original)
            flash("Text summarised successfully.", "success")
        except SummarizationError as exc:
            flash(str(exc), "error")
        except Exception as exc:  # pragma: no cover - safeguard
            flash(f"Unexpected error: {exc}", "error")
    return render_template("summarize.html", original_text=original, summary_text=summary)


def create_summarize_app():
    from flask import Flask

    app = Flask(__name__)
    app.secret_key = "summarize-demo"
    app.register_blueprint(summarize_bp, url_prefix="/summarize")
    return app


if __name__ == "__main__":
    create_summarize_app().run(debug=True)
