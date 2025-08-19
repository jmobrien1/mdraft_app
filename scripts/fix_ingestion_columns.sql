-- Fix missing ingestion columns in proposal_documents table
-- This script safely adds the missing columns with proper defaults and data migration

-- Check if columns exist first
DO $$
BEGIN
    -- Add ingestion_status column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'proposal_documents' 
        AND column_name = 'ingestion_status'
    ) THEN
        ALTER TABLE proposal_documents 
        ADD COLUMN ingestion_status TEXT NOT NULL DEFAULT 'none';
        RAISE NOTICE 'Added ingestion_status column';
    ELSE
        RAISE NOTICE 'ingestion_status column already exists';
    END IF;

    -- Add available_sections column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'proposal_documents' 
        AND column_name = 'available_sections'
    ) THEN
        ALTER TABLE proposal_documents 
        ADD COLUMN available_sections TEXT[] NOT NULL DEFAULT '{}'::text[];
        RAISE NOTICE 'Added available_sections column';
    ELSE
        RAISE NOTICE 'available_sections column already exists';
    END IF;

    -- Add ingestion_error column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'proposal_documents' 
        AND column_name = 'ingestion_error'
    ) THEN
        ALTER TABLE proposal_documents 
        ADD COLUMN ingestion_error TEXT;
        RAISE NOTICE 'Added ingestion_error column';
    ELSE
        RAISE NOTICE 'ingestion_error column already exists';
    END IF;

    -- Add section_mapping column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'proposal_documents' 
        AND column_name = 'section_mapping'
    ) THEN
        ALTER TABLE proposal_documents 
        ADD COLUMN section_mapping JSONB;
        RAISE NOTICE 'Added section_mapping column';
    ELSE
        RAISE NOTICE 'section_mapping column already exists';
    END IF;
END $$;

-- Create index if it doesn't exist
CREATE INDEX IF NOT EXISTS ix_proposal_documents_ingestion_status
ON proposal_documents (ingestion_status);

-- Backfill existing data with sensible defaults
UPDATE proposal_documents
SET ingestion_status = CASE
    WHEN parsed_text IS NOT NULL AND length(coalesce(parsed_text, '')) > 0 THEN 'ready'
    ELSE 'none'
END
WHERE ingestion_status = 'none';

-- Verify the changes
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'proposal_documents' 
AND column_name IN ('ingestion_status', 'available_sections', 'ingestion_error', 'section_mapping')
ORDER BY column_name;

-- Show sample data to verify
SELECT 
    id,
    filename,
    ingestion_status,
    available_sections,
    CASE WHEN ingestion_error IS NOT NULL THEN 'has_error' ELSE 'no_error' END as error_status
FROM proposal_documents 
LIMIT 5;
