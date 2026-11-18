# RallyRate

Django full-stack web application using Django templates and Supabase PostgreSQL.

## Local setup

1. Python 3.14 is supported. Create and activate a virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set a random `DJANGO_SECRET_KEY` plus the Supabase **Session pooler** PostgreSQL URL. Keep `.env` private.
4. Run database migrations: `python manage.py migrate`
5. Create an admin: `python manage.py createsuperuser`
6. Start the server: `python manage.py runserver`

The project is configured to use PostgreSQL only; it does not fall back to SQLite.

## Account feature

Email-based registration and login, player/club-organizer role, preferred paddle and home court profile fields, profile editing, protected dashboard, and Django admin account management.
