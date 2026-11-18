# RallyRate architecture

RallyRate is a Django modular monolith. A single Django project serves the full application through Django views and templates. Feature domains live in separate Django apps under `apps/` so they can evolve independently while sharing the same project, deployment, and Supabase PostgreSQL database.

## App boundaries

- `apps.accounts`: authentication, user roles, and player profile data.
- `apps.matches`: future match logging and score verification.
- `apps.ratings`: future Elo calculations and rating history.
- `apps.clubs`: future club membership and leaderboards.
- `apps.imports`: future CSV and mock API roster/event imports.

The four future feature apps are registered placeholders. Keep their implementation empty until the related feature is scheduled and approved. Cross-app model relationships should refer to users through `settings.AUTH_USER_MODEL` and avoid importing another app's concrete models directly where a string model reference works.

## Repository map

```text
RallyRate/
├── apps/                 # Django feature apps
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
- Add each feature app's URLs through the project URL configuration when that feature is implemented.
- Keep secrets in local `.env`; commit only `.env.example` with placeholders.
- Use PostgreSQL for local and hosted application data. SQLite is not the project database.
- Keep migrations with their owning app and commit schema changes together with the corresponding feature.
