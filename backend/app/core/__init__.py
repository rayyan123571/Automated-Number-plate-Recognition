# =============================================================================
# app/core/__init__.py
# =============================================================================
# PURPOSE:
#   Package marker for the `core` module which holds application-wide
#   configuration (env vars, settings) and the logging setup.
#
# WHY IT EXISTS:
#   Clean Architecture — the "core" layer has zero dependency on routes
#   or services.  Everything else depends on core, never the reverse.
# =============================================================================
