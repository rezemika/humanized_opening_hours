import datetime
import calendar

from humanized_opening_hours.exceptions import SolarHoursNotSetError


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
        return (
            '<Rule ' + str(self.range_selectors) +
            ' - ' +
            str(self.time_selectors) + '>'
        )


class RangeSelector:
    def __init__(self, selectors):
        self.selectors = selectors
    
    def is_included(self, dt, SH_dates, PH_dates):
        for selector in self.selectors:
            if selector.is_included(dt, SH_dates, PH_dates):
                continue
            else:
                return False
        return True
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return '<RangeSelector ' + str(self.selectors) + '>'


class AlwaysOpenSelector:
    def __init__(self):
        self.selectors = [
            TimeSpan(
                Time(("normal", datetime.time.min)),
                Time(("normal", datetime.time.max))
            )
        ]
    
    def is_included(self, dt, SH_dates, PH_dates):
        return True
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return '<AlwaysOpenSelector ' + str(self.selectors) + '>'


class MonthDaySelector:
    def __init__(self, selectors):
        self.selectors = selectors
    
    def is_included(self, dt, SH_dates, PH_dates):
        for selector in self.selectors:
            if selector.is_included(dt, SH_dates, PH_dates):
                return True
        return False
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return '<MonthDaySelector ' + str(self.selectors) + '>'


class WeekdaySelector:
    def __init__(self, selectors):
        self.selectors = selectors
    
    def is_included(self, dt: datetime.datetime, SH_dates, PH_dates):
        if dt in SH_dates:
            return "SH" in self.selectors
        elif dt in PH_dates:
            return "PH" in self.selectors
        else:
            wd = WEEKDAYS[dt.weekday()]
            return wd in self.selectors
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return '<WeekdaySelector ' + str(self.selectors) + '>'


class WeekdayHolidaySelector:
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
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<WeekdayHolidaySelector {} (SH: {}; PH: {})>".format(
            str(self.selectors),
            self.SH,
            self.PH
        )


'''
class HolidaySelector:
    def __init__(self, selectors):
        self.selectors = selectors
    
    def is_included(self, dt: datetime.datetime, SH_dates, PH_dates):
        if dt in SH_dates:
            return self.SH or WEEKDAYS[dt.weekday()] in self.selectors
        elif dt in PH_dates:
            return self.PH or WEEKDAYS[dt.weekday()] in self.selectors
        return False
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<HolidaySelector {}>".format(str(self.selectors))
'''


class WeekdayInHolidaySelector:
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
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<WeekdayInHolidaySelector {} in {}>".format(
            str(self.weekdays), str(self.holidays)
        )


class WeekSelector:
    def __init__(self, week_numbers):
        self.week_numbers = week_numbers
    
    def is_included(self, dt: datetime.datetime, SH_dates, PH_dates):
        week_number = dt.isocalendar()[1]
        return week_number in self.week_numbers
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return '<WeekSelector ' + str(self.week_numbers) + '>'


class MonthDayRange:
    def __init__(self, args):
        self.kind = args[0]
        self.args = args[1:]
    
    def safe_monthrange(self, year, month):
        start, end = calendar.monthrange(year, month)
        if start == 0:
            start = 1
        return (start, end)
    
    def is_included(self, dt: datetime.date, SH_dates, PH_dates):
        if self.kind == "SpecialDate-SpecialDate":
            return self.args[0].get_date(dt) <= dt <= self.args[1].get_date(dt)
        if self.kind == "SpecialDate-":
            return self.args[0].get_date(dt) == dt
        if self.kind == "year_month-month":
            month_from_range = self.safe_monthrange(self.args[0], self.args[1])
            month_to_range = self.safe_monthrange(self.args[0], self.args[2])
            dt_from = datetime.date(
                self.args[0], self.args[1], month_from_range[0]
            )
            dt_to = datetime.date(
                self.args[0], self.args[2], month_to_range[1]
            )
        if self.kind == "month-month":
            month_from_range = self.safe_monthrange(dt.year, self.args[0])
            month_to_range = self.safe_monthrange(dt.year, self.args[1])
            dt_from = datetime.date(dt.year, self.args[0], month_from_range[0])
            dt_to = datetime.date(dt.year, self.args[1], month_from_range[1])
        if self.kind == "month-":
            month_range = self.safe_monthrange(dt.year, self.args[0])
            dt_from = datetime.date(dt.year, self.args[0], month_range[0])
            dt_to = datetime.date(dt.year, self.args[0], month_range[1])
        if self.kind == "year_month-":
            month_range = self.safe_monthrange(self.args[0], self.args[1])
            dt_from = datetime.date(self.args[0], self.args[1], month_range[0])
            dt_to = datetime.date(self.args[0], self.args[1], month_range[1])
        if self.kind == "SpecialDate-INT":
            dt_from = self.args[0].get_date(dt)
            dt_to = (
                dt_from + datetime.timedelta(days=self.args[1])
            )
        return dt_from <= dt <= dt_to
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return '<MonthDayRange ' + self.kind + '>'


class SpecialDate:  # TODO : Clean.
    def __init__(self, args):
        if len(args) == 1:  # [easter]
            self.kind = "easter"
            self.year = None
            self.date = None
            self.offset = None
        if len(args) == 2:  # [year, easter] OR [month, monthday]
            if args[1] == "yeareaster":
                self.kind = "easter"
                self.year = args[0]
                self.date = None
                self.offset = None
            elif isinstance(args[1], tuple):  # Easter with date offset.
                # args[1] == ("offset_sign", "days)
                self.kind = "easter-offset"
                self.year = None
                self.date = easter_date
                self.offset = args[1]
            else:
                self.kind = "monthday"
                self.year = None
                self.date = (MONTHS.index(args[0])+1, int(args[1].value))
                self.offset = None
        if len(args) == 3:  # [year, month, monthday]
            self.kind = "exactdate"
            self.year = args[0]
            self.date = (MONTHS.index(args[1])+1, int(args[2].value))
            self.offset = None
    
    def get_date(self, dt: datetime.date):
        if self.kind == "easter":
            return easter_date(dt.year)
        elif self.kind == "easter-offset":
            base_dt = easter_date(dt.year)
            offset = datetime.timedelta(
                seconds=datetime.timedelta(self.offset[1]).total_seconds() *
                self.offset[0]
            )
            return base_dt + offset
        elif self.kind == "yeareaster":
            return easter_date(self.year)
        elif self.kind == "monthday":
            return datetime.date(dt.year, self.date[0], self.date[1])
        else:
            return datetime.date(self.year, self.date[0], self.date[1])
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return '<SpecialDate {!r}>'.format(self.kind)


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
        
        /!\ If the TimeSpan spans over midnight, the second datetime of the
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
        end_time = self.end.get_time(solar_hours, date)
        if not self.spans_over_midnight():
            return (beginning_time, end_time)
        else:
            return (beginning_time, end_time+datetime.timedelta(1))
    
    def is_open(self, dt, solar_hours):
        """Returns the beginning and the end of the TimeSpan.
        
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
        # TODO : Use named tupple.
    
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
        """
        if self.t[0] == "normal":
            return datetime.datetime.combine(date, self.t[1])
        solar_hour = solar_hours[self.t[0]]
        if solar_hour is None:
            raise SolarHoursNotSetError()
        if self.t[1] == '+':
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
        # TODO : Use 'get_time()"?
        return str(self.t)
