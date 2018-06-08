import os
import re
import datetime
import warnings

import lark
import babel.dates

from humanized_opening_hours.temporal_objects import WEEKDAYS, MONTHS
from humanized_opening_hours.field_parser import (
    PARSER, LOCALES, MainTransformer, DescriptionTransformer
)
from humanized_opening_hours.exceptions import ParseError


BASE_DIR = os.path.dirname(os.path.realpath(__file__))


class OHParser:
    def __init__(self, field, locale="en"):
        """A parser for the OSM opening_hours fields.
        
        >>> oh = hoh.OHParser("Mo-Fr 10:00-19:00")
        
        Parameters
        ----------
        field : str
            The opening_hours field.
        locale : str, optional
            The locale to use. "en" default.
        
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
        solar_hours : dict{str: datetime.time}
            A dict containing hours of sunrise, sunset, dawn and dusk.
            Empty default, you have to fill it yourself with
            **not** localized datetime.time objects.
        
        Raises
        ------
        humanized_opening_hours.ParseError
            When something goes wrong during the parsing
            (e.g. the field is invalid or contains an unsupported pattern).
        humanized_opening_hours.SpanOverMidnight
            When a field has a period which spans over midnight
            (for example: "Mo-Fr 20:00-02:00"), which is not yet supported.
        """
        self.original_field = field
        self.sanitized_field = self.sanitize(self.original_field)
        
        try:
            self._tree = PARSER.parse(self.sanitized_field)
            self.rules = MainTransformer().transform(self._tree)
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
        self.solar_hours = {
            "sunrise": None, "sunset": None,
            "dawn": None, "dusk": None
        }
    
    @staticmethod
    def get_solar_hours(lat, lon, dt=None, tz="UTC"):
        """Returns a dict containing hours of sunrise, sunset, dawn and dusk.
        
        Requires the 'astral' module. Sets values to None (like default)
        in case of error.
        
        Parameters
        ----------
        float
            The latitude of the location.
        float
            The longitude of the location.
        datetime.date, optional
            The date for which to get solar hours.
            None default, meaning use the present day.
        str, optional
            The timezone name of the location. "UTC" default.
        
        Returns
        -------
        solar_hours : dict{str: datetime.time}
            A dict containing hours of sunrise, sunset, dawn and dusk
            (or None in case of error).
        
        Raises
        ------
        ImportError
            If the 'astral' module is not available.
        """
        if not dt:
            dt = datetime.date.now()
        import astral
        loc = astral.Location(["Location", "Region", lat, lon, tz, 0])
        solar_hours = {
            "sunrise": None, "sunset": None,
            "dawn": None, "dusk": None
        }
        for event in solar_hours:
            try:
                solar_hours[event] = (
                    getattr(loc, event)(dt)
                    .time().replace(tzinfo=None)
                )
            except astral.AstralError:
                solar_hours[event] = None
        return solar_hours
    
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
            # Adds colons and removes 'h' when necessary.
            # "0630" => "06:30"
            for moment in re.findall("[0-9]{4}", part):
                if "year" in part:
                    break
                part = part.replace(moment, moment[:2] + ':' + moment[2:])
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
        if not dt:
            dt = datetime.datetime.now()
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
        if not dt:
            dt = datetime.datetime.now()
        for rule in self.rules:
            if rule.range_selectors.is_included(
                dt.date(), self.SH_dates, self.PH_dates
            ):
                return rule.get_status_at(dt, self.solar_hours)
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
        if not dt:
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
        if not dt:
            dt = datetime.datetime.now()
        days_offset, next_timespan = self._current_or_next_timespan(dt)
        
        new_time = dt.time() if days_offset == 0 else datetime.time.min
        new_dt = datetime.datetime.combine(
            dt.date() + datetime.timedelta(days_offset),
            new_time
        )
        
        beginning_time, end_time = next_timespan.get_times(
            new_dt, self.solar_hours
        )
        if dt < beginning_time:
            return beginning_time
        return end_time
    
    def _current_or_next_timespan(self, dt=None, _look_further=True):
        if not dt:
            dt = datetime.datetime.now()
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
                new_dt.date(), self.solar_hours
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
        if not dt:
            dt = datetime.date.today()
        current_rule = self.get_current_rule(dt)
        if current_rule is None:
            return []
        return current_rule.time_selectors
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<OHParser field: '{}'>".format(self.sanitized_field)
