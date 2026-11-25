# RallyRate

Django full-stack web application for pickleball match logging, opponent score verification, and local skill ratings. Server-rendered Django templates power the frontend and Supabase PostgreSQL serves as the database.

## Implemented Features

### Standard Features (Project Development 1)
- **Account Registration (`/accounts/signup/`):** Sign up as a **Player** or **Club organizer** with personal details, preferred paddle, and home court.
- **Login & Logout (`/accounts/login/`, `/accounts/logout/`):** Email-based member authentication (plus username support for Django admin) and CSRF-protected session logout.
- **Role-Based Dashboards (`/player/`, `/organizer/`):** Automatic role routing from `/` with dedicated metrics and action queues per role.
- **User Profile (`/accounts/profile/`):** Manage name, email, phone number, preferred paddle, and home court.

### Core Feature Vertical Slice — Match Logging & Verification (`apps.matches`)
- **Create (`/matches/new/`):** Log **Singles** or **Doubles** pickleball matches (single-game or **Best-of-3** sets) with partner/opponent selection, venue, date, and final scores. New submissions are linked to `submitted_by` (`ForeignKey` to `User`), store team rosters via `MatchParticipant` (`ManyToMany` to `User`), and start in **Pending verification** status.
- **Read (`/matches/`, `/matches/<id>/`):** Filter matches by status (`All`, `Pending`, `Verified`, `Disputed`) and inspect full match scoreboards, rosters, and verification/dispute audit metadata. Players only see matches they submitted or played in; Club Organizers have club-wide visibility.
- **Update & Delete (`/matches/<id>/edit/`, `/matches/<id>/delete/`):** Submitters can edit or delete their own `Pending` matches; `Verified` and `Disputed` matches are locked from player edits. Club Organizers can update or remove club match records when resolving issues.
- **Opponent Verification & Dispute Resolution (`/matches/<id>/verify/`, `/matches/<id>/dispute/`):**
  - Opposing-team players can **Confirm** a `Pending` score (finalizing it as `Verified`) or **Dispute** it with a required reason (`Disputed`). Submitters and same-team partners cannot self-verify.
  - **Club Organizers** can review pending/disputed matches, edit scores if needed, and **Resolve & Verify** disputed records while retaining dispute audit details.
- **Input Validation & Business Rules:** Enforces required fields, non-future match dates, standard pickleball scoring (no ties, winning score >= 11, win by >= 2), required doubles rosters, duplicate-player prevention across teams, and required dispute reasons.
- **Live Role Dashboard Integration:**
  - **Player Dashboard:** Displays verified `W-L` record, match status counts, an **Awaiting Your Confirmation** queue, and recent matches.
  - **Club Organizer Dashboard:** Displays club-wide match totals, Pending/Disputed counters, and a prioritized **Match Review Queue** (Disputed first).

## Repository Structure

- `apps/` — Django feature modules: `accounts` (implemented), `matches` (implemented), and registered placeholders (`ratings`, `clubs`, `imports`).
- `config/` — Django project settings and root URL routing.
- `templates/` & `static/` — Server-rendered HTML templates and shared CSS/assets.
- `Documents/` — Approved project proposal, charter, and Gantt schedule.
- `docs/` — Architecture notes and phase completion reports.

See [docs/architecture.md](docs/architecture.md) for app boundaries and conventions.

## Local Setup

1. Create and activate a Python virtual environment (Python 3.12+ / 3.14 supported):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and configure:
   - `DJANGO_SECRET_KEY` — random secret key
   - `DJANGO_DEBUG` — `True` for local development
   - `DJANGO_ALLOWED_HOSTS` — `127.0.0.1,localhost`
   - `DATABASE_URL` — Supabase **Session pooler** PostgreSQL connection string (keep `.env` private; it is ignored by Git)
4. Apply database migrations to PostgreSQL:
   ```powershell
   python manage.py migrate
   ```
5. (Optional) Create a Django admin superuser:
   ```powershell
   python manage.py createsuperuser
   ```
6. Start the development server:
   ```powershell
   python manage.py runserver
   ```
7. Run automated tests against PostgreSQL:
   ```powershell
   python manage.py test apps.matches apps.accounts --keepdb
   ```

The project is configured strictly for PostgreSQL and does not fall back to SQLite.
