# RallyRate architecture

RallyRate is a Django modular monolith. A single Django project serves the full application through server-rendered Django views and templates backed by Supabase PostgreSQL.

## App boundaries

- `apps.accounts`: player registration, email/username authentication, unified player dashboard, profile management, and the unified in-app `Notification` inbox and context processor.
- `apps.clubs`: multi-club memberships (`Host` / `Co-host` / `Member`), invite codes, `ClubEvent` open-play sessions, balanced/round-robin/shuffle match generation with sit-out rotation, direct host score entry, and Club + Local leaderboards.
- `apps.matches`: Singles/Doubles match records (`club_event` and `casual_peer` sources), pickleball Best-of-3 score validation, mutual peer verification (including counter-edit re-verification), and host dispute resolution.
- `apps.ratings`: `1.000–8.000` performance rating engine (`PlayerRatingProfile`, `RatingHistory`), `0.500` mismatch protection, reliability scaling, chronological recalculation, and rating progression charts.
- `apps.imports`: reserved module for upcoming CSV and external roster/event imports.

## Repository map

```text
RallyRate/
├── apps/                 # Django feature apps (accounts, clubs, matches, ratings, imports)
├── config/               # Project settings and root URL configuration
├── docs/                 # Architecture docs, proposal, charter, schedule, and PD reports
├── static/               # Shared CSS, images, and browser assets
├── templates/            # Shared Court Hub layout and feature templates
├── .env.example          # Safe environment-variable template
├── manage.py
├── requirements.txt
└── README.md
```

## Conventions

- Keep feature logic with its Django app; use shared templates/static assets only for reusable presentation.
- Cross-app model relationships refer to users through `settings.AUTH_USER_MODEL` and string model references (`"clubs.Club"`, `"matches.Match"`).
- Keep secrets in local `.env`; commit only `.env.example` with placeholders.
- Use Supabase PostgreSQL for local and hosted application data.
- Keep migrations with their owning app and commit schema changes together with the corresponding feature branch.
