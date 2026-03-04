# =============================================================================
# app/models/__init__.py
# =============================================================================
# PURPOSE:
#   Package marker for the `models` module.  This module holds Pydantic
#   schemas used for request validation and response serialization.
#
# WHY IT EXISTS:
#   Separating data contracts (schemas) from business logic (services)
#   and transport (routes) is a core Clean Architecture principle.
#   It enables reuse and makes testing trivial.
# =============================================================================
