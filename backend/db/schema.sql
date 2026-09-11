-- Urban Watch Command Center - Production Data Layer Schema
-- Run this in the Supabase SQL Editor

-- 0. CLEAN SLATE (Drops old tables to prevent conflicts)
DROP TABLE IF EXISTS public.bus_telemetry CASCADE;
DROP TABLE IF EXISTS public.buses CASCADE;
DROP TABLE IF EXISTS public.incident_evidence CASCADE;
DROP TABLE IF EXISTS public.maintenance_tasks CASCADE;
DROP TABLE IF EXISTS public.notifications CASCADE;
DROP TABLE IF EXISTS public.traffic_windows CASCADE;
DROP TABLE IF EXISTS public.vehicles CASCADE;
DROP TABLE IF EXISTS public.incidents CASCADE;
DROP TABLE IF EXISTS public.ai_jobs CASCADE;
DROP TABLE IF EXISTS public.road_segments CASCADE;

-- 1. Enable PostGIS extension for geospatial features (optional but recommended)
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Videos / AI Jobs Table
CREATE TABLE IF NOT EXISTS public.ai_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id TEXT NOT NULL, -- Original filename or storage path
    status TEXT NOT NULL DEFAULT 'QUEUED', -- QUEUED, PROCESSING, COMPLETED, FAILED, CANCELLED
    model_version TEXT,
    device TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    total_frames INTEGER,
    frames_processed INTEGER DEFAULT 0,
    processing_fps FLOAT,
    avg_inference_ms FLOAT,
    detections_count INTEGER DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Note: We are migrating the old 'videos' table concept to 'ai_jobs' for clarity
-- For backward compatibility if you already have 'videos', you can choose to alter it instead.

