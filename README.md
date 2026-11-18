# RallyRate

Django full-stack web application for pickleball match logging and local skill ratings. Django templates provide the frontend and Supabase PostgreSQL is the database.

## Repository structure

- `apps/` — Django feature modules: accounts, matches, ratings, clubs, imports.
- `config/` — Django project configuration and root URL routing.
- `templates/` and `static/` — shared server-rendered pages and browser assets.
- `Documents/` — supplied project proposal, charter, and Gantt workbook.
- `docs/` — architecture and development notes.

The future feature modules are registered placeholders. Their behavior will be implemented in later project phases. See [docs/architecture.md](docs/architecture.md) for app boundaries and conventions.

## Local setup

1. Python 3.14 is supported. Create and activate a virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set a random `DJANGO_SECRET_KEY` plus the Supabase **Session pooler** PostgreSQL URL. Keep `.env` private.
4. Run database migrations: `python manage.py migrate`
5. Create an admin: `python manage.py createsuperuser`
6. Start the server: `python manage.py runserver`

The project is configured for PostgreSQL only and does not fall back to SQLite.
