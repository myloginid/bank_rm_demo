from __future__ import annotations

import json
import os
import sys

import cmlapi


def main() -> None:
    base_url = os.getenv("CML_BASE_URL") or os.getenv("CDSW_API_URL")
    api_key = os.getenv("CDSW_APIV2_KEY") or os.getenv("CML_ACCESS_TOKEN")
    project_ref = os.getenv("CDSW_PROJECT_ID") or os.getenv("CML_PROJECT_ID")

    if not base_url:
        sys.exit("Set CML_BASE_URL or CDSW_API_URL before running this script.")
    if not api_key:
        sys.exit("Set CDSW_APIV2_KEY or CML_ACCESS_TOKEN before running this script.")
    if not project_ref:
        sys.exit("Set CDSW_PROJECT_ID or CML_PROJECT_ID to the project name or UUID.")

    # default_client expects the control-plane URL including /api/v1
    if not base_url.endswith("/api/v1"):
        api_url = base_url.rstrip("/") + "/api/v1"
    else:
        api_url = base_url

    client = cmlapi.default_client(url=api_url, cml_api_key=api_key)

    project = client.get_project(project_id=project_ref)
    print(json.dumps(project.to_dict(), indent=2))


if __name__ == "__main__":
    main()
