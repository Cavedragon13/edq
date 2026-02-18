#!/usr/bin/env python3
"""
MCP Inspector - Security Browser for MCP Servers
Serves mcp_inspector.html on port 8020
Analyzes configured MCP servers for trust and security
Stores audit results in Supabase for historical tracking
"""

import http.server
import socketserver
import json
import urllib.request
import urllib.error
import urllib.parse
import os
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/srv/containers/edq/.env')

# Supabase integration
try:
    from supabase import create_client, Client
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_SECRET_KEY = os.getenv('SUPABASE_SECRET_KEY')

    if SUPABASE_URL and SUPABASE_SECRET_KEY:
        supabase: Optional[Client] = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
        SUPABASE_ENABLED = True
        print("✓ Supabase integration enabled")
    else:
        supabase = None
        SUPABASE_ENABLED = False
        print("⚠️  Supabase credentials not found - running without database")
except ImportError:
    supabase = None
    SUPABASE_ENABLED = False
    print("⚠️  supabase-py not installed - running without database")

PORT = 8020
MEDIA_DIR = Path("/srv/containers/edq/media")
HTML_FILE = MEDIA_DIR / "mcp_inspector.html"
MCP_CONFIG_MAIN = Path("/srv/containers/edq/.mcp.json")
MCP_CONFIG_PROJECTS = Path("/srv/containers/edq/projects/.mcp.json")
CACHE_DIR = Path(os.path.expanduser("~/.cache/mcp-inspector"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Security pattern matching
DANGER_PATTERNS = [
    (r'\beval\s*\(', 'eval() - Code execution risk'),
    (r'\bexec\s*\(', 'exec() - Code execution risk'),
    (r'os\.system\s*\(', 'os.system() - Shell command execution'),
    (r'__import__\s*\(', '__import__() - Dynamic imports'),
]

WARNING_PATTERNS = [
    (r'subprocess\.', 'subprocess - Command execution'),
    (r'requests\.', 'requests - Network access'),
    (r'urllib\.', 'urllib - Network access'),
    (r'open\s*\(', 'open() - File access'),
    (r'Path\s*\(.+\)\.write', 'Path.write() - File writing'),
]

SAFE_IMPORTS = {
    'mcp', 'asyncio', 'json', 'pathlib', 'typing', 'dataclasses',
    'aiohttp', 'datetime', 're', 'os', 'sys', 'logging'
}

OFFICIAL_MCP_PACKAGES = [
    '@modelcontextprotocol/server-github',
    '@modelcontextprotocol/server-filesystem',
    '@modelcontextprotocol/server-sequential-thinking',
    '@modelcontextprotocol/server-supabase',
    '@modelcontextprotocol/server-obsidian',
]

TRUSTED_PACKAGES = [
    '@playwright/mcp',
    '@mongodb-js/mongodb-mcp-server',
    'blender-mcp',
]


def parse_mcp_configs() -> Dict[str, Dict]:
    """Parse both .mcp.json files and merge (main takes precedence)."""
    servers = {}

    # Parse projects config first
    if MCP_CONFIG_PROJECTS.exists():
        try:
            with open(MCP_CONFIG_PROJECTS, 'r') as f:
                data = json.load(f)
                if 'mcpServers' in data:
                    servers.update(data['mcpServers'])
        except Exception as e:
            print(f"⚠️  Error parsing {MCP_CONFIG_PROJECTS}: {e}")

    # Parse main config (overwrites duplicates)
    if MCP_CONFIG_MAIN.exists():
        try:
            with open(MCP_CONFIG_MAIN, 'r') as f:
                data = json.load(f)
                if 'mcpServers' in data:
                    servers.update(data['mcpServers'])
        except Exception as e:
            print(f"⚠️  Error parsing {MCP_CONFIG_MAIN}: {e}")

    return servers


def detect_server_type(config: Dict) -> str:
    """Detect server type from command."""
    command = config.get('command', '')

    if command.endswith('/python') or command.endswith('/python3'):
        return 'python-local'
    elif command == 'npx':
        return 'npm-package'
    elif command == 'uvx':
        return 'uvx-package'
    elif command == 'blender':
        return 'blender'
    else:
        return 'unknown'


def extract_package_name(config: Dict, server_type: str) -> str:
    """Extract NPM package name from args."""
    if server_type == 'npm-package':
        args = config.get('args', [])
        # Filter out flags like -y
        for arg in args:
            if not arg.startswith('-'):
                return arg
    elif server_type == 'uvx-package':
        args = config.get('args', [])
        if args:
            return args[0]
    return ''


def get_npm_package_info(package_name: str) -> Dict[str, Any]:
    """Fetch NPM package info from registry."""
    cache_file = CACHE_DIR / f"{package_name.replace('/', '_')}.json"

    # Use cache if exists and recent (< 24 hours)
    if cache_file.exists():
        import time
        if time.time() - cache_file.stat().st_mtime < 86400:
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except:
                pass

    try:
        url = f"https://registry.npmjs.org/{package_name}"
        req = urllib.request.Request(url)
        req.add_header('Accept', 'application/json')

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())

        # Extract useful info
        latest_version = data.get('dist-tags', {}).get('latest', '')
        latest_data = data.get('versions', {}).get(latest_version, {})

        info = {
            'description': data.get('description', ''),
            'license': latest_data.get('license', 'Unknown'),
            'homepage': data.get('homepage', ''),
            'repository': data.get('repository', {}).get('url', ''),
            'version': latest_version,
        }

        # Try to get GitHub stars if repository is GitHub
        repo_url = info['repository']
        if 'github.com' in repo_url:
            owner_repo = extract_github_repo(repo_url)
            if owner_repo:
                stars = get_github_stars(owner_repo)
                if stars is not None:
                    info['stars'] = stars

        # Cache the result
        with open(cache_file, 'w') as f:
            json.dump(info, f)

        return info

    except Exception as e:
        return {'error': str(e)}


def extract_github_repo(repo_url: str) -> str:
    """Extract owner/repo from GitHub URL."""
    match = re.search(r'github\.com[/:]([^/]+)/([^/\.]+)', repo_url)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return ''


def get_github_stars(owner_repo: str) -> int:
    """Fetch GitHub stars count."""
    cache_file = CACHE_DIR / f"gh_{owner_repo.replace('/', '_')}.json"

    # Use cache if exists
    if cache_file.exists():
        import time
        if time.time() - cache_file.stat().st_mtime < 86400:
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f).get('stars', 0)
            except:
                pass

    try:
        url = f"https://api.github.com/repos/{owner_repo}"
        req = urllib.request.Request(url)
        req.add_header('Accept', 'application/vnd.github.v3+json')

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())

        stars = data.get('stargazers_count', 0)

        # Cache
        with open(cache_file, 'w') as f:
            json.dump({'stars': stars}, f)

        return stars

    except Exception:
        return 0


