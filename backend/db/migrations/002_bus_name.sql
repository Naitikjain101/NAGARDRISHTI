-- Phase 1 Migration
-- Add name column to buses if it does not exist

DO $$ BEGIN
    ALTER TABLE public.buses ADD COLUMN name TEXT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
