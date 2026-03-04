# =============================================================================
# app/__init__.py
# =============================================================================
# PURPOSE:
#   Makes the `app/` directory a Python package so that all submodules
#   (core, models, routes, services, utils) can be imported using
#   dotted paths like `from app.core.config import settings`.
#
# WHY IT EXISTS:
#   Without this file Python would not recognize `app/` as a package,
#   and all internal imports would break.
# =============================================================================