def scan_python_source(file_path: Path) -> Dict[str, Any]:
    """Scan Python source for security issues."""
    if not file_path.exists():
        return {'error': 'File not found'}

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
    except Exception as e:
        return {'error': str(e)}

    # Check for danger patterns
    dangers = []
    for pattern, desc in DANGER_PATTERNS:
        if re.search(pattern, source):
            dangers.append(desc)

    # Check for warning patterns
    warnings = []
    for pattern, desc in WARNING_PATTERNS:
        if re.search(pattern, source):
            warnings.append(desc)

    # Extract imports
    imports = re.findall(r'^(?:from|import)\s+([\w\.]+)', source, re.MULTILINE)
    imports = list(set([imp.split('.')[0] for imp in imports]))

    # Flag suspicious imports
    suspicious_imports = [imp for imp in imports if imp not in SAFE_IMPORTS]

    return {
        'dangers': dangers,
        'warnings': warnings,
        'imports': imports,
        'suspicious_imports': suspicious_imports,
        'line_count': len(source.split('\n')),
    }


def calculate_trust_score(server_name: str, config: Dict, server_type: str, package_info: Dict) -> int:
    """Calculate trust score (1-3 stars)."""
    # Official MCP packages: always 3 stars
    if server_type == 'npm-package':
        package = extract_package_name(config, server_type)
        if package in OFFICIAL_MCP_PACKAGES:
            return 3
        if package in TRUSTED_PACKAGES:
            return 3

        # Check stars
        stars = package_info.get('stars', 0)
        if stars > 1000:
            return 3
        elif stars > 100:
            return 2
        else:
            return 1

    # Local Python: 3 stars (user can audit)
    elif server_type == 'python-local':
        return 3

    # UVX packages: 2 stars by default
    elif server_type == 'uvx-package':
        return 2

    return 1


