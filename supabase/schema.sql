-- Urban Watch Phase 5.1 — Supabase PostgreSQL Schema
-- Single Source of Truth database definition

-- 1. Enable PostGIS Extension for GIS capabilities
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Clean up existing tables if this script is re-run (useful during dev)
DROP TABLE IF EXISTS ai_models CASCADE;
DROP TABLE IF EXISTS road_segments CASCADE;
DROP TABLE IF EXISTS traffic_windows CASCADE;
DROP TABLE IF EXISTS vehicles CASCADE;
DROP TABLE IF EXISTS incidents CASCADE;
DROP TABLE IF EXISTS videos CASCADE;

-- 3. Create Tables

-- VIDEOS TABLE
CREATE TABLE videos (
    id UUID PRIMARY KEY,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    storage_path TEXT,
    duration FLOAT,
    fps FLOAT,
    width INTEGER,
    height INTEGER,
    codec TEXT,
    processing_status TEXT NOT NULL DEFAULT 'pending',
    processing_fps FLOAT,
    total_frames INTEGER DEFAULT 0,
    processed_frames INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- INCIDENTS TABLE
CREATE TABLE incidents (
    id UUID PRIMARY KEY,
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    incident_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    confidence FLOAT NOT NULL,
    composite_score FLOAT,
    frame_number INTEGER NOT NULL,
    timestamp FLOAT NOT NULL,
    track_id INTEGER,
    -- Store bounding box as JSON array [x_min, y_min, x_max, y_max]
    bbox JSONB,
    
    -- Optional GPS Data
    latitude FLOAT,
    longitude FLOAT,
    
    -- PostGIS Point Geometry (SRID 4326 - WGS84)
    location GEOMETRY(Point, 4326),
    
    -- Model Tracking
    model_name TEXT,
    model_version TEXT,
    
    description TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Create a spatial index for incidents
CREATE INDEX idx_incidents_location ON incidents USING GIST(location);

-- VEHICLES TABLE
CREATE TABLE vehicles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    track_id INTEGER NOT NULL,
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    vehicle_type TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    first_seen FLOAT NOT NULL,
    last_seen FLOAT NOT NULL,
    
    -- Optional GPS Data
    latitude FLOAT,
    longitude FLOAT,
    location GEOMETRY(Point, 4326),
    
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE INDEX idx_vehicles_location ON vehicles USING GIST(location);
CREATE INDEX idx_vehicles_video_track ON vehicles(video_id, track_id);

-- TRAFFIC WINDOWS TABLE
CREATE TABLE traffic_windows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    vehicle_count INTEGER NOT NULL DEFAULT 0,
    congestion_level TEXT NOT NULL,
    congestion_score FLOAT NOT NULL DEFAULT 0.0,
    car_count INTEGER NOT NULL DEFAULT 0,
    motorcycle_count INTEGER NOT NULL DEFAULT 0,
    bus_count INTEGER NOT NULL DEFAULT 0,
    truck_count INTEGER NOT NULL DEFAULT 0,
    other_vehicle_count INTEGER NOT NULL DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ROAD SEGMENTS TABLE (For GIS aggregations)
CREATE TABLE road_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    road_name TEXT,
    road_identifier TEXT,
    
    -- PostGIS LineString for road segment
    geometry GEOMETRY(LineString, 4326),
    centroid GEOMETRY(Point, 4326),
    
    pothole_count INTEGER DEFAULT 0,
    incident_count INTEGER DEFAULT 0,
    congestion_score FLOAT DEFAULT 0.0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE INDEX idx_road_segments_geom ON road_segments USING GIST(geometry);

-- AI MODELS TABLE
CREATE TABLE ai_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    task TEXT NOT NULL,
    framework TEXT,
    device TEXT,
    confidence_threshold FLOAT,
    enabled BOOLEAN DEFAULT true,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(model_name, model_version)
);

-- 4. Row Level Security (RLS) Policies

-- Enable RLS on all tables
ALTER TABLE videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE traffic_windows ENABLE ROW LEVEL SECURITY;
ALTER TABLE road_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_models ENABLE ROW LEVEL SECURITY;

-- Service Role Bypass: The backend uses the service_role key.
-- Supabase by default allows the service_role key to bypass RLS completely.
-- Therefore, backend access is guaranteed.

-- Frontend (Anon Role) Policies:
-- We restrict the anon key to READ ONLY access (SELECT).
-- Insert/Update/Delete operations MUST go through the FastAPI backend.

-- Policies for videos
CREATE POLICY "Allow public read access to videos" 
    ON videos FOR SELECT 
    TO anon, authenticated
    USING (true);

-- Policies for incidents
CREATE POLICY "Allow public read access to incidents" 
    ON incidents FOR SELECT 
    TO anon, authenticated
    USING (true);

-- Policies for vehicles
CREATE POLICY "Allow public read access to vehicles" 
    ON vehicles FOR SELECT 
    TO anon, authenticated
    USING (true);

-- Policies for traffic_windows
CREATE POLICY "Allow public read access to traffic_windows" 
    ON traffic_windows FOR SELECT 
    TO anon, authenticated
    USING (true);

-- Policies for road_segments
CREATE POLICY "Allow public read access to road_segments" 
    ON road_segments FOR SELECT 
    TO anon, authenticated
    USING (true);

-- Policies for ai_models
CREATE POLICY "Allow public read access to ai_models" 
    ON ai_models FOR SELECT 
    TO anon, authenticated
    USING (true);

-- 5. Triggers for updated_at

CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_videos_modtime BEFORE UPDATE ON videos FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_incidents_modtime BEFORE UPDATE ON incidents FOR EACH ROW EXECUTE FUNCTION update_modified_column();
CREATE TRIGGER update_road_segments_modtime BEFORE UPDATE ON road_segments FOR EACH ROW EXECUTE FUNCTION update_modified_column();
