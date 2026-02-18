#!/usr/bin/env python3
"""
Blender MCP Startup Script
Enables the BlenderMCP addon and starts the server
"""
import bpy
import addon_utils
import time

print("Starting BlenderMCP addon...")

# Enable the BlenderMCP addon
addon_name = 'blender_mcp_addon'
try:
    addon_utils.enable(addon_name, default_set=True)
    print(f"✓ Enabled addon: {addon_name}")
except Exception as e:
    print(f"Error enabling addon: {e}")

# Auto-connect the MCP server
try:
    if hasattr(bpy.ops, 'blendermcp'):
        if hasattr(bpy.ops.blendermcp, 'start_server'):
            bpy.ops.blendermcp.start_server()
            print('✓ BlenderMCP server started and listening on port 9876')
        else:
            print('⚠️ start_server operator not found')
    else:
        print('⚠️ blendermcp operators not found')
except Exception as e:
    print(f"Error starting MCP server: {e}")

# Keep Blender running (wait indefinitely)
print("✓ Blender running in headless mode, MCP server active...")
while True:
    time.sleep(3600)
