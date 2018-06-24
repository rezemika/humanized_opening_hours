import datetime
import os

import lark

from humanized_opening_hours.temporal_objects import (
    WEEKDAYS, MONTHS,
    Rule, RangeSelector, AlwaysOpenSelector,
    MonthDaySelector, WeekdayHolidaySelector,
    WeekdayInHolidaySelector, WeekSelector,
    YearSelector, MonthDayRange, MonthDayDate,
    TimeSpan, Time
)
from humanized_opening_hours.frequent_fields import (
    FREQUENT_FIELDS, parse_simple_field
)


BASE_DIR = os.path.dirname(os.path.realpath(__file__))


def cycle_slice(l, start_index, end_index):
    """Allows to do a cyclical slicing on any iterable.
    It's like a regular slicing, but it allows the start index
    to be greater than the end index.
    
    Parameters
    ----------
    iterable
        The object on which to iterate.
    int
        The start index.
    int
        The end index (can be lower than the start index).
    
    Returns
    -------
    list
        The objects between the start and the end index (inclusive).
    """
    if start_index <= end_index:
        return l[start_index:end_index+1]
    return l[start_index:] + l[:end_index+1]


class MainTransformer(lark.Transformer):
    def time_domain(self, args):
        return args
    
    def rule_sequence(self, args):
        return Rule(args)
    
    def always_open(self, args):
        return [AlwaysOpenSelector()]
    
    def selector_sequence(self, args):
        if len(args) == 1:
            return [AlwaysOpenSelector(), args[0]]
        return args
    
    def range_selectors(self, args):
        return RangeSelector(args)
    
    # Dates
    def monthday_selector(self, args):
        return MonthDaySelector(args)
    
    def monthday_range(self, args):
        # Prevent case like "Jan 1-5-Feb 1-5" (monthday_date - monthday_date).
        return MonthDayRange(args)
    
    def monthday_date_monthday(self, args):
        year = args.pop(0) if len(args) == 3 else None
        month = MONTHS.index(args[0].value) + 1
        monthday = int(args[1].value)
        return MonthDayDate(
            "monthday", year=year, month=month, monthday=monthday
        )
    
    def monthday_date_day_to_day(self, args):
        year = args.pop(0) if len(args) == 4 else None
        month = MONTHS.index(args[0].value) + 1
        monthday_from = int(args[1].value)
        monthday_to = int(args[2].value)
        return MonthDayDate(
            "monthday-day", year=year, month=month,
            monthday=monthday_from, monthday_to=monthday_to
        )
    
    def monthday_date_month(self, args):
        year = args[0] if len(args) == 3 else None
        month = MONTHS.index(args[0]) + 1
        return MonthDayDate("month", year=year, month=month)
    
    def monthday_date_easter(self, args):
        year = args[0] if len(args) == 3 else None
        return MonthDayDate("easter", year=year)
    
    def day_offset(self, args):  # TODO : Make usable.
        # TODO : Review.
        # [Token(DAY_OFFSET, ' +2 days')]
        offset_sign, days = args[0].value.strip("days ")
        offset_sign = 1 if offset_sign == '+' else -1
        days = int(days)
        return (offset_sign, days)
    
    # Holidays
    def holiday_sequence(self, args):
        return set(args)
    
    def holiday(self, args):
        return set([args[0].value])
    
    # weekday_selector
    def weekday_or_holiday_sequence_selector(self, args):
        args = set([item for sublist in args for item in sublist])
        SH, PH = 'SH' in args, 'PH' in args
        if SH:
            args.remove('SH')
        if PH:
            args.remove('PH')
        return WeekdayHolidaySelector(args, SH, PH)
    
    def holiday_and_weekday_sequence_selector(self, args):
        args = set([item for sublist in args for item in sublist])
        SH, PH = 'SH' in args, 'PH' in args
        if SH:
            args.remove('SH')
        if PH:
            args.remove('PH')
        return WeekdayHolidaySelector(args, SH, PH)
    
    def holiday_in_weekday_sequence_selector(self, args):
        if len(args) == 2:  # TODO : Clean.
            holiday, weekday = args
        else:
            holiday = set(("PH", "SH"))
            weekday = args[-1]
        return WeekdayInHolidaySelector(weekday, holiday)
    
    # Weekdays
    def weekday_sequence(self, args):
        return set([item for sublist in args for item in sublist])
    
    def weekday_range(self, args):
        if len(args) == 1:
            return [args[0].value]
        first_day = WEEKDAYS.index(args[0])
        last_day = WEEKDAYS.index(args[1])
        return set(cycle_slice(WEEKDAYS, first_day, last_day))
    
    # Year
    def year(self, args):
        return int(args[0].value)
    
    def year_range(self, args):
        if len(args) == 1:
            return set([args[0]])
        elif len(args) == 2:
            return set(range(args[0], args[1]+1))
        else:
            return set(range(args[0], args[1]+1, int(args[2].value)))
    
    def year_selector(self, args):
        print(args)
        return YearSelector(set([item for sublist in args for item in sublist]))
    
    # Week
    def week_selector(self, args):
        args = args[1:]
        return WeekSelector(args[0])
    
    def week(self, args):
        if len(args) == 1:
            return set([args[0]])
        elif len(args) == 2:
            return set(range(args[0], args[1]+1))
        else:
            return set(range(args[0], args[1]+1, int(args[2].value)))
    
    def weeknum(self, args):
        return int(args[0].value)
    
    # Time
    def time_selector(self, args):
        return args
    
    def timespan(self, args):
        return TimeSpan(*args)
    
    def time(self, args):
        return Time(args[0])
    
    def hour_minutes(self, args):
        h, m = int(args[0].value), int(args[1].value)
        if (h, m) == (24, 0):
            dt = datetime.time.max
        else:
            dt = datetime.time(h % 24, m)  # Converts "26:00" to "02:00".
        return ("normal", dt)
    
    def variable_time(self, args):
        # ("event", "offset_sign", "hour_minutes")
        kind = args[0].value
        if len(args) == 1:
            return (kind, 1, datetime.timedelta(0))
        offset_sign = 1 if args[1].value == '+' else -1
        delta = (  # Because "datetime.time" cannot be substracted.
            datetime.datetime.combine(datetime.date(1, 1, 1), args[2][1]) -
            datetime.datetime.combine(datetime.date(1, 1, 1), datetime.time.min)
        )
        return (kind, offset_sign, delta)
    
    def rule_modifier_open(self, args):
        return "open"
    
    def rule_modifier_closed(self, args):
        return "closed"


def get_parser():
    """
        Returns a Lark parser able to parse a valid field.
    """
    base_dir = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(base_dir, "field.ebnf"), 'r') as f:
        grammar = f.read()
    return lark.Lark(grammar, start="time_domain", parser="earley")


def get_tree_and_rules(field, optimize=True):
    # If the field is in FREQUENT_FIELDS, returns directly its tree.
    tree = None
    if optimize:
        tree = FREQUENT_FIELDS.get(field)
        if not tree:
            tree = parse_simple_field(field)
    if not tree:
        tree = PARSER.parse(field)
    rules = MainTransformer().transform(tree)
    return (tree, rules)


PARSER = get_parser()
