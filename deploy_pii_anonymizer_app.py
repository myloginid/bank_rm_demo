"""
CLI helper to deploy or update the PII anonymizer Flask application on
Cloudera Machine Learning / CDSW using the public REST API.

Usage:
    python deploy_pii_anonymizer_app.py --name "PII Anonymizer" --subdomain pii-anon

By default the script reads configuration from environment variables:

    CML_HOST / CDSW_API_URL       - API endpoint, e.g. https://ml.example.com/api/v1
    CML_API_KEY / CDSW_API_KEY    - Personal access token with application rights
    CML_PROJECT_ID / CDSW_PROJECT_ID - Target project identifier

All options can also be provided explicitly through CLI flags. The script
is idempotent: if an application with the given name or subdomain already
exists it will be updated, otherwise it will be created.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Optional

from cmlapi.api.cml_service_api import CMLServiceApi
from cmlapi.api_client import ApiClient
from cmlapi.configuration import Configuration
from cmlapi.models.application import Application
from cmlapi.models.create_application_request import CreateApplicationRequest

DEFAULT_APP_NAME = "PII Anonymizer"
DEFAULT_SUBDOMAIN = "pii-anonymizer"
DEFAULT_SCRIPT = "PORT=8080 python app.py"
DEFAULT_KERNEL = "Python 3.13"
DEFAULT_CPU = 2.0
DEFAULT_MEMORY = 4_000  # MB
POLL_INTERVAL = 5
TIMEOUT = 600


def resolve_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def build_client(host: str, api_key: str, verify_ssl: bool = True) -> CMLServiceApi:
    config = Configuration()
    config.host = host
    config.api_key = {"ApiKeyAuth": api_key}
    config.api_key_prefix = {"ApiKeyAuth": "Bearer"}
    config.verify_ssl = verify_ssl
    client = ApiClient(configuration=config)
    return CMLServiceApi(client)


def find_application(api: CMLServiceApi, project_id: str, name: str, subdomain: str):
    existing = api.list_applications(project_id)
    matches = [
        app
        for app in existing.applications or []
        if app.name == name or app.subdomain == subdomain
    ]
    return matches[0] if matches else None


def wait_for_status(api: CMLServiceApi, project_id: str, application_id: str, target_status: str) -> Application:
    """Poll until the application reaches the desired status or times out."""
    deadline = time.time() + TIMEOUT
    last_status = None
    while time.time() < deadline:
        app = api.get_application(project_id, application_id)
        last_status = getattr(app.status, "value", None) or app.status or ""
        normalized = last_status.lower()
        if normalized == target_status.lower():
            return app
        if normalized == "failed":
            raise RuntimeError(f"Application deployment failed (status=failed)")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Timed out waiting for application to reach status '{target_status}'. Last status: {last_status}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy or update the PII anonymizer CDSW application.")
    parser.add_argument("--host", default=resolve_env("CML_HOST", "CDSW_API_URL"), help="CML/CDSW API host (default: env CML_HOST or CDSW_API_URL)")
    parser.add_argument("--api-key", default=resolve_env("CML_API_KEY", "CDSW_API_KEY"), help="CML/CDSW API key (default: env CML_API_KEY or CDSW_API_KEY)")
    parser.add_argument("--project-id", default=resolve_env("CML_PROJECT_ID", "CDSW_PROJECT_ID"), help="Target project ID (default: env CML_PROJECT_ID or CDSW_PROJECT_ID)")
    parser.add_argument("--name", default=DEFAULT_APP_NAME, help="Application display name")
    parser.add_argument("--subdomain", default=DEFAULT_SUBDOMAIN, help="Application subdomain (URL slug)")
    parser.add_argument("--script", default=DEFAULT_SCRIPT, help="Launch command for the application")
    parser.add_argument("--kernel", default=DEFAULT_KERNEL, help="Kernel/runtime name (matches dropdown in UI)")
    parser.add_argument("--cpu", type=float, default=DEFAULT_CPU, help="CPU cores requested for the application")
    parser.add_argument("--memory", type=int, default=DEFAULT_MEMORY, help="Memory (MB) requested for the application")
    parser.add_argument("--description", default="Flask UI for anonymizing XML/JSON/text using transformers.", help="Application description")
    parser.add_argument("--skip-wait", action="store_true", help="Do not wait for the application to reach RUNNING state")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL verification for self-signed workspaces")
    parser.add_argument("--domain", default=resolve_env("CML_DOMAIN", "CDSW_DOMAIN"), help="Workspace domain used to construct the application URL")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if not args.host:
        print("Error: API host not provided. Use --host or set CML_HOST / CDSW_API_URL.", file=sys.stderr)
        return 2
    if not args.api_key:
        print("Error: API key not provided. Use --api-key or set CML_API_KEY / CDSW_API_KEY.", file=sys.stderr)
        return 2
    if not args.project_id:
        print("Error: Project ID not provided. Use --project-id or set CML_PROJECT_ID / CDSW_PROJECT_ID.", file=sys.stderr)
        return 2

    api = build_client(args.host, args.api_key, verify_ssl=not args.no_verify_ssl)

    existing = find_application(api, args.project_id, args.name, args.subdomain)
    if existing:
        print(f"Updating existing application '{existing.name}' (ID: {existing.id})...")
        update_body = Application(
            name=args.name,
            subdomain=args.subdomain,
            description=args.description,
            script=args.script,
            kernel=args.kernel,
            cpu=args.cpu,
            memory=args.memory,
        )
        app = api.update_application(update_body, args.project_id, existing.id)
        application_id = app.id
    else:
        print(f"Creating application '{args.name}' in project {args.project_id}...")
        request = CreateApplicationRequest(
            project_id=args.project_id,
            name=args.name,
            subdomain=args.subdomain,
            description=args.description,
            script=args.script,
            kernel=args.kernel,
            cpu=args.cpu,
            memory=args.memory,
        )
        app = api.create_application(request)
        application_id = app.id

    if args.skip_wait:
        print("Skipping wait for RUNNING status.")
        return 0

    print("Waiting for application to reach RUNNING status...")
    final_app = wait_for_status(api, args.project_id, application_id, "running")
    if args.domain:
        protocol = "https://" if args.host.startswith("https") else "http://"
        print(f"Application running at: {protocol}{args.domain}/apps/{args.subdomain}")
    else:
        print("Application reported RUNNING. Retrieve the URL from the CDSW UI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
