import datetime
import calendar

from humanized_opening_hours.exceptions import SolarHoursError


WEEKDAYS = (
    "Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"
)
MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
)


def easter_date(year):
    """Returns the datetime.date of easter for a given year (int)."""
    # Code from https://github.com/ActiveState/code/tree/master/recipes/Python/576517_Calculate_Easter_Western_given  # noqa
    a = year % 19
    b = year // 100
    c = year % 100
    d = (19 * a + b - b // 4 - ((b - (b + 8) // 25 + 1) // 3) + 15) % 30
    e = (32 + 2 * (b % 4) + 2 * (c // 4) - d - (c % 4)) % 7
    f = d + e - 7 * ((a + 11 * d + 22 * e) // 451) + 114
    month = f // 31
    day = f % 31 + 1
    return datetime.date(year, month, day)


class Rule:
    def __init__(self, sequence):
        self.status = "open"
        if len(sequence) > 1:
            self.status = sequence[1]  # Can be "open" or "closed".
        sequence = sequence[0]
        if len(sequence) == 1:
            self.range_selectors = sequence[0]
            self.time_selectors = []
        else:
            self.range_selectors = sequence[0]
            self.time_selectors = sequence[1]
        
        if isinstance(self.range_selectors, AlwaysOpenSelector):
            self.time_selectors = [TimeSpan(
                Time(("normal", datetime.time.min)),
                Time(("normal", datetime.time.max))
            )]
            self.always_open = True
        else:
            self.always_open = False
        
        try:
            self.priority = sum(
                [sel.priority for sel in self.range_selectors.selectors]
            )
        except AttributeError:  # TimeSpan in range selectors.
            self.priority = 1
    
    def get_status_at(self, dt: datetime.datetime, solar_hours):
        for timespan in self.time_selectors:
            if timespan.is_open(dt, solar_hours):
                if self.status == "open":
                    return True
                else:  # self.status == "closed"
                    return False
        return False
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<Rule {} - {} (priority: {})>".format(
            self.range_selectors,
            self.time_selectors,
            self.priority
        )


# Selectors


class BaseSelector:
    priority = 1
    
    def __init__(self, selectors):
        self.selectors = selectors
    
    def is_included(self, dt, SH_dates, PH_dates):
        pass
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<{name} {selectors}>".format(
            name=self.__class__.__name__,
            selectors=str(self.selectors)
        )


class RangeSelector(BaseSelector):
    def is_included(self, dt, SH_dates, PH_dates):
        for selector in self.selectors:
            if selector.is_included(dt, SH_dates, PH_dates):
                continue
            else:
                return False
        return True


class AlwaysOpenSelector(BaseSelector):
    def __init__(self):
        self.selectors = [
            TimeSpan(
                Time(("normal", datetime.time.min)),
                Time(("normal", datetime.time.max))
            )
        ]
    
    def is_included(self, dt, SH_dates, PH_dates):
        return True


class MonthDaySelector(BaseSelector):
    priority = 2
    
    def is_included(self, dt, SH_dates, PH_dates):
        for selector in self.selectors:
            if selector.is_included(dt, SH_dates, PH_dates):
                return True
        return False


class WeekdayHolidaySelector(BaseSelector):
    def __init__(self, selectors, SH, PH):
        self.selectors = selectors
        self.SH = SH  # Boolean
        self.PH = PH  # Boolean
    
    def is_included(self, dt: datetime.datetime, SH_dates, PH_dates):
        if dt in SH_dates:
            return self.SH or WEEKDAYS[dt.weekday()] in self.selectors
        elif dt in PH_dates:
            return self.PH or WEEKDAYS[dt.weekday()] in self.selectors
        else:
            wd = WEEKDAYS[dt.weekday()]
            return wd in self.selectors
    
    def __str__(self):
        return "<WeekdayHolidaySelector {} (SH: {}; PH: {})>".format(
            str(self.selectors),
            self.SH,
            self.PH
        )


'''
class HolidaySelector(BaseSelector):
    def is_included(self, dt: datetime.datetime, SH_dates, PH_dates):
        if dt in SH_dates:
            return self.SH or WEEKDAYS[dt.weekday()] in self.selectors
        elif dt in PH_dates:
            return self.PH or WEEKDAYS[dt.weekday()] in self.selectors
        return False
'''


class WeekdayInHolidaySelector(BaseSelector):
    priority = 3
    
    def __init__(self, weekdays, holidays):
        self.weekdays = weekdays
        self.holidays = holidays
    
    def is_included(self, dt: datetime.datetime, SH_dates, PH_dates):
        if (
            (
                (dt in SH_dates and 'SH' in self.holidays) or
                (dt in PH_dates and 'PH' in self.holidays)
            ) and WEEKDAYS[dt.weekday()] in self.weekdays
        ):
            return True
        return False
    
    def __str__(self):
        return "<WeekdayInHolidaySelector {} in {}>".format(
            str(self.weekdays), str(self.holidays)
        )


class WeekSelector(BaseSelector):
    priority = 3
    
    def __init__(self, week_numbers):
        self.week_numbers = week_numbers
    
    def is_included(self, dt: datetime.datetime, SH_dates, PH_dates):
        week_number = dt.isocalendar()[1]
        return week_number in self.week_numbers
    
    def __str__(self):
        return '<WeekSelector ' + str(self.week_numbers) + '>'


class YearSelector(BaseSelector):
    priority = 4
    
    def is_included(self, dt: datetime.datetime, SH_dates, PH_dates):
        return dt.year in self.selectors


# Ranges


class MonthDayRange:
    def __init__(self, monthday_dates):
        # TODO: Prevent case like "Jan 1-5-Feb 1-5"
        # (monthday_date - monthday_date).
        self.date_from = monthday_dates[0]
        self.date_to = monthday_dates[1] if len(monthday_dates) == 2 else None
    
    def is_included(self, dt: datetime.date, SH_dates, PH_dates):
        if not self.date_to:
            return dt in self.date_from.get_dates(dt)
        else:
            dt_from = sorted(self.date_from.get_dates(dt))[0]
            dt_to = sorted(self.date_to.get_dates(dt))[-1]
            return dt_from <= dt <= dt_to
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<MonthDayRange {date_from} - {date_to}>".format(
            date_from=self.date_from,
            date_to=self.date_to
        )


class MonthDayDate:
    def __init__(
        self, kind, year=None, month=None, monthday=None, monthday_to=None
    ):
        self.kind = kind  # "monthday", "monthday-day", "month" or "easter"
        self.year = year
        self.month = month  # int between 1 and 12
        self.monthday = monthday
        self.monthday_to = monthday_to
    
    def safe_monthrange(self, year, month):
        start, end = calendar.monthrange(year, month)
        if start == 0:
            start = 1
        return (start, end)
    
    def get_dates(self, dt: datetime.date):
        # Returns a set of days covered by the object.
        if self.kind == "easter":
            return set([easter_date(dt.year)])
        elif self.kind == "month":
            first_monthday = datetime.date(
                self.year or dt.year,
                self.month,
                1
            )
            last_monthday = datetime.date(
                self.year or dt.year,
                self.month,
                self.safe_monthrange(self.year or dt.year, dt.month)[1]
            )
            dates = []
            for i in range((last_monthday - first_monthday).days + 1):
                dates.append(first_monthday+datetime.timedelta(i))
            return set(dates)
        elif self.kind == "monthday-day":
            first_day = datetime.date(
                self.year or dt.year,
                self.month,
                self.monthday
            )
            last_day = datetime.date(
                self.year or dt.year,
                self.month,
                self.monthday_to
            )
            dates = []
            for i in range((last_day - first_day).days + 1):
                dates.append(first_day+datetime.timedelta(i))
            return set(dates)
        else:  # self.kind == "monthday"
            return set([datetime.date(
                self.monthday,
                self.month,
                self.year or dt.year
            )])
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        if self.kind == "easter":
            return "<MonthDayDate 'easter'>"
        elif self.kind == "month":
            return "<MonthDayDate {year}{month}>".format(
                year=(self.year if self.year else '') + ' ',
                month=MONTHS[self.month-1]
            )
        elif self.kind == "monthday-day":
            return "<MonthDayDate {year}{month} {day_from} - {day_to}>".format(
                year=(self.year if self.year else '') + ' ',
                month=MONTHS[self.month-1],
                day_from=self.monthday,
                day_to=self.monthday_to
            )
        else:  # self.kind == "monthday"
            return "<MonthDayDate {year}{month} {day}>".format(
                year=(self.year if self.year else '') + ' ',
                month=MONTHS[self.month-1],
                day=self.monthday
            )


class TimeSpan:
    def __init__(self, beginning, end):
        self.beginning = beginning
        self.end = end
    
    def spans_over_midnight(self):
        """Returns whether the TimeSpan spans over midnight."""
        if (
            self.beginning.t[0] == self.end.t[0] == "normal" and
            self.beginning.t[1] > self.end.t[1]
        ):
                return True
        elif any((
            self.beginning.t[0] == "sunset" and self.end.t[0] == "sunrise",
            self.beginning.t[0] == "sunset" and self.end.t[0] == "dawn",
            self.beginning.t[0] == "sunrise" and self.end.t[0] == "dawn",
            self.beginning.t[0] == "dusk"
        )):
            return True
        else:
            return False
    
    def get_times(self, date, solar_hours):
        """Returns the beginning and the end of the TimeSpan.
        
        Note
        ----
            If the TimeSpan spans over midnight, the second datetime of the
            returned tuple will be one day later than the first.
        
        Parameters
        ----------
        date: datetime.date
            The day to use for returned datetimes.
        solar_hours: dict{str: datetime.time}
            A dict containing hours of sunrise, sunset, dawn and dusk.
        
        Returns
        -------
        tuple[datetime.datetime]
            A tuple containing the beginning and the end of the TimeSpan.
        """
        beginning_time = self.beginning.get_time(solar_hours, date)
        if self.spans_over_midnight():
            delta = datetime.timedelta(1)
        else:
            delta = datetime.timedelta()
        end_time = self.end.get_time(solar_hours, date+delta)
        return (beginning_time, end_time)
    
    def is_open(self, dt, solar_hours):
        """Returns whether it's open at the given datetime.
        
        Parameters
        ----------
        datetime.datetime
            The date for which to check the opening.
        solar_hours: dict{str: datetime.time}
            A dict containing hours of sunrise, sunset, dawn and dusk.
        
        Returns
        -------
        bool
            True if it's open, False else.
        """
        beginning_time, end_time = self.get_times(dt.date(), solar_hours)
        return beginning_time <= dt <= end_time
    
    def __repr__(self):
        return "<TimeSpan from {} to {}>".format(
            str(self.beginning), str(self.end)
        )
    
    def __str__(self):
        return "{} - {}".format(str(self.beginning), str(self.end))


class Time:
    def __init__(self, t):
        self.t = t
        # ("normal", datetime.time) / ("name", "offset_sign", "delta_seconds")
        # TODO: Set only two attributes: "kind" (str) and "offset" (signed int).
    
    def get_time(self, solar_hours, date):
        """Returns the corresponding datetime.datetime.
        
        Parameters
        ----------
        solar_hours: dict{str: datetime.time}
            A dict containing hours of sunrise, sunset, dawn and dusk.
        datetime.datetime
            The day to use for the returned datetime.
        
        Returns
        -------
        datetime.datetime
            The datetime of the Time.
        """
        if self.t[0] == "normal":
            return datetime.datetime.combine(date, self.t[1])
        solar_hour = solar_hours[self.t[0]]
        if solar_hour is None:
            raise SolarHoursError()
        if self.t[1] == 1:
            return datetime.datetime.combine(
                date,
                (
                    datetime.datetime.combine(
                        datetime.date(1, 1, 1), solar_hour
                    ) + self.t[2]
                ).time()
            )
        else:
            return datetime.datetime.combine(
                date,
                (
                    datetime.datetime.combine(
                        datetime.date(1, 1, 1), solar_hour
                    ) -
                    self.t[2]
                ).time()
            )
    
    def __repr__(self):
        return "<Time ({!r})>".format(str(self))
    
    def __str__(self):
        # TODO : Use 'rendering.render_time()"?
        return str(self.t)
