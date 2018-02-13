from lark import Lark, Transformer
import datetime
import os

from temporal_objects import (
    WEEKDAYS,
    MONTHS,
    MomentKind,
    Period,
    Moment
)


class YearTransformer(Transformer):
    # Moments
    def digital_moment(self, arg):
        if arg[0] == "24:00":
            time = datetime.time.max
        else:
            time = datetime.datetime.strptime(arg[0], "%H:%M").time()
        return Moment(MomentKind.NORMAL, time=time)
    
    def solar_moment(self, arg):
        return Moment(MomentKind[arg[0].upper()], delta=datetime.timedelta())
    
    def solar_complex_moment(self, arg):
        arg = arg[0].strip('()')
        if arg.find('+') != -1:
            offset_sign = 1
            arg = arg.split('+')
        else:
            offset_sign = -1
            arg = arg.split('-')
        kind = arg[0]
        offset_hours, offset_minutes = arg[1].split(':')
        offset_seconds = (
            int(offset_hours) * 60 * 60 +
            int(offset_minutes) * 60
        ) * offset_sign
        offset = datetime.timedelta(seconds=offset_seconds)
        return Moment(kind, delta=offset)
    
    # Period
    def period(self, args):
        return Period(args[0], args[1])
    
    def day_periods(self, args):
        return args
    
    def period_closed(self, args):
        return []
    
    # Concerned days
    def unconsecutive_days(self, args):
        return set([tk.value for tk in args])
    
    def consecutive_day_range(self, args):  # TODO : Fix this dirty hack.
        if len(args) == 1:
            return args[0]
        s = args[0]
        for day in args[1:]:
            s.add(day.value)
        return s
    
    def raw_consecutive_day_range(self, args):
        first_day = WEEKDAYS.index(args[0])
        last_day = WEEKDAYS.index(args[1])
        day_indexes = list(range(first_day, last_day+1))
        return set([WEEKDAYS[i] for i in day_indexes])
    
    def everyday_periods(self, args):
        return (set('*'), args[0])
    
    # Concerned months
    def unconsecutive_months(self, args):
        return set([tk.value for tk in args])
    
    def consecutive_month_range(self, args):
        return args[0]
    
    def raw_consecutive_month_range(self, args):
        first_month = MONTHS.index(args[0])
        last_month = MONTHS.index(args[1])
        month_indexes = list(range(first_month, last_month+1))
        return set([MONTHS[i] for i in month_indexes])
    
    # Exceptional days
    def exceptional_day(self, args):
        # "month_index-day" - "Dec 25" -> "12-25"
        return str(MONTHS.index(args[0])+1) + '-' + args[1]
    
    def exceptional_dates(self, args):
        return tuple((set(args[:-1]), args[-1]))
    
    # Holidays
    def holiday(self, args):
        return set([tk.value for tk in args])
    
    # Always open
    def always_open(self, args):
        return (set('*'), [self.period([
            self.digital_moment(["00:00"]),
            self.digital_moment(["24:00"])
        ])])
    
    # Field part
    def field_part(self, args):
        return tuple(args)


# TODO : Build SH and PR weeks.
class ParsedField:
    def __init__(self, tree):
        self.tree = tree
        self.regular_week = [list() for _ in range(7)]
        for part in self.tree.children:
            for day in part[0].intersection(WEEKDAYS):
                self.regular_week[WEEKDAYS.index(day)] = part[1]
            if '*' in part[0]:
                self.regular_week = [part[1] for _ in range(7)]
        
        self.months = []
        for month in MONTHS:
            self.months.append({
                # Not supported by the parser yet.
                "regular_week": [False, [list() for _ in range(7)]],
                "every_days": [False, []]
            })
        for part in self.tree.children:
            for month in part[0].intersection(MONTHS):
                self.months[MONTHS.index(month)]["every_days"] = [True, part[1]]
        
        # TODO : Improve and change "exceptional_day" method.
        self.exceptional_dates = []
        for part in self.tree.children:
            for date in [date for date in part[0] if '-' in date]:
                month, day = date.split('-')
                self.exceptional_dates.append(((int(month), int(day)), part[1]))
        
        self.holidays_status = {"PH": None, "SH": None}
        for part in self.tree.children:
            if "PH" in part[0]:
                self.holidays_status["PH"] = bool(part[1])
            if "SH" in part[0]:
                self.holidays_status["SH"] = bool(part[1])
    
    def get_periods_of_day(self, dt):
        requested_month, requested_weekday = dt.month, dt.weekday()
        requested_month -= 1
        requested_monthday = dt.day
        for date in self.exceptional_dates:
            if date[0] == (requested_month+1, requested_monthday):
                return date[1]
        if self.months[requested_month]["regular_week"][0]:
            return self.months[requested_month]["regular_week"][1][requested_weekday]  # noqa
        if self.months[requested_month]["every_days"][0]:
            return self.months[requested_month]["every_days"][1]
        return self.regular_week[requested_weekday]


def get_parser():
    """
        Returns a Lark parser able to parse a valid field.
    """
    base_dir = os.path.realpath(os.path.join(
        os.getcwd(), os.path.dirname(__file__)
    ))
    with open(os.path.join(base_dir, "field.ebnf"), 'r') as f:
        grammar = f.read()
    return Lark(grammar, start="field", ambiguity="explicit")


def parse_field(field, parser):
    tree = YearTransformer().transform(parser.parse(field))
    parsed_field = ParsedField(tree)
    return parsed_field
