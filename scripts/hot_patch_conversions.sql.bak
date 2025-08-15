-- Hot-patch for conversions.proposal_id column
-- Run this once in your Render Postgres psql to unblock the app immediately

-- Add the missing column if it doesn't exist
ALTER TABLE public.conversions ADD COLUMN IF NOT EXISTS proposal_id INTEGER;

-- Create an index for better performance
CREATE INDEX IF NOT EXISTS ix_conversions_proposal_id ON public.conversions (proposal_id);

-- Verify the column was added
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'conversions' AND column_name = 'proposal_id';

-- Show the index was created
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'conversions' AND indexname = 'ix_conversions_proposal_id';
