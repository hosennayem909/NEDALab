# Architecture

## Tiers

Frontend (HTML/CSS/JS) -> Backend (FastAPI) -> Database (PostgreSQL)

## Backend Folders

- core/          config, database, security, deps
- auth/          users
- data_hub/      datasets, cleaning, aggregation, analytics
- workspace/     teams + RBAC
- forecasting/   5 models
- notifications/ inbox

## Frontend Folders

- shared/        api.js, auth.js, ui.js, theme.css, dark-mode, notifications
- feature/       each page has HTML + JS

## Database Tables

- users              id, name, email, password_hash, role, created_at
- datasets           id, user_email, filename, row_count, column_count, status, cleaned_path, created_at
- cleaning_reports   id, dataset_id, preset, config_json, log_json, stats_json, created_at
- aggregations       id, source_dataset_id, result_dataset_id, date_column, value_columns_json, frequency, method, report_json, created_by, created_at
- workspaces         id, name, slug, owner_id, created_at
- members            id, workspace_id, user_id, role, created_at
- models             id, dataset_id, name, model_type, target_column, params_json, metrics_json, trained_by, created_at
- forecasts          id, model_id, horizon, predictions_json, created_at
- notifications      id, user_id, type, title, message, link, actor_email, is_read, created_at

## Auth

POST /api/auth/login -> verify bcrypt -> return JWT (24h) -> frontend stores in localStorage -> requests include Authorization: Bearer token.

## RBAC

Global: admin (all data), researcher (own + workspaces), viewer (read-only)
Workspace: admin (control), researcher (view), viewer (read-only)

## Security

bcrypt hashing, JWT expiry, SQLAlchemy parameterized queries, escapeHtml frontend, RBAC per request, file extension whitelist.
