-- Add progress column to conversions table if it doesn't exist
-- This script is safe to run multiple times

-- For PostgreSQL
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'conversions' 
        AND column_name = 'progress'
    ) THEN
        ALTER TABLE conversions ADD COLUMN progress INTEGER;
        RAISE NOTICE 'Added progress column to conversions table';
    ELSE
        RAISE NOTICE 'Progress column already exists in conversions table';
    END IF;
END $$;

-- For SQLite (fallback)
-- ALTER TABLE conversions ADD COLUMN progress INTEGER;
