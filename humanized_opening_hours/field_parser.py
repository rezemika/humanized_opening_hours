import datetime
import os
import gettext

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

LOCALES = {
    "en": gettext.translation(
        "HOH", os.path.join(BASE_DIR, "locales"), languages=["en"]
    ),
    "fr": gettext.translation(
        "HOH", os.path.join(BASE_DIR, "locales"), languages=["fr"]
    )
}

ON_WEEKDAY = True  # TODO : Relevant?


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
        return MonthDayDate("monthday", year=year, month=month, monthday=monthday)
    
    def monthday_date_day_to_day(self, args):
        year = args.pop(0) if len(args) == 4 else None
        month = MONTHS.index(args[0].value) + 1
        monthday_from = int(args[1].value)
        monthday_to = int(args[2].value)
        return MonthDayDate("monthday-day", year=year, month=month, monthday=monthday_from, monthday_to=monthday_to)
    
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


class DescriptionTransformer(lark.Transformer):  # TODO : Specify "every days".
    def _install_locale(self):
        LOCALES.get(self._locale.language).install()
    
    # Meta
    def _get_wday(self, wday_index: int) -> str:
        return self._human_names["days"][wday_index]
    
    def _get_month(self, month_index: int) -> str:
        return self._human_names["months"][month_index]
    
    def _join_list(self, l: list) -> str:
        if not l:
            return ''
        values = [str(value) for value in l]
        if len(values) == 1:
            return values[0]
        return ', '.join(values[:-1]) + _(" and ") + values[-1]
    
    # Main
    def time_domain(self, args):
        return args
    
    def rule_sequence(self, args):
        if len(args) == 1 and not isinstance(args[0], tuple):
            return args[0][0].upper() + args[0][1:] + '.'
        else:
            if isinstance(args[0], tuple):
                if args[0][0] == 'NO_TS':
                    range_selectors = args[0][1]
                    time_selector = args[1]
                else:
                    range_selectors = _("Every days")
                    time_selector = args[0][1]
            else:
                range_selectors = args[0][0].upper()+args[0][1:]
                time_selector = args[0][1:]
            return _("{range_selectors}: {time_selector}.").format(
                range_selectors=range_selectors,
                time_selector=time_selector
            )
    
    def always_open(self, args):
        return _("open 24 hours a day and 7 days a week")
    
    def range_selectors(self, args):
        descriptions = []
        for i, selector in enumerate(args):
            if type(selector) is list:  # TODO : Clean.
                selector = selector[0]
            if isinstance(selector, tuple):
                if len(selector) == 3:
                    descriptions.append(selector[0].format(
                        wd1=selector[1], wd2=selector[2]
                    ))
                elif i == 0 and ON_WEEKDAY:
                    descriptions.append(selector[0].format(wd=selector[1]))
                else:
                    descriptions.append(selector[1])
            else:
                descriptions.append(selector)
        output = ', '.join(descriptions)
        output = output[0].upper() + output[1:]
        return ('RS', output)
    
    def selector_sequence(self, args):
        if len(args) == 1:
            if isinstance(args[0], tuple):
                return ('NO_TS', args[0][1])
            else:
                return ('TS_ONLY', args[0])
        return args[0][1] + _(': ') + args[1]
    
    # Monthday range
    def monthday_selector(self, args):
        return self._join_list(args)
    
    def monthday_range(self, args):
        if len(args) == 1:  # "Dec 25"
            return args[0]
        else:  # "Jan 1-Feb 1"
            return _("from {monthday1} to {monthday2}").format(
                monthday1=args[0],
                monthday2=args[1]
            )
    # Dates
    def monthday_date_monthday(self, args):
        year = args.pop(0) if len(args) == 3 else None
        month = MONTHS.index(args[0].value)+1
        monthday = int(args[1].value)
        if year:
            dt = datetime.date(year, month, monthday)
            return dt.strftime(_("%B %-d %Y"))
        else:
            dt = datetime.date(2000, month, monthday)
            return dt.strftime(_("%B %-d"))
    
    def monthday_date_day_to_day(self, args):
        year = args.pop(0) if len(args) == 4 else None
        month = MONTHS.index(args[0].value)+1
        monthday_from = int(args[1].value)
        monthday_to = int(args[2].value)
        dt_from = datetime.date(2000, month, monthday_from)
        dt_to = datetime.date(2000, month, monthday_to)
        if year:
            return _("in {year}, from {monthday1} to {monthday2}").format(
                year=year,
                monthday1=dt_from.strftime(_("%B %-d")),
                monthday2=dt_to.strftime(_("%B %-d"))
            )
        else:
            return _("from {monthday1} to {monthday2}").format(
                monthday1=dt_from.strftime(_("%B %-d")),
                monthday2=dt_to.strftime(_("%B %-d"))
            )
    
    def monthday_date_month(self, args):
        year = args.pop(0) if len(args) == 3 else None
        month = self._get_month(MONTHS.index(args[0].value))
        if year:
            return _("in {year}, in {month}").format(
                year=year, month=month
            )
        else:
            return month
    
    def monthday_date_easter(self, args):
        year = args.pop(0) if len(args) == 3 else None
        if year:
            return _("in {year}, on easter").format(year=year)
        else:
            return _("on easter")
    
    # Week
    def week_selector(self, args):
        return self._join_list(args[1:])
    
    def week(self, args):
        if len(args) == 1:
            return _("week {n}").format(n=args[0])
        elif len(args) == 2:
            return _("from week {week1} to week {week2}").format(
                week1=args[0], week2=args[1]
            )
        elif len(args) == 3:
            return _(
                "from week {week1} to week {week2}, every {n} weeks"
            ).format(
                week1=args[0], week2=args[1], n=args[2].value
            )
    
    def weeknum(self, args):
        return args[0].value
    
    # Year
    def year(self, args):
        return args[0].value
    
    def year_range(self, args):
        if len(args) == 1:
            return args[0]
        elif len(args) == 2:
            return _("from {year1} to {year2}").format(
                year1=args[0], year2=args[1]
            )
        elif len(args) == 3:
            return _("from {year1} to {year2}, every {n} years").format(
                year1=args[0], year2=args[1], n=args[2].value
            )
    
    def year_selector(self, args):
        return self._join_list(args)
    
    # Weekdays
    def weekday_range(self, args):
        if len(args) == 1:
            return (  # ("On weekday", "weekday")
                _("on {wd}"),
                self._get_wday(WEEKDAYS.index(args[0]))
            )
        first_day = self._get_wday(WEEKDAYS.index(args[0]))
        last_day = self._get_wday(WEEKDAYS.index(args[1]))
        return (_("from {wd1} to {wd2}"), first_day, last_day)
    
    def weekday_sequence(self, args):
        # TODO : Fix this hack.
        if len(args) != 1:
            weekdays = [t[1] for t in args]
            return (_("on {wd}"), self._join_list(weekdays))
        return args
    
    def weekday_or_holiday_sequence_selector(self, args):
        if len(args) == 1:
            return args[0]
        else:
            return _("Public and school holidays")
    
    def holiday_and_weekday_sequence_selector(self, args):
        if type(args[0]) == str:
            return args[0] + _(" and ") + args[1]
        else:
            return args[0][0][0].format(wd=args[0][0][1]) + _(" and ") + args[1]
    
    def holiday_in_weekday_sequence_selector(self, args):
        if len(args[1][0]) == 2:
            wd = args[1][0][0].format(wd=args[1][0][1])
        else:
            wd = args[1][0][0].format(wd1=args[1][0][1], wd2=args[1][0][2])
        return _("{holiday}, {wd}").format(holiday=args[0], wd=wd)
    
    def holiday(self, args):
        if args[0].value == "PH":
            return _("public holidays")
        else:
            return _("school holidays")
    
    # Time
    def hour_minutes(self, args):
        h, m = int(args[0].value), int(args[1].value)
        if (h, m) == (24, 0):
            dt = datetime.time.max
        else:
            dt = datetime.time(h, m)
        dt = datetime.datetime.combine(
            datetime.date.today(),
            dt
        )
        return dt.strftime("%H:%M")
    
    def time(self, args):
        return args[0]
    
    def timespan(self, args):
        return _("from {} to {}").format(args[0], args[1])
    
    def time_selector(self, args):
        return self._join_list(args)
    
    def variable_time(self, args):
        # ("event", "offset_sign", "hour_minutes")
        kind = args[0].value
        if len(args) == 1:
            return {
                "sunrise": _("sunrise"),
                "sunset": _("sunset"),
                "dawn": _("dawn"),
                "dusk": _("dusk")
            }.get(kind)
        offset_sign = 1 if args[1].value == '+' else -1
        if offset_sign:
            return {
                "sunrise": _("{time} after sunrise"),
                "sunset": _("{time} after sunset"),
                "dawn": _("{time} after dawn"),
                "dusk": _("{time} after dusk")
            }.get(kind).format(time=args[2])
        else:
            return {
                "sunrise": _("{time} before sunrise"),
                "sunset": _("{time} before sunset"),
                "dawn": _("{time} before dawn"),
                "dusk": _("{time} before dusk")
            }.get(kind).format(time=args[2])
    
    # Rule modifiers
    def rule_modifier_open(self, args):
        return "open"  # TODO: Remove?
    
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