-- 3. Buses & Fleet Management
CREATE TABLE IF NOT EXISTS public.buses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fleet_number TEXT UNIQUE NOT NULL,
    route_id TEXT,
    status TEXT DEFAULT 'ONLINE', -- ONLINE, OFFLINE, MAINTENANCE, WARNING
    camera_status TEXT DEFAULT 'OK',
    ai_status TEXT DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.bus_telemetry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bus_id UUID REFERENCES public.buses(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    speed FLOAT,
    heading FLOAT,
    route_info JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Road Segments
CREATE TABLE IF NOT EXISTS public.road_segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    geometry JSONB, -- Storing GeoJSON here, or use PostGIS geometry(LineString, 4326)
    road_type TEXT,
    zone TEXT,
    congestion_score FLOAT DEFAULT 0.0,
    pothole_count INTEGER DEFAULT 0,
    incident_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Incidents
CREATE TABLE IF NOT EXISTS public.incidents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_type TEXT NOT NULL, -- pothole, waterlogging, vehicle, etc.
    severity TEXT DEFAULT 'LOW', -- LOW, MODERATE, HIGH, CRITICAL
    status TEXT DEFAULT 'OPEN', -- OPEN, ASSIGNED, RESOLVED, DISMISSED
    confidence FLOAT,
    model_name TEXT,
    model_version TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    frame_index INTEGER,
    ai_job_id UUID REFERENCES public.ai_jobs(id) ON DELETE CASCADE,
    bus_id UUID REFERENCES public.buses(id) ON DELETE SET NULL,
    camera_id TEXT,
    latitude FLOAT,
    longitude FLOAT,
    road_segment_id UUID REFERENCES public.road_segments(id) ON DELETE SET NULL,
    validation_status TEXT DEFAULT 'PENDING',
    
    -- Specific features
    water_area_ratio FLOAT,
    bbox JSONB,
    tracking_id TEXT,
    vehicle_class TEXT,
    
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Incident Evidence
CREATE TABLE IF NOT EXISTS public.incident_evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id UUID REFERENCES public.incidents(id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL, -- image, video, mask
    storage_path TEXT NOT NULL, -- Path in Supabase Storage
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Vehicles Tracking
CREATE TABLE IF NOT EXISTS public.vehicles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tracking_id TEXT NOT NULL,
    vehicle_class TEXT NOT NULL,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    ai_job_id UUID REFERENCES public.ai_jobs(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. Traffic Windows
CREATE TABLE IF NOT EXISTS public.traffic_windows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    road_segment_id UUID REFERENCES public.road_segments(id) ON DELETE CASCADE,
    ai_job_id UUID REFERENCES public.ai_jobs(id) ON DELETE CASCADE,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    vehicle_count INTEGER DEFAULT 0,
    average_speed FLOAT,
    congestion_score FLOAT DEFAULT 0.0,
    congestion_level TEXT,
    vehicle_distribution JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 9. Maintenance Tasks
CREATE TABLE IF NOT EXISTS public.maintenance_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id UUID REFERENCES public.incidents(id) ON DELETE SET NULL,
    road_segment_id UUID REFERENCES public.road_segments(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    severity TEXT DEFAULT 'MODERATE',
    status TEXT DEFAULT 'OPEN', -- OPEN, ASSIGNED, IN_PROGRESS, RESOLVED, DISMISSED
    assigned_to TEXT,
    resolution_notes TEXT,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 10. Notifications
CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    incident_id UUID REFERENCES public.incidents(id) ON DELETE CASCADE,
    read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================================================================
-- INDEXES & TRIGGERS
-- ==============================================================================

CREATE INDEX IF NOT EXISTS idx_incidents_type_status ON public.incidents(incident_type, status);
CREATE INDEX IF NOT EXISTS idx_incidents_job_id ON public.incidents(ai_job_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_bus_id ON public.bus_telemetry(bus_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_maintenance_status ON public.maintenance_tasks(status);
CREATE INDEX IF NOT EXISTS idx_notifications_read ON public.notifications(read) WHERE read = FALSE;

-- Update updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_ai_jobs_modtime BEFORE UPDATE ON public.ai_jobs FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_buses_modtime BEFORE UPDATE ON public.buses FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_road_segments_modtime BEFORE UPDATE ON public.road_segments FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_incidents_modtime BEFORE UPDATE ON public.incidents FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_maintenance_tasks_modtime BEFORE UPDATE ON public.maintenance_tasks FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- ==============================================================================
-- REALTIME
-- ==============================================================================
-- You must manually enable Realtime on these tables in the Supabase Dashboard:
-- incidents, maintenance_tasks, notifications, bus_telemetry, ai_jobs

-- ==============================================================================
-- RLS POLICIES (Assuming standard open access for service_role backend, anon limited)
-- ==============================================================================
ALTER TABLE public.incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.buses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bus_telemetry ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.road_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.incident_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.traffic_windows ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.maintenance_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- Allow anon read access to everything (since this is a dashboard)
-- Allow anon read access to everything (since this is a dashboard) but STRICTLY forbid modifications
CREATE POLICY "Enable read access for all users" ON public.incidents FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON public.ai_jobs FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON public.buses FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON public.bus_telemetry FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON public.road_segments FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON public.incident_evidence FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON public.vehicles FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON public.traffic_windows FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON public.maintenance_tasks FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON public.notifications FOR SELECT USING (true);

-- ==============================================================================
-- STORAGE BUCKETS (Private by default)
-- ==============================================================================
-- You must run this in the Supabase SQL editor to create the buckets and policies.
INSERT INTO storage.buckets (id, name, public) 
VALUES ('urban_watch_evidence', 'urban_watch_evidence', false)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS
-- Allow anon to SELECT ONLY if they have a signed URL (Supabase handles this natively for private buckets)
-- Writes are completely forbidden for anon. Backend uses service_role key to bypass this.
CREATE POLICY "Deny all public writes to evidence" ON storage.objects FOR INSERT TO public WITH CHECK (false);
CREATE POLICY "Deny all public updates to evidence" ON storage.objects FOR UPDATE TO public USING (false);
CREATE POLICY "Deny all public deletes to evidence" ON storage.objects FOR DELETE TO public USING (false);

