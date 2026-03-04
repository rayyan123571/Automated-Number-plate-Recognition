"""Quick test to check if ws_detection router loads correctly."""
import sys
try:
    from app.routes.ws_detection import router
    print("OK: ws_detection imported successfully")
    for route in router.routes:
        print(f"  Route: {route.path} ({type(route).__name__})")
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()

# Also check all routes on the app
print("\n--- All app routes ---")
try:
    from app.main import app
    for route in app.routes:
        path = getattr(route, 'path', '?')
        name = type(route).__name__
        print(f"  {path} ({name})")
except Exception as e:
    print(f"APP IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()
