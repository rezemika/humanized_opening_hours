import datetime
import calendar
import gettext
from itertools import groupby
from operator import itemgetter

import babel
import babel.dates

from humanized_opening_hours.rendering import (
    set_locale, join_list, render_timespan, render_time, translate_open_closed
)
from humanized_opening_hours.exceptions import SolarHoursError


gettext.install("hoh", "locales")


WEEKDAYS = (
    "Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"
)
MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
)


def consecutive_groups(iterable, ordering=lambda x: x):
    """Yields groups of consecutive items using 'itertools.groupby'.
    
    The *ordering* function determines whether two items are adjacent by
    returning their position.
    
    By default, the ordering function is the identity function. This is
    suitable for finding runs of numbers:
    
    >>> iterable = [1, 10, 11, 12, 20, 30, 31, 32, 33, 40]
    >>> for group in consecutive_groups(iterable):
    ...     print(list(group))
    [1]
    [10, 11, 12]
    [20]
    [30, 31, 32, 33]
    [40]
    """
    # Code from https://more-itertools.readthedocs.io/en/latest/api.html#more_itertools.consecutive_groups  # noqa
    for k, g in groupby(
        enumerate(iterable), key=lambda x: x[0] - ordering(x[1])
    ):
        yield map(itemgetter(1), g)


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


class Day:
    def __init__(self, ohparser, date, computed_timespans):
        """A representation of a day and its opening periods.
        
        Parameters
        ----------
        OHParser instance
            The instance where the field come from.
        datetime.datetime
            The date of the day.
        list[ComputedTimeSpan]
            The opening periods of the day.
        
        Attributes
        ----------
        ohparser
            The instance where the field come from.
        date
            The date of the day.
        weekday_name
            The name of the weekday, in the locale given to OHParser.
        timespans
            The opening periods of the day.
        locale
            The Babel locale given to OHParser.
        """
        self.ohparser = ohparser
        self.date = date
        self.locale = self.ohparser.locale
        self.weekday_name = babel.dates.get_day_names(
            locale=self.locale
        )[date.weekday()]
        self.timespans = computed_timespans
    
    def opens_today(self):
        """Returns whether there is at least one opening period on this day."""
        return bool(self.timespans)
    
    def opening_periods(self):
        """
        Returns the opening periods of the day as tuples of the shape
        '(beginning, end)' (represented by datetime.datetime objects).
        """
        return [ts.to_tuple() for ts in self.timespans]
    
    def total_duration(self):
        """
        Returns the total duration of the opening periods of the day,
        as a datetime.timedelta object.
        """
        return sum(
            [p[1] - p[0] for p in self.opening_periods()],
            datetime.timedelta()
        )
    
    def render_periods(self, join=True):
        """
        Returns a list of translated strings
        describing the opening periods of the day.
        """
        if self.opens_today():
            rendered_periods = [
                render_timespan(ts.timespan, self.locale)
                for ts in self.timespans
            ]
        else:
            closed_word = translate_open_closed(self.locale)[1]
            rendered_periods = [closed_word]
        if join:
            return join_list(rendered_periods, self.locale)
        else:
            return rendered_periods
    
    def tomorrow(self):
        """
        Returns a Day object representing the next day.
        
        You can also use additions or subtractions with datetime.timedelta
        objects, like this.
        
        >>> seven_days_later = day + datetime.timedelta(7)
        >>> type(seven_days_later) == Day
        """
        return self + datetime.timedelta(1)
    
    def yersterday(self):
        """
        Returns a Day object representing the eve.
        
        You can also use additions or subtractions with datetime.timedelta
        objects, like this.
        
        >>> seven_days_before = day - datetime.timedelta(7)
        >>> type(seven_days_before) == Day
        """
        return self - datetime.timedelta(1)
    
    def __add__(self, other):
        if isinstance(other, datetime.timedelta):
            return self.ohparser.get_day(self.date + other)
        return NotImplemented
    
    def __sub__(self, other):
        if isinstance(other, datetime.timedelta):
            return self.ohparser.get_day(self.date - other)
        return NotImplemented
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<Day {!r} ({} periods)>".format(self.date, len(self.timespans))


