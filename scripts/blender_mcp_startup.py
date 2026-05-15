#!/usr/bin/env python3
"""
Blender MCP Startup Script
Enables the BlenderMCP addon and starts the server
"""
import bpy
import addon_utils
import importlib.util
import sys
import time

ADDON_PATH = "/srv/containers/edq/scripts/blender_mcp_addon.py"

print("Starting BlenderMCP addon...", flush=True)

# Enable the BlenderMCP addon
addon_name = 'blender_mcp_addon'
addon_module = None
try:
    spec = importlib.util.spec_from_file_location(addon_name, ADDON_PATH)
    addon_module = importlib.util.module_from_spec(spec)
    sys.modules[addon_name] = addon_module
    spec.loader.exec_module(addon_module)
    addon_module.register()
    print(f"✓ Registered addon from {ADDON_PATH}", flush=True)
except Exception as e:
    print(f"Direct addon registration failed: {e}", flush=True)
    try:
        addon_utils.enable(addon_name, default_set=True)
        addon_module = sys.modules.get(addon_name)
        print(f"✓ Enabled addon: {addon_name}", flush=True)
    except Exception as enable_error:
        print(f"Error enabling addon: {enable_error}", flush=True)

# Auto-connect the MCP server
try:
    if hasattr(bpy.ops, 'blendermcp'):
        if hasattr(bpy.ops.blendermcp, 'start_server'):
            bpy.ops.blendermcp.start_server()
            print('✓ BlenderMCP server started and listening on port 9876', flush=True)
        else:
            print('⚠️ start_server operator not found', flush=True)
    else:
        print('⚠️ blendermcp operators not found', flush=True)

    if addon_module and not hasattr(bpy.types, "blendermcp_server"):
        bpy.types.blendermcp_server = addon_module.BlenderMCPServer(port=9876)
        bpy.types.blendermcp_server.start()
        print('✓ BlenderMCP server started directly on port 9876', flush=True)
except Exception as e:
    print(f"Error starting MCP server: {e}", flush=True)

# Keep Blender running (wait indefinitely)
print("✓ Blender running in headless mode, MCP server active...", flush=True)
while True:
    time.sleep(3600)
