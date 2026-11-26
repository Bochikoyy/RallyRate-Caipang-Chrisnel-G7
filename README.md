# RallyRate

Django full-stack pickleball club, open-play matchmaking, and **1.000–8.000 DUPR-style performance rating** platform. Server-rendered Django templates power the frontend and Supabase PostgreSQL serves as the database.

## Implemented Features

### 1. Player Accounts & Unified Workspace (`apps.accounts`)
- **Player-First Registration (`/accounts/signup/`):** Every member registers directly as a player starting at **3.000** on the `1.000–8.000` rating scale (separate Doubles & Singles ratings).
- **Email Authentication (`/accounts/login/`, `/accounts/logout/`):** Case-insensitive email sign-in with CSRF-protected session management.
- **Unified Player Dashboard (`/`):** Live Doubles & Singles ratings, reliability percentages, verified `W–L` record, pending peer confirmations, active club shortcuts, recent match rating deltas, and top local leaders.
- **Player Profile (`/accounts/profile/`):** Manage personal details, preferred paddle, home court, and view active club memberships & player rating card.

### 2. Reclub-Style Clubs, Co-Hosts & Open-Play Match Generator (`apps.clubs`)
- **Clubs & Invite Codes (`/clubs/`, `/clubs/create/`, `/clubs/join/`):**
  - Any player can create a club (becoming **Host**) or join existing clubs via public directory or instant **invite code** (e.g., `RR-7K4M9P`).
  - **Hosts** can promote members to **Co-host**, transfer Host ownership, rotate invite codes, and approve/manage club rosters (`/clubs/<slug>/manage/`).
- **Club Games / Open-Play Sessions (`/clubs/<slug>/events/...`):**
  - Hosts and Co-hosts create Singles or Doubles sessions with configurable court counts, player caps (with automatic **waitlist** promotion), and matchmaking modes.
  - **Smart Match Generator:** Fair sit-out rotation (`games_played`) + **Balanced Rating** pairing (`#1 + #4` vs `#2 + #3`), **Round Robin** minimal-repeat rotation, **Random Shuffle**, or manual custom matchups.
  - **Direct Host Score Entry:** Hosts input Game 1–3 scores right on the live court board to immediately verify matches (`1.0x` club weight) and update player ratings.

### 3. Individual Peer Match Logging & Verification (`apps.matches`)
- **Peer Match Logging (`/matches/new/`):** Players can independently log Singles or Doubles matches (single game or Best-of-3, optionally linked to a club).
- **Opponent Verification & Disputes (`/matches/<id>/verify/`, `/matches/<id>/dispute/`):**
  - Opponents confirm `Pending` scores (`0.6x` peer weight) or flag an issue (`Disputed`).
  - Club Hosts and Co-hosts oversee club matches, resolve disputes, and edit/delete records with automatic chronological rating recalculation.

### 4. 1.000–8.000 DUPR-Style Rating Engine & Dual Leaderboards (`apps.ratings`, `apps.clubs`)
- **Performance vs. Expectation Engine (`apps/ratings/engine.py`):**
  - Evaluates team rating averages, expected score share, and **margin of victory** (point share + outcome).
  - **0.500 Mismatch Protection:** When opposing teams differ by `>= 0.500` and the favorite wins, ratings remain unchanged (`0.000` delta); underdog upsets earn full rewards.
  - **Source & Reliability Scaling:** Dynamic K-factor scales from `0.40` (new players) to `0.12` (established `100%` reliability players), weighting `club_event` (`1.0x`) above `casual_peer` (`0.6x`).
  - **Zero-Drift Ledger:** Immutable `RatingHistory` entries per match with full chronological replay when verified scores are edited or removed.
- **Dual Leaderboards (`/leaderboard/`, `/clubs/<slug>/leaderboard/`):**
  - Switch between **Local Standings** (all players) and **Club Standings** (club members + club `W–L`), with **Doubles / Singles** and **All / Established (≥30% reliability)** filters.

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
3. Configure `.env` from `.env.example` (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`).
4. Apply database migrations:
   ```powershell
   python manage.py migrate
   ```
5. Run automated tests:
   ```powershell
   python manage.py test apps.accounts apps.clubs apps.matches apps.ratings --keepdb
   ```
