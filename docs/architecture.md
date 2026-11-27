# RallyRate architecture

RallyRate is a Django modular monolith. A single Django project serves the full application through server-rendered Django views and templates backed by Supabase PostgreSQL.

## App boundaries

- `apps.accounts`: player registration, email/username authentication, unified player dashboard, and profile management.
- `apps.clubs`: Reclub-style clubs, `Host` / `Co-host` / `Member` roles, invite codes, `ClubEvent` open-play sessions, balanced/round-robin match generation, direct host score entry, and Club + Local leaderboards.
- `apps.matches`: Singles/Doubles match records (`club_event` and `casual_peer` sources), pickleball score validation, opponent verification, and host dispute resolution.
- `apps.ratings`: `1.000–8.000` performance rating engine (`PlayerRatingProfile`, `RatingHistory`), `0.500` mismatch protection, reliability scaling, chronological recalculation, and rating progression charts.
- `apps.imports`: reserved module for future CSV and external roster/event imports.

## Repository map

```text
RallyRate/
├── apps/                 # Django feature apps (accounts, clubs, matches, ratings, imports)
├── config/               # Project settings and root URL configuration
├── docs/                 # Architecture and project documentation
├── Documents/            # Supplied project proposal, charter, and schedule
├── static/               # Shared CSS, images, and browser assets
├── templates/            # Shared and feature templates
├── .env.example          # Safe environment-variable template
├── manage.py
├── requirements.txt
└── README.md
```

## Conventions

- Keep feature logic with its Django app; use shared templates/static assets only for reusable presentation.
- Cross-app model relationships refer to users through `settings.AUTH_USER_MODEL` and string model references (`"clubs.Club"`, `"matches.Match"`).
- Keep secrets in local `.env`; commit only `.env.example` with placeholders.
- Use PostgreSQL for local and hosted application data.
- Keep migrations with their owning app and commit schema changes together with the corresponding feature phase.
