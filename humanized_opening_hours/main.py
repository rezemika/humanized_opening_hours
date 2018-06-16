import os
import re
import datetime
import warnings
from collections import namedtuple

import lark
import babel.dates
import astral

from humanized_opening_hours.temporal_objects import WEEKDAYS, MONTHS
from humanized_opening_hours.field_parser import (
    PARSER, get_tree_and_rules
)
from humanized_opening_hours.rendering import (
    DescriptionTransformer, LOCALES, render_timespan,
    join_list, translate_open_closed
)
from humanized_opening_hours.exceptions import (
    ParseError, CommentOnlyField, NextChangeRecursionError
)


BASE_DIR = os.path.dirname(os.path.realpath(__file__))

DayPeriods = namedtuple(
    "DayPeriods", [
        "weekday_name", "date", "periods",
        "rendered_periods", "joined_rendered_periods"
    ]
)
DayPeriods.__doc__ += """\n
weekday_name : str
    The name of the day (ex: "Monday").
date : datetime.date
    The date of the day.
periods : list[tuple(datetime.datetime, datetime.datetime)]
    The opening periods of the day, of the shape (beginning, end).
rendered_periods : list[str]
    A list of strings describing the opening periods of the day.
joined_rendered_periods : str
    The same list, but joined to string by comas and a terminal word.
    Ex: "09:00 - 12:00 and 13:00 - 19:00"."""


def set_dt(dt):
    """
    Sets 'dt' argument to 'datetime.datetime.now' if it's set to None.
    """
    return dt if dt is not None else datetime.datetime.now()


RE_NUMERICAL_TIME_HH_H_MM = re.compile(r"([0-2][0-9])h([0-5][0-9])")
RE_NUMERICAL_TIME_HH_H = re.compile(r"([0-2][0-9])h")
RE_NUMERICAL_TIME_H_H = re.compile(r"(?:[^0-9]|^)([0-9])h")
TIME_REGEX = (
    r"[0-2][0-9]:[0-5][0-9]|"
    r"\((?:sunrise|sunset|dawn|dusk)(?:\+|-)[0-2][0-9]:[0-5][0-9]\)|"
    r"(?:sunrise|sunset|dawn|dusk)"
)
RE_TIMESPAN = re.compile(
    r"({time_regex}) ?- ?({time_regex})".format(time_regex=TIME_REGEX)
)
RE_MULTIPLE_TIMESPANS = re.compile(
    r"({time_regex}-{time_regex}) ?,? ?({time_regex}-{time_regex})".format(
        time_regex=TIME_REGEX
    )
)
RE_TIME_H_MM = re.compile(r"([^0-9]|^)([0-9]):([0-2][0-9])")
SPECIAL_WORDS = WEEKDAYS + MONTHS + (
    "sunrise", "sunset", "dawn", "dusk", "PH", "SH",
    "open", "off", "closed", "easter", "week"
)
RE_SPECIAL_WORDS = [
    (word, re.compile(word, re.IGNORECASE)) for word in SPECIAL_WORDS
]


def sanitize(field):
    """Returns a "more valid" version of the given field.
    /!\ It does not sanitize parts with comments.
    
    Parameters
    ----------
    str
        The field to sanitize.
    
    Returns
    -------
    str
        The sanitized field.
    """
    splited_field = [
        part.strip() for part in field.strip(' \n\t;').split(';')
    ]
    parts = []
    for part in splited_field:
        # Skips part if it contains a comment.
        if '"' in part:
            parts.append(part)
            continue
        # Replaces 'h' by ':' in times.
        part = RE_NUMERICAL_TIME_HH_H_MM.sub("\\1:\\2", part)
        part = RE_NUMERICAL_TIME_HH_H.sub("\\1:00", part)
        part = RE_NUMERICAL_TIME_H_H.sub("0\\1:00", part)
        # Removes spaces between times.
        # "10:00 - 20:00" -> "10:00-20:00"
        part = RE_TIMESPAN.sub("\\1-\\2", part)
        # Removes spaces between timespans and adds coma if necessary.
        # "10:00-12:00 , 13:00-20:00" -> "10:00-12:00,13:00-20:00"
        # "10:00-12:00 13:00-20:00" -> "10:00-12:00,13:00-20:00"
        part = RE_MULTIPLE_TIMESPANS.sub("\\1,\\2", part)
        # Replaces "00:00" by "24:00" when necessary.
        part = part.replace("-00:00", "-24:00")
        # Adds zeros when necessary.
        # "7:30" -> "07:30"
        part = RE_TIME_H_MM.sub(r"\g<1>0\g<2>:\g<3>", part)
        # Corrects the case errors.
        # "mo" -> "Mo"
        for word in RE_SPECIAL_WORDS:
            part = word[1].sub(word[0], part)
        #
        parts.append(part)
    return '; '.join(parts)