def analyze_server(name: str, config: Dict) -> Dict[str, Any]:
    """Analyze a single MCP server configuration."""
    server_type = detect_server_type(config)

    result = {
        'name': name,
        'type': server_type,
        'description': config.get('description', ''),
        'command': config.get('command', ''),
        'args': config.get('args', []),
        'env_vars': list(config.get('env', {}).keys()),
    }

    # Extract source location
    if server_type == 'python-local':
        args = config.get('args', [])
        if args:
            source_path = Path(args[0])
            result['source'] = str(source_path)

            # Scan source code
            scan_result = scan_python_source(source_path)
            result['security'] = {
                'dangers': scan_result.get('dangers', []),
                'warnings': scan_result.get('warnings', []),
                'suspicious_imports': scan_result.get('suspicious_imports', []),
                'safe': len(scan_result.get('dangers', [])) == 0,
                'line_count': scan_result.get('line_count', 0),
            }

    elif server_type in ['npm-package', 'uvx-package']:
        package = extract_package_name(config, server_type)
        result['package'] = package

        if server_type == 'npm-package':
            # Fetch NPM package info
            package_info = get_npm_package_info(package)
            if 'error' not in package_info:
                result['npm_stats'] = package_info
                result['homepage'] = package_info.get('homepage', '')
                result['repository'] = package_info.get('repository', '')

            result['security'] = {
                'dangers': [],
                'warnings': [],
                'safe': True,
            }
        else:
            result['security'] = {
                'dangers': [],
                'warnings': [],
                'safe': True,
            }

    # Calculate trust score
    trust_score = calculate_trust_score(
        name, config, server_type,
        result.get('npm_stats', {})
    )
    result['trust_score'] = trust_score

    # Save audit scan to database
    if SUPABASE_ENABLED:
        try:
            audit_id = save_audit_scan(name, result)
            if audit_id:
                result['audit_id'] = audit_id
        except Exception as e:
            print(f"⚠️  Failed to save audit for {name}: {e}")

    return result


def fetch_official_registry(limit: int = 100, search: str = "", cursor: str = "") -> Dict[str, Any]:
    """Fetch servers from official MCP registry with cursor-based pagination."""
    try:
        url = f"https://registry.modelcontextprotocol.io/v0/servers?limit={limit}"
        if search:
            url += f"&search={urllib.parse.quote(search)}"
        if cursor:
            url += f"&cursor={urllib.parse.quote(cursor)}"

        req = urllib.request.Request(url)
        req.add_header('Accept', 'application/json')

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())

        return data

    except Exception as e:
        return {'error': str(e), 'servers': [], 'metadata': {}}


