# Relationship Manager Productivity Demo

This prototype showcases how bank Relationship Managers (RMs) can streamline
client engagement by centralising three workflows:

1. **Intelligent scheduling** – captures the data required to create a meeting
   invitation via Microsoft Graph (placeholder).
2. **Live note-taking** – records progress updates during the engagement.
3. **Automatic summarisation** – ingests a call transcript and produces a
   synthetic summary plus action items (placeholder LLM).

The application ships with mocked service integrations so it can be explored
offline, while clearly marking where production APIs (Graph, call recording,
speech-to-text, summarisation) should be wired in.

## Running the demo

```bash
python -m productivity.app
```

Then open `http://127.0.0.1:5000/` to access the dashboard.

### What happens behind the scenes?

- **Meeting scheduling** – `services.SmartScheduler.schedule_meeting` shows the
  payload you would post to the Microsoft Graph `/events` endpoint and returns
  mocked IDs.
- **Call automation** – `services.CallAutomation` mimics starting a recording
  session and storing the transcript.
- **Summarisation** – `services.TranscriptProcessor.summarise` performs a
  simple heuristic summary so the UX behaves. Replace it with an LLM call to
  something like Azure OpenAI or a Hugging Face model for production.

## Extending the prototype

- Swap the placeholder services with real integrations.
- Persist meetings in a database (Postgres, MongoDB, etc.).
- Connect to a task management system (e.g. Microsoft Planner) to push action
  items created from transcripts.
- Embed dashboards highlighting meeting frequency, coverage, and follow-up SLA
  adherence.
