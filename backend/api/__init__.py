"""FastAPI route modules.

Each module owns a small slice of the surface area:

  officers.py   — list officers (the picker)
  tenders.py    — CRUD + state transitions
  documents.py  — upload, list, page+word fetch
  bidders.py    — register, debarment check
  criteria.py   — extract trigger, list, edit, approve
  checklist.py  — auto-match, list, decide, finalize
  evaluations.py — run, list, decide, second-officer, matrix, replay, reproduce
  anomalies.py  — list, dismiss
  chat.py       — Copilot SSE streaming
  reports.py    — generate, list, download
  audit.py      — get_trail, verify
"""