def analyze_external_server(server_data: Dict) -> Dict[str, Any]:
    """Analyze external server from registry (trust scoring only, no source scan)."""
    # Handle official MCP registry format: {server: {...}, _meta: {...}}
    server = server_data.get('server', server_data)

    # Extract metadata
    name = server.get('name', '')
    description = server.get('description', '')
    repository = server.get('repository', {})
    repo_url = repository.get('url', '') if isinstance(repository, dict) else str(repository)

    # Extract package info from packages array (official registry format)
    packages = server.get('packages', [])
    package = ''
    command = 'npx'
    args = []

    if packages and len(packages) > 0:
        pkg = packages[0]
        identifier = pkg.get('identifier', '')
        # Try to extract package name from identifier
        if '@' in identifier and '/' in identifier:
            # Format like docker.io/owner/package:version or registry/package
            parts = identifier.split('/')
            if len(parts) >= 2:
                package = f"{parts[-2]}/{parts[-1].split(':')[0]}"
        elif identifier:
            package = identifier.split(':')[0]

    # Check if official (from _meta)
    meta = server_data.get('_meta', {})
    official_meta = meta.get('io.modelcontextprotocol.registry/official', {})
    is_official = official_meta.get('status') == 'active'

    # Calculate trust score
    verified = is_official
    trust_score = 3 if verified else 1

    result = {
        'name': name,
        'package': package,
        'description': description,
        'command': command,
        'args': args if args else ['-y', package] if package else [],
        'repository': repo_url,
        'verified': verified,
        'stars': 0,  # Registry doesn't provide stars
        'category': '',
        'trust_score': trust_score,
        'installed': False,  # Will be checked against local config
    }

    # Save to catalog database
    if SUPABASE_ENABLED:
        try:
            save_catalog_server(result)
        except Exception as e:
            print(f"⚠️  Failed to save catalog server {name}: {e}")

    return result


def install_server(name: str, config: Dict) -> Dict[str, Any]:
    """Install a server by adding it to .mcp.json."""
    try:
        # Check which config file to use (prefer main)
        target_config = MCP_CONFIG_MAIN

        # Read current config
        if target_config.exists():
            with open(target_config, 'r') as f:
                current_config = json.load(f)
        else:
            current_config = {'mcpServers': {}}

        # Check if server already exists
        if name in current_config.get('mcpServers', {}):
            return {'success': False, 'error': f'Server "{name}" already exists'}

        # Add new server
        current_config.setdefault('mcpServers', {})[name] = config

        # Write atomically (temp file + rename)
        temp_file = target_config.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(current_config, f, indent=2)

        temp_file.replace(target_config)

        # Record installation in Supabase
        if SUPABASE_ENABLED:
            try:
                save_installation_history(name, config, 'ui-install')
            except Exception as e:
                print(f"⚠️  Failed to record installation in database: {e}")

        return {'success': True, 'message': f'Server "{name}" installed successfully'}

    except Exception as e:
        return {'success': False, 'error': str(e)}


# =============================================================================
# Supabase Database Functions
# =============================================================================

def compute_source_hash(source_code: str) -> str:
    """Compute SHA256 hash of source code."""
    return hashlib.sha256(source_code.encode('utf-8')).hexdigest()


def save_audit_scan(server_name: str, analysis: Dict[str, Any]) -> Optional[str]:
    """Save audit scan results to Supabase."""
    if not SUPABASE_ENABLED or not supabase:
        return None

    try:
        # Compute source hash if available
        source_hash = None
        if analysis.get('source'):
            source_hash = compute_source_hash(analysis['source'])

        # Prepare audit data
        audit_data = {
            'server_name': server_name,
            'scan_timestamp': datetime.utcnow().isoformat(),
            'server_type': analysis.get('type', 'unknown'),
            'trust_score': analysis.get('trust_score', 1),
            'dangers': json.dumps(analysis.get('security', {}).get('dangers', [])),
            'warnings': json.dumps(analysis.get('security', {}).get('warnings', [])),
            'suspicious_imports': json.dumps(analysis.get('security', {}).get('suspicious_imports', [])),
            'line_count': analysis.get('security', {}).get('line_count', 0),
            'source_hash': source_hash,
            'package_name': analysis.get('package', ''),
            'package_version': analysis.get('npm_stats', {}).get('version', ''),
            'config': json.dumps({
                'command': analysis.get('command', ''),
                'args': analysis.get('args', []),
                'env_vars': analysis.get('env_vars', []),
                'description': analysis.get('description', '')
            }),
            'npm_stats': json.dumps(analysis.get('npm_stats', {}))
        }

        # Insert into database
        result = supabase.table('audit_scans').insert(audit_data).execute()

        if result.data and len(result.data) > 0:
            return result.data[0].get('id')
        return None

    except Exception as e:
        print(f"⚠️  Failed to save audit scan: {e}")
        return None


