import datetime
import gettext
from collections import namedtuple
import re

import pytz
import babel.dates
import lark

from humanized_opening_hours.exceptions import (
    ParseError,
    SolarHoursNotSetError
)
from humanized_opening_hours.temporal_objects import (
    WEEKDAYS,
    MONTHS,
    MomentKind,
    Day
)
from humanized_opening_hours.utils import (
    days_of_week_from_day, days_from_week_number
)
from humanized_opening_hours import field_parser


def render_field(field, **kwargs):
    """
        Returns an OHRenderer object directly from a field.
        In addition to the field, it can take all the arguments
        of the __init__ method of OHRenderer.
    """
    return OHParser(field).render(**kwargs)


class OHParser:
    def __init__(self, field):
        """A parser for the OSM opening_hours fields.
        
        >>> oh = hoh.OHParser("Th-Sa 10:00-19:00")
        
        Parameters
        ----------
        field : str
            The opening_hours field.
        
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
            datetime.time objects.
        
        Raises
        ------
        humanized_opening_hours.exceptions.ParseError
            When something goes wrong during the parsing
            (e.g. the field is invalid or contains an unsupported pattern).
        """
        self.original_field = field
        self.sanitized_field = self.sanitize(self.original_field)
        try:
            self._tree = field_parser.parse_field(self.sanitized_field)
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
    
    def _get_solar_hour(self, key):
        """Returns a solar hour from a key, or raises an exception.
        
        Parameters
        ----------
        key : str
            The name of the solar moment to get.
        
        Returns
        -------
        datetime.time
            The time of the solar moment.
        
        Raises
        ------
        humanized_opening_hours.exceptions.SolarHoursNotSetError
            When the requested solar hour is not set.
        """
        if key not in self.solar_hours.keys():
            raise KeyError("The solar hour {key!r} does not exist.".format(key))
        hour = self.solar_hours.get(key)
        if hour:
            return hour
        raise SolarHoursNotSetError(
            "The {key!r} solar hour is not set.".format(key=key)
        )
    
    def get_day(self, dt):
        """Returns a Day object from a datetime.date(time)? object.
        
        Parameters
        ----------
        dt : datetime.date / datetime.datetime
            The date of the day to get.
        
        Returns
        -------
        Day
            The requested day.
        """
        is_PH, is_SH = False, False
        if dt in self.PH_dates:
            is_PH = True
        elif dt in self.SH_dates:
            is_SH = True
        if isinstance(dt, datetime.date):
            dt = datetime.datetime.combine(dt, datetime.time())
        d = Day(dt)
        d.periods = self._tree.get_periods_of_day(dt, is_PH=is_PH, is_SH=is_SH)
        d._set_solar_hours(self.solar_hours)
        if is_PH:
            d.is_PH = True
        elif is_SH:
            d.is_SH = True
        return d
    
    def _get_now(self):
        """Returns a datetime.datetime object localized on UTC timzone."""
        return datetime.datetime.now().replace(tzinfo=pytz.UTC)
    
    def is_open(self, dt=None):
        """Is it open?
        
        Parameters
        ----------
        moment : datetime.datetime, optional
            The moment for which to check the opening. None default,
            meaning use the present time.
        
        Returns
        -------
        bool
            True if it's open, False else.
        
        Raises
        ------
        humanized_opening_hours.exceptions.ParseError
            When something goes wrong during the parsing
            (e.g. the field is invalid).
        """
        if not dt:
            dt = datetime.datetime.now().replace(tzinfo=pytz.UTC)
        elif dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            dt = pytz.UTC.localize(dt)
        day = self.get_day(dt=dt)
        return day.is_open(dt)
    
    def next_change(self, moment=None, allow_recursion=False):
        """Gets the next opening status change.
        
        Parameters
        ----------
        moment : datetime.datetime, optional
            The moment for which to check the opening. None default,
            meaning use the present time.
        allow_recursion : bool, optional
            Allows to use recursion to get the true next change if it
            is in another day. It may cause 'RecusionError' with "24/7"
            fields. False default, meaning return the first period ending.
        
        Returns
        -------
        datetime.datetime
            The datetime of the next change.
        """
        # TODO : Handle the cases where it's always / never open.
        if not moment:
            moment = datetime.datetime.now().replace(tzinfo=pytz.UTC)
        elif moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
            moment = pytz.UTC.localize(moment)
        initial_day = self.get_day(dt=moment)
        right_day = False
        if initial_day.opens_today():
            if initial_day.periods[-1].end.time() >= moment.timetz():
                right_day = True
        
        def get_moment_in_right_day(day, moment, days_offset=0, allow_recursion=False, in_recursion=False):  # noqa
            if allow_recursion and in_recursion:
                output_moment = (
                    datetime.datetime.combine(
                        day.date, day.periods[0].end.time()
                    ) + datetime.timedelta(days=days_offset)
                )
                return output_moment
            if day.is_open(moment):
                if (
                    moment == day.periods[0].beginning.time() and
                    not allow_recursion
                ):
                    output_moment = (
                        datetime.datetime.combine(
                            day.date, day.periods[0].beginning.time()
                        )
                    )
                    return output_moment
                for period in day.periods:
                    if moment in period:
                        # "-24:00"
                        if period.end.time() == datetime.time.max.replace(tzinfo=pytz.UTC) and allow_recursion:  # noqa
                            tomorrow = self.get_day(
                                day.date+datetime.timedelta(days=1)
                            )
                            days_offset += 1
                            return get_moment_in_right_day(
                                tomorrow, datetime.time.min,
                                days_offset, allow_recursion=True,
                                in_recursion=True
                            )
                        output_moment = (
                            datetime.datetime.combine(
                                day.date, period.end.time()
                            )
                        )
                        return output_moment
                # Should not come here.
            for period in day.periods:
                # There is no need to check for end of periods as it's closed.
                if moment.timetz() <= period.beginning.time():
                    output_moment = (
                        datetime.datetime.combine(
                            day.date,
                            period.beginning.time()
                        ) + datetime.timedelta(days=days_offset)
                    )
                    return output_moment
            # Should not come here.
        
        if right_day:
            return get_moment_in_right_day(
                initial_day, moment, allow_recursion=allow_recursion
            )
        days_offset = 0
        while not right_day:
            days_offset += 1
            current_day = self.get_day(
                initial_day.date+datetime.timedelta(days=days_offset)
            )
            if current_day.opens_today():
                if current_day.periods[-1].end.time() >= datetime.time(0, 0, tzinfo=pytz.UTC):  # noqa
                    right_day = True
        return get_moment_in_right_day(
            current_day,
            datetime.time(0, 0, tzinfo=pytz.UTC),
            days_offset=days_offset,
            allow_recursion=allow_recursion
        )
    
    def holidays_status(self):
        """Returns the opening statuses of the holidays.
        
        Returns
        -------
        dict
            The opening statuses of the holidays (None if undefined).
            Shape : {"PH": bool/None, "SH": bool/None}
        """
        # TODO : Use an "opens_this_week()" method or something?
        return self._tree.holidays_status
    
    def render(self, *args, **kwargs):
        """Returns an OHRenderer object. See its docstring for details."""
        return OHRenderer(self, *args, **kwargs)
    
    def __getitem__(self, val):
        """Allows to get Day object(s) with slicing. Takes datetime.date objects.
        
        >>> oh[datetime.date.today()]
        '<Day 'Mo' (2 periods)>'
        
        >>> oh[datetime.date(2018, 1, 1):datetime.date(2018, 1, 3)]
        [
            '<Day 'Mo' (2 periods)>',
            '<Day 'Tu' (2 periods)>',
            '<Day 'We' (2 periods)>'
        ]
        
        Also supports stepping with `oh[start:stop:step]` (as int).
        """
        if type(val) is datetime.date:
            return self.get_day(val)
        # Type checking
        if val.start is not None or val.stop is not None:
            if (
                type(val.start) is not datetime.date or
                type(val.stop) is not datetime.date
            ):
                return NotImplemented
        if val.step is not None and type(val.step) is not int:
            return NotImplemented
        
        step = val.step if val.step is not None else 1
        ordinals = range(val.start.toordinal(), val.stop.toordinal()+1, step)
        return [self.get_day(datetime.date.fromordinal(o)) for o in ordinals]
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<OHParser field: '{}'>".format(self.sanitized_field)


