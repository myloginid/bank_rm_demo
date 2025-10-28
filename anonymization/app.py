"""
Minimal Flask application that exposes the PII anonymizer over HTTP.

Designed for use with Cloudera Data Science Workbench (CDSW) applications:
start the app with `python app.py` and point the CDSW application to the
resulting service.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Tuple
from xml.etree import ElementTree as ET

from flask import (
    Blueprint,
    Flask,
    Request,
    current_app,
    render_template_string,
    request,
)

from anonymization.pii_anonymizer import PlaceholderManager, anonymize_document

anonymization_bp = Blueprint("anonymization", __name__)


@anonymization_bp.before_app_request
def _configure_upload_limit() -> None:
    current_app.config.setdefault("MAX_CONTENT_LENGTH", 5 * 1024 * 1024)


def detect_content_type(filename: str | None, text: str) -> str:
    """Infer content type from file extension or by attempting to parse."""
    if filename:
        suffix = Path(filename).suffix.lower()
        if suffix in {".json"}:
            return "json"
        if suffix in {".xml", ".html"}:
            return "xml"

    stripped = text.strip()
    if not stripped:
        return "text"

    try:
        json.loads(stripped)
        return "json"
    except json.JSONDecodeError:
        pass

    try:
        ET.fromstring(stripped)
        return "xml"
    except ET.ParseError:
        return "text"


def get_source_text(req: Request) -> Tuple[str, str | None]:
    """Extract textual payload and original filename from the request."""
    uploaded = req.files.get("document")
    text_field = req.form.get("text_input", "").strip()

    if uploaded and uploaded.filename:
        raw = uploaded.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="ignore")
        return text, uploaded.filename

    return text_field, None


def format_mapping(mapping: List[Tuple[Tuple[str, str], str]]):
    rows = []
    for (label, original), placeholder in mapping:
        rows.append(
            {
                "label": label,
                "original": original,
                "placeholder": placeholder,
            }
        )
    return rows


TEMPLATE = """
<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8">
        <title>PII Anonymizer</title>
        <style>
            body { font-family: "Segoe UI", Arial, sans-serif; margin: 2rem; line-height: 1.6; background: #f4f6fb; color: #0c3559; }
            .container { max-width: 1100px; margin: auto; background: #fff; padding: 2.25rem; border-radius: 16px; box-shadow: 0 18px 40px rgba(12, 53, 89, 0.14); border-top: 6px solid #f58025; }
            .container h1 { margin: 0; color: #0c3559; letter-spacing: 0.02em; }
            textarea { width: 100%; min-height: 260px; font-family: monospace; resize: vertical; padding: 1rem; border-radius: 10px; border: 1px solid #c1cede; background: #fff; }
            .row { display: flex; gap: 2rem; flex-wrap: wrap; margin-top: 1.5rem; }
            .column { flex: 1 1 45%; min-width: 320px; display: flex; flex-direction: column; }
            label { font-weight: 600; margin-bottom: 0.5rem; color: #0c3559; }
            table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
            th, td { border: 1px solid #d6e2ef; padding: 0.65rem; text-align: left; }
            th { background: rgba(12, 53, 89, 0.08); color: #0c3559; }
            .error { color: #c23a1f; font-weight: 600; margin-top: 1rem; }
            .mapping-table { max-height: 320px; overflow-y: auto; display: block; margin-top: 1rem; }
            .actions { display: flex; align-items: center; gap: 1rem; margin-top: 1.5rem; flex-wrap: wrap; }
            button { padding: 0.6rem 1.8rem; background: #f58025; color: #fff; border: none; border-radius: 999px; font-size: 1rem; cursor: pointer; transition: background 0.2s ease, transform 0.2s ease; }
            button:hover { background: #d96c1f; transform: translateY(-1px); }
            input[type="text"] { padding: 0.6rem 1rem; border-radius: 8px; border: 1px solid #c1cede; background: #fff; color: #0c3559; }
            .upload { margin-top: 1rem; }
            .placeholder { color: #5e718f; font-style: italic; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>PII Anonymizer</h1>
            <p>Paste text or upload a document, then click <strong>Anonymize</strong> to see an obfuscated copy alongside detected PII.</p>
            {% if error %}
                <p class="error">{{ error }}</p>
            {% endif %}
            <form method="post" enctype="multipart/form-data">
                <div class="upload">
                    <label for="document">Optional file upload:</label>
                    <input type="file" name="document" id="document" accept=".xml,.json,.txt,.csv,.log">
                </div>
                <div class="row">
                    <div class="column">
                        <label for="text_input">Input text</label>
                        <textarea name="text_input" id="text_input" placeholder="Paste XML, JSON, or plain text to anonymize">{{ original_text }}</textarea>
                    </div>
                    <div class="column">
                        <label for="anonymized_output">Anonymized output</label>
                        <textarea id="anonymized_output" readonly>{% if anonymized_text %}{{ anonymized_text }}{% else %}{{ output_placeholder }}{% endif %}</textarea>
                    </div>
                </div>
                <div class="actions">
                    <button type="submit">Anonymize</button>
                    <div>
                        <label for="detected_type">Detected type:</label>
                        <input type="text" id="detected_type" value="{{ detected_type }}" placeholder="(auto-detected after anonymizing)" readonly>
                    </div>
                </div>
            </form>

            {% if anonymized_text %}
            <div style="margin-top: 2rem;">
                <h2>Detected PII</h2>
                {% if mappings %}
                    <div class="mapping-table">
                        <table>
                            <thead>
                                <tr>
                                    <th>Label</th>
                                    <th>Placeholder</th>
                                    <th>Original</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for row in mappings %}
                                <tr>
                                    <td>{{ row.label }}</td>
                                    <td>{{ row.placeholder }}</td>
                                    <td>{{ row.original }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                {% else %}
                    <p>No PII detected.</p>
                {% endif %}
            </div>
            {% endif %}
        </div>
    </body>
</html>
"""


@anonymization_bp.route("/", methods=["GET", "POST"])
def index():
    original_text, filename = get_source_text(request)
    anonymized_text = ""
    detected_type = ""
    mappings = []
    error = ""

    if request.method == "POST":
        if not original_text.strip():
            error = "Please provide a file or paste content to anonymize."
        else:
            detected_type = detect_content_type(filename, original_text)
            try:
                anonymized_text, manager = anonymize_document(original_text, detected_type)
                mappings = format_mapping(list(manager.items()))
            except Exception as exc:  # pragma: no cover - narrow scope runtime errors
                error = f"Failed to anonymize document: {exc}"

    output_placeholder = "Anonymized text will appear here after you click Anonymize."

    return render_template_string(
        TEMPLATE,
        original_text=original_text,
        anonymized_text=anonymized_text,
        detected_type=detected_type,
        mappings=mappings,
        error=error,
        output_placeholder=output_placeholder,
    )


def create_anonymization_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(anonymization_bp, url_prefix="/anonymization")
    return app


if __name__ == "__main__":
    port = os.getenv('CDSW_APP_PORT', 8080)
    debug = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    create_anonymization_app().run(host="127.0.0.1", port=port, debug=debug)