def save_catalog_server(server_data: Dict[str, Any]) -> Optional[str]:
    """Save catalog server to Supabase (upserts based on name+package)."""
    if not SUPABASE_ENABLED or not supabase:
        return None

    try:
        catalog_data = {
            'server_name': server_data.get('name', ''),
            'package_name': server_data.get('package', ''),
            'description': server_data.get('description', ''),
            'repository': server_data.get('repository', ''),
            'homepage': server_data.get('homepage', ''),
            'verified': server_data.get('verified', False),
            'stars': server_data.get('stars', 0),
            'category': server_data.get('category', ''),
            'metadata': json.dumps(server_data),
            'last_seen': datetime.utcnow().isoformat()
        }

        # Upsert (insert or update)
        result = supabase.table('catalog_servers').upsert(
            catalog_data,
            on_conflict='server_name,package_name'
        ).execute()

        if result.data and len(result.data) > 0:
            return result.data[0].get('id')
        return None

    except Exception as e:
        print(f"⚠️  Failed to save catalog server: {e}")
        return None


def save_installation_history(server_name: str, config: Dict, method: str = 'manual') -> Optional[str]:
    """Record server installation in history."""
    if not SUPABASE_ENABLED or not supabase:
        return None

    try:
        install_data = {
            'server_name': server_name,
            'installed_at': datetime.utcnow().isoformat(),
            'config': json.dumps(config),
            'installation_method': method
        }

        result = supabase.table('installation_history').insert(install_data).execute()

        if result.data and len(result.data) > 0:
            return result.data[0].get('id')
        return None

    except Exception as e:
        print(f"⚠️  Failed to save installation history: {e}")
        return None