class Rule:
    def __init__(self, range_selectors, time_selectors, status="open"):
        self.range_selectors = range_selectors
        self.time_selectors = time_selectors
        self.status = status
        
        for timespan in self.time_selectors:
            timespan.status = status == "open"
        
        self.priority = sum(
            [sel.priority for sel in self.range_selectors.selectors]
        )
    
    def get_status_at(self, dt: datetime.datetime, solar_hours):
        # TODO: Remove?
        for timespan in self.time_selectors:
            if timespan.compute(dt, solar_hours).is_open(dt):
                if self.status == "open":
                    return True
                else:  # self.status == "closed"
                    return False
        return False
    
    def description(self, localized_names, babel_locale):
        set_locale(babel_locale)
        if (
            isinstance(self.range_selectors, AlwaysOpenSelector) and
            self.time_selectors == [TIMESPAN_ALL_THE_DAY]
        ):
            return _("Open 24 hours a day and 7 days a week.")
        
        range_selectors_description = ', '.join(
            [
                sel.description(localized_names, babel_locale)
                for sel in self.range_selectors.selectors
            ]
        )
        if not range_selectors_description:
            range_selectors_description = _("every days")
        if not self.time_selectors:
            time_selectors_description = _("closed")
        else:
            time_selectors_description = join_list(
                [
                    timespan.description(localized_names, babel_locale)
                    for timespan in self.time_selectors
                ],
                babel_locale
            )
        full_description = _("{}: {}").format(
            range_selectors_description,
            time_selectors_description
        ) + '.'
        return full_description[0].upper() + full_description[1:]
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<Rule {} - {} (priority: {})>".format(
            self.range_selectors,
            self.time_selectors,
            self.priority
        )


# Selectors


class BaseSelector:  # pragma: no cover
    priority = 1
    rendering_data = ()
    
    def __init__(self, selectors):
        self.selectors = selectors
    
    def is_included(self, dt, SH_dates, PH_dates):
        pass
    
    def description(self, localized_names, babel_locale):
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
        self.selectors = []
    
    def is_included(self, dt, SH_dates, PH_dates):
        return True


class MonthDaySelector(BaseSelector):
    priority = 5
    
    def is_included(self, dt, SH_dates, PH_dates):
        for selector in self.selectors:
            if selector.is_included(dt, SH_dates, PH_dates):
                return True
        return False
    
    def description(self, localized_names, babel_locale):
        set_locale(babel_locale)
        rendered_selectors = [
            sel.description(localized_names, babel_locale)
            for sel in self.selectors
        ]
        return join_list(rendered_selectors, babel_locale)


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
    
    def description(self, localized_names, babel_locale):
        # TODO: SH and PH
        set_locale(babel_locale)
        day_groups = []
        for group in consecutive_groups(
            sorted(self.selectors, key=WEEKDAYS.index), ordering=WEEKDAYS.index
        ):
            group = list(group)
            if len(group) == 1:
                day_groups.append((group[0],))
            else:
                day_groups.append((group[0], group[-1]))
        output = []
        for group in day_groups:
            if len(group) == 1:
                output.append(_("on {weekday}").format(
                    weekday=localized_names["days"][WEEKDAYS.index(group[0])]
                ))
            else:
                output.append(_("from {weekday1} to {weekday2}").format(
                    weekday1=localized_names["days"][WEEKDAYS.index(group[0])],
                    weekday2=localized_names["days"][WEEKDAYS.index(group[1])]
                ))
        holidays_description = {
            (True, True): _("on public and school holidays"),
            (True, False): _("on public holidays"),
            (False, True): _("on school holidays")
        }.get((self.PH, self.SH))
        if holidays_description:
            return babel.lists.format_list(
                [holidays_description] + output,
                locale=babel_locale
            )
        else:
            return join_list(output, babel_locale)
    
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
    
    def _weekdays_description(self, localized_names, babel_locale):
        set_locale(babel_locale)
        day_groups = []
        for group in consecutive_groups(
            sorted(self.weekdays, key=WEEKDAYS.index), ordering=WEEKDAYS.index
        ):
            group = list(group)
            if len(group) == 1:
                day_groups.append((group[0],))
            else:
                day_groups.append((group[0], group[-1]))
        output = []
        for group in day_groups:
            if len(group) == 1:
                output.append(_("on {weekday}").format(
                    weekday=localized_names["days"][WEEKDAYS.index(group[0])]
                ))
            else:
                output.append(_("from {weekday1} to {weekday2}").format(
                    weekday1=localized_names["days"][WEEKDAYS.index(group[0])],
                    weekday2=localized_names["days"][WEEKDAYS.index(group[1])]
                ))
        return output
    
    def description(self, localized_names, babel_locale):
        set_locale(babel_locale)
        weekdays_description = self._weekdays_description(
            localized_names, babel_locale
        )
        holidays_description = {
            (True, True): _("on public and school holidays"),
            (True, False): _("on public holidays"),
            (False, True): _("on school holidays")
        }.get(('PH' in self.holidays, 'SH' in self.holidays))
        return ', '.join([holidays_description] + weekdays_description)
    
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
    
    def description(self, localized_names, babel_locale):
        set_locale(babel_locale)
        output = []
        for week_range in self.rendering_data:
            if len(week_range) == 1:
                output.append(_("in week {week}").format(week=week_range[0]))
            elif len(week_range) == 2:
                output.append(_("from week {week1} to week {week2}").format(
                    week1=week_range[0],
                    week2=week_range[1]
                ))
            else:
                output.append(
                    _(
                        "from week {week1} to week {week2}, every {n} weeks"
                    ).format(
                        week1=week_range[0],
                        week2=week_range[1],
                        n=week_range[2]
                    )
                )
        return join_list(output, babel_locale)
    
    def __str__(self):
        return '<WeekSelector ' + str(self.week_numbers) + '>'


