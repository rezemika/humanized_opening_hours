import datetime
import calendar


def iter_dates(start, end):  # TODO: Check.
    delta = (end - start).days
    for d in range(delta+1):
        yield start + d


def get_monthdays_nth(year, month):  # TODO
    first_monthday = datetime.date(year, month, 1)
    last_monthday = datetime.date(
        year, month, calendar.monthrange(year, month)[1]
    )
    nths = {}
    for d in range(7):
        l = list(range(-5, 6))
        l.remove(0)
        nths[d] = {nth: None for nth in l}


class YearRange:
    def __init__(self, years, plus=False):
        self.years = years
        self.plus = plus
    
    def check(self, dt, PH, SH):
        if not plus:
            return dt.year in self.years
        return dt.year >= self.years[0]


class MonthdayRange:
    pass


class WeekRange:
    pass


class WeekdayRange:
    def __init__(self, weekdays, nth=None):
        self.weekdays = weekdays
        self.nth = nth
    
    def check(self, dt, PH, SH):
        if not self.nth:
            return dt.weekday() in self.weekdays
        # TODO


class Holiday:
    def __init__(self, type, td=datetime.timedelta()):
        self.type = type
        self.td = td
    
    def check(self, dt, PH, SH):
        if self.type == "PH":
            return dt in [date + self.td for date in PH]
        else:
            return dt in [date + self.td for date in SH]


class Rule:
    pass
