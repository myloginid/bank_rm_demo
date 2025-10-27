# PII Anonymization Scaffold

This repository contains sample data and a Python utility for detecting and anonymizing personally identifiable information (PII) in XML and JSON documents using CPU-friendly NLP models.

## Contents

- `anonymization/sample_data.xml` – XML fixture mixing PII and operational text.
- `anonymization/sample_data.json` – JSON fixture with nested structures and PII embedded alongside non-sensitive context.
- `anonymization/pii_anonymizer.py` – Script that runs a Hugging Face NER pipeline (`dslim/bert-base-NER`) with supplemental regex detectors to replace sensitive substrings with deterministic placeholders.
- `anonymization/output/` – Destination for anonymized copies (created on demand).
- `anonymization/requirements.txt` – Minimal dependencies needed to run the script with CPU-only wheels.

## Setup

1. Ensure Python 3.13 (or later) is active (`python --version`).
2. Install CPU wheels for PyTorch and Transformers:
   ```bash
   python -m pip install --user --index-url https://download.pytorch.org/whl/cpu torch
   python -m pip install --user transformers
   ```
   If you need to isolate dependencies, create a virtual environment first (`python -m venv .venv && source .venv/bin/activate`).

## Usage

Run the anonymizer from the repository root:

```bash
python anonymization/pii_anonymizer.py
```

The script will:

- download the `dslim/bert-base-NER` model (first run only),
- scan both sample data files,
- replace detected PII with placeholders like `[PERSON_1]`, `[EMAIL_2]`, `[CREDIT_CARD_1]`,
- and write anonymized versions to `anonymization/output/`.

Refer to the script logs for a mapping between original values and placeholders when auditing results.

## Customization

- To plug in different models, change `NER_MODEL` in `pii_anonymizer.py`.
- Additional regex patterns can be defined in the `PII_REGEXES` dictionary for domain-specific identifiers.
- Replace the sample data files with your own inputs to test broader scenarios; the anonymizer traverses arbitrary nested JSON and XML structures.

## Refinements

- Reorder or adjust `PII_REGEXES` so SSNs and credit cards map to `[SSN_*]` and `[CREDIT_CARD_*]` placeholders instead of the more generic phone label.
- Consider additional post-processing or custom label aggregation to merge adjacent NER spans and eliminate partial-name leftovers (e.g., `Jane Do` + trailing `e`).

## Web Application

A simple Flask interface (`app.py`) wraps the anonymizer so you can upload documents and inspect both anonymized output and detected PII mappings.

### Install Dependencies

```bash
python -m pip install --user -r anonymization/requirements.txt
```

### Run Locally

```bash
PORT=8080 python app.py
```

Navigate to `http://127.0.0.1:8080` (or the CDSW-provided URL) and upload XML/JSON/plain text files or paste content directly.

## Deploying on CDSW

1. From the project terminal, ensure dependencies are installed (see above).
2. In the CDSW UI, create an *Application* pointing to this project.
3. Use the launch command `PORT=8080 python app.py` and choose an engine size with at least 2 CPUs for faster model warm-up.
4. Once the application status is *Running*, CDSW will expose an external URL serving the anonymization UI.
