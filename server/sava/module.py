"""SAVA module definition (new async Module system).

Registered by adding ``MODULES.append("sava")`` in the Superdesk server
``settings.py``; the app then imports the ``sava`` package and reads this
``module`` instance.
"""

from superdesk.core.module import Module

from .views import sava_endpoints

module = Module("sava", endpoints=[sava_endpoints])
