"""Fast route check - no model loading."""
import importlib
import sys

# Only import the router module, NOT the full app (to avoid model loading)
print("Testing ws_detection router import...")
try:
    mod = importlib.import_module("app.routes.ws_detection")
    router = mod.router
    print(f"OK: router has {len(router.routes)} routes")
    for r in router.routes:
        print(f"  {r.path} - {type(r).__name__}")
except Exception as e:
    print(f"FAIL: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
