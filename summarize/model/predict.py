from __future__ import annotations

"""CML model entrypoint for BART summarisation."""

import os
from typing import Any, Dict

from transformers import pipeline


MODEL_ID = os.environ.get("BART_MODEL_ID", "facebook/bart-large-cnn")
_summarizer = pipeline("summarization", model=MODEL_ID)


def predict(data: Any) -> Dict[str, str]:
    """Return a concise summary for the provided payload."""

    if isinstance(data, dict):
        text = data.get("input") or data.get("text")
    else:
        text = data

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Input payload must contain text to summarise.")

    result = _summarizer(text.strip(), max_length=130, min_length=30, do_sample=False)
    return {"summary": result[0]["summary_text"]}
