from enum import Enum
import datetime
import pytz
import isoweek
from exceptions import ParseError, ImpreciseField, SolarHoursNotSetError, PeriodsConflictError
from itertools import chain, islice
import copy
from collections import namedtuple
from itertools import zip_longest

WEEKDAYS = (
    "Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"
)
MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
)

class SimilarDay:
    """An object which can represent many days with similar periods.
    
    Attributes
    ----------
    periods : list[Period]
        The list of opening periods.
    dates : list[datetime.date]
        The list of dates of similar days.
    """
    
    def __init__(self):
        self.periods = []
        self.dates = []
        return
    
    def opens_today(self) -> bool:
        """Is it open today?
        
        Returns
        -------
        bool
            True if the day contains any opening period. False else.
        """
        return len(self.periods) > 0
    
    def is_open(self, moment):
        """Is it open?
        
        Parameters
        ----------
        moment : datetime.datetime
            The moment for which to check the opening.
        
        Returns
        -------
        bool
            True if it's open, False else.
            /!\ Returns False if the concerned day contains an unset
            solar moment.
        """
        if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
            moment = pytz.UTC.localize(moment)
        for period in self.periods:
            if moment in period:
                return True
        return False
    
    def last_open_hour(self):
        """Returns the last Moment of the day, or None if there is none."""
        if self.opens_today():
            return self.periods[-1].end
        return None
    
    def __eq__(self, other):
        return hash(self) == hash(other)
    
    def __ne__(self, other):
        return not self == other
    
    def __hash__(self):
        return hash(tuple(self.periods))
    
    def __repr__(self):
        return self.__str__()
    
    def __str__(self):
        return "<SimilarDay ({nd} dates - {np} periods)>".format(
            nd=len(self.dates),
            np=len(self.periods)
        )

class SimilarWeek:
    """An object which can represent many weeks with similar days.
    
    Attributes
    ----------
    indexes : list[int]
        The list of indexes of similar weeks in the year
        (between 0 and 52 inclusive).
    days : list[SimilarDay]
        The similar days of the week..
    """
    
    def __init__(self):
        self.indexes = []
        self.days = []
        return
    
    def opens_this_week(self):
        """Returns whether there is an opening period
        for any day in the week.
        
        Returns True if so, False else.
        """
        return any([day.opens_today() for day in self.days])
    
    @classmethod
    def _from_week(cls, week):
        instance = cls()
        instance.indexes.append(week.index)
        for day in week.days:
            d = SimilarDay()
            d.periods = day.periods
            d.dates.append(day.date)
            instance.days.append(d)
        return instance
    
    def __eq__(self, other):
        return hash(self) == hash(other)
    
    def __ne__(self, other):
        return not self == other
    
    def __hash__(self):
        return hash(tuple(self.days))
    
    def __repr__(self):
        return self.__str__()
    
    def __str__(self):
        return "<SimilarWeek ({n} weeks - {start}-{end})>".format(
            n=len(self.indexes),
            start=min(self.indexes)+1,
            end=max(self.indexes)+1
        )

