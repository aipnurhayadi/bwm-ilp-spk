# bwm-ilp-spk FastAPI Boilerplate

A FastAPI starter kit configured for MySQL with asynchronous SQLAlchemy sessions and Alembic migrations.

## Features

- FastAPI application structure with versioned routers (`/api/v1`).
- Asynchronous SQLAlchemy setup using the `asyncmy` MySQL driver.
- Alembic configuration wired for async migrations and an initial `users` table migration.
- Pydantic schemas and example CRUD endpoints for users.
- Environment-driven configuration powered by `pydantic-settings`.

## Requirements

- Python 3.11+
- MySQL 8+
- Virtual environment (already available as `.venv` according to the project setup).

## Getting started

1. **Install dependencies**

   ```powershell
   pip install -r requirements.txt
   ```

2. **Configure environment variables**

   Copy the sample configuration and adjust the MySQL credentials:

   ```powershell
   Copy-Item .env.example .env
   ```

   Update `DATABASE_URL` inside `.env` with your actual credentials:

   ```
   mysql+asyncmy://<user>:<password>@<host>:<port>/<database>
   ```

3. **Apply database migrations**

   ```powershell
   alembic upgrade head
   ```

4. **Run the FastAPI app**

   ```powershell
   uvicorn app.main:app --reload
   ```

   The API will be available at http://127.0.0.1:8000 (interactive docs at `/docs`).

## Database migrations

- Create a new migration after modifying models:

  ```powershell
  alembic revision --autogenerate -m "<describe change>"
  ```

- Apply migrations:

  ```powershell
  alembic upgrade head
  ```

- Revert the last migration:

  ```powershell
  alembic downgrade -1
  ```

Alembic pulls metadata from `app.db.base` to discover models. Ensure new SQLAlchemy models are imported there.

## Project structure

```
app/
  api/
    deps.py
    v1/
      router.py
      endpoints/
        users.py
  core/
    config.py
  db/
    base.py
    session.py
  models/
    base.py
    user.py
  schemas/
    user.py
  main.py
alembic/
  env.py
  logging.ini
  script.py.mako
  versions/
    202410080001_create_users_table.py
```

## Running tests

Currently no automated tests are provided. Add your preferred test framework (e.g., `pytest`) and start covering the API as you build features.
