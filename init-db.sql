-- PostgreSQL initialization script for PhishGuard
-- This script runs automatically when the container is first created

-- Create database if not exists (handled by POSTGRES_DB env var)
-- Set timezone
SET timezone = 'UTC';

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create indexes will be handled by SQLAlchemy/Alembic
-- This file ensures the database is properly initialized

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE threat_intel TO postgres;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'PhishGuard database initialized successfully';
END $$;
