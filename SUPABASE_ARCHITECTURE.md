# Urban Watch Supabase Architecture

Urban Watch leverages Supabase (PostgreSQL) as its primary Persistent Database and Geographic Information System (GIS) engine.

## 1. High-Level Data Flow

```
                      React Frontend (Vite)
                               |
                               | (HTTP JSON API via REST)
                               v
                       FastAPI Backend
                               |
                   Domain / Event Handlers
                               |
                      Repository Layer
                    (db.supabase_client)
                               |
                               | (Supabase Python SDK / PostgREST)
                               v
                      Supabase PostgreSQL
```

## 2. Access Patterns & Security

### Row Level Security (RLS)
The frontend never receives database credentials capable of writing data. The Supabase `service_role_key` is strictly injected only into the FastAPI backend container via environment variables.

- **Backend (Python)**: Uses `SUPABASE_SERVICE_ROLE_KEY` to bypass all RLS policies, allowing it to freely insert incidents, vehicles, traffic windows, and road segments parsed from the video pipeline.
- **Frontend (React)**: Does not connect directly to Supabase. It consumes the FastAPI endpoints to ensure all data logic, pagination, and AI validation layers are centralized on the server. If public read access was enabled via the Anon key, RLS policies explicitly restrict it to `SELECT` operations only.

## 3. Database Schema Overview

The database contains six primary tables, built to handle standard CRUD as well as PostGIS intelligence.

### `videos`
Tracks uploaded media and AI processing states (e.g., `pending`, `running`, `complete`, `failed`).

### `incidents`
Records singular events detected by the AI (Potholes, Helmet Violations).
- Features temporal and bounding box data.
- Stores composite scores and confidences.
- Optional `location GEOMETRY(Point, 4326)` for PostGIS capabilities if GPS exists.

### `vehicles`
Records identified vehicles over a specific tracked lifespan.

### `traffic_windows`
Stores aggregated traffic metrics (e.g., count by vehicle class) and a normalized `congestion_score` spanning specific time segments of a video.

### `road_segments`
Geospatial entities representing stretches of road (LineString). Supports spatial joining to aggregate incidents into holistic road-condition metrics (`pothole_count`, `congestion_score`).

### `ai_models`
A registry identifying which AI weights were used to generate data for auditability.

## 4. PostGIS and Null Handling

Urban Watch strictly prohibits the fabrication of geographic data.
- If a source video lacks GPS telemetry, the corresponding `latitude`, `longitude`, and `location` fields will be written as `NULL`.
- The database schema is designed to tolerate this naturally.
- The `react-leaflet` map layer on the frontend explicitly checks for NULL values, displaying only verifiable GPS incidents and presenting a clear UI disclaimer otherwise.
