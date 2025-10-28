"""
PII anonymization utilities for XML and JSON documents.

This script loads a CPU-friendly named-entity-recognition model and applies
token-level anonymization for detected entities together with a handful of
regex-based PII detectors (emails, phone numbers, SSNs, etc.).

Usage:
    python pii_anonymizer.py

The script reads sample inputs from this directory and writes anonymized copies
to anonymization/output/.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from xml.etree import ElementTree as ET

from transformers import pipeline

ROOT = Path(__file__).resolve().parent
INPUT_XML = ROOT / "sample_data.xml"
INPUT_JSON = ROOT / "sample_data.json"
OUTPUT_DIR = ROOT / "output"
OUTPUT_XML = OUTPUT_DIR / "sample_data.anonymized.xml"
OUTPUT_JSON = OUTPUT_DIR / "sample_data.anonymized.json"

NER_MODEL = "dslim/bert-base-NER"

# Regex patterns for specific PII classes that generic NER may miss.
PII_REGEXES: Dict[str, re.Pattern[str]] = {
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "CREDIT_CARD": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "EMAIL": re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
    "PHONE": re.compile(
        r"\b(?!\d{4}([- ])\d{4}\1\d{4}\1\d{4}\b)(?!\d{15,16}\b)(?:\+?\d{1,3}[-\s]?)?(?:\(?\d{2,4}\)?[-\s]?){2,3}\d{3,4}\b"
    ),
    "DOB": re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
}

# Mapping huggingface entity labels to more descriptive placeholders.
LABEL_MAP = {
    "PER": "PERSON",
    "ORG": "ORGANIZATION",
    "LOC": "LOCATION",
    "MISC": "MISC",
}


@dataclass
class PlaceholderManager:
    """Keeps track of synthetic placeholders for PII values."""

    counters: Dict[str, int]
    lookup: Dict[Tuple[str, str], str]

    def __init__(self) -> None:
        self.counters = defaultdict(int)
        self.lookup = {}

    def get(self, label: str, value: str) -> str:
        key = (label, value)
        if key not in self.lookup:
            self.counters[label] += 1
            self.lookup[key] = f"[{label}_{self.counters[label]}]"
        return self.lookup[key]

    def items(self) -> Iterable[Tuple[Tuple[str, str], str]]:
        return self.lookup.items()


@lru_cache(maxsize=1)
def load_ner_pipeline():
    """Initialises a CPU-only Hugging Face NER pipeline."""
    return pipeline(
        "ner",
        model=NER_MODEL,
        aggregation_strategy="simple",
        device=-1,  # -1 forces CPU
    )


def gather_regex_spans(text: str, manager: PlaceholderManager) -> List[Tuple[int, int, str]]:
    spans: List[Tuple[int, int, str]] = []
    occupied: List[Tuple[int, int]] = []
    for label, pattern in PII_REGEXES.items():
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(start >= s and end <= e for s, e in occupied):
                continue
            value = match.group()
            if label == "PHONE":
                digit_count = sum(ch.isdigit() for ch in value)
                if digit_count >= 12:
                    continue
            placeholder = manager.get(label, value)
            spans.append((start, end, placeholder))
            occupied.append((start, end))
    return spans


def gather_ner_spans(text: str, manager: PlaceholderManager, ner_pipeline) -> List[Tuple[int, int, str]]:
    spans: List[Tuple[int, int, str]] = []
    for entity in ner_pipeline(text):
        raw_label = entity.get("entity_group", "").upper()
        label = LABEL_MAP.get(raw_label, raw_label or "ENTITY")
        start = int(entity["start"])
        end = int(entity["end"])
        value = text[start:end]
        placeholder = manager.get(label, value)
        spans.append((start, end, placeholder))
    return spans


def apply_spans(text: str, spans: List[Tuple[int, int, str]]) -> str:
    if not spans:
        return text

    # Deduplicate and keep the longest span when overlaps occur.
    normalized: Dict[Tuple[int, int], str] = {}
    for start, end, replacement in spans:
        key = (start, end)
        if key in normalized:
            continue
        normalized[key] = replacement

    sorted_spans = sorted(normalized.items(), key=lambda item: item[0][0])
    result: List[str] = []
    cursor = 0
    for (start, end), replacement in sorted_spans:
        if start < cursor:
            # Overlapping span, skip to avoid corrupting prior replacements.
            continue
        result.append(text[cursor:start])
        result.append(replacement)
        cursor = end
    result.append(text[cursor:])
    return "".join(result)


def anonymize_text(text: str, manager: PlaceholderManager, ner_pipeline) -> str:
    spans = gather_regex_spans(text, manager)
    spans.extend(gather_ner_spans(text, manager, ner_pipeline))
    return apply_spans(text, spans)


def anonymize_xml_element(element: ET.Element, manager: PlaceholderManager, ner_pipeline) -> None:
    for node in element.iter():
        if node.text:
            node.text = anonymize_text(node.text, manager, ner_pipeline)
        if node.tail:
            node.tail = anonymize_text(node.tail, manager, ner_pipeline)


def anonymize_xml_string(xml_text: str, manager: PlaceholderManager, ner_pipeline) -> str:
    root = ET.fromstring(xml_text)
    anonymize_xml_element(root, manager, ner_pipeline)
    return ET.tostring(root, encoding="unicode")


def anonymize_xml(path: Path, destination: Path, manager: PlaceholderManager, ner_pipeline) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    anonymize_xml_element(root, manager, ner_pipeline)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def anonymize_json_value(value, manager: PlaceholderManager, ner_pipeline):
    if isinstance(value, str):
        return anonymize_text(value, manager, ner_pipeline)
    if isinstance(value, list):
        return [anonymize_json_value(item, manager, ner_pipeline) for item in value]
    if isinstance(value, dict):
        return {key: anonymize_json_value(val, manager, ner_pipeline) for key, val in value.items()}
    return value


def anonymize_json_string(json_text: str, manager: PlaceholderManager, ner_pipeline) -> str:
    data = json.loads(json_text)
    cleaned = anonymize_json_value(data, manager, ner_pipeline)
    return json.dumps(cleaned, indent=4)


def anonymize_json(path: Path, destination: Path, manager: PlaceholderManager, ner_pipeline) -> None:
    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)

    cleaned = anonymize_json_value(data, manager, ner_pipeline)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as fp:
        json.dump(cleaned, fp, indent=4)


def anonymize_document(content: str, content_type: str) -> Tuple[str, PlaceholderManager]:
    """
    Anonymizes textual content according to the provided type.

    Args:
        content: Raw text payload (XML/JSON/plain).
        content_type: One of {"xml", "json", "text"}.

    Returns:
        Tuple of anonymized text and the placeholder manager describing mappings.
    """

    ner_pipeline = load_ner_pipeline()
    manager = PlaceholderManager()

    if content_type == "xml":
        result = anonymize_xml_string(content, manager, ner_pipeline)
    elif content_type == "json":
        result = anonymize_json_string(content, manager, ner_pipeline)
    else:
        result = anonymize_text(content, manager, ner_pipeline)

    return result, manager


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if not INPUT_XML.exists() or not INPUT_JSON.exists():
        raise FileNotFoundError("Sample data files are missing; run this script from the anonymization directory.")

    logging.info("Loading NER model '%s' (CPU-only)...", NER_MODEL)
    ner_pipeline = load_ner_pipeline()
    manager = PlaceholderManager()

    logging.info("Anonymizing XML: %s", INPUT_XML.name)
    anonymize_xml(INPUT_XML, OUTPUT_XML, manager, ner_pipeline)

    logging.info("Anonymizing JSON: %s", INPUT_JSON.name)
    anonymize_json(INPUT_JSON, OUTPUT_JSON, manager, ner_pipeline)

    logging.info("Anonymized files written to %s", OUTPUT_DIR)
    for (label, original), placeholder in manager.items():
        logging.info("Mapped %s '%s' -> %s", label, original, placeholder)


if __name__ == "__main__":
    main()
