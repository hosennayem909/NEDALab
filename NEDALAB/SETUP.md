# Setup

## Prerequisites

- Python 3.12.x (NOT 3.13/3.14)
- PostgreSQL 15+
- pgAdmin 4
- VS Code + Live Server

## 1. Database

pgAdmin 4: Databases > Create > Database, name neda_lab, owner postgres.

## 2. .env

Edit NEDALAB/backend/.env:

    DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/neda_lab
    JWT_SECRET=change_to_long_random_string
    JWT_ALGORITHM=HS256
    JWT_EXPIRE_MINUTES=1440
    CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:5500,http://localhost:5500

## 3. Install

    cd NEDALAB/backend
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt

## 4. Backend

    uvicorn main:app --reload --port 8000

Verify: http://127.0.0.1:8000

## 5. Frontend

VS Code: right-click NEDALAB/frontend/index.html > Open with Live Server.

## 6. First Account

Register with role Admin.

## Troubleshooting

- Backend error: activate venv
- DB error: check .env password
- CORS: add Live Server port to CORS_ORIGINS
- Port busy: use 8001, update api.js
