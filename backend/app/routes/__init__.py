# =============================================================================
# app/routes/__init__.py
# =============================================================================
# PURPOSE:
#   Package marker for the `routes` module.  Each file inside defines
#   an APIRouter for a specific domain (health, detection, etc.).
#
# WHY IT EXISTS:
#   Router-per-feature keeps endpoints organized and allows independent
#   versioning, testing, and middleware attachment.
# =============================================================================
