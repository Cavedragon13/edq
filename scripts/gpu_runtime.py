"""gpu_runtime.py — shared GPU runtime safety for Dragonsuite server scripts.

CANONICAL SOURCE. The dragonsuite-add skill installs an identical copy to
/srv/containers/edq/scripts/gpu_runtime.py, which every server script imports.
Improve the OOM handling once here; redeploy; all services benefit.

This is the runtime companion to scripts/vram_guard.sh:
  - vram_guard.sh runs in the LAUNCHER and refuses to start if VRAM is short.
  - gpu_runtime.py runs in the SERVER and keeps a mid-generation OOM from
    crashing the process with a stack trace.

Usage — import BEFORE `import torch` so the CUDA allocator is configured before
CUDA initializes:

    import gpu_runtime          # sets PYTORCH_CUDA_ALLOC_CONF on import
    import torch

Wrap any VRAM-heavy call so an OOM warns cleanly instead of crashing:

    # Long-running server (Gradio/FastAPI): catch the clean error, keep serving.
    try:
        with gpu_runtime.oom_guard("image generation"):
            result = pipe(prompt)
    except RuntimeError as e:
        raise gr.Error(str(e))         # Gradio; or return HTTP 507 in FastAPI

    # One-shot CLI script: print the message and exit 1 instead of a traceback.
    with gpu_runtime.oom_guard("generate", exit_on_oom=True):
        result = generate(args)
"""

import contextlib
import os
import sys

# Must be set before torch initializes CUDA. setdefault() so an explicit value
# already exported by the launcher (set_pytorch_env) is respected, not clobbered.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")


def _is_cuda_oom(exc: BaseException) -> bool:
    """True if exc is a CUDA out-of-memory error.

    Prefer torch.cuda.OutOfMemoryError (PyTorch >= 1.13, subclass of
    RuntimeError); fall back to message sniffing for OOMs that surface as a
    plain RuntimeError (e.g. some cuDNN/cuBLAS paths).
    """
    try:
        import torch
        if isinstance(exc, torch.cuda.OutOfMemoryError):
            return True
    except Exception:
        pass
    return "out of memory" in str(exc).lower()


def free_cuda_cache() -> None:
    """Release cached VRAM back to the driver. Safe to call anytime."""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass


@contextlib.contextmanager
def oom_guard(label: str = "operation", *, exit_on_oom: bool = False):
    """Turn a mid-generation CUDA OOM into a clean message instead of a crash.

    On OOM: frees the CUDA cache, then either
      - re-raises RuntimeError(clean_msg) (default) so a server can map it to a
        user-facing error (gr.Error / HTTP 507) and keep serving, or
      - prints clean_msg to stderr and sys.exit(1) when exit_on_oom=True, for
        one-shot CLI scripts.
    Non-OOM exceptions propagate unchanged.
    """
    try:
        yield
    except BaseException as exc:
        if not _is_cuda_oom(exc):
            raise
        free_cuda_cache()
        msg = (f"⚠️  Out of VRAM during {label}. Freed cache and aborted this "
               f"request — close other GPU tools or try a smaller input.")
        if exit_on_oom:
            print(msg, file=sys.stderr)
            sys.exit(1)
        raise RuntimeError(msg) from None
