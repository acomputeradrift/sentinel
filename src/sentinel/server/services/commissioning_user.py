"""Stub commissioning console user until real authentication is implemented.

The stub user is the dealer/company operator for this slice: named technicians
belong to that operator. There is no login product yet.
"""

# Deterministic ID — keep in sync with migration ``006_users_scoped_clients.sql``.
COMMISSIONING_STUB_USER_ID = "8a7e9c2d-5f41-4b9c-9c31-2b8f0e6d1a00"
COMMISSIONING_STUB_DISPLAY_NAME = "Jamie"
COMMISSIONING_STUB_COMPANY_ID = COMMISSIONING_STUB_USER_ID
COMMISSIONING_STUB_COMPANY_NAME = COMMISSIONING_STUB_DISPLAY_NAME
