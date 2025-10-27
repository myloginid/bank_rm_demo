"""
Service-layer helpers for the Relationship Manager productivity demo.

Each class below includes placeholder implementations that show where real
integrations would be wired in (e.g. Microsoft Graph, call recording, speech
to text, summarisation).  They return mocked payloads so the demo UI can run
end to end without external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import uuid


def _generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@dataclass
class Meeting:
    rm_name: str
    client_name: str
    objective: str
    scheduled_for: datetime
    duration_minutes: int
    event_id: str = field(default_factory=lambda: _generate_id("evt"))
    notes: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    recording_id: Optional[str] = None


class SmartScheduler:
    """Placeholder wrapper for Microsoft Graph meeting orchestration."""

    def schedule_meeting(
        self,
        rm_name: str,
        client_name: str,
        scheduled_for: datetime,
        duration_minutes: int,
        objective: str,
    ) -> Dict[str, str]:
        """
        Pretend to call Microsoft Graph to create a meeting invitation.

        Replace the body of this method with a real Graph API call:
        https://learn.microsoft.com/graph/api/user-post-events
        """
        payload = {
            "status": "success",
            "graph_event_id": _generate_id("graph"),
            "join_url": "https://teams.microsoft.com/l/meetup-join/placeholder",
            "rm_name": rm_name,
            "client_name": client_name,
            "scheduled_for": scheduled_for.isoformat(),
            "duration_minutes": duration_minutes,
            "objective": objective,
        }
        return payload


class CallAutomation:
    """Placeholder for recording calls and attaching artifacts to meetings."""

    def start_recording(self, meeting: Meeting) -> Dict[str, str]:
        """
        Simulate a call recording session.  Replace this with your provider's
        SDK (e.g. Teams, Zoom, Twilio).
        """
        meeting.recording_id = _generate_id("rec")
        return {
            "status": "recording_started",
            "recording_id": meeting.recording_id,
            "details": "Recording service invoked (placeholder).",
        }

    def ingest_transcript(self, meeting: Meeting, transcript_text: str) -> Dict[str, str]:
        """
        Store the raw transcript and return metadata.  Real implementations
        might push this to blob storage or a knowledge base.
        """
        storage_id = _generate_id("trn")
        return {
            "status": "stored",
            "storage_id": storage_id,
            "recording_id": meeting.recording_id,
            "characters": len(transcript_text),
        }


class TranscriptProcessor:
    """Placeholder for LLM-powered summarisation and action item extraction."""

    def summarise(self, transcript_text: str) -> Dict[str, List[str] | str]:
        """
        Produce a synthetic summary.  Replace with an LLM call and/or Azure AI.
        """
        if not transcript_text.strip():
            return {"summary": "No transcript provided.", "action_items": []}

        sentences = [line.strip() for line in transcript_text.splitlines() if line.strip()]
        summary = sentences[0] if sentences else transcript_text[:140]
        action_items = [
            sentence for sentence in sentences if sentence.lower().startswith(("action", "follow up", "task"))
        ]
        return {"summary": summary, "action_items": action_items}


class MeetingRepository:
    """Simple in-memory meeting store for the demo."""

    def __init__(self) -> None:
        self._meetings: Dict[str, Meeting] = {}

    def add(self, meeting: Meeting) -> Meeting:
        self._meetings[meeting.event_id] = meeting
        return meeting

    def get(self, event_id: str) -> Optional[Meeting]:
        return self._meetings.get(event_id)

    def list_ordered(self) -> List[Meeting]:
        return sorted(self._meetings.values(), key=lambda meeting: meeting.scheduled_for)

    def append_note(self, event_id: str, note: str) -> None:
        meeting = self._meetings.get(event_id)
        if meeting:
            meeting.notes.append(note)

    def update_summary(self, event_id: str, summary: str) -> None:
        meeting = self._meetings.get(event_id)
        if meeting:
            meeting.summary = summary
