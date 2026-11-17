"""Compatibility import for the shared Sales Order completion helpers.

The app keeps API/report modules under ``client_akivision.client_akivision``
while older modules import utilities from ``client_akivision.utils``.  Keep
both import paths valid so dashboard and report endpoints load consistently.
"""

from client_akivision.client_akivision.utils.sales_order_completion import *  # noqa: F401,F403
