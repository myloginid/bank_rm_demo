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
python app.py
```

Navigate to `http://127.0.0.1:8080` (or the CDSW-provided URL) and paste text or upload XML/JSON/plain text files, then press **Anonymize** to see the redacted output and detected PII mappings.

## CDSW Application Configuration Reference

The reference CDSW application is configured with the following settings so you can recreate or troubleshoot the deployment quickly:

- Script: `app.py`
- Subdomain: `pii`
- Resources: 2 vCPUs, 8 GB memory, 0 GPUs
- Runtime image: `docker.repository.cloudera.com/cloudera/cdsw/ml-runtime-pbj-workbench-python3.13-standard:2025.09.1-b5`
- Runtime add-on: `hadoop-cli-7.2.17-hf800`
- Environment overrides: `CDSW_APP_POLLING_ENDPOINT=/`

You can retrieve the latest configuration at any time with the CDSW REST API:

```bash
python - <<'PY'
from cmlapi.api.cml_service_api import CMLServiceApi
from cmlapi.api_client import ApiClient
from cmlapi.configuration import Configuration

host = "<workspace_base_url>"  # e.g. https://ml.example.com
api_key = "<personal_access_token>"
project_id = "<project_id>"
application_id = "<application_id>"

config = Configuration()
config.host = host
client = ApiClient(configuration=config)
client.default_headers["Authorization"] = f"Bearer {api_key}"
api = CMLServiceApi(client)

app = api.get_application(project_id, application_id)
print(app.to_dict())
PY
```

Replace the placeholders with your workspace details. The response reflects the current CDSW application configuration (script, runtime, resources, etc.), making it easy to verify settings before updating or redeploying.