class SolarHoursManager:
    def __init__(self, location):
        """Stores solar hours by dates.
        
        Parameters
        ----------
        astral.Location or tuple, optional
            Allows you to provide a location, allowing an automatic
            getting of solar hours. Must be an 'astral.Location' object
            or a tuple like '(latitude, longitude, timezone_name, elevation)'.
            None default, meaning it relies only on manual settings.
        
        Attributes
        ----------
        location : astral.Location, optional
            The location for which to get solar hours.
        solar_hours : dict{str: datetime.time}
            A dict containing hours of sunrise, sunset, dawn and dusk.
        
        To get solar hours, see '__getitem__()'.
        To manually set them, see '__setitem__()'.
        """
        if isinstance(location, astral.Location):
            self.location = location
        elif location:
            self.location = astral.Location(
                ["Location", "Region", *location]
            )
        else:
            self.location = None
        self.solar_hours = {}
    
    def __setitem__(self, dt: datetime.date, hours: dict):
        """Sets solar hours for a given day.
        
        Usage:
        >>> solar_hours_manager[datetime.date] = dict
        """
        self.solar_hours[dt] = hours
    
    def __getitem__(self, dt: datetime.date) -> dict:
        """Returns solar hours for a given day.
        
        Usage:
        >>> solar_hours = solar_hours_manager[datetime.date]
        """
        sh = self.solar_hours.get(dt)
        if sh:
            return sh
        solar_hours = {
            "sunrise": None, "sunset": None,
            "dawn": None, "dusk": None
        }
        if not self.location:
            return solar_hours
        
        for event in solar_hours:
            try:
                solar_hours[event] = (
                    getattr(self.location, event)(dt)
                    .time().replace(tzinfo=None)
                )
            except astral.AstralError:
                solar_hours[event] = None
        self.solar_hours[dt] = solar_hours
        return solar_hours
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<SolarHours for {!r}>".format(self.location)


