# =============================================================================
# app/services/__init__.py
# =============================================================================
# PURPOSE:
#   Package marker for the `services` module.  Services encapsulate
#   all business / AI logic (model loading, inference, post-processing).
#
# WHY IT EXISTS:
#   The Service Layer pattern decouples HTTP concerns (routes) from
#   domain logic.  Routes only call services; services never import
#   routes.  This makes the AI pipeline testable without spinning up
#   a web server.
# =============================================================================
