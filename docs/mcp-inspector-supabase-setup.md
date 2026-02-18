# MCP Inspector - Supabase Integration Setup

This guide walks you through setting up the Supabase database for MCP Inspector's historical tracking features.

## Overview

The Supabase integration adds:
- **Audit History**: Track security scans over time, detect changes
- **Catalog Archive**: Search historical MCP registry data
- **Installation Tracking**: Monitor when servers were installed
- **Security Trends**: Visualize trust scores and vulnerabilities over time

## Prerequisites

1. **Supabase Account**: Sign up at [supabase.com](https://supabase.com)
2. **Project Created**: Create a new Supabase project
3. **Credentials**: Get your project URL and service role key

## Step 1: Get Supabase Credentials

1. Go to your Supabase project dashboard
2. Click **Settings** → **API**
3. Copy these values:
   - **Project URL**: `https://[project-ref].supabase.co`
   - **Service Role Key**: `eyJ...` (secret key, not anon key)

## Step 2: Configure Environment Variables

Credentials are already set in `/srv/containers/edq/.env`:

```bash
SUPABASE_URL=<your-supabase-url>
SUPABASE_SECRET_KEY=<your-supabase-secret-key>
# See /srv/containers/edq/.env for actual values
```

✅ **No action needed** - credentials are already configured!

## Step 3: Create Database Schema

### Option A: Supabase Studio SQL Editor (Recommended)

1. Open Supabase Studio: `https://supabase.com/dashboard/project/[your-project-id]/sql/new`
2. Copy the contents of `/srv/containers/edq/docs/mcp-inspector-schema.sql`
3. Paste into the SQL Editor
4. Click **Run** to execute

### Option B: Run Setup Script (Info Only)

The setup script is provided for reference:

```bash
cd /srv/containers/edq
venv_mcp_inspector/bin/python scripts/mcp_inspector_init_db.py
```

**Note**: This script currently only displays instructions. Use Supabase Studio for actual schema creation.

## Step 4: Verify Database Tables

After running the schema, verify these tables exist in Supabase Studio:

- ✅ `audit_scans` - Security audit results
- ✅ `catalog_servers` - MCP registry history
- ✅ `installation_history` - Installation tracking
- ✅ `vulnerability_alerts` - Security alerts (future use)

## Step 5: Test the Integration

1. Start MCP Inspector:
   ```bash
   bash scripts/start_mcp_inspector.sh
   ```

2. Look for this message in the output:
   ```
   ✓ Supabase integration enabled
   ```

3. Check database status via API:
   ```bash
   curl http://localhost:8020/api/database/status
   ```

   Expected response:
   ```json
   {
     "enabled": true,
     "url": "https://zpmxdcmtpbuedojndstc.supabase.co",
     "connected": true,
     "message": "Database connected successfully"
   }
   ```

## Step 6: Verify Data Collection

1. Open MCP Inspector UI: `http://192.168.7.226:8020`
2. Navigate to **Installed Servers** tab
3. Watch for servers to be analyzed (happens automatically on load)
4. Check Supabase Studio → **Table Editor** → `audit_scans`
5. You should see new rows with scan results

## New API Endpoints

Once configured, these endpoints become available:

### Audit History
```bash
# Get all audit scans
GET /api/history/audits?limit=100

# Get scans for specific server
GET /api/history/audits?server=dragonsuite&limit=50
```

### Security Trends
```bash
# Get security trends (30 days)
GET /api/history/trends?days=30
```

### Installation History
```bash
# Get installation history
GET /api/history/installations
```

### Database Status
```bash
# Check connection status
GET /api/database/status
```

## Schema Overview

### `audit_scans`
Stores security scan results for each server:
- Trust scores (1-3 stars)
- Danger patterns detected (eval, exec, etc.)
- Warning patterns (subprocess, requests, etc.)
- Suspicious imports
- Source code hash (for change detection)
- NPM stats (stars, license, version)

### `catalog_servers`
Historical archive of MCP registry:
- Server metadata from official registry
- First/last seen timestamps
- Verification status
- Repository and documentation links

### `installation_history`
Tracks when servers were installed:
- Installation timestamp
- Full configuration snapshot
- Installation method (manual, UI, external)
- Optional user notes

### `vulnerability_alerts`
Future feature for tracking known vulnerabilities:
- CVE tracking
- Severity ratings
- Resolution status
- Metadata and references

## Views and Functions

### `latest_audit_per_server`
View showing most recent audit for each server.

### `security_trends`
View aggregating security scores over time.

### `record_catalog_server()`
Function for upserting catalog servers (handles duplicates).

## Troubleshooting

### "Supabase credentials not found"
- Check `/srv/containers/edq/.env` contains `SUPABASE_URL` and `SUPABASE_SECRET_KEY`
- Restart the server after updating `.env`

### "Database connection failed"
- Verify credentials are correct
- Check Supabase project is active (not paused)
- Verify network connectivity to Supabase

### "Table does not exist"
- Run the schema SQL in Supabase Studio
- Check table names match exactly (case-sensitive)

### No data appearing in tables
- Check browser console for errors
- Verify server is using venv: `ps aux | grep mcp_inspector`
- Check server logs for database errors

## Future Enhancements

Planned features:
- 📊 **Dashboard Tab**: Charts and visualizations of trends
- 🔔 **Vulnerability Alerts**: Integration with security databases
- 📈 **Comparison Views**: Compare trust scores across servers
- 🔍 **Search History**: Full-text search across all audits
- 📅 **Scheduled Scans**: Automatic periodic re-scanning
- 📧 **Email Alerts**: Notifications for security changes

## Data Retention

By default, all historical data is retained indefinitely. To implement retention policies:

```sql
-- Example: Delete audit scans older than 90 days
DELETE FROM audit_scans
WHERE scan_timestamp < NOW() - INTERVAL '90 days';
```

Consider setting up a Supabase Edge Function for automated cleanup.

## Privacy & Security

- **Service Role Key**: Keep secret, grants full database access
- **Row Level Security (RLS)**: Schema includes commented-out RLS policies
- **API Keys**: Never commit `.env` to version control
- **Network Access**: MCP Inspector runs on local network only

## Summary

✅ Schema created in Supabase
✅ Environment variables configured
✅ Virtual environment with supabase-py
✅ Server integration complete
✅ API endpoints available
⏳ UI updates (coming next)

The MCP Inspector now stores all audit data in Supabase for long-term tracking and analysis!
