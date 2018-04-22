import datetime
import os

from lark import Lark, Transformer

from humanized_opening_hours.temporal_objects import (
    WEEKDAYS,
    MONTHS,
    MomentKind,
    Period,
    Moment
)
from humanized_opening_hours.exceptions import (
    SolarHoursNotSetError, SpanOverMidnight
)
from humanized_opening_hours.utils import easter_date


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
        kind = MomentKind[arg[0].upper()]
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
    
    def days_of_month(self, args):
        # TODO : Check specifications.
        output = set()
        months = []
        weekdays = []
        for tk in args:
            if tk.value in MONTHS:
                months.append(tk.value)
            else:
                weekdays.append(tk.value)
        for m in months:
            for wd in weekdays:
                output.add(m + '-' + wd)
        return output
    
    def consecutive_days_of_month(self, args):
        months = [tk.value for tk in args[:-1]]
        days = args[-1]
        output = set()
        for m in months:
            for d in days:
                output.add(m + '-' + d)
        return output
    
    def days_of_consecutive_months(self, args):
        months = args[0]
        days = [tk.value for tk in args[1:]]
        output = set()
        for m in months:
            for d in days:
                output.add(m + '-' + d)
        return output
    
    def consecutive_days_of_consecutive_months(self, args):
        output = set()
        for m in args[0]:
            for d in args[1]:
                output.add(m + '-' + d)
        return output
    
    # Exceptional days
    def exceptional_day(self, args):
        # "month_index-day" - "Dec 25" -> "12-25"
        return str(MONTHS.index(args[0])+1) + '-' + args[1]
    
    def exceptional_dates(self, args):
        return tuple((set(args[:-1]), args[-1]))
    
    def easter(self, args):
        arg = args[0]
        if arg == "easter":
            return "easter"
        _, offset, _ = arg.split()
        offset_sign, days = offset[0], offset[1:]
        return "easter" + offset_sign + days
    
    # Holidays
    def holiday(self, args):
        return set([tk.value for tk in args])
    
    def holidays_unconsecutive_days(self, args):
        return args[0].value + '-' + args[1].value
    
    def holidays_consecutive_days(self, args):
        output = []
        for d in args[1]:
            output.append(args[0].value + '-' + d)
        return output
    
    # Always open
    def always_open(self, args):
        return (set('*'), [self.period([
            self.digital_moment(["00:00"]),
            self.digital_moment(["24:00"])
        ])])
    
    # Field part
    def field_part(self, args):
        for period in args[1]:
            try:
                if period.beginning.time() > period.end.time():
                    raise SpanOverMidnight(
                        "The field contains a period which spans "
                        "over midnight, which not yet supported."
                    )
            except SolarHoursNotSetError:
                pass
        return tuple(args)


# TODO : Build SH and PH weeks.
class ParsedField:
    def __init__(self, tree):
        self.tree = tree
        # TODO : Remove all this stuff.
        self.holidays_status = {"PH": None, "SH": None}
        for part in self.tree.children:
            if "PH" in part[0]:
                self.holidays_status["PH"] = bool(part[1])
            if "SH" in part[0]:
                self.holidays_status["SH"] = bool(part[1])
    
    def get_exceptional_dates(self):
        dates = []
        for targets, periods in self.tree.children:
            for target in targets:
                try:  # TODO : Clean.
                    month, day = target.split('-')
                    month, day = int(month), int(day)
                    dates.append((month, day))
                except ValueError:
                    pass
        return dates
    
    def get_easter_string(self, dt):
        easter = easter_date(dt.year)
        if easter == dt:
            return "easter"
        offset = (easter - dt.date()).days
        sign = '+' if offset > 0 else '-'
        return "easter" + sign + str(abs(offset))
    
    def get_periods_of_day(self, dt, is_PH=False, is_SH=False):
        # Tries to get the opening periods of a day,
        # with the following patterns:
        # Jan-1 - Jan-Mo - Jan - Mo - *
        if is_PH and is_SH:
            raise ValueError("A day cannot be both PH and SH.")
        easter_string = self.get_easter_string(dt)
        patterns = (
            easter_string,
            str(dt.month) + '-' + str(dt.day),
            MONTHS[dt.month-1] + '-' + WEEKDAYS[dt.weekday()],
            MONTHS[dt.month-1],
            WEEKDAYS[dt.weekday()],
            '*'
        )
        if is_PH:
            patterns = (
                "PH-" + WEEKDAYS[dt.weekday()],
                "PH"
            ) + patterns
        elif is_SH:
            patterns = (
                "SH-" + WEEKDAYS[dt.weekday()],
                "SH"
            ) + patterns
        for pattern in patterns:
            for targets, periods in self.tree.children:
                if pattern in targets:
                    return periods
        return []


def get_parser(include_transformer=True):
    """
        Returns a Lark parser able to parse a valid field.
        Set "include_transformer" to False to make the parser return
        a Tree instead of a parsed tree.
    """
    base_dir = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(base_dir, "field.ebnf"), 'r') as f:
        grammar = f.read()
    if include_transformer:
        return Lark(
            grammar, start="field", parser="lalr",
            transformer=YearTransformer()
        )
    return Lark(grammar, start="field", parser="lalr")


PARSER = get_parser()


def parse_field(field):
    tree = PARSER.parse(field)
    parsed_field = ParsedField(tree)
    return parsed_field
