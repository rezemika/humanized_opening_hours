import datetime

import lark

from temporal_ranges import (YearRange, MonthdayRange, WeekRange, WeekdayRange,
    Holiday)


def flatten(s):
    # From https://stackoverflow.com/a/12472564/10466714
    if not len(s):
        return s
    if isinstance(s[0], list) or isinstance(s[0], tuple):
        return flatten(s[0]) + flatten(s[1:])
    return s[:1] + flatten(s[1:])


def get_wday(wday):
    return ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su").index(wday)


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
    # time_domain
    def time_domain(self, args): ###
        parts = []
        for arg in args:
            if isinstance(arg, lark.lexer.Token):
                parts.append(
                    {';': '; ', ',': ', ', '||': ' || '}.get(arg.value.strip())
                )
            else:
                parts.append(arg.strip())
        return ''.join(parts)
    
    def wide_range_selectors(self, args): ###
        return ' '.join(args)
    
    def small_range_selectors(self, args): ###
        return ' '.join(args)
    
    def rule_sequence(self, args): ###
        return ' '.join(args)
    
    def selector_sequence_always_open(self, args): ###
        return "24/7"
    
    def selector_sequence_with_colon(self, args): ###
        args = [a for a in args if a]
        if len(args) == 1:
            return args[0] + ':'
        return args[0] + ': ' + ' '.join(args[1:])
    
    def selector_sequence_without_colon(self, args): ###
        return ' '.join([a for a in args if a])
    
    def selector_sequence_comment_time_selector(self, args): ###
        return args[0].value + ': ' + args[1]
    
    # weekday_selector
    def weekday_selector(self, args): ###
        return args[0]
    
    def weekday_selector_wd_and_holiday(self, args): ###
        return ','.join(args)
    
    def weekday_selector_wd_and_holiday_wrong(self, args): ###
        return ','.join(args[::-1])
    
    def weekday_selector_wd_in_holiday(self, args): ###
        return ' '.join(args)
    
    def weekday_sequence(self, args): ###
        return flatten(args)
    
    def holiday_sequence(self, args): ###
        return args
    
    def weekday_range(self, args):
        return WeekdayRange(
            cycle_slice(range(7), get_wday(args[0]), get_wday(args[1]))
        )
    
    def weekday_range_nth(self, args):
        #return WeekdayRange([args[0]], nth=args[1])
        raise UnsupportedPattern("Weekdays nth are not supported yet.")
    
    def holiday(self, args):
        if len(args) == 1:
            return Holiday(args[0].value)
        return Holiday(args[0].value, td=args[1])
    
    def wday_nth_sequence(self, args):
        return flatten(args)
    
    def nth_entry(self, args):
        if len(args) == 1:
            return int(args[0])
        return list(range(int(args[0]), int(args[1])+1))
    
    def negative_nth_entry(self, args):
        return -int(args[0])
    
    # week_selector
    def week_selector(self, args): ###
        return "week " + ','.join(args)
    
    def week(self, args): ###
        if len(args) == 1:
            return args[0].zfill(2)
        elif len(args) == 2:
            return args[0].zfill(2) + '-' + args[1].zfill(2)
        else:
            return "{}-{}/{}".format(args[0].zfill(2), args[1].zfill(2), args[2])
    
    # monthday_selector
    def monthday_selector(self, args): ###
        return ','.join(args)
    
    def monthday_range_ym(self, args): ###
        if len(args) == 2:
            return args[0] + ' ' + args[1].value.capitalize()
        return args[0].value.capitalize()
    
    def monthday_range_ymm(self, args): ###
        if len(args) == 2:
            return '-'.join([a.value.capitalize() for a in args])
        return args[0] + ' ' + args[1].value.capitalize() + '-' + args[2].value.capitalize()
    
    def monthday_range_date(self, args): ###
        return args[0]
    
    def monthday_range_date_plus(self, args): ###
        return args[0] + '+'
    
    def monthday_range_dd(self, args): ###
        return args[0] + '-' + args[1]
    
    def monthday_range_date_to(self, args): ###
        return args[0] + '-' + args[1]
    
    def date(self, args): ###
        if args[0].type == "VARIABLE_DATE":
            return ''.join(args)
        if isinstance(args[0], str):
            return args[0] + ' ' + args[1].value.capitalize() + ' '.join(args[2:])
        return args[0].value + ' '.join(args[1:])
    
    def date_offset(self, args):
        raise UnsupportedPattern("Date offsets are not supported yet.")
    
    def day_offset(self, args):
        offset_sign = 1 if args[0] == '+' else -1
        days = int(args[1].value)
        return datetime.timedelta(days=offset_sign * days)
    
    # year_selector
    '''
    def year_selector(self, args):
        return lambda dt: any(arg(dt) for arg in args)
    
    def year_range(self, args):
        if len(args) == 1:
            if '+' in args[0]
                return lambda dt: int(args[0][:-1]) <= dt.year
            return lambda dt: int(args[0]) == dt.year
        elif len(args) == 2:
            return lambda dt: int(args[0]) <= dt.year <= int(args[1])
        else:
            years = set(range(int(args[0]), int(args[1]+1), int(args[2].value)))
            return lambda dt: dt.year in years
    
    def year_range_plus(self, args):
        return args[0] + '+'
    
    def year(self, args):
        return args[0]
    '''
    def year_selector(self, args): ###
        return args
    
    def year_range(self, args):
        if len(args) == 1:
            if '+' in args[0]:
                return YearRange([int(args[0][:-1]]), plus=True)
            return YearRange([int(args[0])])
        elif len(args) == 2:
            return YearRange(range(int(args[0]), int(args[1])+1))
        else:
            return YearRange(
                range(int(args[0]), int(args[1]+1), int(args[2].value))
            )
    
    def year_range_plus(self, args):
        return args[0] + '+'
    
    def year(self, args):
        return args[0]
    
    # time_selector
    def time_selector(self, args): ###
        return ','.join(args)
    
    def timespan_normal(self, args): ###
        return args[0]
    
    def timespan_plus(self, args):
        raise UnsupportedPattern("The <timespan +> pattern is not supported.")
    
    def timespan_tt(self, args): ###
        return args[0] + '-' + args[1]
    
    def timespan_tt_plus(self, args):
        raise UnsupportedPattern("The <timespan +> pattern is not supported.")
    
    def timespan_tt_minute(self, args):
        raise UnsupportedPattern("Points in time are not supported yet.")
    
    def timespan_tt_hm(self, args):
        raise UnsupportedPattern("Points in time are not supported yet.")
    
    def time(self, args): ###
        return args[0]
    
    def hour_minutes(self, args): ###
        return args[0].value.zfill(2) + ':' + args[1].value.zfill(2)
    
    def variable_time_event(self, args): ###
        return args[0].value.lower()
    
    def variable_time_event_plus_time(self, args): ###
        event = args[0].value.lower()
        time = args[1]
        return "({}+{})".format(event, time)
    
    def variable_time_event_minus_time(self, args): ###
        event = args[0].value.lower()
        time = args[1]
        return "({}-{})".format(event, time)
    
    # rule_modifier
    def rule_modifier_open(self, args): ###
        if len(args) == 2:
            return "open " + args[1].value
        return "open"
    
    def rule_modifier_closed(self, args): ###
        if len(args) == 2:
            return args[0].value.lower() + ' ' + args[1].value
        return args[0].value.lower()
    
    def rule_modifier_comment(self, args): ###
        return args[0].value
