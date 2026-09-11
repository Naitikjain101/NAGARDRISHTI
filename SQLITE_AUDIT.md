# Urban Watch Phase 5.1 — SQLite Audit

This document is the result of Step 1 in the Phase 5.1 Supabase-First Database Migration plan. It identifies all locations, dependencies, and implementations of the current SQLite database.

## 1. Current Database Status

- **CURRENT DATABASE**: SQLite (via SQLAlchemy)
- **CURRENT DATABASE PATH**: `backend/results/urban_watch.db` (Default, configurable via `URBAN_WATCH_DB_URL` env var)
- **DATABASE URL**: `sqlite:///[path_to_db]`
- **TABLES**: 
  - `videos`
  - `incidents`
  - `traffic_windows`
  - `road_segments`
- **MODELS**: All defined in `backend/db/models.py` inheriting from SQLAlchemy's `DeclarativeBase`.

## 2. Dependencies and Files

### A. Database Implementation Files
All SQLite/SQLAlchemy implementation code is encapsulated within the `backend/db/` package:
- **`backend/db/session.py`**: Handles `create_engine`, `sessionmaker`, and the FastAPI dependency `get_db()`.
- **`backend/db/models.py`**: Defines the SQLite schemas.
- **`backend/db/repository.py`**: Implements the Data Access Object (DAO) pattern with `IncidentRepository`, `VideoRepository`, `TrafficWindowRepository`, and `RoadSegmentRepository`.
- **`backend/db/__init__.py`**: Package initialization.

### B. API Dependencies
The FastAPI routes directly rely on the SQLite session dependency (`get_db`) and the repository classes:
- **`backend/api/routes_incidents.py`**: Uses `get_db` and `IncidentRepository`.
- **`backend/api/routes_traffic.py`**: Uses `get_db` and `TrafficWindowRepository`.
- **`backend/api/routes_system.py`**: Uses `get_db`, `VideoRepository`, `IncidentRepository`, and `RoadSegmentRepository`.
- **`backend/main.py`**: Imports `init_db()` from `db.session` to create the SQLite tables on application startup.

### C. Package Dependencies
- **`requirements.txt`**: Contains `sqlalchemy>=2.0.0`.

### D. Test Dependencies
Currently, the test suite (`backend/tests/`) focuses predominantly on AI algorithms, schemas, and detection pipelines. A review of `backend/tests/` revealed no tests explicitly mocking or requiring the SQLite database connection. Integration testing appears to rely on mocked Pydantic models (e.g., `test_gis_schemas.py`) rather than actual SQLite persistence.

## 3. Migration Assessment

The existing codebase demonstrates excellent separation of concerns. The database logic is strictly confined to the `backend/db/` package and the `backend/api/routes_*.py` files. The AI pipeline (`ai/` directory) and the video processing orchestrator (`UnifiedVideoProcessor`) do not contain raw SQL or SQLAlchemy queries.

This architecture means replacing SQLite with Supabase will require:
1. Creating a new Supabase client wrapper (`supabase_client.py`).
2. Rewriting the classes in `backend/db/repository.py` to use the Supabase Python client instead of SQLAlchemy.
3. Updating the API routes in `backend/api/` to use the new Supabase repository methods without the `Depends(get_db)` FastAPI injection.
4. Removing `backend/db/models.py`, `backend/db/session.py`, and the SQLAlchemy requirement.

No AI model files (`yolo11n.pt`, `best_roadx.pt`, etc.) or core processing logic will need modification to achieve this database migration.
