import re

from lark.lark import Tree
from lark.lexer import Token

from humanized_opening_hours.temporal_objects import WEEKDAYS

# flake8: noqa

FREQUENT_FIELDS = {
    "24/7": Tree("time_domain", [Tree("rule_sequence", [Tree("always_open", [Token("ALWAYS_OPEN", '24/7')])])]),
    "sunrise-sunset": Tree("time_domain", [Tree("rule_sequence", [Tree("selector_sequence", [Tree("time_selector", [Tree("timespan", [Tree("time", [Tree("variable_time", [Token("EVENT", 'sunrise')])]), Tree("time", [Tree("variable_time", [Token("EVENT", 'sunset')])])])])])])]),
    "sunset-sunrise": Tree("time_domain", [Tree("rule_sequence", [Tree("selector_sequence", [Tree("time_selector", [Tree("timespan", [Tree("time", [Tree("variable_time", [Token("EVENT", 'sunset')])]), Tree("time", [Tree("variable_time", [Token("EVENT", 'sunrise')])])])])])])]),
}


RE_WDAY_OFF = re.compile("^[A-Z][a-z] off$")
RE_WDAY_TIMESPAN = re.compile("^[A-Z][a-z] [0-9]{2}:[0-9]{2}-[0-9]{2}:[0-9]{2}$")
RE_WDAY_WDAY_TIMESPAN = re.compile("^[A-Z][a-z]-[A-Z][a-z] [0-9]{2}:[0-9]{2}-[0-9]{2}:[0-9]{2}$")
RE_TIMESPAN = re.compile("^[0-9]{2}:[0-9]{2}-[0-9]{2}:[0-9]{2}$")
RE_TIMESPANS = re.compile("([0-9]{2}):([0-9]{2})-([0-9]{2}):([0-9]{2})")


def parse_simple_field(field):
    """Returns None or a tree if the field is simple enough.
    
    Simple field example: "Mo-Fr 08:00-20:00; Sa 08:00-12:00"
    """
    # It's about 12 times faster than with Lark.
    # Effective for a bit more than 35% of OSM fields.
    splited_field = [
        part.strip() for part in field.strip(' \n\t;').split(';')
    ]
    parsed_parts = []
    for part in splited_field:
        if RE_WDAY_OFF.match(part):
            wday = part[:2]
            if wday not in WEEKDAYS:
                return None
            parsed_parts.append(
                Tree("rule_sequence", [Tree("selector_sequence", [Tree("range_selectors", [Tree("weekday_or_holiday_sequence_selector", [Tree("weekday_sequence", [Tree("weekday_range", [Token("WDAY", wday)])])])])]), Tree("rule_modifier_closed", [Token("CLOSED", ' off')])])
            )
        elif RE_WDAY_TIMESPAN.match(part):
            wday = part[:2]
            if wday not in WEEKDAYS:
                return None
            timespans = []
            for timespan in RE_TIMESPANS.findall(part):
                from_h, from_m, to_h, to_m = timespan
                timespans.append(
                    Tree("timespan", [Tree("time", [Tree("hour_minutes", [Token("TWO_DIGITS", from_h), Token("TWO_DIGITS", from_m)])]), Tree("time", [Tree("hour_minutes", [Token("TWO_DIGITS", to_h), Token("TWO_DIGITS", to_m)])])])
                )
            parsed_parts.append(
                Tree("rule_sequence", [Tree("selector_sequence", [Tree("range_selectors", [Tree("weekday_or_holiday_sequence_selector", [Tree("weekday_sequence", [Tree("weekday_range", [Token("WDAY", wday)])])])]), Tree("time_selector", timespans)])])
            )
        elif RE_WDAY_WDAY_TIMESPAN.match(part):
            wday_from, wday_to = part[:5].split('-')
            if wday_from not in WEEKDAYS or wday_to not in WEEKDAYS:
                return None
            timespans = []
            for timespan in RE_TIMESPANS.findall(part):
                from_h, from_m, to_h, to_m = timespan
                timespans.append(
                    Tree("timespan", [Tree("time", [Tree("hour_minutes", [Token("TWO_DIGITS", from_h), Token("TWO_DIGITS", from_m)])]), Tree("time", [Tree("hour_minutes", [Token("TWO_DIGITS", to_h), Token("TWO_DIGITS", to_m)])])])
                )
            parsed_parts.append(
                Tree("rule_sequence", [Tree("selector_sequence", [Tree("range_selectors", [Tree("weekday_or_holiday_sequence_selector", [Tree("weekday_sequence", [Tree("weekday_range", [Token("WDAY", wday_from), Token("WDAY", wday_to)])])])]), Tree("time_selector", timespans)])])
            )
        elif RE_TIMESPAN.match(part):
            from_h, from_m = part[:5].split(':')
            to_h, to_m = part[6:].split(':')
            parsed_parts.append(
                Tree("selector_sequence", [Tree("time_selector", [Tree("timespan", [Tree("time", [Tree("hour_minutes", [Token("TWO_DIGITS", from_h), Token("TWO_DIGITS", from_m)])]), Tree("time", [Tree("hour_minutes", [Token("TWO_DIGITS", to_h), Token("TWO_DIGITS", to_m)])])])])])
            )
        else:
            return None
    return Tree("time_domain", parsed_parts)
