from __future__ import annotations

"""Register and deploy the BART summarization model on CML."""

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Optional

import requests

try:  # pragma: no cover - optional dependency in local dev environments
    import cmlapi
    from cmlapi.models.create_model_build_request import CreateModelBuildRequest
    from cmlapi.models.create_model_deployment_request import CreateModelDeploymentRequest
    from cmlapi.models.create_model_request import CreateModelRequest
except ModuleNotFoundError:  # pragma: no cover
    cmlapi = None  # type: ignore[assignment]


BART_MODEL_ID = "facebook/bart-large-cnn"
DEFAULT_MODEL_NAME = "bart-text-summarizer"
ARTIFACT_BASENAME = "bart_summarizer"


def _build_headers(access_token: Optional[str]) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def register_model_rest(base_url: str, access_token: Optional[str], name: str, description: str = "") -> dict:
    payload = {"name": name, "description": description}
    response = requests.post(
        f"{base_url}/api/v2/registeredModels",
        headers=_build_headers(access_token),
        data=json.dumps(payload),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def create_model_version_rest(
    base_url: str,
    access_token: Optional[str],
    registered_model_id: str,
    model_path: Path,
) -> dict:
    payload: Dict[str, object] = {
        "registeredModelId": registered_model_id,
        "sourceType": "local",
        "sourcePath": str(model_path.resolve()),
    }
    response = requests.post(
        f"{base_url}/api/v2/modelVersions",
        headers=_build_headers(access_token),
        data=json.dumps(payload),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def deploy_model_rest(
    base_url: str,
    access_token: Optional[str],
    project_id: str,
    model_version_id: str,
    workload_size: str,
) -> dict:
    payload = {
        "modelVersionId": model_version_id,
        "targetProject": project_id,
        "deployConfig": {"workloadSize": workload_size},
    }
    response = requests.post(
        f"{base_url}/api/v2/modelDeployments",
        headers=_build_headers(access_token),
        data=json.dumps(payload),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def build_bart_artifact() -> Path:
    """Create a lightweight archive that loads BART lazily at inference time."""

    artifacts_dir = Path(__file__).resolve().parent / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / ARTIFACT_BASENAME
        tmp_path.mkdir(parents=True, exist_ok=True)

        predict_py = tmp_path / "predict.py"
        predict_py.write_text(
            '''from __future__ import annotations

import os

from transformers import pipeline

MODEL_ID = os.environ.get("BART_MODEL_ID", "facebook/bart-large-cnn")
_summarizer = pipeline("summarization", model=MODEL_ID)


def predict(data):
    if isinstance(data, dict):
        text = data.get("input") or data.get("text")
    else:
        text = data
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Input payload must contain text to summarise.")
    result = _summarizer(text.strip(), max_length=130, min_length=30, do_sample=False)
    return {"summary": result[0]["summary_text"]}
''',
            encoding="utf-8",
        )

        requirements = tmp_path / "requirements.txt"
        requirements.write_text(
            "torch>=2.2.0\ntransformers>=4.36.0\n",
            encoding="utf-8",
        )

        archive_base = artifacts_dir / ARTIFACT_BASENAME
        archive_path = Path(
            shutil.make_archive(
                str(archive_base),
                "gztar",
                root_dir=tmp_path,
                base_dir=".",
            )
        )

    return archive_path


def ensure_predict_script() -> Path:
    path = Path(__file__).resolve().parent / "model" / "predict.py"
    if not path.exists():
        raise FileNotFoundError(
            "summarize/model/predict.py is missing. Run this script from the project root."
        )
    return path


def resolve_runtime_identifier(client, runtime_identifier: Optional[str]) -> str:
    if runtime_identifier:
        return runtime_identifier

    response = client.list_runtimes(page_size=1)
    runtimes = getattr(response, "runtimes", [])
    if runtimes:
        return runtimes[0].image_identifier

    raise ValueError(
        "Could not determine a runtime identifier. Provide one via --runtime or set CML_RUNTIME_IDENTIFIER."
    )


def _ensure_api_v1_url(url: str) -> str:
    cleaned = url.rstrip("/")
    if cleaned.endswith("/api/v1"):
        return cleaned
    if cleaned.endswith("/api/v2"):
        return cleaned[:-len("/api/v2")] + "/api/v1"
    return cleaned + "/api/v1"


def _strip_api_suffix(url: str) -> str:
    cleaned = url.rstrip("/")
    for suffix in ("/api/v1", "/api/v2"):
        if cleaned.endswith(suffix):
            return cleaned[: -len(suffix)]
    return cleaned


def build_cmlapi_client(url: Optional[str], api_key: Optional[str]):
    if cmlapi is None:
        return None

    kwargs: Dict[str, Optional[str]] = {}
    if url:
        kwargs["url"] = url
    if api_key:
        kwargs["cml_api_key"] = api_key

    api_url = None
    if kwargs.get("url"):
        api_url = _ensure_api_v1_url(kwargs["url"])
    else:
        env_url = os.getenv("CDSW_API_URL") or os.getenv("CML_BASE_URL")
        if env_url:
            api_url = _ensure_api_v1_url(env_url)

    if api_url:
        kwargs["url"] = api_url

    try:
        return cmlapi.default_client(**kwargs)
    except ValueError:
        return None


def deploy_with_cmlapi(args) -> Dict[str, dict]:
    client = build_cmlapi_client(args.url, args.api_key)
    if client is None:
        raise RuntimeError(
            "Unable to initialise cmlapi client. Provide --url/--api-key or set the appropriate environment variables."
        )

    project_id = args.project_id or os.getenv("CDSW_PROJECT_ID")
    if not project_id:
        raise ValueError("Provide --project-id or set CDSW_PROJECT_ID before running the script.")

    runtime_identifier = resolve_runtime_identifier(client, args.runtime)
    predict_path = ensure_predict_script()
    relative_predict_path = str(predict_path.relative_to(Path.cwd()))

    model_req = CreateModelRequest(
        project_id=project_id,
        name=args.name,
        description=args.description,
        disable_authentication=args.disable_authentication,
    )
    model = client.create_model(model_req, project_id)

    build_req = CreateModelBuildRequest(
        project_id=project_id,
        model_id=model.id,
        file_path=relative_predict_path,
        function_name="predict",
        runtime_identifier=runtime_identifier,
    )
    build = client.create_model_build(build_req, project_id, model.id)

    deploy_req = CreateModelDeploymentRequest(
        project_id=project_id,
        model_id=model.id,
        build_id=build.id,
        cpu=args.cpu,
        memory=args.memory,
        replicas=args.replicas,
    )
    deployment = client.create_model_deployment(deploy_req, project_id, model.id, build.id)

    return {
        "model": model.to_dict(),
        "model_build": build.to_dict(),
        "deployment": deployment.to_dict(),
    }


def deploy_with_rest(args) -> Dict[str, dict]:
    base_url = args.url or os.getenv("CDSW_API_URL")
    if not base_url:
        raise ValueError("Provide --url or export CML_BASE_URL/ CDSW_API_URL.")
    base_url = _strip_api_suffix(base_url)

    access_token = args.api_key or os.getenv("CML_ACCESS_TOKEN") or os.getenv("CDSW_APIV2_KEY")
    project_id = args.project_id or os.getenv("CDSW_PROJECT_ID")
    if not project_id:
        raise ValueError("Provide --project-id or set CDSW_PROJECT_ID before running the script.")

    artifact_path = args.artifact or build_bart_artifact()

    registered = register_model_rest(base_url, access_token, args.name, args.description)
    version = create_model_version_rest(base_url, access_token, registered["id"], artifact_path)
    deployment = deploy_model_rest(base_url, access_token, project_id, version["id"], args.workload)

    return {
        "registered_model": registered,
        "model_version": version,
        "deployment": deployment,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register and deploy a summarization model on CML.")
    parser.add_argument("--name", default=DEFAULT_MODEL_NAME, help="Model name")
    parser.add_argument(
        "--description",
        default=f"BART summarizer seeded from {BART_MODEL_ID}",
        help="Model description",
    )
    parser.add_argument("--project-id", default=os.getenv("CDSW_PROJECT_ID"), help="CML project UUID")
    parser.add_argument("--url", default=os.getenv("CML_BASE_URL") or os.getenv("CDSW_API_URL"), help="CML control plane base URL")
    parser.add_argument(
        "--api-key",
        default=os.getenv("CML_ACCESS_TOKEN") or os.getenv("CDSW_APIV2_KEY"),
        help="CML personal access token",
    )
    parser.add_argument("--runtime", default=os.getenv("CML_RUNTIME_IDENTIFIER"), help="Runtime image identifier to build with")
    parser.add_argument("--artifact", type=Path, default=None, help="Optional prebuilt archive for REST deployment")
    parser.add_argument("--workload", default="S", help="Deployment workload size when using the REST flow (S/M/L)")
    parser.add_argument("--cpu", type=float, default=2.0, help="vCPU allocation for the deployment")
    parser.add_argument("--memory", type=float, default=4.0, help="Memory (GB) for the deployment")
    parser.add_argument("--replicas", type=int, default=1, help="Replica count for the deployment")
    parser.add_argument("--disable-authentication", action="store_true", help="Disable authentication for the deployed model")
    parser.add_argument("--rest-only", action="store_true", help="Force the REST workflow even if cmlapi is available")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        if not args.rest_only and cmlapi is not None:
            result = deploy_with_cmlapi(args)
            print(json.dumps(result, indent=2))
            return
    except Exception as exc:
        print(f"Falling back to REST deployment due to cmlapi error: {exc}")

    result = deploy_with_rest(args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