class YearSelector(BaseSelector):
    priority = 4
    
    def is_included(self, dt: datetime.datetime, SH_dates, PH_dates):
        return dt.year in self.selectors
    
    def description(self, localized_names, babel_locale):
        set_locale(babel_locale)
        output = []
        for year_range in self.rendering_data:
            if len(year_range) == 1:
                output.append(_("in {year}").format(year=year_range[0]))
            elif len(year_range) == 2:
                output.append(_("from {year1} to {year2}").format(
                    year1=year_range[0],
                    year2=year_range[1]
                ))
            else:
                output.append(
                    _(
                        "from {year1} to {year2}, every {n} years"
                    ).format(
                        year1=year_range[0],
                        year2=year_range[1],
                        n=year_range[2]
                    )
                )
        return join_list(output, babel_locale)


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
            if dt_to < dt_from:  # TODO: Fix this in parsing.
                # When 'dt_to' is "before" 'dt_from'
                # (ex: 'Oct-Mar 07:30-19:30; Apr-Sep 07:00-21:00'),
                # it returns False. It shoud fix this bug.
                dt_to += datetime.timedelta(weeks=52)
            return dt_from <= dt <= dt_to
    
    def description(self, localized_names, babel_locale):
        set_locale(babel_locale)
        if not self.date_to:
            return self.date_from.description(localized_names, babel_locale)
        else:
            return _("from {monthday1} to {monthday2}").format(
                monthday1=self.date_from.description(
                    localized_names, babel_locale
                ),
                monthday2=self.date_to.description(
                    localized_names, babel_locale
                )
            )
    
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
                self.safe_monthrange(self.year or dt.year, self.month)[1]
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
                self.year or dt.year,
                self.month,
                self.monthday
            )])
    
    def description(self, localized_names, babel_locale):
        set_locale(babel_locale)
        if self.kind == "easter":
            return _("on easter")
        elif self.kind == "month":
            return localized_names["months"][self.month-1]
        elif self.kind == "monthday-day":
            if self.year:
                return _("{month} {day1} to {day2}, {year}").format(
                    month=localized_names["months"][self.month-1],
                    day1=self.monthday,
                    day2=self.monthday_to,
                    year=self.year
                )
            else:
                return _("from {month} {day1} to {day2}").format(
                    month=localized_names["months"][self.month-1],
                    day1=self.monthday,
                    day2=self.monthday_to
                )
        else:  # self.kind == "monthday"
            if self.year:
                date = datetime.date(self.year, self.month, self.monthday)
                return babel.dates.format_date(date, format="long")
            else:
                date = datetime.date(2000, self.month, self.monthday)
                return date.strftime(_("%B %-d"))
    
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


