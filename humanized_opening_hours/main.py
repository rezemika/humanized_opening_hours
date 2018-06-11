import os
import re
import datetime
import warnings

import lark
import babel.dates
import astral

from humanized_opening_hours.temporal_objects import WEEKDAYS, MONTHS
from humanized_opening_hours.field_parser import (
    PARSER, LOCALES, DescriptionTransformer, get_tree_and_rules
)
from humanized_opening_hours.exceptions import ParseError


BASE_DIR = os.path.dirname(os.path.realpath(__file__))


def set_dt(dt):
    """
    Sets 'dt' argument to 'datetime.datetime.now' if it's set to None.
    """
    return dt if dt is not None else datetime.datetime.now()


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
            The field once sanitized by the "sanitize()" method.
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
        self.sanitized_field = self.sanitize(self.original_field)
        
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
        if locale not in LOCALES.keys():  # TODO : Warning.
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
    
    @staticmethod
    def sanitize(field):
        """Returns a "more valid" version of the given field.
        
        Parameters
        ----------
        str
            The field to sanitize.
        
        Returns
        -------
        str
            The sanitized field.
        """
        special_words = WEEKDAYS + MONTHS + (
            "sunrise", "sunset",
            "dawn", "dusk",
            "PH", "SH",
            "open", "off", "closed",
            "easter"
        )
        splited_field = [
            part.strip() for part in field.strip(' \n\t;').split(';')
        ]
        parts = []
        for part in splited_field:
            # Adds or removes spaces when necessary.
            # "Mo-Su 10:00-19:00;Sa off" => "Mo-Su 10:00-19:00; Sa off"
            part = re.sub("\s*(;)\s*", "\1 ", part)
            # " , " => ","
            part = re.sub(" ?, ?", ",", part)
            # "10:00 - 20:00" -> "10:00-20:00"
            part = re.sub(
                "([0-2][0-9]:[0-5][0-9]) ? - ?([0-2][0-9]:[0-5][0-9])",
                r"\1-\2", part
            )
            # Replaces "00:00" by "24:00" when necessary.
            part = part.replace("-00:00", "-24:00")
            # Corrects the case errors.
            # "mo" => "Mo"
            for word in special_words:
                part = re.sub("(?i){}(?!\w+)".format(word), word, part)
            # Removes 'h' when necessary.
            for moment in re.findall("([0-9][0-9]h)[^0-9]", part):
                part = part.replace(moment, moment[:2] + ':00')
            for moment in re.findall("[0-9][0-9]h[0-9]", part):
                part = part.replace(moment, moment[:2] + ':' + moment[-1])
            # Adds zeros when necessary.
            # "7:30" => "07:30"
            part = re.sub("([^0-9]|^)([0-9]:[0-9])", r"\g<1>0\g<2>", part)
            # Adds semicolons when necessary.
            part = re.sub("([0-9]) ?, ?([A-Za-z][a-z][^a-z])", r"\1; \2", part)
            # Adds comas when necessary.
            # "10:00-12:00 14:00-19:00" -> "10:00-12:00,14:00-19:00"
            MOMENT_REGEX = (
                r"\((?:sunrise|sunset|dawn|dusk)(?:\+|-)"
                r"[0-2][0-9]:[0-5][0-9]\)|"
                r"[0-2][0-9]:[0-5][0-9]|"
                r"(?:sunrise|sunset|dawn|dusk)"
            )
            part = re.sub(
                "({m}) ?- ?({m}) *({m}) ?- ?({m})".format(m=MOMENT_REGEX),
                r"\1-\2,\3-\4",
                part
            )
            # Replaces "24" by "24/7".
            if part in ("24", "24 hours", "24 Hours", "24h"):
                part = "24/7"
            parts.append(part)
        return '; '.join(parts)
    
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
        str : The descriptive string (not capitalized at the beginning).
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
    
    def get_human_names(self):
        """Gets months and days names in the locale given to the constructor.
        
        Returns
        -------
        dict[lists] : A dict with the keys "days" and "months"
            containing lists of respectively 7 and 12 strings.
        """
        days = []
        months = []
        for i in range(7):
            days.append(self.babel_locale.days["format"]["wide"][i])
        for i in range(12):
            months.append(self.babel_locale.months['format']['wide'][i+1])
        return {"days": days, "months": months}
    
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
        for rule in self.rules:  # TODO : Use "get_current_rule()" ?
            if rule.range_selectors.is_included(
                dt.date(), self.SH_dates, self.PH_dates
            ):
                return rule.get_status_at(
                    dt, self.solar_hours_manager[dt.date()]
                )
        return False
    
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
    
    def next_change(self, dt=None):
        """Gets the next opening status change.
        
        Parameters
        ----------
        dt : datetime.datetime, optional
            The moment for which to check the opening. None default,
            meaning use the present time.
        
        Returns
        -------
        datetime.datetime
            The datetime of the next change.
        """
        dt = set_dt(dt)
        days_offset, next_timespan = self._current_or_next_timespan(dt)
        
        new_time = dt.time() if days_offset == 0 else datetime.time.min
        new_dt = datetime.datetime.combine(
            dt.date() + datetime.timedelta(days_offset),
            new_time
        )
        
        beginning_time, end_time = next_timespan.get_times(
            new_dt, self.solar_hours_manager[new_dt.date()]
        )
        if dt < beginning_time:
            return beginning_time
        return end_time
    
    def _current_or_next_timespan(self, dt=None):
        dt = set_dt(dt)
        current_rule = None
        i = 0
        while current_rule is None:
            current_rule = self.get_current_rule(
                dt.date()+datetime.timedelta(i)
            )
            if current_rule is None:
                i += 1
        new_time = dt.time() if i == 0 else datetime.time.min
        new_dt = datetime.datetime.combine(
            dt.date() + datetime.timedelta(i),
            new_time
        )
        
        for timespan in current_rule.time_selectors:
            beginning_time, end_time = timespan.get_times(
                new_dt.date(), self.solar_hours_manager[new_dt.date()]
            )
            if new_dt < end_time:
                return (i, timespan)
        
        return self._current_or_next_timespan(new_dt)
    
    def get_day_periods(self, dt=None):
        """Returns the opening periods of the given day.
        
        Parameters
        ----------
        dt : datetime.date
            The day for which to get the rule. None default,
            meaning use the present day.
        
        Returns
        -------
        list[humanized_opening_hours.TimeSpan]
            The timespans of the given day.
        """
        current_rule = self.get_current_rule(dt)
        if current_rule is None:
            return []
        return current_rule.time_selectors
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<OHParser field: '{}'>".format(self.sanitized_field)
