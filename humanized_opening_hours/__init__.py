"""A parser for the opening_hours fields from OpenStreetMap.

Provides an OHParser object with the most useful methods
(`is_open()`, `next_change()`, etc). Allows you to set
public and school holidays. Provides a `description()` method
to get a human-readable describing of the opening hours.

Automatically sanitizes the fields to prevent some common mistakes.

To get started, simply do:
>>> import humanized_opening_hours as hoh
>>> oh = hoh.OHParser("Mo-Sa 10:00-19:00")
"""
# flake8: noqa

__version__ = "1.0.0b2"
__appname__ = "osm_humanized_opening_hours"
__author__ = "rezemika <reze.mika@gmail.com>"
__licence__ = "AGPLv3"

import os as _os
import gettext as _gettext
_gettext.install("HOH",
    _os.path.join(
        _os.path.dirname(_os.path.realpath(__file__)), "locales"
    )
)

from humanized_opening_hours.main import OHParser, sanitize, days_of_week
from humanized_opening_hours.temporal_objects import easter_date
from humanized_opening_hours.rendering import AVAILABLE_LOCALES
from humanized_opening_hours import exceptions