class ComputedTimeSpan:
    def __init__(self, beginning, end, status, timespan):
        # 'beginning' and 'end' are 'datetime.datetime' objects.
        self.beginning = beginning
        self.end = end
        self.status = status
        self.timespan = timespan
    
    def spans_over_midnight(self):
        """Returns whether the TimeSpan spans over midnight."""
        return self.beginning.day != self.end.day
    
    def __contains__(self, dt):
        if (
            not isinstance(dt, datetime.date) or
            not isinstance(dt, datetime.datetime)
        ):
            return NotImplemented
        return self.beginning <= dt < self.end
    
    def __lt__(self, other):
        if isinstance(other, ComputedTimeSpan):
            return self.beginning < other.beginning
        elif isinstance(other, datetime.datetime):
            return self.beginning < other
        return NotImplemented
    
    def to_tuple(self):
        return (self.beginning, self.end)
    
    def is_open(self, dt):
        return (dt in self) and self.status
    
    def __repr__(self):
        return "<ComputedTimeSpan from {} to {}>".format(
            self.beginning.strftime("%H:%M"), self.end.strftime("%H:%M")
        )
    
    def __str__(self):
        return "{} - {}".format(
            self.beginning.strftime("%H:%M"),
            self.end.strftime("%H:%M")
        )


class TimeSpan:
    def __init__(self, beginning, end):
        self.beginning = beginning
        self.end = end
        self.status = True  # False if closed period.
    
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
    
    def compute(self, date, solar_hours):
        """Returns a 'ComputedTimeSpan' object."""
        return ComputedTimeSpan(
            *self.get_times(date, solar_hours),
            self.status,
            self
        )
    
    def get_times(self, date, solar_hours):
        """Returns the beginning and the end of the TimeSpan.
        
        Note
        ----
            If the TimeSpan spans over midnight, the second datetime of the
            returned tuple will be one day later than the first.
        
        Parameters
        ----------
        date: datetime.date
            The day to use for returned datetimes. If the timespan spans
            over midnight, it will be the date of the first day.
        solar_hours: dict{str: datetime.time}
            A dict containing hours of sunrise, sunset, dawn and dusk.
        
        Returns
        -------
        tuple[datetime.datetime]
            A tuple containing the beginning and the end of the TimeSpan.
        """
        beginning_time = self.beginning.get_time(solar_hours, date)
        end_time = self.end.get_time(solar_hours, date)
        if self.spans_over_midnight():
            end_time += datetime.timedelta(1)
        return (beginning_time, end_time)
    
    def description(self, localized_names, babel_locale):
        set_locale(babel_locale)
        return render_timespan(self, babel_locale)
    
    def __repr__(self):
        return "<TimeSpan from {} to {}>".format(
            str(self.beginning), str(self.end)
        )
    
    def __str__(self):
        return "{} - {}".format(str(self.beginning), str(self.end))


class Time:
    def __init__(self, t):
        # ("normal", datetime.time) / ("name", "offset_sign", "delta_seconds")
        self.t = t
        self.is_min_time = (
            self.t[0] == "normal" and self.t[1] == datetime.time.min
        )
        self.is_max_time = (
            self.t[0] == "normal" and self.t[1] == datetime.time.max
        )
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
    
    def description(self, localized_names, babel_locale):
        set_locale(babel_locale)
        return render_time(self, babel_locale)
    
    def __repr__(self):
        return "<Time ({!r})>".format(str(self))
    
    def __str__(self):
        # TODO : Use 'rendering.render_time()"?
        return str(self.t)


TIMESPAN_ALL_THE_DAY = TimeSpan(
    Time(("normal", datetime.time.min)),
    Time(("normal", datetime.time.max))
)
