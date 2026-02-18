-- MCP Inspector - Supabase Database Schema
-- Stores security audit results, catalog data, and installation history

-- Table: audit_scans
-- Stores historical security scan results for each MCP server
CREATE TABLE IF NOT EXISTS audit_scans (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    server_name TEXT NOT NULL,
    scan_timestamp TIMESTAMPTZ DEFAULT NOW(),
    server_type TEXT NOT NULL, -- python-local, npm-package, uvx-package, etc.
    trust_score INTEGER CHECK (trust_score BETWEEN 1 AND 3),
    dangers JSONB DEFAULT '[]'::jsonb, -- Array of danger patterns found
    warnings JSONB DEFAULT '[]'::jsonb, -- Array of warning patterns
    suspicious_imports JSONB DEFAULT '[]'::jsonb, -- Array of suspicious imports
    line_count INTEGER,
    source_hash TEXT, -- SHA256 hash of source code (for change detection)
    package_name TEXT, -- NPM/PyPI package name
    package_version TEXT, -- Package version scanned
    config JSONB NOT NULL, -- Full server configuration
    npm_stats JSONB, -- NPM stats (stars, license, etc.)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for querying scans by server and time
CREATE INDEX IF NOT EXISTS idx_audit_scans_server_time ON audit_scans(server_name, scan_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_scans_trust ON audit_scans(trust_score);

-- Table: catalog_servers
-- Stores servers discovered from MCP registry (historical catalog)
CREATE TABLE IF NOT EXISTS catalog_servers (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    server_name TEXT NOT NULL,
    package_name TEXT,
    description TEXT,
    repository TEXT,
    homepage TEXT,
    verified BOOLEAN DEFAULT FALSE,
    stars INTEGER DEFAULT 0,
    category TEXT,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB, -- Full server data from registry
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(server_name, package_name)
);

-- Index for searching catalog
CREATE INDEX IF NOT EXISTS idx_catalog_name ON catalog_servers(server_name);
CREATE INDEX IF NOT EXISTS idx_catalog_package ON catalog_servers(package_name);
CREATE INDEX IF NOT EXISTS idx_catalog_verified ON catalog_servers(verified);

-- Table: installation_history
-- Tracks when servers were installed and their configurations
CREATE TABLE IF NOT EXISTS installation_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    server_name TEXT NOT NULL,
    installed_at TIMESTAMPTZ DEFAULT NOW(),
    config JSONB NOT NULL,
    installation_method TEXT, -- 'manual', 'ui-install', 'external'
    user_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for installation history queries
CREATE INDEX IF NOT EXISTS idx_install_history_server ON installation_history(server_name, installed_at DESC);

-- Table: vulnerability_alerts
-- Stores known vulnerabilities and security issues
CREATE TABLE IF NOT EXISTS vulnerability_alerts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    server_name TEXT,
    package_name TEXT,
    severity TEXT CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    title TEXT NOT NULL,
    description TEXT,
    cve_id TEXT, -- CVE identifier if applicable
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for active vulnerabilities
CREATE INDEX IF NOT EXISTS idx_vulns_active ON vulnerability_alerts(server_name, resolved_at) WHERE resolved_at IS NULL;

-- View: latest_audit_per_server
-- Shows the most recent audit scan for each server
CREATE OR REPLACE VIEW latest_audit_per_server AS
SELECT DISTINCT ON (server_name)
    id,
    server_name,
    scan_timestamp,
    server_type,
    trust_score,
    dangers,
    warnings,
    suspicious_imports,
    line_count,
    package_name,
    package_version
FROM audit_scans
ORDER BY server_name, scan_timestamp DESC;

-- View: security_trends
-- Shows security score trends over time
CREATE OR REPLACE VIEW security_trends AS
SELECT
    server_name,
    DATE_TRUNC('day', scan_timestamp) as scan_date,
    AVG(trust_score) as avg_trust_score,
    COUNT(*) as scan_count,
    COUNT(CASE WHEN jsonb_array_length(dangers) > 0 THEN 1 END) as scans_with_dangers,
    COUNT(CASE WHEN jsonb_array_length(warnings) > 0 THEN 1 END) as scans_with_warnings
FROM audit_scans
GROUP BY server_name, DATE_TRUNC('day', scan_timestamp);

-- Function: record_catalog_server
-- Upserts catalog server (updates last_seen if exists)
CREATE OR REPLACE FUNCTION record_catalog_server(
    p_server_name TEXT,
    p_package_name TEXT,
    p_description TEXT,
    p_repository TEXT,
    p_homepage TEXT,
    p_verified BOOLEAN,
    p_stars INTEGER,
    p_category TEXT,
    p_metadata JSONB
) RETURNS UUID AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO catalog_servers (
        server_name, package_name, description, repository, homepage,
        verified, stars, category, metadata, last_seen
    ) VALUES (
        p_server_name, p_package_name, p_description, p_repository, p_homepage,
        p_verified, p_stars, p_category, p_metadata, NOW()
    )
    ON CONFLICT (server_name, package_name)
    DO UPDATE SET
        description = EXCLUDED.description,
        repository = EXCLUDED.repository,
        homepage = EXCLUDED.homepage,
        verified = EXCLUDED.verified,
        stars = EXCLUDED.stars,
        category = EXCLUDED.category,
        metadata = EXCLUDED.metadata,
        last_seen = NOW()
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- Enable Row Level Security (RLS) if needed
-- ALTER TABLE audit_scans ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE catalog_servers ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE installation_history ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE vulnerability_alerts ENABLE ROW LEVEL SECURITY;

-- Create policies (example - adjust based on your auth requirements)
-- CREATE POLICY "Allow all operations for authenticated users" ON audit_scans
--     FOR ALL USING (auth.role() = 'authenticated');