def get_audit_history(server_name: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """Get audit history from database."""
    if not SUPABASE_ENABLED or not supabase:
        return []

    try:
        query = supabase.table('audit_scans').select('*').order('scan_timestamp', desc=True).limit(limit)

        if server_name:
            query = query.eq('server_name', server_name)

        result = query.execute()
        return result.data if result.data else []

    except Exception as e:
        print(f"⚠️  Failed to get audit history: {e}")
        return []


def get_security_trends(days: int = 30) -> List[Dict]:
    """Get security trends from database."""
    if not SUPABASE_ENABLED or not supabase:
        return []

    try:
        result = supabase.table('security_trends').select('*').limit(1000).execute()
        return result.data if result.data else []

    except Exception as e:
        print(f"⚠️  Failed to get security trends: {e}")
        return []


def search_catalog_history(search: str = '', limit: int = 100) -> List[Dict]:
    """Search catalog server history."""
    if not SUPABASE_ENABLED or not supabase:
        return []

    try:
        query = supabase.table('catalog_servers').select('*').order('last_seen', desc=True).limit(limit)

        if search:
            query = query.ilike('server_name', f'%{search}%')

        result = query.execute()
        return result.data if result.data else []

    except Exception as e:
        print(f"⚠️  Failed to search catalog: {e}")
        return []


class MCPInspectorHandler(http.server.BaseHTTPRequestHandler):
    """Serve MCP Inspector UI and API."""

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass

    def do_GET(self):
        """Handle GET requests."""
        if self.path in ['/', '/mcp_inspector.html']:
            self._serve_html()
        elif self.path == '/api/servers':
            self._serve_servers_list()
        elif self.path.startswith('/api/server/'):
            server_name = self.path.split('/')[-1]
            self._serve_server_detail(server_name)
        elif self.path.startswith('/api/source/'):
            server_name = self.path.split('/')[-1]
            self._serve_source_code(server_name)
        elif self.path.startswith('/api/browse/official'):
            self._serve_browse_official()
        elif self.path.startswith('/api/history/audits'):
            self._serve_audit_history()
        elif self.path.startswith('/api/history/trends'):
            self._serve_security_trends()
        elif self.path.startswith('/api/history/installations'):
            self._serve_installation_history()
        elif self.path == '/api/database/status':
            self._serve_database_status()
        elif self.path.startswith('/media/'):
            self._serve_static()
        else:
            self.send_error(404, f"Path {self.path} not found")

    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/api/install':
            self._handle_install()
        else:
            self.send_error(404, f"Path {self.path} not found")

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _serve_html(self):
        """Serve the main HTML file."""
        try:
            with open(HTML_FILE, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, f"{HTML_FILE} not found")

    def _serve_static(self):
        """Serve static media files."""
        file_path = (MEDIA_DIR / self.path.replace('/media/', '', 1)).resolve()
        if not str(file_path).startswith(str(MEDIA_DIR.resolve())):
            self.send_error(403, "Forbidden")
            return
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, f"{file_path} not found")
            return

        content_type = 'application/octet-stream'
        if file_path.suffix == '.svg':
            content_type = 'image/svg+xml'
        elif file_path.suffix in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            content_type = f"image/{file_path.suffix.lstrip('.')}"

        with open(file_path, 'rb') as f:
            content = f.read()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(content))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(content)

    def _serve_servers_list(self):
        """Serve list of all configured servers."""
        servers_config = parse_mcp_configs()
        servers = []

        for name, config in servers_config.items():
            server_info = analyze_server(name, config)
            servers.append(server_info)

        # Sort by trust score (desc), then name
        servers.sort(key=lambda s: (-s['trust_score'], s['name']))

        response_data = {
            'servers': servers,
            'total': len(servers),
            'config_locations': [
                str(MCP_CONFIG_MAIN),
                str(MCP_CONFIG_PROJECTS),
            ]
        }

        response = json.dumps(response_data, indent=2).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response)

    def _serve_server_detail(self, server_name: str):
        """Serve detailed info for a specific server."""
        servers_config = parse_mcp_configs()

        if server_name not in servers_config:
            self.send_error(404, f"Server {server_name} not found")
            return

        server_info = analyze_server(server_name, servers_config[server_name])

        response = json.dumps(server_info, indent=2).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response)

    def _serve_source_code(self, server_name: str):
        """Serve source code for local Python servers."""
        servers_config = parse_mcp_configs()

        if server_name not in servers_config:
            self.send_error(404, f"Server {server_name} not found")
            return

        config = servers_config[server_name]
        server_type = detect_server_type(config)

        if server_type != 'python-local':
            error = json.dumps({'error': 'Source code only available for local Python servers'}).encode()
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(error))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(error)
            return

        args = config.get('args', [])
        if not args:
            self.send_error(400, "No source file in args")
            return

        source_path = Path(args[0])
        if not source_path.exists():
            self.send_error(404, f"Source file not found: {source_path}")
            return

        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            response = json.dumps({'source': source_code, 'path': str(source_path)}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)

        except Exception as e:
            error = json.dumps({'error': str(e)}).encode()
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(error))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(error)

    def _serve_browse_official(self):
        """Serve list of servers from official registry."""
        # Parse query parameters
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        limit = int(params.get('limit', ['100'])[0])
        search = params.get('search', [''])[0]
        cursor = params.get('cursor', [''])[0]

        # Fetch from registry
        registry_data = fetch_official_registry(limit, search, cursor)

        if 'error' in registry_data:
            error = json.dumps(registry_data).encode()
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(error))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(error)
            return

        # Analyze each server and check if installed
        installed_servers = parse_mcp_configs()
        servers = []

        for server in registry_data.get('servers', []):
            analyzed = analyze_external_server(server)
            # Check if already installed
            analyzed['installed'] = analyzed['name'] in installed_servers
            servers.append(analyzed)

        # Extract pagination metadata
        metadata = registry_data.get('metadata', {})
        next_cursor = metadata.get('nextCursor', None)

        response_data = {
            'servers': servers,
            'count': len(servers),
            'nextCursor': next_cursor,
            'hasMore': next_cursor is not None,
        }

        response = json.dumps(response_data, indent=2).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response)

    def _handle_install(self):
        """Handle server installation request."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No request body")
                return

            body = self.rfile.read(content_length)
            data = json.loads(body)

            # Extract installation data
            name = data.get('name')
            config = data.get('config', {})

            if not name:
                error = json.dumps({'success': False, 'error': 'Missing server name'}).encode()
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', len(error))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(error)
                return

            # Install the server
            result = install_server(name, config)

            response = json.dumps(result).encode()
            status = 200 if result.get('success') else 400
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response)

        except json.JSONDecodeError as e:
            error = json.dumps({'success': False, 'error': f'Invalid JSON: {str(e)}'}).encode()
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(error))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(error)

        except Exception as e:
            error = json.dumps({'success': False, 'error': str(e)}).encode()
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(error))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(error)

    def _serve_audit_history(self):
        """Serve audit history from database."""
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        server_name = params.get('server', [None])[0]
        limit = int(params.get('limit', ['100'])[0])

        audits = get_audit_history(server_name, limit)

        response_data = {
            'audits': audits,
            'count': len(audits),
            'database_enabled': SUPABASE_ENABLED
        }

        response = json.dumps(response_data, indent=2, default=str).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response)

    def _serve_security_trends(self):
        """Serve security trends from database."""
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        days = int(params.get('days', ['30'])[0])

        trends = get_security_trends(days)

        response_data = {
            'trends': trends,
            'count': len(trends),
            'database_enabled': SUPABASE_ENABLED
        }

        response = json.dumps(response_data, indent=2, default=str).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response)

    def _serve_installation_history(self):
        """Serve installation history from database."""
        if not SUPABASE_ENABLED or not supabase:
            response_data = {
                'installations': [],
                'count': 0,
                'database_enabled': False
            }
        else:
            try:
                result = supabase.table('installation_history').select('*').order('installed_at', desc=True).limit(100).execute()
                installations = result.data if result.data else []

                response_data = {
                    'installations': installations,
                    'count': len(installations),
                    'database_enabled': True
                }
            except Exception as e:
                response_data = {
                    'installations': [],
                    'count': 0,
                    'error': str(e),
                    'database_enabled': True
                }

        response = json.dumps(response_data, indent=2, default=str).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response)

    def _serve_database_status(self):
        """Serve database connection status."""
        status_data = {
            'enabled': SUPABASE_ENABLED,
            'url': SUPABASE_URL if SUPABASE_ENABLED else None,
            'connected': False
        }

        if SUPABASE_ENABLED and supabase:
            try:
                # Test connection with a simple query
                result = supabase.table('audit_scans').select('id').limit(1).execute()
                status_data['connected'] = True
                status_data['message'] = 'Database connected successfully'
            except Exception as e:
                status_data['error'] = str(e)
                status_data['message'] = f'Database connection failed: {str(e)}'

        response = json.dumps(status_data, indent=2).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response)


class ReuseTCPServer(socketserver.TCPServer):
    """TCP server with SO_REUSEADDR enabled."""
    allow_reuse_address = True

    def server_bind(self):
        """Set SO_REUSEADDR on socket before binding."""
        self.socket.setsockopt(socketserver.socket.SOL_SOCKET, socketserver.socket.SO_REUSEADDR, 1)
        super().server_bind()


if __name__ == "__main__":
    print(f"🔍 MCP Inspector Server")
    print(f"   Port: {PORT}")
    print(f"   Configs:")
    print(f"     - {MCP_CONFIG_MAIN}")
    print(f"     - {MCP_CONFIG_PROJECTS}")
    print(f"   Access: http://127.0.0.1:{PORT}")
    print(f"   LAN: http://192.168.7.226:{PORT}")
    print()

    # Start server
    with ReuseTCPServer(("", PORT), MCPInspectorHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n✓ MCP Inspector server stopped")
