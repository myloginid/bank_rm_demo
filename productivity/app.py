from __future__ import annotations

from datetime import datetime
from flask import Flask, flash, redirect, render_template, request, url_for

from .services import (
    CallAutomation,
    Meeting,
    MeetingRepository,
    SmartScheduler,
    TranscriptProcessor,
)

app = Flask(__name__)
app.secret_key = "rm-productivity-demo"  # For flash messages; replace in production.

scheduler = SmartScheduler()
automation = CallAutomation()
processor = TranscriptProcessor()
MEETINGS: MeetingRepository = MeetingRepository()


@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        meetings=MEETINGS.list_ordered() if MEETINGS else [],
    )


@app.route("/schedule", methods=["POST"])
def schedule():
    try:
        rm_name = request.form["rm_name"].strip()
        client_name = request.form["client_name"].strip()
        objective = request.form["objective"].strip()
        scheduled_for_str = request.form["scheduled_for"].strip()
        duration_minutes = int(request.form.get("duration_minutes", "30"))
    except (KeyError, ValueError):
        flash("Missing or invalid scheduling details.", "error")
        return redirect(url_for("dashboard"))

    if not rm_name or not client_name or not scheduled_for_str:
        flash("Relationship Manager, client, and time are required.", "error")
        return redirect(url_for("dashboard"))

    scheduled_for = datetime.fromisoformat(scheduled_for_str)

    graph_response = scheduler.schedule_meeting(
        rm_name=rm_name,
        client_name=client_name,
        scheduled_for=scheduled_for,
        duration_minutes=duration_minutes,
        objective=objective,
    )

    meeting = Meeting(
        rm_name=rm_name,
        client_name=client_name,
        objective=objective,
        scheduled_for=scheduled_for,
        duration_minutes=duration_minutes,
    )
    MEETINGS.add(meeting)

    flash(
        f"Meeting scheduled via Microsoft Graph placeholder (event {graph_response['graph_event_id']}).",
        "success",
    )
    return redirect(url_for("dashboard"))


@app.route("/notes", methods=["POST"])
def record_notes():
    event_id = request.form.get("event_id", "").strip()
    note = request.form.get("note", "").strip()
    if not event_id or not note:
        flash("Select a meeting and add a note.", "error")
        return redirect(url_for("dashboard"))

    if not MEETINGS or not MEETINGS.get(event_id):
        flash("Unknown meeting.", "error")
        return redirect(url_for("dashboard"))

    MEETINGS.append_note(event_id, note)
    flash("Note captured for the meeting.", "success")
    return redirect(url_for("dashboard"))


@app.route("/transcripts", methods=["POST"])
def process_transcript():
    event_id = request.form.get("event_id_transcript", "").strip()
    transcript = request.form.get("transcript", "")

    meeting = MEETINGS.get(event_id) if MEETINGS else None
    if not meeting:
        flash("Select a valid meeting before uploading a transcript.", "error")
        return redirect(url_for("dashboard"))

    automation.start_recording(meeting)
    automation.ingest_transcript(meeting, transcript)
    summary_payload = processor.summarise(transcript)

    summary_lines = [summary_payload.get("summary", "")]
    action_items = summary_payload.get("action_items", [])
    if action_items:
        summary_lines.append("\nAction items:")
        summary_lines.extend(f"- {item}" for item in action_items)

    MEETINGS.update_summary(event_id, "\n".join(summary_lines))
    flash("Transcript processed and summary attached.", "success")
    return redirect(url_for("dashboard"))


def create_demo_meetings() -> None:
    """Seed the repository with illustrative data."""
    if MEETINGS and MEETINGS.list_ordered():
        return

    sample = Meeting(
        rm_name="Anita Gomez",
        client_name="Northwind Trading",
        objective="Portfolio review and Q1 expansion plan",
        scheduled_for=datetime.now(),
        duration_minutes=45,
    )
    MEETINGS.add(sample)


def main() -> None:
    create_demo_meetings()
    app.run(debug=True)


if __name__ == "__main__":
    main()
