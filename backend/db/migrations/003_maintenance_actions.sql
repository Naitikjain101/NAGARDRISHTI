-- Urban Watch Phase 7 — Maintenance Actions Schema

-- 1. Create Maintenance Actions Table
CREATE TABLE IF NOT EXISTS public.maintenance_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id UUID REFERENCES public.incidents(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'UNASSIGNED', -- UNASSIGNED, ASSIGNED, IN_PROGRESS, RESOLVED, REJECTED
    assigned_team TEXT,
    assigned_department TEXT,
    action_type TEXT,
    resolution_note TEXT,
    created_by TEXT,
    assigned_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(incident_id) -- One action per incident (as per Phase 7 requirements)
);

-- 2. Indexes
CREATE INDEX IF NOT EXISTS idx_maintenance_actions_status ON public.maintenance_actions(status);
CREATE INDEX IF NOT EXISTS idx_maintenance_actions_incident_id ON public.maintenance_actions(incident_id);

-- 3. Triggers for updated_at
CREATE TRIGGER update_maintenance_actions_modtime BEFORE UPDATE ON public.maintenance_actions FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- 4. Row Level Security
ALTER TABLE public.maintenance_actions ENABLE ROW LEVEL SECURITY;

-- Allow anon read access to everything (dashboard requirement)
CREATE POLICY "Enable read access for all users" ON public.maintenance_actions FOR SELECT USING (true);