class Year:
    """A year, containing between 365 and 366 days.
    
    Attributes
    ----------
    all_days : list
        A list of all the days in the year.
    PH_days : list
        All the days indicated as public holidays.
    SH_days : list
        All the days indicated as school holidays.
    PH_week : Week
        A regular public holidays week.
    SH_week : Week
        A regular school holidays week.
    always_open : bool
        True if it's always open (24/7), False else.
    
    /!\ Default, the school and public holidays aren't included
    in "all_days" attribute: you must define them first
    (see the OHParser's "set_PH()" and "set_SH()" methods).
    
    This class is not intended to be created by anything other
    than the OHParser.
    """
    
    def __init__(self):
        self.all_days = []
        self.PH_days = []
        self.SH_days = []
        self.PH_week = Week()
        self.SH_week = Week()
        self.PH_week.closed = False
        self.SH_week.closed = False
        self.always_open = False
        self.exceptional_days = []
        return
    
    def iter_weeks_as_lists(self):
        """Provides a generator to iterate over all the weeks of the year.
        
        /!\ Default, the school and public holidays aren't included,
        you must define them first (see the OHParser's "set_PH()"
        and "set_SH()" methods).
        
        To get a week from its index, simply do "iter_weeks()[index]".
        
        Yields
        ------
        tuple
            The days of the next week in the year,
            which may **not** contain 7 days.
        """
        first_week = []
        first_week_index = 0
        next_day_index = 0
        for i, day in enumerate(self.all_days):
            if day.index == 6:
                first_week.append(self.all_days[:i+1])
                next_day_index = i + 1
                break
        yield first_week
        
        def grouper(iterable, n):
            """Collects data into fixed-length chunks or blocks."""
            # See https://docs.python.org/3/library/itertools.html#itertools-recipes
            # TODO : Check it does not provide copy.
            args = [iter(iterable)] * n
            iterable = zip_longest(*args, fillvalue=None)
            l = []
            for item in iterable:
                g = [i for i in item if i is not None]
                l.append(tuple(g))
            return l
        
        remaining_days = self.all_days[next_day_index:]
        for i, days_group in enumerate(grouper(remaining_days, 7)):
            yield days_group
    
    def iter_weeks(self):
        """Provides a generator to iterate over all the weeks of the year.
        
        /!\ Default, the school and public holidays aren't included,
        you must define them first (see the OHParser's "set_PH()"
        and "set_SH()" methods).
        
        Yields
        ------
        Week : The next week in the year, which may **not** contain 7 days.
        """
        first_week = Week()
        first_week.index = 0
        next_day_index = 0
        for i, day in enumerate(self.all_days):
            if day.index == 6:
                first_week.days = self.all_days[:i+1]
                next_day_index = i + 1
                break
        yield first_week
        
        def grouper(iterable, n):
            """Collects data into fixed-length chunks or blocks."""
            # See https://docs.python.org/3/library/itertools.html#itertools-recipes
            args = [iter(iterable)] * n
            iterable = zip_longest(*args, fillvalue=None)
            l = []
            for item in iterable:
                g = [i for i in item if i is not None]
                l.append(tuple(g))
            return l
        
        remaining_days = self.all_days[next_day_index:]
        for i, days_group in enumerate(grouper(remaining_days, 7)):
            week = Week()
            week.index = i + 1
            week.days = days_group
            yield week
    
    def similar_weeks(self):
        """Returns a list of SimilarWeeks.
        
        Each SimilarWeeks as two attributes :
        - `indexes` : a list of integers, the indexes of the weeks;
        - `days` : a list of SimilarDay objects.
        
        A SimilarDay has the following attributes :
        - `periods` : a list of periods;
        - `dates` : a list of datetime.date objects.
        
        Returns
        -------
        list[SimilarWeeks]
            All the weeks of the year combined in a shorter list.
        """
        all_weeks = list(self.iter_weeks())
        weeks = []
        
        temp_week = SimilarWeek._from_week(all_weeks[0])
        weeks.append(temp_week)
        
        for week in all_weeks[1:]:
            temp_week = SimilarWeek._from_week(week)
            new = True
            for w in weeks:
                if temp_week == w:
                    w.indexes.append(week.index)
                    new = False
            if new:
                weeks.append(temp_week)
        return weeks
    
    def all_months(self):
        """Provides a generator to iterate over all the months of the year.
        
        /!\ Default, the school and public holidays aren't included,
        you must define them first (see the OHParser's "set_PH()"
        and "set_SH()" methods).
        
        Yields
        ------
        Month : The next month in the year.
        """
        current_month_index = 0
        current_month = []
        last_month = None
        for day in self.all_days:
            if day.month_index == current_month_index:
                current_month.days.append(day)
            else:
                last_month = copy.copy(current_month)
                current_month = current_month_index + 1
                yield last_month
        yield current_month
    
    def get_day(self, dt):
        """Returns a Day from a datetime.
        
        Parameters
        ----------
        datetime.datetime / datetime.date
            The date of the day. /!\ This method will ignore
            the year of the given datetime.
        
        Returns
        -------
        Day : The requested day.
        
        Raises
        ------
        KeyError
            When the requested Day is not in the year.
        ValueError
            When no datetime and no index are provided.
        """
        # TODO : Check and improve.
        if type(dt) == datetime.datetime:
            dt = dt.date()
        start_index = self._get_day_index(dt) - 5
        if start_index < 0:
            start_index = 0
        for day in self.all_days[start_index:]:
            if day.date == dt:
                return day
        raise KeyError
    
    def _get_day_index(self, dt):
        """Returns a day index (in the year) from a datetime."""
        return dt.timetuple().tm_yday - 1
    
    def _set_always_open(self):
        self.always_open = True
        for day in self.all_days:
            day._set_always_open()
    
    # From https://stackoverflow.com/questions/390250/elegant-ways-to-support-equivalence-equality-in-python-classes
    def __eq__(self, other):
        """Overrides the default Equals behavior."""
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return NotImplemented

    def __ne__(self, other):
        """Defines a non-equality test."""
        if isinstance(other, self.__class__):
            return not self.__eq__(other)
        return NotImplemented

    def __hash__(self):
        """
        Overrides the default hash behavior (that returns the id or the object).
        """
        return hash(tuple(sorted(self.__dict__.items())))
    
    def __repr__(self):
        return self.__str__()
    
    def __str__(self):
        return "<Year>"

