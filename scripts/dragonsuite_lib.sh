#!/bin/bash
# dragonsuite_lib.sh — Shared functions for all Dragonsuite service launchers
# Source this at the top of every start_*.sh:
#   source "$(dirname "$0")/dragonsuite_lib.sh"

# ─── Paths ────────────────────────────────────────────────────────────────────
DRAGONSUITE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRAGONSUITE_CONFIG="$DRAGONSUITE_ROOT/config/dragonsuite.json"

# ─── GPU Eviction ─────────────────────────────────────────────────────────────

# Kill any Python AI processes that are holding VRAM, except:
#   - Ollama (managed separately, always-on)
#   - The Dragonsuite dashboard itself
#   - The calling script's own process
#
# Usage: evict_gpu_processes
evict_gpu_processes() {
    local freed=0

    # Find Python processes with VRAM > 100MB (AI models, not tiny utilities)
    while IFS=, read -r pid vram name; do
        pid="${pid// /}"
        vram="${vram// /}"
        name="${name// /}"

        # Skip non-Python processes (Ollama handles its own VRAM)
        cmdline=$(cat /proc/$pid/cmdline 2>/dev/null | tr '\0' ' ')
        [[ "$cmdline" == *"python"* ]] || continue
        [[ "$cmdline" == *"dragonsuite_server"* ]] && continue
        [[ "$cmdline" == *"ollama"* ]] && continue

        echo "  ⚡ Evicting PID $pid (${vram} VRAM): $(echo "$cmdline" | grep -oP '[^/]+\.py' | head -1)"
        kill -TERM "$pid" 2>/dev/null || true
        freed=1
    done < <(nvidia-smi --query-compute-apps=pid,used_memory,name --format=csv,noheader 2>/dev/null | \
             awk -F, '{gsub(/ /,"",$2); gsub(/MiB/,"",$2); if ($2+0 > 100) print}')

    if [ "$freed" -eq 1 ]; then
        echo "  ⏳ Waiting for VRAM to clear..."
        sleep 3
    fi
}

# ─── LM Studio Eviction ───────────────────────────────────────────────────────

# Kill LM Studio if running (it holds ~400MB VRAM + RAM even when idle)
evict_lmstudio() {
    if pgrep -f "lmstudio\|LM_Studio\|\.lmstudio" > /dev/null 2>&1; then
        echo "  ⚡ Evicting LM Studio (idle VRAM consumer)..."
        pkill -f "lmstudio\|LM_Studio\|\.lmstudio" 2>/dev/null || true
        sleep 2
    fi
}

# ─── Port Cleanup ─────────────────────────────────────────────────────────────

# Kill anything holding a port before we try to bind it
# Usage: clear_port 8011
clear_port() {
    local port="$1"
    local pids
    pids=$(lsof -ti ":$port" 2>/dev/null) || true
    if [ -n "$pids" ]; then
        echo "  ⚡ Clearing port $port (PIDs: $pids)..."
        echo "$pids" | xargs kill -TERM 2>/dev/null || true
        sleep 2
        # SIGKILL any survivors
        pids=$(lsof -ti ":$port" 2>/dev/null) || true
        [ -n "$pids" ] && echo "$pids" | xargs kill -KILL 2>/dev/null || true
    fi
}

# ─── VRAM Report ──────────────────────────────────────────────────────────────

# Print current VRAM state
vram_status() {
    nvidia-smi --query-gpu=name,memory.used,memory.free,memory.total \
        --format=csv,noheader 2>/dev/null | \
        awk -F, '{printf "  GPU: %s | Used: %s | Free: %s / %s\n", $1, $2, $3, $4}'
}

# ─── Port Wait ────────────────────────────────────────────────────────────────

# Wait for a port to become active (service startup)
# Usage: wait_for_port 8011 30
wait_for_port() {
    local port="$1"
    local timeout="${2:-30}"
    local elapsed=0
    while ! curl -s --max-time 1 "http://127.0.0.1:$port" > /dev/null 2>&1; do
        sleep 1
        elapsed=$((elapsed + 1))
        if [ "$elapsed" -ge "$timeout" ]; then
            return 1
        fi
    done
    return 0
}

# ─── Standard Service Header ──────────────────────────────────────────────────

# Print a standard header for service startup
# Usage: service_header "Z-Image Base" 8011
service_header() {
    local name="$1"
    local port="$2"
    echo ""
    echo "🐉 $name"
    echo "$(echo "$name" | sed 's/./─/g')──"
    echo "   Port:  $port"
    echo "   LAN:   http://192.168.7.226:$port"
    echo "   Local: http://localhost:$port"
    echo ""
}

# ─── Standard GPU Service Start ───────────────────────────────────────────────

# Full pre-flight for GPU services: evict + clear port + show VRAM
# Usage: gpu_preflight 8011
gpu_preflight() {
    local port="$1"
    echo "🔧 Pre-flight checks..."
    vram_status
    evict_lmstudio
    evict_gpu_processes
    clear_port "$port"
    echo "✓ VRAM after eviction:"
    vram_status
    echo ""
}

# ─── Standard Venv Activation ─────────────────────────────────────────────────

# Activate a venv, fail clearly if it doesn't exist
# Usage: activate_venv venv_zimage
activate_venv() {
    local venv_name="$1"
    local venv_path="$DRAGONSUITE_ROOT/$venv_name"
    if [ ! -f "$venv_path/bin/activate" ]; then
        echo "❌ Venv not found: $venv_path"
        echo "   Run the setup/install script first."
        exit 1
    fi
    source "$venv_path/bin/activate"
    echo "✓ Venv: $venv_name"
}

# ─── PyTorch Memory Env ───────────────────────────────────────────────────────

# Set standard PyTorch VRAM optimizations
set_pytorch_env() {
    export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
    export CUDA_VISIBLE_DEVICES=0
}