class OHParser:
    def __init__(self, field, locale="en", location=None, optimize=True):
        """A parser for the OSM opening_hours fields.
        
        >>> oh = hoh.OHParser("Mo-Fr 10:00-19:00")
        
        Parameters
        ----------
        field : str
            The opening_hours field.
        locale : str, optional
            The locale to use. "en" default.
        location : astral.Location or tuple, optional
            Allows you to provide a location, allowing an automatic
            getting of solar hours. Must be an 'astral.Location' object
            or a tuple like '(latitude, longitude, timezone_name, elevation)'.
        optimize : bool, optional
            If True (default), the parsing will be skipped if the field is
            very frequent (ex: "24/7")  or simple and HOH will use a simpler
            and faster parser than Lark. Set to False to prevent this behavior.
        
        Attributes
        ----------
        original_field : str
            The raw field given to the constructor.
        sanitized_field : str
            The field once sanitized by the "sanitize()" function.
        needs_solar_hours_setting : dict{str: bool}
            A dict indicating if solar hours setting is required
            for each solar hour (sunrise, sunset, dawn and dusk).
        PH_dates : list[datetime.date]
            A list of the days considered as public holidays.
            Empty default, you have to fill it yourself.
        SH_dates : list[datetime.date]
            A list of the days considered as school holidays.
            Empty default, you have to fill it yourself.
        solar_hours_manager : SolarHoursManager
            An object storing and calculating solar hours for the desired dates.
        
        Raises
        ------
        humanized_opening_hours.ParseError
            When something goes wrong during the parsing
            (e.g. the field is invalid or contains an unsupported pattern).
        """
        self.original_field = field
        # TODO : Rename to 'field' ?
        self.sanitized_field = sanitize(self.original_field)
        
        if (  # Ex: "on appointment"
            self.sanitized_field.count('"') == 2 and
            self.sanitized_field.startswith('"') and
            self.sanitized_field.endswith('"')
        ):
            raise CommentOnlyField(
                "The field {!r} contains only a comment.".format(
                    self.sanitized_field
                ),
                field.strip('"')
            )
        
        try:
            self._tree, self.rules = get_tree_and_rules(
                self.sanitized_field, optimize
            )
        except lark.lexer.UnexpectedInput as e:
            raise ParseError(
                "The field could not be parsed, it may be invalid. "
                "Error happened on column {col} when "
                "parsing {context!r}.".format(
                    col=e.column,
                    context=e.context
                )
            )
        except lark.common.UnexpectedToken as e:
            raise ParseError(
                "The field could not be parsed, it may be invalid. "
                "Error happened on column {col} when "
                "parsing {context!r}.".format(
                    col=e.column,
                    context=e.token.value
                )
            )
        except lark.common.ParseError as e:
            raise ParseError(
                "The field could not be parsed, it may be invalid."
            )
        
        self.babel_locale = babel.Locale.parse(locale)
        if locale not in LOCALES.keys():
            warnings.warn(
                (
                    "The locale {!r} is not supported "
                    "by the 'description()' method, "
                    "using it will raise an exception."
                ).format(locale),
                UserWarning
            )
        
        self.PH_dates = []
        self.SH_dates = []
        self.needs_solar_hours_setting = {
            "sunrise": "sunrise" in self.sanitized_field,
            "sunset": "sunset" in self.sanitized_field,
            "dawn": "dawn" in self.sanitized_field,
            "dusk": "dusk" in self.sanitized_field
        }
        self.solar_hours_manager = SolarHoursManager(location)
    
    def is_open(self, dt=None):
        """Is it open?
        
        Parameters
        ----------
        dt : datetime.datetime, optional
            The moment for which to check the opening. None default,
            meaning use the present time.
        
        Returns
        -------
        bool
            True if it's open, False else.
        """
        dt = set_dt(dt)
        timespans = self._get_day_timespans(dt)
        for timespan in timespans:
            beginning, end = timespan[1].get_times(
                timespan[0], self.solar_hours_manager[timespan[0]]
            )
            if beginning < dt < end:
                return True
        return False
    
    def next_change(self, dt=None, max_recursion=31, _recursion_level=0):
        """Gets the next opening status change.
        
        Parameters
        ----------
        dt : datetime.datetime, optional
            The moment for which to check the opening. None default,
            meaning use the present time.
        max_recursion : int, optional
            The maximum recursion, to check if the next change is in
            another day. If it's reached, a NextChangeRecursionError
            will be raised. Set it to zero to return the first next
            change without trying recursion.
        
        Returns
        -------
        datetime.datetime
            The datetime of the next change.
        """
        # Returns None if in recursion and don't start with datetime.time.min.
        def _current_or_next_timespan(dt):
            current_rule = None
            i = 0
            while current_rule is None:
                current_rule = self.get_current_rule(
                    dt.date()+datetime.timedelta(i)
                )
                if current_rule is None:
                    if _recursion_level != 0:
                        return (None, None)
                    i += 1
            new_time = dt.time() if i == 0 else datetime.time.min
            new_dt = datetime.datetime.combine(
                dt.date() + datetime.timedelta(i),
                new_time
            )
            
            timespans = self._get_day_timespans(new_dt)
            for timespan in timespans:
                beginning, end_time = timespan[1].get_times(
                    timespan[0], self.solar_hours_manager[timespan[0]]
                )
                if new_dt < end_time:
                    return (i, timespan[1])
            
            return _current_or_next_timespan(new_dt)
        
        dt = set_dt(dt)
        days_offset, next_timespan = _current_or_next_timespan(dt)
        if (days_offset, next_timespan) == (None, None):
            return None
        
        new_time = dt.time() if days_offset == 0 else datetime.time.min
        new_dt = datetime.datetime.combine(
            dt.date() + datetime.timedelta(days_offset),
            new_time
        )
        
        beginning_time, end_time = next_timespan.get_times(
            new_dt, self.solar_hours_manager[new_dt.date()]
        )
        
        if _recursion_level > 1 and beginning_time.time() != datetime.time.min:
            return None
        
        if dt < beginning_time:
            return beginning_time
        
        if _recursion_level == max_recursion != 0:
            raise NextChangeRecursionError(
                "Done {} recursions but couldn't get "
                "the true next change.".format(_recursion_level),
                end_time
            )
        if (
            end_time.time() == datetime.time.max and
            max_recursion != 0
        ):
            next_next_change = self.next_change(
                datetime.datetime.combine(
                    new_dt.date()+datetime.timedelta(1), datetime.time.min
                ),
                max_recursion=max_recursion,
                _recursion_level=_recursion_level+1
            )
            if next_next_change is not None:
                return next_next_change
        
        return end_time
    
    def description(self):
        """Returns a list of strings (sentences) describing all opening hours.
        
        Returns
        -------
        list[str]
            A list of sentences (beginning with a capital letter and ending
            with a point). Ex: ['From Monday to Friday: 10:00 - 20:00.']
        """
        if not self._tree:
            self._tree = PARSER.parse(self.sanitized_field)
        transformer = DescriptionTransformer()
        transformer._locale = self.babel_locale
        transformer._human_names = self.get_human_names()
        transformer._install_locale()
        return transformer.transform(self._tree)
    
    def time_before_next_change(self, dt=None, word=True):
        """Returns a human-readable string of the remaining time
        before the next opening status change.
        
        Parameters
        ----------
        dt : datetime.datetime, optional
            The moment for which to check the opening. None default,
            meaning use the present time. Same as for the
            `next_change()` method of OHParser.
        word : bool, optional
            Defines whether to add a descriptive word before the delay.
            For example: "in X minutes" if True, "X minutes" if False.
            True default.
        
        Returns
        -------
        str
            The descriptive string (not capitalized at the beginning).
            For example: "in 15 minutes" (en) or "dans 2 jours" (fr).
        """
        dt = set_dt(dt)
        next_change = self.next_change(dt=dt)
        delta = next_change - dt
        # TODO : Check granularity.
        return babel.dates.format_timedelta(
            delta,
            granularity="minute",
            threshold=2,
            locale=self.babel_locale,
            add_direction=word
        )
    
    def get_human_names(self):  # TODO : Rename ?
        """Gets months and days names in the locale given to the constructor.
        
        Returns
        -------
        dict{str: list[str]}
            A dict with the keys "days" and "months" containing lists
            of respectively 7 and 12 strings.
        """
        days = []
        months = []
        for i in range(7):
            days.append(self.babel_locale.days["format"]["wide"][i])
        for i in range(12):
            months.append(self.babel_locale.months['format']['wide'][i+1])
        return {"days": days, "months": months}
    
    def get_current_rule(self, dt=None):
        """Returns the rule corresponding to the given day.
        
        Parameters
        ----------
        dt : datetime.date, optional
            The day for which to get the rule. None default,
            meaning use the present day.
        
        Returns
        -------
        humanized_opening_hours.Rule or None
            The rule matching the given datetime, if available.
        """
        if dt is None:
            dt = datetime.date.today()
        for rule in self.rules:
            if rule.range_selectors.is_included(
                dt, self.SH_dates, self.PH_dates
            ):
                return rule
        return None
    
    def _get_day_timespans(self, dt=None, _check_yesterday=True):
        """
            Returns a list of tuples like (datetime.date, TimeSpan)
            from the given date.
        """
        # '_check_yesterday=True' allows to get TimeSpan from yesterday which
        # span over midnight.
        if not dt:
            dt = datetime.date.today()
        current_rule = self.get_current_rule(dt)
        
        # List of tuples (datetime.date, TimeSpan).
        # The datetimes are used to get times (if the TimeSpan is yesterday).
        timespans = []
        if current_rule:
            for current_rule_timespan in current_rule.time_selectors:
                timespans.append((dt, current_rule_timespan))
        
        # If '_check_yesterday' is True, check in yesterday timespans if
        # one spans over midnight (and so, is in the current day), and adds it
        # to the current day timespans.
        if _check_yesterday:
            yesterday_date = dt-datetime.timedelta(1)
            yesterday_rule = self.get_current_rule(
                yesterday_date
            )
            if yesterday_rule:
                yesterday_timespans = []
                for yesterday_timespan in yesterday_rule.time_selectors:
                    yesterday_timespan_times = yesterday_timespan.get_times(
                        yesterday_date,
                        self.solar_hours_manager[yesterday_date]
                    )
                    if yesterday_timespan_times[1].date() == dt:
                        yesterday_timespans.append(
                            (yesterday_date, yesterday_timespan)
                        )
                timespans = yesterday_timespans + timespans
        return timespans
    
    def get_day_periods(self, dt=None, _check_yesterday=True):
        """Returns the opening periods of the given day.
        
        Parameters
        ----------
        dt : datetime.date
            The day for which to get the rule. None default,
            meaning use the present day.
        
        Returns
        -------
        DayPeriods (collections.namedtuple)
            A namedtuple representing the requested day.
            
            Attributes :
            - weekday_name : str
                The named of the day (ex: "Monday").
            - date : datetime.date
                The date of the day.
            - periods : list[tuple(datetime.datetime, datetime.datetime)]
                The opening periods of the day, of the shape (beginning, end).
            - rendered_periods : list[str]
                A list of strings describing the opening periods of the day.
            - joined_rendered_periods : str
                The same list, but joined to string by comas
                and a terminal word. Ex: "09:00 - 12:00 and 13:00 - 19:00".
        """
        if not dt:
            dt = datetime.date.today()
        timespans = self._get_day_timespans(
            dt, _check_yesterday=_check_yesterday
        )
        
        weekday_name = self.get_human_names()["days"][dt.weekday()]
        periods = []
        for timespan in timespans:
            periods.append(
                timespan[1].get_times(
                    timespan[0], self.solar_hours_manager[timespan[0]]
                )
            )
        if periods:
            rendered_periods = [
                render_timespan(ts[1], self.babel_locale) for ts in timespans
            ]
            # TODO : Check for locale.
            joined_rendered_periods = join_list(rendered_periods)
        else:
            closed_word = translate_open_closed(self.babel_locale)[1]
            rendered_periods = [closed_word]
            joined_rendered_periods = closed_word
        return DayPeriods(
            weekday_name, dt, periods,
            rendered_periods, joined_rendered_periods
        )
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<OHParser field: '{}'>".format(self.sanitized_field)