class Week:
    """A week, containing 7 days.
    
    Attributes
    ----------
    index : int
        The index of week in the year (between 0 and 52).
    days : list[Day]
        All the days in this week.
    
    Parameters
    ----------
    index : int, optional
        The index of week in the year (between 0 and 52).
        -1 default meaning a regular or repetitive week.
    
    This class is not intended to be created by anything other
    than the OHParser.
    """
    
    def __init__(self, index=-1):
        self.index = index
        self.days = []
        for i in range(7):
            self.days.append(Day(i))
        return
    
    def opens_this_week(self):
        """Returns whether there is an opening period
        for any day in the week.
        
        Returns True if so, False else.
        """
        return any([day.opens_today() for day in self.days])
    
    def __contains__(self, dt):
        """Returns whether a datetime.datetime is included in the week.
        
        Parameters
        ----------
        datetime.datetime
            The moment for which to check.
        
        Returns
        -------
        bool
            True if the given datetime is between the first and the last
            day of the week. False else.
        """
        if type(dt) != datetime.datetime:
            return NotImplemented
        week_start = datetime.datetime.combine(self.days[0].date, datetime.time.min)
        week_stop = datetime.datetime.combine(self.days[0].date, datetime.time.max)
        return week_start <= dt <= week_stop
    
    # From https://stackoverflow.com/questions/390250/elegant-ways-to-support-equivalence-equality-in-python-classes
    def __eq__(self, other):
        """
        Overrides the default Equals behavior.
        """
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return NotImplemented

    def __ne__(self, other):
        """
        Defines a non-equality test.
        """
        if isinstance(other, self.__class__):
            return not self.__eq__(other)
        return NotImplemented

    def __hash__(self):
        """
        Overrides the default hash behavior (that returns the id or the object).
        """
        return hash(tuple(sorted(self.__dict__.items())))
    
    def __repr__(self):
        return self.__str__()
    
    def __str__(self):
        if self.index == -1:
            return "<Regular Week>"
        else:
            return "<Week #{}>".format(self.index)

