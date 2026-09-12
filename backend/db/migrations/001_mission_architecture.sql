-- ==============================================================================
-- Urban Watch — Mission Architecture Migration
-- Phase A: demo_missions, route_points, incident_observations
--           + additive columns on incidents
--
-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor → New query)
-- Safe to re-run: uses IF NOT EXISTS / DO blocks.
-- Does NOT drop any existing tables.
-- ==============================================================================

-- ── 1. demo_missions ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.demo_missions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bus_id          TEXT NOT NULL,                       -- e.g. "BUS-104"
    route_id        TEXT NOT NULL,                       -- e.g. "R-01"
    route_name      TEXT NOT NULL,                       -- human-readable
    video_filename  TEXT NOT NULL,                       -- file in demo_videos/
    duration_seconds FLOAT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'READY',       -- READY | RUNNING | COMPLETED
    metadata        JSONB,                               -- arbitrary extra fields
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── 2. route_points (GPS timeline per mission) ────────────────────────────────
CREATE TABLE IF NOT EXISTS public.route_points (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mission_id        UUID NOT NULL REFERENCES public.demo_missions(id) ON DELETE CASCADE,
    timestamp_seconds FLOAT NOT NULL,   -- seconds into video (0 = start)
    latitude          FLOAT NOT NULL,
    longitude         FLOAT NOT NULL,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_route_points_mission_ts
    ON public.route_points (mission_id, timestamp_seconds);

-- ── 3. incident_observations (raw evidence trail) ────────────────────────────
CREATE TABLE IF NOT EXISTS public.incident_observations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id     UUID NOT NULL REFERENCES public.incidents(id) ON DELETE CASCADE,
    mission_id      UUID REFERENCES public.demo_missions(id) ON DELETE SET NULL,
    bus_id          TEXT,                   -- e.g. "BUS-104"
    video_timestamp FLOAT,                  -- seconds into video
    latitude        FLOAT,
    longitude       FLOAT,
    confidence      FLOAT,
    bbox            JSONB,                  -- [x1, y1, x2, y2]
    frame_index     INTEGER,
    evidence_url    TEXT,                   -- signed storage URL (optional)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_observations_incident
    ON public.incident_observations (incident_id);

CREATE INDEX IF NOT EXISTS idx_observations_mission
    ON public.incident_observations (mission_id);

-- ── 4. Additive columns on incidents ─────────────────────────────────────────
-- Each column is added only if it doesn't already exist.

DO $$ BEGIN
    ALTER TABLE public.incidents ADD COLUMN first_seen_at TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE public.incidents ADD COLUMN last_seen_at TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE public.incidents ADD COLUMN observation_count INTEGER NOT NULL DEFAULT 1;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE public.incidents ADD COLUMN observed_by JSONB DEFAULT '[]'::jsonb;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE public.incidents ADD COLUMN dedup_status TEXT NOT NULL DEFAULT 'PENDING';
    -- PENDING | CONFIRMED | DISPUTED
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE public.incidents ADD COLUMN source_mission_id UUID
        REFERENCES public.demo_missions(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- ── 5. Spatial index on incidents (for fast dedup radius queries) ─────────────
CREATE INDEX IF NOT EXISTS idx_incidents_latlon
    ON public.incidents (latitude, longitude)
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

-- ── 6. Triggers ───────────────────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TRIGGER update_demo_missions_modtime
        BEFORE UPDATE ON public.demo_missions
        FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── 7. RLS ────────────────────────────────────────────────────────────────────
ALTER TABLE public.demo_missions          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.route_points           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.incident_observations  ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE POLICY "Enable read access for all users" ON public.demo_missions
        FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE POLICY "Enable read access for all users" ON public.route_points
        FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE POLICY "Enable read access for all users" ON public.incident_observations
        FOR SELECT USING (true);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
