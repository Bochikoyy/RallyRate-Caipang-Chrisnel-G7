# RallyRate

Django full-stack pickleball club, open-play matchmaking, match verification, and **1.000–8.000 performance rating** platform. Server-rendered Django templates power the responsive web/mobile interface and Supabase PostgreSQL serves as the relational database.

## Core Feature (PD2 Vertical Slice) & Implemented Modules

### 1. Match Logging, Mutual Score Verification & Dispute Workflow (`apps.matches`)
- **Individual Peer Match Logging (`/matches/new/`):** Logged-in players record Singles or Doubles games (single game or Best-of-3 to 11, win by 2) with full pickleball score, date, court, and roster validation.
- **Mutual Peer Verification (`/matches/<id>/verify/`, `/matches/<id>/edit/`, `/matches/<id>/dispute/`):**
  - Submitted peer matches remain `Pending` (`0.000` rating impact) until an opposing player confirms the result (`0.6x` peer match weight).
  - **Mutual Counter-Edit Protection:** If an opponent edits a pending or disputed score, submission ownership flips to the editor, self-confirmation is blocked, and the original recorder is notified to confirm the updated score. Once `Verified`, peer matches are locked from unilateral edits.
  - **Delete & Dispute Handling (`/matches/<id>/delete/`):** Submitters can delete their own `Pending` matches; disputed club matches can be reviewed and resolved by Club Hosts/Co-hosts with automatic chronological rating recalculation.

### 2. Multi-Club Management, Open-Play Sessions & Match Generator (`apps.clubs`)
- **Clubs & Role-Based Access (`/clubs/`, `/clubs/create/`, `/clubs/join/`, `/clubs/<slug>/manage/`):**
  - Any player can create a club (becoming **Host**) or join clubs via the public directory or instant **invite code** (e.g., `RR-PD2TST`).
  - **Hosts** and **Co-hosts** manage club details, member approvals, role promotions, invite code rotation, and club deletion.
- **Open-Play Sessions & Smart Match Generator (`/clubs/<slug>/events/...`):**
  - Hosts and Co-hosts schedule Singles or Doubles sessions with configurable court counts, player caps (with automatic **waitlist** promotion), and matchmaking modes (**Balanced Skill**, **Round Robin**, **Random Shuffle**, or manual custom court pairings) with fair sit-out rotation.
  - **Direct Courtside Host Score Entry:** Hosts record Game 1–3 scores directly on the court board to verify session games (`1.0x` club session weight) and immediately update ratings.

### 3. 1.000–8.000 Performance Rating Engine & Dual Leaderboards (`apps.ratings`, `apps.clubs`)
- **Performance Rating Engine (`apps/ratings/engine.py`):**
  - Separate Doubles and Singles ratings (`1.000–8.000`, starting at `3.000`) evaluating team rating averages, expected win probability, and margin of victory.
  - **0.500 Mismatch Protection:** Favorites winning against opponents rated `>= 0.500` lower receive `0.000` delta to prevent rating inflation, while underdog upsets earn full credit.
  - **Immutable Rating Ledger (`/ratings/history/`):** Stores pre-match, post-match, and delta records in `RatingHistory` with an interactive SVG progression chart and full chronological replay when club matches are updated or deleted.
- **Club & Local Leaderboards (`/leaderboard/`, `/clubs/<slug>/leaderboard/`):**
  - View **Club Standings** (scoped to active members of a specific club) and **Local Standings** (community-wide rankings) across Doubles and Singles.

### 4. Unified Notification System & Standard PD1 Account Flows (`apps.accounts`)
- **In-App Notifications (`/accounts/notifications/`):** Real-time unread badges (desktop **Court Hub** sidebar + mobile topbar bell popover) and filterable inbox alerting players on peer match submissions, score edits, confirmations, disputes, new clubs, membership updates, and court matchups.
- **Standard PD1 Account Features:** Player Registration (`/accounts/signup/`), Email/Username Login & Logout (`/accounts/login/`, `/accounts/logout/`), Unified Player Dashboard (`/`), and Profile Management (`/accounts/profile/`).

## Local Setup

1. Create and activate a Python virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and configure `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, and your Supabase PostgreSQL `DATABASE_URL`.
4. Apply database migrations:
   ```powershell
   python manage.py migrate
   ```
5. *(Optional)* Seed evaluation test accounts and sample club/match data:
   ```powershell
   python manage.py seed_test_accounts
   ```
6. Start the development server and open `http://127.0.0.1:8000/`:
   ```powershell
   python manage.py runserver
   ```
7. Run the automated PostgreSQL test suite:
   ```powershell
   python manage.py test apps.accounts apps.clubs apps.matches apps.ratings --keepdb
   ```

## Evaluation Test Accounts

| Role | Email | Password | Notes |
|---|---|---|---|
| **Club Host** | `host.test@rallyrate.app` | `RallyTest123!` | Host of *Cebu Pickleball Test Club* (`RR-PD2TST`); creates sessions, generates matchups, records court scores |
| **Club Co-host** | `cohost.test@rallyrate.app` | `RallyTest123!` | Co-host of *Cebu Pickleball Test Club*; manages sessions, court pairings, and member approvals |
| **Club Member / Player** | `member.test@rallyrate.app` | `RallyTest123!` | Active club member & casual peer match submitter |
| **Opposing Player** | `opponent.test@rallyrate.app` | `RallyTest123!` | Has a pending singles match from `member.test@rallyrate.app` ready to confirm, edit, or dispute |