class Day:
    """A day, containing periods.
    
    Attributes
    ----------
    index : int
        The index of the day in a week (between 0 and 6).
    periods : list[Period]
        The opening periods of the day.
    date : datetime.date
        The date of the day.
    week_index : int
        The index of the week of the day (between 0 and 52).
    month_index : int
        The index of the month of the day (between 0 and 11).
    always_open : bool
        True if it's open all the day (24/7), False else.
    
    Parameters
    ----------
    index : int
        The index of the day in a week (between 0 and 6).
    
    This class is not intended to be created by anything other
    than the OHParser.
    """
    
    def __init__(self, index):
        self.index = index
        self.periods = []
        self.date = None
        self.week_index = None
        self.month_index = None
        return
    
    def opens_today(self) -> bool:
        """Is it open today?
        
        Returns
        -------
        bool
            True if the day contains any opening period. False else.
        """
        return len(self.periods) > 0
    
    def is_open(self, moment):
        """Is it open?
        
        Parameters
        ----------
        moment : datetime.datetime
            The moment for which to check the opening.
        
        Returns
        -------
        bool
            True if it's open, False else.
            /!\ Returns False if the concerned day contains an unset
            solar moment.
        """
        if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
            moment = pytz.UTC.localize(moment)
        for period in self.periods:
            if moment in period:
                return True
        return False
    
    def is_always_open(self):
        return len(self.periods) == 1 and self.periods[0].beginning.time() == datetime.time.min and self.periods[0].end.time() == datetime.time.max
    
    def last_open_hour(self):
        """Returns the last Moment of the day, or None if there is none."""
        if self.opens_today():
            return self.periods[-1].end
        return None
    
    def _contains_unknown_times(self):
        """Returns whether there are unknown solar hours in the day.
        
        Returns True if so, False else.
        """
        for period in self.periods:
            if not period.beginning.time() or not period.end.time():
                return True
        return False
    
    def _add_period(self, period_to_add, force=False):
        """Adds a period to the day.
        
        Parameters
        ----------
        Period
            The period to add.
        force : bool, optional
            Override the other periods if they are overlapping.
        
        Raises
        ------
        humanized_opening_hours.exceptions.PeriodsConflictError
            When the added period overlaps an already present one
            and "force" is False.
            When "always_open" is True.
        """
        if self.is_always_open() and not force:
            raise PeriodsConflictError("It's already open all the day (24/7).")
        for i, period in enumerate(self.periods):
            if period.beginning.kind.requires_parsing() or period.end.kind.requires_parsing():
                continue
            if period.beginning in period_to_add or period.end in period_to_add:
                if force:
                    del self.periods[i]
                    break
                raise PeriodsConflictError(
                    "The period '{p1}' is in conflict with this one: "
                    "'{p2}' in the day '{day}'.".format(
                        p1=period_to_add, p2=period, day=WEEKDAYS[self.index]
                    )
                )
        self.periods.append(period_to_add)
    
    def _set_always_open(self):
        self.always_open = True
        self.periods = [Period(datetime.time.min, datetime.time.max)]
    
    # From https://stackoverflow.com/questions/390250/elegant-ways-to-support-equivalence-equality-in-python-classes
    def __eq__(self, other):
        """
        Overrides the default Equals behavior.
        """
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return NotImplemented
    
    def __ne__(self, other):
        """
        Defines a non-equality test.
        """
        return not self == other
    
    def __hash__(self):
        """
        Overrides the default hash behavior (that returns the id or the object).
        """
        s = 0
        for a, b in self.__dict__.items():
            try:
                s += hash((a, b))
            except TypeError:
                s += hash(a) + hash(tuple(b))
        return s
    
    def __repr__(self):
        return self.__str__()
    
    def __str__(self):
        return "<Day '{}' ({} periods)>".format(
            WEEKDAYS[self.index],
            len(self.periods)
        )

class Period:
    """An opening period, containing a beginning and an end.
    
    Attributes
    ----------
    Moment
        A Moment representing the beginning of the period.
    Moment
        A Moment representing the end of the period.
    
    Parameters
    ----------
    beginning : Moment
        A Moment representing the beginning of the period.
    end : Moment
        A Moment representing the end of the period.
    
    This class is not intended to be created by anything other
    than the OHParser.
    """
    
    def __init__(self, beginning, end):
        self.beginning = beginning
        self.end = end
        return
    
    def is_variable(self):
        """Returns whether the period is variable.
        
        Returns
        -------
        bool
            True if the period contains a non-normal moment, False else.
        """
        return self.beginning.kind.requires_parsing() or self.end.kind.requires_parsing()
    
    # From https://stackoverflow.com/questions/390250/elegant-ways-to-support-equivalence-equality-in-python-classes
    def __eq__(self, other):
        """
        Overrides the default Equals behavior.
        """
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return NotImplemented
    
    def __ne__(self, other):
        """
        Defines a non-equality test.
        """
        if isinstance(other, self.__class__):
            return not self.__eq__(other)
        return NotImplemented
    
    def __hash__(self):
        """
        Overrides the default hash behavior (that returns the id or the object).
        """
        return hash(tuple(sorted(self.__dict__.items())))
    
    def __contains__(self, moment):
        """Returns whether a moment is included in the period.
        
        Parameters
        ----------
        Moment / datetime.datetime / datetime.time
            The moment for which to check. Must be timezone aware.
        """
        if not self.beginning.time() or not self.end.time():
            return False
        try:
            if type(moment) is Moment:
                return self.beginning.time() <= moment.time() <= self.end.time()
            elif type(moment) is datetime.time:
                moment = moment.replace(tzinfo=pytz.UTC)
                return self.beginning.time() <= moment <= self.end.time()
            elif type(moment) is datetime.datetime:
                moment = moment.timetz().replace(tzinfo=pytz.UTC)
                return self.beginning.time() <= moment <= self.end.time()
            else:
                return NotImplemented
        except TypeError as e:  # Handles "unorderable types" with None values.
            raise SolarHoursNotSetError("This day contains unknown solar hours.")
    
    def __repr__(self):
        return "<Period from {} to {}>".format(str(self.beginning), str(self.end))
    
    def __str__(self):
        return "{} - {}".format(str(self.beginning), str(self.end))

