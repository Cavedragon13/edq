#!/usr/bin/env python3
"""
Standalone diagnostic test for Topaz Labs MCP Server
Run this to debug issues without Claude Code:

  cd /srv/containers/edq/mcp-servers/topaz-labs
  source venv/bin/activate
  source /srv/containers/edq/.env
  python test_server.py
"""

import os
import sys


def test_imports() -> bool:
    print("Testing imports...")
    try:
        import httpx
        import mcp
        print(f"  ✓ httpx {httpx.__version__}")
        print(f"  ✓ mcp {mcp.__version__}")
        return True
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        print("  Fix: source venv/bin/activate && pip install -r requirements.txt")
        return False


def test_api_key() -> bool:
    print("\nTesting API key...")
    api_key = os.getenv("TOPAZ_API_KEY")
    if not api_key:
        print("  ❌ TOPAZ_API_KEY not set!")
        print("  Fix: source /srv/containers/edq/.env")
        return False
    redacted = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "****"
    print(f"  ✓ TOPAZ_API_KEY found: {redacted}")
    return True


def test_api_connectivity() -> bool:
    print("\nTesting API connectivity...")
    try:
        import httpx

        api_key = os.getenv("TOPAZ_API_KEY")
        if not api_key:
            print("  ⚠️  Skipping (no API key)")
            return False

        with httpx.Client(timeout=10.0) as client:
            # Test with a HEAD request to the enhance endpoint
            try:
                response = client.head(
                    "https://api.topazlabs.com/image/v1/enhance",
                    headers={"X-API-Key": api_key}
                )
                # 405 Method Not Allowed = endpoint exists (just needs POST)
                if response.status_code in [200, 405, 400]:
                    print(f"  ✓ API reachable (status: {response.status_code})")
                    return True
                elif response.status_code == 401:
                    print(f"  ❌ API key rejected (401 Unauthorized)")
                    print("  Check your key at https://topazlabs.com/my-account/")
                    return False
                else:
                    print(f"  ⚠️  Unexpected status: {response.status_code}")
                    return False
            except httpx.ConnectError:
                print("  ❌ Cannot connect to api.topazlabs.com")
                print("  Check network connectivity")
                return False
    except Exception as e:
        print(f"  ❌ Connectivity test failed: {e}")
        return False


def test_log_directory() -> bool:
    print("\nTesting log directory...")
    from pathlib import Path
    log_dir = Path(__file__).parent / "logs"
    try:
        log_dir.mkdir(exist_ok=True)
        test_file = log_dir / ".test_write"
        test_file.write_text("ok")
        test_file.unlink()
        print(f"  ✓ Log directory writable: {log_dir}")
        return True
    except Exception as e:
        print(f"  ❌ Cannot write to log directory: {e}")
        return False


def main():
    print("=" * 60)
    print("Topaz Labs MCP Server - Diagnostic Test")
    print("=" * 60)

    tests = [
        ("Imports", test_imports),
        ("API Key", test_api_key),
        ("API Connectivity", test_api_connectivity),
        ("Log Directory", test_log_directory),
    ]

    results = []
    for name, func in tests:
        results.append((name, func()))

    print("\n" + "=" * 60)
    passed = sum(1 for _, p in results if p)
    for name, result in results:
        print(f"  {'✓ PASS' if result else '❌ FAIL':10} {name}")
    print(f"\nPassed: {passed}/{len(tests)}")

    if passed == len(tests):
        print("\n✅ All tests passed! Server should work correctly.")
        print(f"\nLog file location:")
        from pathlib import Path
        from datetime import datetime
        print(f"  {Path(__file__).parent / 'logs' / f'topaz_mcp_{datetime.now().strftime(\"%Y%m%d\")}.log'}")
    else:
        print("\n⚠️  Some tests failed. Fix issues above and re-run.")
        sys.exit(1)


if __name__ == "__main__":
    main()
