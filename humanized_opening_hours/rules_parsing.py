import datetime

import lark

from exceptions import UnsupportedPattern
from temporal_ranges import (YearRange, MonthdayRange, WeekRange, WeekdayRange,
    WeekdaySelector, Holiday, Time, Timespan, TimeSelector, AlwaysOpenRule, Rule)


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
                if arg.value == ',':
                    raise UnsupportedPattern("Comma rule separator is not supported yet.")
                elif arg.value == '||':
                    raise UnsupportedPattern("Fallback rule separator is not supported yet.")
                continue
            else:
                parts.append(arg)
        return parts
    
    def rule_sequence(self, args):
        if args[0] == "24/7":
            opening_rule = True
            if len(args) == 2:
                opening_rule = args[1]
            return AlwaysOpenRule(opening_rule=opening_rule)
        
        wide_range_selectors, small_range_selectors = args[0]
        if len(small_range_selectors) == 3:
            time_selector = small_range_selectors[2]
            small_range_selectors = small_range_selectors[:2]
        else:
            time_selector = None
        
        if len(args) == 2:
            rule_modifier = args[1]
        else:
            rule_modifier = True
        
        return Rule(
            wide_range_selectors[1],
            small_range_selectors[1],
            time_selector=time_selector,
            opening_rule=rule_modifier
        )
    
    def selector_sequence_always_open(self, args):
        return "24/7"
    
    def selector_sequence_with_colon(self, args):
        return args
    
    def selector_sequence_without_colon(self, args):
        return args
    
    def selector_sequence_comment_time_selector(self, args):
        raise UnsupportedPattern("<comment: time_selector> pattern is not supported.")
    
    def wide_range_selectors(self, args):
        return ("wide", args)
    
    def small_range_selectors(self, args):
        if len(args) == 1 and isinstance(args[0], TimeSelector):
            return ("small", [], args[0])
        if isinstance(args[-1], TimeSelector):
            return ("small", args[:-1], args[-1])
        return ("small", args)
    
    # weekday_selector
    def weekday_selector(self, args):
        return WeekdaySelector(args[0], [])
    
    def weekday_selector_wd_and_holiday(self, args):
        return WeekdaySelector(args[1], args[0])
    
    def weekday_selector_wd_and_holiday_wrong(self, args):
        return WeekdaySelector(args[0], args[1])
    
    def weekday_selector_wd_in_holiday(self, args):
        return WeekdaySelector(args[1], args[0], wd_in_holiday=True)
    
    def weekday_sequence(self, args):
        return flatten(args)
    
    def holiday_sequence(self, args):
        return flatten(args)
    
    def weekday_range(self, args):
        if len(args) == 1:
            return WeekdayRange([get_wday(args[0])])
        return WeekdayRange(
            cycle_slice(list(range(7)), get_wday(args[0]), get_wday(args[1]))
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
                return YearRange([int(args[0][:-1])], plus=True)
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
    def time_selector(self, args):
        return TimeSelector(args)
    
    def timespan_normal(self, args):
        raise UnsupportedPattern("Points in time are not supported yet.")
    
    def timespan_plus(self, args):
        raise UnsupportedPattern("The <timespan +> pattern is not supported.")
    
    def timespan_tt(self, args):
        if args[0].type == args[1].type == "normal":
            if args[1].delta < args[0].delta:
                t2 = args[1]
                t2.delta += datetime.timedelta(days=1)
                return Timespan(args[0], t2)
        return Timespan(args[0], args[1])
    
    def timespan_tt_plus(self, args):
        raise UnsupportedPattern("The <timespan +> pattern is not supported.")
    
    def timespan_tt_minute(self, args):
        raise UnsupportedPattern("Points in time are not supported yet.")
    
    def timespan_tt_hm(self, args):
        raise UnsupportedPattern("Points in time are not supported yet.")
    
    def time(self, args):
        return Time(args[0][0], args[0][1])
    
    def hour_minutes(self, args):
        return (
            "normal",
            datetime.timedelta(hours=int(args[0]), minutes=int(args[1]))
        )
    
    def variable_time_event(self, args):
        return (args[0].value, datetime.timedelta())
    
    def variable_time_event_plus_time(self, args):
        return (args[0].value, args[1][1])
    
    def variable_time_event_minus_time(self, args):
        return (args[0].value, args[1][1] * -1)
    
    # rule_modifier
    def rule_modifier_open(self, args):
        if len(args) == 2:
            raise UnsupportedPattern("Comments are not supported.")
        return True
    
    def rule_modifier_closed(self, args):
        if len(args) == 2:
            raise UnsupportedPattern("Comments are not supported.")
        return False
    
    def rule_modifier_unknown(self, args):
        raise UnsupportedPattern("Unknown schedules are not supported.")
    
    def rule_modifier_comment(self, args):
        raise UnsupportedPattern("Comment only rules are not supported.")