class MomentKind(Enum):
    """The kinds of moments, as defined in the OSM's doc."""
    
    NORMAL = 0
    SUNRISE = 1
    SUNSET = 2
    DAWN = 3
    DUSK = 4
    
    def requires_parsing(self) -> bool:
        """Returns whether a MomentKind requires a solar hours parsing."""
        return bool(self.value)

class Moment:
    """A moment in the time, which defines the beginning or the end
    of a period.
    
    Attributes
    ----------
    kind : MomentKind
        The kind of the moment.
    
    Parameters
    ----------
    MomentKind
        The kind of the moment.
    time : datetime.time, optional
        The time, if kind is "normal".
    delta : datetime.timedelta
        A timedelta from a specific moment, if kind is not "normal".
        For example, is kind is "sunrise", delta must be a timedelta
        between the moment itself and the sunrise.
    
    This class is not intended to be created by anything other
    than the OHParser.
    """
    
    def __init__(self, kind, time=None, delta=None):
        self.kind = kind
        if self.kind == MomentKind.NORMAL and not time:
            raise ValueError("A time must be given when kind is 'normal'.")
        self._time = time
        if self.kind != MomentKind.NORMAL and delta is None:
            raise ValueError("A delta must be given when kind is solar (e.g. 'sunrise', 'sunset', etc).")
        self._delta = delta
        return
    
    def time(self):
        """The time of the moment, if available.
        
        Returns
        -------
        datetime.time / None
            A datetime.time on UTC timezone, or None if solar hours have
            not been set.
        """
        if self._time:
            if not self.kind.requires_parsing():
                return self._time.replace(tzinfo=pytz.UTC)
            else:
                return (
                    datetime.datetime.combine(
                        datetime.date(2000, 1, 1),
                        self._time.replace(tzinfo=pytz.UTC)
                    ) + self._delta
                ).timetz()
        return None
    
    def _has_offset(self):
        """Returns whether the moment has an offset.
        
        Returns
        -------
        bool
            True if `self._delta.seconds` is not 0. False else.
        """
        if not self._delta:
            return False
        return self._delta.seconds != 0
    
    # From https://stackoverflow.com/questions/390250/elegant-ways-to-support-equivalence-equality-in-python-classes
    def __eq__(self, other):
        """
        Overrides the default Equals behavior.
        """
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return NotImplemented
    
    def __ne__(self, other):
        """
        Defines a non-equality test.
        """
        if isinstance(other, self.__class__):
            return not self.__eq__(other)
        return NotImplemented
    
    def __hash__(self):
        """
        Overrides the default hash behavior (that returns the id or the object).
        """
        return hash(tuple(sorted(self.__dict__.items())))
    
    def __repr__(self):
        # TODO : Be more precise.
        return "<Moment ('{}')>".format(self.__str__())
    
    def __str__(self):
        if self.kind == MomentKind.NORMAL:
            return self.time().strftime("%H:%M")
        else:
            word = self.kind.name.lower()
            if not self._delta.seconds:
                return word
            else:
                delta = (
                    datetime.datetime(2000, 1, 1, 0) +
                    self._delta
                ).time().strftime("%H:%M")
                return "{word} {sign} {delta}".format(
                    word=word,
                    sign='-' if self._delta.days == -1 else '+',
                    delta=delta
                )

NextChange = namedtuple("NextChange", ["dt", "moment"])
