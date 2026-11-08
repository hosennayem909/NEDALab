# NEDA LAB

Professional research platform for cleaning, aggregating, and forecasting datasets.

Stack: FastAPI + PostgreSQL + SQLAlchemy (backend) | HTML/CSS/JS + Tailwind + Chart.js (frontend)

## Features

- Auth: register, login, JWT, bcrypt, 3 roles (admin/researcher/viewer)
- Profile: edit name, change password, activity stats
- Data Hub: CSV/Excel upload, cleaning wizard (minimal/standard/aggressive/custom)
- Preview: table, statistics, cleaning report
- Aggregation: group by day/week/month
- Workspaces: teams with role-based access
- Forecasting: 5 models (linear, moving_average, exponential_smoothing, polynomial, arima)
- Predictions: chart + table, MAE/RMSE/MAPE
- Dashboard: analytics charts
- Search, filter, sort
- Notifications inbox
- Dark mode
- CSV export

## Quick Start

Backend:
    cd NEDALAB/backend
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Frontend: open frontend/index.html with Live Server.

URLs:
- Frontend: http://127.0.0.1:5500/NEDALAB/frontend/
- API docs: http://127.0.0.1:8000/docs

## Structure

    NEDALAB/
      backend/
        core/          config, database, security, deps
        auth/          users
        data_hub/      datasets, cleaning, aggregation, analytics
        workspace/     teams + RBAC
        forecasting/   models + predictions
        notifications/ inbox
        main.py
        requirements.txt
      frontend/
        shared/        api, auth, ui, theme, dark-mode, notifications
        login/ register/ dashboard/ dataset/
        workspace/ forecast/ profile/
        index.html

## Docs

- SETUP.md - Installation
- ARCHITECTURE.md - Technical details

## License

MIT
