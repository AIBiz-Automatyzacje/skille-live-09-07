-- Meeting Transcripts — schema tabeli PostgreSQL
--
-- Użycie:
--   psql $CONNECTION_STRING -f schema.sql
--   lub
--   psql -h HOST -U USER -d DATABASE -f schema.sql

CREATE TABLE IF NOT EXISTS meeting_transcripts (
    id SERIAL PRIMARY KEY,
    recall_bot_id UUID,
    meeting_id VARCHAR(255),
    platform VARCHAR(50),
    title VARCHAR(500),
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    transcript TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_meeting_started_at ON meeting_transcripts(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_meeting_meeting_id ON meeting_transcripts(meeting_id);

-- Sprawdzenie że wszystko siadło:
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'meeting_transcripts';
