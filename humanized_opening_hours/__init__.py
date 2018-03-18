"""A parser for the opening_hours fields from OpenStreetMap.

Provides an OHParser object with the most useful methods
(`is_open()`, `next_change()`, etc). Allows you to set
public and school holidays. Provides a `render()` method
to get human-readable strings describing the opening hours.

Automatically sanitizes the fields to prevent some common mistakes.

To get started, simply do:
>>> import humanized_opening_hours as hoh
>>> oh = hoh.OHParser("Th-Sa 10:00-19:00")
"""
# flake8: noqa

__version__ = "0.5.0"
__appname__ = "osm_humanized_opening_hours"
__author__ = "rezemika <reze.mika@gmail.com>"
__licence__ = "AGPLv3"

import gettext
gettext.install("HOH", "locales/")

from humanized_opening_hours.main import (
    OHParser,
    HOHRenderer,
    days_of_week_from_day
)

from humanized_opening_hours import exceptions
