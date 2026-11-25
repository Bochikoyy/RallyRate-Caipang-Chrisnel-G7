# Match management (`apps.matches`)

Implements RallyRate's core Match Logging & Opponent Score Verification vertical slice:

- `models.py` — `Match` and `MatchParticipant` (`submitted_by`, `verified_by`, `disputed_by` FKs + `players` M2M through `MatchParticipant`).
- `forms.py` — `MatchForm` (Singles/Doubles roster & pickleball score validation) and `MatchDisputeForm`.
- `views.py` & `urls.py` — Role-scoped CRUD (`list`, `create`, `detail`, `update`, `delete`) plus `verify` and `dispute` actions under `/matches/`.
- `services.py` — Dashboard summary queries consumed by Player and Club Organizer dashboards.
- `tests.py` — Automated CRUD, validation, permission, verification, and dispute resolution tests.
