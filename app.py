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

from flask import Flask, Request, render_template_string, request

from anonymization.pii_anonymizer import PlaceholderManager, anonymize_document

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB uploads


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
            body { font-family: Arial, sans-serif; margin: 2rem; line-height: 1.5; }
            .container { max-width: 960px; margin: auto; }
            textarea { width: 100%; min-height: 200px; font-family: monospace; }
            .row { display: flex; gap: 2rem; flex-wrap: wrap; }
            .column { flex: 1 1 45%; min-width: 320px; }
            table { border-collapse: collapse; width: 100%; margin-top: 1rem;}
            th, td { border: 1px solid #ddd; padding: 0.5rem; }
            th { background: #f3f3f3; text-align: left; }
            .error { color: #a00; font-weight: bold; }
            .mapping-table { max-height: 300px; overflow-y: auto; display: block; }
            .mapping-table table { width: 100%; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>PII Anonymizer</h1>
            <p>Upload an XML/JSON/text document or paste content to receive an anonymized version.</p>
            {% if error %}
                <p class="error">{{ error }}</p>
            {% endif %}
            <form method="post" enctype="multipart/form-data">
                <label for="document">Upload file:</label>
                <input type="file" name="document" id="document" accept=".xml,.json,.txt,.csv,.log">
                <p><strong>OR</strong></p>
                <label for="text_input">Paste text:</label>
                <textarea name="text_input" id="text_input" placeholder="Paste XML, JSON, or plain text">{{ original_text }}</textarea>
                <div style="margin-top: 1rem;">
                    <label for="detected_type">Detected type:</label>
                    <input type="text" id="detected_type" value="{{ detected_type }}" readonly>
                    <button type="submit">Anonymize</button>
                </div>
            </form>

            {% if anonymized_text %}
            <div class="row" style="margin-top: 2rem;">
                <div class="column">
                    <h2>Anonymized Output</h2>
                    <textarea readonly>{{ anonymized_text }}</textarea>
                </div>
                <div class="column">
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
            </div>
            {% endif %}
        </div>
    </body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
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

    return render_template_string(
        TEMPLATE,
        original_text=original_text,
        anonymized_text=anonymized_text,
        detected_type=detected_type,
        mappings=mappings,
        error=error,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host="0.0.0.0", port=port, debug=debug)
