import os
import re
import datetime
import warnings
from collections import namedtuple
import statistics

import lark
import babel.dates
import astral

from humanized_opening_hours.temporal_objects import WEEKDAYS, MONTHS
from humanized_opening_hours.field_parser import get_tree_and_rules
from humanized_opening_hours.rendering import (
    DescriptionTransformer, AVAILABLE_LOCALES, render_timespan,
    join_list, translate_open_closed, translate_colon
)
from humanized_opening_hours.exceptions import (
    ParseError, CommentOnlyField, AlwaysClosed, NextChangeRecursionError
)


BASE_DIR = os.path.dirname(os.path.realpath(__file__))

DayPeriods = namedtuple(
    "DayPeriods", [
        "weekday_name", "date", "periods",
        "rendered_periods", "joined_rendered_periods"
    ]
)
DayPeriods.__doc__ += """\n
Attributes
----------
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


def days_of_week(year=None, weeknumber=None, first_weekday=0):
    """Returns a list of the days in the requested week.
    
    Parameters
    ----------
    year : int, optional
        The year of the week.
        The current year default.
    weeknumber : int, optional
        The index of the week in the year (1-53).
        The current week default.
    first_weekday : int, optional
        The first day of the week, 0 means "Monday".
        0 default.
    
    Returns
    -------
    list[datetime.date]
        The days of the requested week.
    """
    if not year or not weeknumber:
        dt = datetime.date.today()
        year, weeknumber, _ = dt.isocalendar()
    
    # Code inspired from https://github.com/gisle/isoweek/blob/c6f2cc01f1dbc7cfdf75294421ad14ab4007d93b/isoweek.py#L93-L96  # noqa
    base_date = datetime.date(year, 1, 4+first_weekday)
    days = []
    for i in range(7):
        days.append(
            base_date + datetime.timedelta(
                weeks=weeknumber-1, days=(-base_date.weekday())+i-first_weekday
            )
        )
    return days


class SolarHours(dict):
    _SH_DICT = {
        "sunrise": None, "sunset": None,
        "dawn": None, "dusk": None
    }
    
    def __init__(self, *args, location=None):
        """An object inheriting from dict, storing solar hours for a location.
        
        Parameters
        ----------
        location : astral.Location or tuple, optional
            Allows you to provide a location, allowing an automatic
            getting of solar hours. Must be an 'astral.Location' object
            or a tuple like '(latitude, longitude, timezone_name, elevation)'.
            None default, meaning it relies only on manual settings.
            Although this is mostly intended for manual testing, you can
            also use one of the capital/city names supported by Astral,
            like "London" or "Copenhagen".
        
        Attributes
        ----------
        location : astral.Location or None
            The location for which to get solar hours.
        
        To manually set solar hours for the present day, do the following:
        
        >>> solar_hours[datetime.date.today()] = {...}
        """
        if isinstance(location, astral.Location):
            self.location = location
        elif isinstance(location, tuple):
            self.location = astral.Location(
                ["Location", "Region", *location]
            )
        elif isinstance(location, str):
            self.location = astral.Astral()[location]
        else:
            self.location = None
        super().__init__(*args)
    
    def __getitem__(self, dt: datetime.date) -> dict:
        sh = self.get(dt)
        if sh is not None:
            return sh
        if not self.location:
            return self._SH_DICT
        
        try:
            # Removes localization and date part
            # from datetimes returned by Astral.
            sh = dict([
                (k, v.replace(tzinfo=None).time()) for (k, v) in
                self.location.sun(date=dt, local=True).items()
            ])
            self[dt] = sh
            return sh
        except astral.AstralError:
            return self._SH_DICT


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
        field : str
            The field once sanitized by the "sanitize()" function.
        locale : babel.Locale
            The locale used for translations. As it is a property,
            you can change it by assigning a new string (the name of the locale)
            to it, it will be converted into a `babel.Locale` object.
        is_24_7 : bool
            Indicates whether the field is "24/7", i.e. the facility is
            always open.
        needs_solar_hours_setting : dict{str: bool}
            A dict indicating if solar hours setting is required
            for each solar hour (sunrise, sunset, dawn and dusk).
        PH_dates : list[datetime.date]
            A list of the days considered as public holidays.
            Empty default, you have to fill it yourself.
        SH_dates : list[datetime.date]
            A list of the days considered as school holidays.
            Empty default, you have to fill it yourself.
        solar_hours : SolarHours
            An object storing and calculating solar hours for the desired dates.
        
        Warns
        -----
        UserWarning
            When the given locale is not supported by the 'description()'
            method (the others will work fine).
        
        Raises
        ------
        humanized_opening_hours.exceptions.ParseError
            When something goes wrong during the parsing
            (e.g. the field is invalid or contains an unsupported pattern).
        humanized_opening_hours.exceptions.CommentOnlyField
            When the field contains only a comment.
            The comment is accessible via the 'comment' attribute.
            Inherits from 'ParseError'.
        humanized_opening_hours.exceptions.AlwaysClosed
            When the field indicates only "closed" or "off".
            Inherits from 'ParseError'.
        """
        self.original_field = field
        self.field = sanitize(self.original_field)
        
        if (  # Ex: "on appointment"
            self.field.count('"') == 2 and
            self.field.startswith('"') and
            self.field.endswith('"')
        ):
            raise CommentOnlyField(
                "The field {!r} contains only a comment.".format(
                    self.field
                ),
                field.strip('"')
            )
        if self.field in ("closed", "off"):
            raise AlwaysClosed("This facility is always closed.")
        
        if self.field in ("24/7", "00:00-24:00"):
            self.is_24_7 = True
        else:
            self.is_24_7 = False
        
        try:
            self._tree, self.rules = get_tree_and_rules(
                self.field, optimize
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
        
        self.locale = locale
        
        self.PH_dates = []
        self.SH_dates = []
        self.needs_solar_hours_setting = {
            "sunrise": "sunrise" in self.field,
            "sunset": "sunset" in self.field,
            "dawn": "dawn" in self.field,
            "dusk": "dusk" in self.field
        }
        self.solar_hours = SolarHours(location=location)
    
    @classmethod
    def from_geojson(cls, geojson, timezone_getter=None, locale="en"):
        """A classmethod which creates an OHParser instance from a GeoJSON.
        
        Parameters
        ----------
        geojson : dict
            The GeoJSON to use, which must contain 'geometry' and 'properties'
            keys (which must contain an 'opening_hours' key).
        timezone_getter : callable, optional
            A function to call, which takes two arguments (latitude and
            longitude, as floats), and returns a timezone name or None,
            allowing to get solar hours for the facility.
        locale : str, optional
            The locale to use. "en" default.
        
        Returns
        -------
        OHParser instance
        
        Raises
        ------
        KeyError
            If the given GeoJSON doesn't contain 'geometry' and 'properties'
            keys and an 'opening_hours' key in 'properties'.
        """
        def centroid(coordinates):
            # Returns the mean of a list of coordinates like [(lat, lon)].
            # Source: https://stackoverflow.com/a/23021198
            latitudes, longitudes = coordinates[0::2], coordinates[1::2]
            return (statistics.mean(latitudes), statistics.mean(longitudes))
        
        if geojson["geometry"]["type"] != "Point":
            coordinates = centroid(geojson["geometry"]["coordinates"][::-1])
        else:
            coordinates = tuple(geojson["geometry"]["coordinates"][::-1])
        
        location = None
        if timezone_getter:
            timezone = timezone_getter(*coordinates)
            if timezone:
                location = (*coordinates, timezone, 0)
        
        field = geojson["properties"]["opening_hours"]
        return cls(field, locale=locale, location=location)
    
    @property
    def locale(self):
        return self._locale
    
    @locale.setter
    def locale(self, locale):
        """Sets the locale to use for translations.
        
        Parameters
        ----------
        str
            The name of the locale to use.
        
        Warns
        -----
            When the given locale is not supported by the 'description()'
            method (the others will work fine).
        """
        self._locale = babel.Locale.parse(locale)
        if locale not in AVAILABLE_LOCALES and locale != "en":
            warnings.warn(
                (
                    "The locale {!r} is not supported by the 'description()' "
                    "method, using it will return inconsistent sentences."
                ).format(locale),
                UserWarning
            )
    
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
        if self.is_24_7:
            return True
        dt = set_dt(dt)
        timespans = self._get_day_timespans(dt.date())
        for timespan in timespans:
            beginning, end = timespan[1].get_times(
                timespan[0], self.solar_hours[timespan[0]]
            )
            if beginning <= dt < end:
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
        
        Raises
        ------
        humanized_opening_hours.exceptions.NextChangeRecursionError
            When reaching the maximum recursion level.
        """
        def _current_or_next_timespan(dt, i=0):
            # Returns None if in recursion and don't start
            # with datetime.time.min.
            # The 'i' parameter fixes a RecursionError in some weird cases.
            while True:
                current_rule = self.get_current_rule(
                    dt.date()+datetime.timedelta(i)
                )
                if current_rule:
                    break
                elif _recursion_level > 0:
                    return (None, None)
                i += 1
            new_dt = datetime.datetime.combine(
                dt.date() + datetime.timedelta(i),
                dt.time() if i == 0 else datetime.time.min
            )
            
            timespans = self._get_day_timespans(new_dt.date())
            for timespan in timespans:
                beginning, end_time = timespan[1].get_times(
                    timespan[0], self.solar_hours[timespan[0]]
                )
                if new_dt < end_time:
                    return (i, timespan[1])
            
            new_dt = datetime.datetime.combine(
                new_dt.date()+datetime.timedelta(i),
                datetime.time.min
            )
            return _current_or_next_timespan(new_dt, i=i+1)
        
        dt = set_dt(dt)
        days_offset, next_timespan = _current_or_next_timespan(dt)
        if (days_offset, next_timespan) == (None, None):
            return None
        
        new_dt = datetime.datetime.combine(
            dt.date() + datetime.timedelta(days_offset),
            dt.time() if days_offset == 0 else datetime.time.min
        )
        
        beginning_time, end_time = next_timespan.get_times(
            new_dt, self.solar_hours[new_dt.date()]
        )
        
        if self.is_24_7:
            if max_recursion == 0:
                return end_time
            else:
                raise NextChangeRecursionError(
                    "This facility is always open ('24/7').",
                    end_time
                )
        elif (
            _recursion_level > 1 and
            beginning_time.time() != datetime.time.min
        ):
            return None
        elif dt < beginning_time:
            return beginning_time
        elif _recursion_level == max_recursion != 0:
            raise NextChangeRecursionError(
                "Done {} recursions but couldn't get "
                "the true next change.".format(_recursion_level),
                end_time
            )
        elif (
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
        transformer = DescriptionTransformer()
        transformer._locale = self.locale
        transformer._human_names = self.get_localized_names()
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
            locale=self.locale,
            add_direction=word
        )
    
    def get_localized_names(self):
        """Gets months and days names in the locale given to the constructor.
        
        Returns
        -------
        dict{str: list[str]}
            A dict with the keys "days" and "months" containing lists
            of respectively 7 and 12 strings.
        """
        return {
            "days": list(
                babel.dates.get_day_names(locale=self.locale).values()
            ),
            "months": list(
                babel.dates.get_month_names(locale=self.locale).values()
            )
        }
    
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
        matching_rules = [
            r for r in self.rules if r.range_selectors.is_included(
                dt, self.SH_dates, self.PH_dates
            )
        ]
        matching_rules = list(reversed(
            sorted(matching_rules, key=lambda r: r.priority)
        ))
        if matching_rules:
            return matching_rules[0]
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
        
        if type(dt) is not datetime.date:
            raise TypeError(
                "The 'dt' parameter must be a 'datetime.date' object."
            )
        
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
                        self.solar_hours[yesterday_date]
                    )
                    if yesterday_timespan_times[1].date() == dt:
                        yesterday_timespans.append(
                            (yesterday_date, yesterday_timespan)
                        )
                timespans = yesterday_timespans + timespans
        return timespans
    
    def plaintext_week_description(
        self, year=None, weeknumber=None, first_weekday=None
    ):
        """Returns the opening periods of the given day.
        
        Parameters
        ----------
        year : int, optional
            The year of the week.
            The current year default.
        weeknumber : int, optional
            The index of the week in the year (1-53).
            The current week default.
        first_weekday : int, optional
            The first day of the week, 0 means "Monday".
            None default, meaning use the current locale's first weekday.
        
        Returns
        -------
        str
            The plaintext schedules of the week. Contains 7 lines.
        """
        if first_weekday is None:
            first_weekday = self.locale.first_week_day
        week = days_of_week(year, weeknumber, first_weekday)
        output = []
        for day in week:  # TODO: Check yesterday for first day?
            day_periods = self.get_day_periods(dt=day, _check_yesterday=False)
            output.append(
                (day_periods.weekday_name, day_periods.joined_rendered_periods)
            )
        colon_str = translate_colon(self.locale)
        return '\n'.join(
            [colon_str.format(day[0], day[1]) for day in output]
        )
    
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
        
        weekday_name = self.get_localized_names()["days"][dt.weekday()]
        periods = []
        for timespan in timespans:
            periods.append(
                timespan[1].get_times(
                    timespan[0], self.solar_hours[timespan[0]]
                )
            )
        if periods:
            rendered_periods = [
                render_timespan(ts[1], self.locale) for ts in timespans
            ]
            joined_rendered_periods = join_list(rendered_periods, self.locale)
        else:
            closed_word = translate_open_closed(self.locale)[1]
            rendered_periods = [closed_word]
            joined_rendered_periods = closed_word
        return DayPeriods(
            weekday_name, dt, periods,
            rendered_periods, joined_rendered_periods
        )
    
    def opening_periods_between(self, dt1, dt2):
        """Returns a list of tuples representing opening periods.
        
        Parameters
        ----------
        datetime.date or datetime.datetime
            The date from which get the opening periods.
            Give a 'datetime.datetime' to "chop" opening periods before
            this datetime.
        datetime.date or datetime.datetime
            The date until which to get the opening periods.
            Give a 'datetime.datetime' to "chop" opening periods after
            this datetime.
        
        Returns
        -------
        list[tuple(datetime.datetime, datetime.datetime)]
            The opening periods between the given dates,
            of the shape (beginning, end).
        """
        dt1_date = dt1.date() if isinstance(dt1, datetime.datetime) else dt1
        dt2_date = dt2.date() if isinstance(dt2, datetime.datetime) else dt2
        delta = dt2_date - dt1_date
        periods = []
        for date in (
            dt1_date + datetime.timedelta(n) for n in range(delta.days+1)
        ):
            day_periods = self.get_day_periods(date)
            periods.extend(day_periods.periods)
        # Uses a set to removes doubles periods (cause we also get those which
        # span over midnight.
        periods = sorted(set(periods))
        output_periods = []
        for i, period in enumerate(periods):
            if (
                i == 0 and isinstance(dt1, datetime.datetime) and
                period[0] < dt1 < period[1]
            ):
                output_periods.append((dt1, period[1]))
            elif (
                i+1 == len(periods) and isinstance(dt2, datetime.datetime) and
                period[0] < dt2 < period[1]
            ):
                output_periods.append((period[0], dt2))
            else:
                output_periods.append(period)
        return output_periods
    
    def __eq__(self, other):
        if type(other) is OHParser:
            self_location = self.solar_hours.location
            other_location = other.solar_hours.location
            if (
                self_location is None and other_location is not None or
                self_location is not None and other_location is None
            ):
                return False
            if self_location is None and other_location is None:
                return self.field == other.field
            return (
                self.field == other.field and
                # All this tests are necessary because Astral does not
                # provide equality method for Location yet.
                self_location.name == other_location.name and
                self_location.region == other_location.region and
                self_location.latitude == other_location.latitude and
                self_location.longitude == other_location.longitude and
                self_location.timezone == other_location.timezone and
                self_location.elevation == other_location.elevation
            )
        return NotImplemented
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<OHParser field: '{}'>".format(self.field)
