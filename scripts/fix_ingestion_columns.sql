-- Fix missing ingestion columns in proposal_documents table
-- Run this script against your PostgreSQL database

-- Add missing columns with proper defaults
ALTER TABLE proposal_documents
  ADD COLUMN IF NOT EXISTS ingestion_status TEXT NOT NULL DEFAULT 'none',
  ADD COLUMN IF NOT EXISTS available_sections TEXT[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS ingestion_error TEXT;

-- Backfill existing rows with sensible defaults
UPDATE proposal_documents
SET ingestion_status = CASE
  WHEN parsed_text IS NOT NULL AND length(coalesce(parsed_text, '')) > 0 THEN 'ready'
  ELSE 'none'
END
WHERE ingestion_status = 'none';

-- Create index for performance
CREATE INDEX IF NOT EXISTS ix_proposal_documents_ingestion_status
  ON proposal_documents (ingestion_status);

-- Verify the changes
SELECT 
  column_name, 
  data_type, 
  is_nullable, 
  column_default
FROM information_schema.columns 
WHERE table_name = 'proposal_documents' 
  AND column_name IN ('ingestion_status', 'available_sections', 'ingestion_error')
ORDER BY column_name;
