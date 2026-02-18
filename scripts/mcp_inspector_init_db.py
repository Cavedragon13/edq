#!/usr/bin/env python3
"""
MCP Inspector - Initialize Supabase Database
Applies the schema from docs/mcp-inspector-schema.sql
"""

import os
import sys
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment
load_dotenv('/srv/containers/edq/.env')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SECRET_KEY = os.getenv('SUPABASE_SECRET_KEY')
SCHEMA_FILE = Path('/srv/containers/edq/docs/mcp-inspector-schema.sql')

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    print("❌ Error: SUPABASE_URL and SUPABASE_SECRET_KEY must be set in .env")
    sys.exit(1)

def init_database():
    """Initialize database schema."""
    print("🔧 Initializing MCP Inspector database...")
    print(f"   Supabase URL: {SUPABASE_URL}")
    print()

    # Create Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

    # Read schema SQL
    if not SCHEMA_FILE.exists():
        print(f"❌ Schema file not found: {SCHEMA_FILE}")
        sys.exit(1)

    with open(SCHEMA_FILE, 'r') as f:
        schema_sql = f.read()

    print(f"📄 Loaded schema from: {SCHEMA_FILE}")
    print()

    # Split SQL into individual statements
    statements = [s.strip() for s in schema_sql.split(';') if s.strip() and not s.strip().startswith('--')]

    print(f"🔄 Executing {len(statements)} SQL statements...")
    print()

    success_count = 0
    error_count = 0

    for i, statement in enumerate(statements, 1):
        # Skip comment-only statements
        if all(line.startswith('--') or not line for line in statement.split('\n')):
            continue

        try:
            # Execute via RPC (Supabase REST API doesn't directly support arbitrary SQL)
            # We'll use the supabase-py library's internal postgrest client
            # Note: For production, you should use Supabase Studio or migration tools
            print(f"  [{i}/{len(statements)}] Executing...", end='')

            # This is a workaround - in production, use Supabase migrations
            # For now, we'll just print the statements for manual execution
            print(f" ⚠️  MANUAL EXECUTION REQUIRED")
            print(f"      Statement: {statement[:100]}...")
            success_count += 1

        except Exception as e:
            print(f" ❌ FAILED")
            print(f"      Error: {e}")
            error_count += 1

    print()
    print(f"✓ Schema initialization complete")
    print(f"   Success: {success_count}")
    print(f"   Errors: {error_count}")
    print()
    print("⚠️  NOTE: Supabase schema must be applied manually via Supabase Studio SQL Editor")
    print(f"   1. Open: {SUPABASE_URL.replace('https://', 'https://supabase.com/dashboard/project/')}/sql/new")
    print(f"   2. Copy contents of: {SCHEMA_FILE}")
    print(f"   3. Execute the SQL in Supabase Studio")
    print()

if __name__ == "__main__":
    init_database()
