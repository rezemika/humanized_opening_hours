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
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<WeekdayRange {}[{}]>".format(self.weekdays, self.nth)


class Holiday:
    def __init__(self, type, td=datetime.timedelta()):
        self.type = type
        self.td = td
    
    def check(self, dt, PH, SH):
        if self.type == "PH":
            return dt in [date + self.td for date in PH]
        else:
            return dt in [date + self.td for date in SH]


class Time:
    def __init__(self, type, delta):
        self.type = type
        self.delta = delta
    
    def get_datetime(self, dt, location=None):  # TODO: Location.
        if self.type != "normal":
            raise NotImplementedError()
        base_dt = dt.date()
        return datetime.datetime.combine(base_dt, datetime.time()) + self.delta
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<{} {!r}>".format(self.type, self.delta)


class Timespan:
    def __init__(self, time1, time2):
        self.time1 = time1
        self.time2 = time2
    
    def check(self, dt):
        return self.time1.get_datetime(dt) <= dt < self.time2.get_datetime(dt)
    
    def period(self, dt):
        return (self.time1.get_datetime(dt), self.time2.get_datetime(dt))
    
    def __contains__(self, dt):
        return self.check(dt)
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<{} - {}>".format(self.time1, self.time2)


class TimeSelector:
    def __init__(self, timespans):
        self.timespans = timespans
    
    def check(self, dt):
        for timespan in self.timespans:
            if timespan.check(dt) is True:
                return True
        return False
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<TimeSelector {!r}>".format(self.timespans)


#####


class WeekdaySelector:
    def __init__(self, weekday_sequence, holiday_sequence, wd_in_holiday=False):
        # weekday_sequence and holiday_sequence undiscerned for 'weekday_selector'.
        self.weekday_sequence = weekday_sequence
        self.holiday_sequence = holiday_sequence
        self.wd_in_holiday = wd_in_holiday
    
    def check(self, dt, PH, SH):
        if not self.wd_in_holiday:
            return (
                any((wd_range.check(dt, PH, SH) for wd_range in self.weekday_sequence))
                or
                any((holiday.check(dt, PH, SH) for holiday in self.holiday_sequence))
            )
        return (
            any((holiday.check(dt, PH, SH) for holiday in self.holiday_sequence))
            and
            any((wd_range.check(dt, PH, SH) for wd_range in self.weekday_sequence))
        )
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<WeekdaySelector {} {} {}>".format(
            self.weekday_sequence,
            'in' if self.wd_in_holiday else 'and',
            self.holiday_sequence
        )


class AlwaysOpenRule:
    def __init__(self, opening_rule=True):
        self.opening_rule = opening_rule


class Rule:
    def __init__(self, wide_range_selectors, small_range_selectors, time_selector=None, opening_rule=True):
        self.wide_range_selectors = wide_range_selectors
        self.small_range_selectors = small_range_selectors
        self.time_selector = time_selector
        self.opening_rule = opening_rule
    
    def match_date(self, dt, PH, SH):
        for selector in self.wide_range_selectors:
            if selector.check(dt, PH, SH) is False:
                return False
        for selector in self.small_range_selectors:
            if selector.check(dt, PH, SH) is False:
                return False
        return True
    
    def match_dt(self, dt, PH, SH):
        for selector in self.wide_range_selectors:
            if selector.check(dt, PH, SH) is False:
                return False
        for selector in self.small_range_selectors:
            if selector.check(dt, PH, SH) is False:
                return False
        return self.time_selector.check(dt)
    
    def is_open(self, dt, PH, SH):
        match = self.match_dt(dt, PH, SH)
        return match and self.opening_rule
    
    def period(self, dt, PH, SH):
        for selector in self.wide_range_selectors:
            if selector.check(dt, PH, SH) is False:
                return (None, None)
        for selector in self.small_range_selectors:
            if selector.check(dt, PH, SH) is False:
                return (None, None)
        
        if self.is_open(dt, PH, SH):
            for timespan in self.time_selector.timespans:
                if dt in timespan:
                    return timespan.period(dt)
        for timespan in self.time_selector.timespans:
            beginning, end = timespan.period(dt)
            last = end
            if dt < beginning:
                return (None, beginning)
            if dt > end:
                last = end
        return (None, last)
