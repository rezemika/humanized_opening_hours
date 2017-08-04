# -*- coding: utf-8 -*-

"""
    A parser for the opening_hours fields from OpenStreetMap.
    
    Provides Day objects, containing (among others) datetime.time objects
    representing the beginning and the end of all the opening periods.
    Can handle solar hours with "sunrise" or "sunset", including with
    offset like "(sunrise+02:00)".
    
    Automatically sanitizes the fields to prevent some common mistakes.
"""

__version__ = "0.1.0"
__appname__ = "humanized_opening_hours"
__author__ = "rezemika <reze.mika@gmail.com>"
__licence__ = "AGPLv3"

import sys as _sys
import os as _os
_sys.path.append(_os.path.dirname(_os.path.abspath(__file__)))

from humanized_opening_hours.humanized_opening_hours import HumanizedOpeningHours