RenderableDay = namedtuple("RenderableDay", ["name", "description", "dt"])
RenderableDay.__doc__ = """A namedtuple containing three attributes:
- name (str): the name of the day (e.g. "Monday");
- description (str): the description of the periods of the day;
- dt (datetime.date): the date of the day."""


class OHRenderer:
    """A renderer for the OSM opening_hours fields.
    
    >>> ohr = hoh.OHRenderer(oh_parser_instance)
    OR
    >>> ohr = oh_parser_instance.render()
    
    Parameters
    ----------
    ohparser : OHParser
        An instance of OHParser.
    universal : bool, optional
        Defines whether to print (e.g.) "sunrise" or "21:05".
        True default, meaning "sunrise".
    locale_name : str, optional
        The name of the locale to use. "en" default.
        See OHRenderer.available_locales() to get the
        available locales.
    
    Attributes
    ----------
    ohparser : OHParser
        The OHParser object given to the constructor.
    universal : bool
        The universal state given to the constructor.
    
    Raises
    ------
    ValueError
        When the requested "locale_name" is not available.
    """
    def __init__(self, ohparser, universal=True, locale_name="en"):
        self.ohparser = ohparser
        self.universal = universal
        if not locale_name:
            locale_name = "en"
        self.set_locale(locale_name)
    
    @staticmethod
    def available_locales():
        """Returns a list of all suported languages.
        
        Returns
        -------
        list[str]
            The list of all suported languages.
        """
        locales = gettext.find("HOH", "locales/", all=True)
        locales = [l.split('/')[-3] for l in locales]
        locales.append("en")
        return locales
    
    def set_locale(self, locale_name):
        """Sets a new locale to the renderer.
        
        Parameters
        ----------
        locale_name : str
            The locale name. E.g. "en".
            See OHRenderer.available_locales() (static method) to get
            a list of available locales.
        
        Returns
        -------
        self
            The instance itself.
        """
        if locale_name not in OHRenderer.available_locales():
            raise ValueError(
                "'locale_name' must be one of the locales given by the "
                "OHRenderer`available_locales()` method."
            )
        self.locale_name = locale_name
        self.babel_locale = babel.Locale.parse(locale_name)
        lang = self.babel_locale.language
        gettext.install("HOH", "locales/")
        i18n_lang = gettext.translation(
            "HOH", localedir="locales/",
            languages=[lang],
            fallback=True
        )
        i18n_lang.install()
        return self
    
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
    
    def _format_date(self, date):
        """Formats a datetime with the appropriate locale.
        
        Parameters
        ----------
        date : datetime.date
            The date to format.
        
        Returns
        -------
        str
            The formatted date.
        """
        # Gets the locale pattern.
        pattern = babel.dates.get_date_format(format="long").pattern
        # Removes the year.
        pattern = pattern.replace('y', ' ').replace('  ', '')
        return babel.dates.format_date(
            date,
            locale=self.babel_locale,
            format=pattern
        )
    
    def time_before_next_change(self, moment=None, allow_recursion=False, word=True):  # noqa
        """Returns a human-readable string of the remaining time
        before the next opening status change.
        
        Parameters
        ----------
        moment : datetime.datetime, optional
            The moment for which to check the opening. None default,
            meaning use the present time. Same as for the
            `next_change()` method of OHParser.
        allow_recursion : bool, optional
            Allows to use recursion to get the true next change if it
            is in another day. It may cause 'RecusionError' with "24/7"
            fields. False default, meaning return the first period ending.
        word : bool, optional
            Defines whether to add a descriptive word before the delay.
            For example: "in X minutes" if True, "X minutes" if False.
            True default.
        
        Returns
        -------
        str : The descriptive string (not capitalized at the beginning).
            For example: "in 15 minutes" (en) or "dans 2 jours" (fr).
        """
        next_change = self.ohparser.next_change(moment=moment)
        if not moment:
            moment = self.ohparser._get_now()
        delta = next_change - moment
        # TODO : Check granularity.
        return babel.dates.format_timedelta(
            delta,
            granularity="minute",
            threshold=2,
            locale=self.babel_locale,
            add_direction=word
        )
    
    def _join_list(self, l):
        """Returns a string from a list.
        
        Parameters
        ----------
        list
            The list to join.
        
        Returns
        -------
        str
            The joined list.
        """
        
        if not l:
            return ''
        values = [str(value) for value in l]
        if len(values) == 1:
            return values[0]
        return ', '.join(values[:-1]) + _(" and ") + values[-1]
    
    def _render_universal_moment(self, moment):
        if not moment._has_offset():
            string = {
                MomentKind.SUNRISE: _("sunrise"),
                MomentKind.SUNSET: _("sunset"),
                MomentKind.DAWN: _("dawn"),
                MomentKind.DUSK: _("dusk")
            }.get(moment.kind)
            if string:
                return string
            elif moment._time == datetime.time.max:
                # TODO : Relevant?
                return _("%H:%M").replace('%H', '00').replace('%M', '00')
            else:
                return moment.time().strftime(_("%H:%M"))
        else:
            if moment._delta.days == 0:
                string = {
                    MomentKind.SUNRISE: _("{} after sunrise"),
                    MomentKind.SUNSET: _("{} after sunset"),
                    MomentKind.DAWN: _("{} after dawn"),
                    MomentKind.DUSK: _("{} after dusk")
                }.get(moment.kind)
            else:
                string = {
                    MomentKind.SUNRISE: _("{} before sunrise"),
                    MomentKind.SUNSET: _("{} before sunset"),
                    MomentKind.DAWN: _("{} before dawn"),
                    MomentKind.DUSK: _("{} before dusk")
                }.get(moment.kind)
            delta = (
                datetime.datetime(2000, 1, 1, 0) +
                moment._delta
            ).time().strftime(_("%H:%M"))
        return string.format(delta)
    
    def periods_of_day(self, day):
        """Returns a description of the opening periods of a day.
        
        Parameters
        ----------
        day : datetime.date
            The day for which to get the periods description.
        
        Returns
        -------
        RenderableDay (collections.namedtuple)
            A namedtuple containing two strings:
            - "name": the name of the day (e.g. "Monday");
            - "description": the description of the periods of the day.
        """
        d = self.ohparser.get_day(day)
        rendered_periods = []
        for period in d.periods:
            rendered_periods.append(
                "{} - {}".format(
                    self._render_universal_moment(period.beginning),
                    self._render_universal_moment(period.end)
                )
            )
        rendered_periods = self._join_list(rendered_periods)
        name = self.get_locale_day(day.weekday())
        return RenderableDay(name=name, description=rendered_periods, dt=d.date)
    
    def plaintext_week_description(self, obj=None):
        """Returns a plaintext descriptions of the schedules of a week.
        
        Parameters
        ----------
        datetime.date / list[datetime.date] : optional
            A day in the week to render, or a list of the week days
            to render. May be None to mean "the current week".
        
        Returns
        -------
        str
            The plaintext schedules of the week. Contains 7 lines,
            or as many lines as in the given list.
        """
        if not obj:
            obj = datetime.date.today()
        if type(obj) is not list:
            obj = days_of_week_from_day(obj)
        output = ''
        for day in obj:
            d = self.periods_of_day(day)
            description = d.description if d.description else _("closed")
            output += _("{name}: {periods}").format(
                name=d.name,
                periods=description
            ) + '\n'
        return output.rstrip()
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return "<OHRenderer>"
