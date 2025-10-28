from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


class SummarizationError(RuntimeError):
    """Raised when the summarization service fails."""


@dataclass
class CMLSummarizationConfig:
    endpoint_url: str
    access_token: Optional[str] = None
    project_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> Optional["CMLSummarizationConfig"]:
        endpoint = os.getenv("CML_MODEL_ENDPOINT")
        if not endpoint:
            return None
        return cls(
            endpoint_url=endpoint.rstrip("/"),
            access_token=os.getenv("CML_ACCESS_TOKEN"),
            project_key=os.getenv("CML_PROJECT_KEY"),
        )


class SummarizationClient:
    """Client to talk to a CML deployed model, with graceful fallback."""

    def __init__(self, config: Optional[CMLSummarizationConfig] = None) -> None:
        self.config = config or CMLSummarizationConfig.from_env()

    def summarize(self, text: str) -> str:
        text = text.strip()
        if not text:
            raise SummarizationError("Provide text to summarise.")

        if self.config:
            try:
                return self._summarize_via_cml(text)
            except Exception as exc:  # pragma: no cover - network/runtime handling
                raise SummarizationError(f"CML summarization failed: {exc}") from exc

        return self._fallback_summary(text)

    def _summarize_via_cml(self, text: str) -> str:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.config.access_token:
            headers["Authorization"] = f"Bearer {self.config.access_token}"
        if self.config.project_key:
            headers["X-Project-Key"] = self.config.project_key

        payload: Dict[str, Any] = {"input": text}
        response = requests.post(
            self.config.endpoint_url,
            headers=headers,
            data=json.dumps(payload),
            timeout=20,
        )
        response.raise_for_status()

        data = response.json()
        if isinstance(data, dict):
            summary = data.get("summary") or data.get("output")
            if isinstance(summary, str):
                return summary.strip()
        if isinstance(data, list) and data and isinstance(data[0], str):
            return data[0].strip()

        raise SummarizationError("Unexpected response payload from CML model.")

    def _fallback_summary(self, text: str) -> str:
        sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
        if not sentences:
            return text
        if len(sentences) == 1:
            return sentences[0]
        return ". ".join(sentences[:2]) + "."
