import re
import datetime
import pytz
import babel.dates
import gettext

from exceptions import (
    HOHError,
    SolarHoursNotSetError,
    InNextYear
)

from temporal_objects import (
    WEEKDAYS,
    MONTHS,
    MomentKind,
    Year,
    Week,
    SimilarDay,
    SimilarWeek,
    Day,
    Period,
    Moment,
    NextChange
)

from field_parser import parse_field
import validators

import sys as _sys
import os as _os
_os.chdir(_os.path.dirname(_os.path.realpath(__file__)))

class OHParser:
    def __init__(self, field, year=None):
        """
        A parser for the OSM opening_hours fields.
        
        >>> oh = hoh.OHParser("Th-Sa 10:00-19:00", pytz.timezone("UTC"))
        
        Parameters
        ----------
        field : str
            The opening_hours field.
        year : int, optional
            The year for which to parse the field.
            Current year default.
        
        Attributes
        ----------
        original_field : str
            The raw field given to the constructor.
        sanitized_field : str
            The field once sanitized by the "sanitize()" method.
        year : Year
            The Year object, containing all Months, Weeks,
            Days, Periods and Moments.
        tz : pytz.timezone
            The currently used timezone.
            Just change this attribute to set a new one.
        current_year : int
            The year used for the parsing.
        
        Raises
        ------
        NotImplementedError 
            When the field contains year or month indexing.
        humanized_opening_hours.exceptions.HOHError
            DoesNotExistError
                When a day does not exists ("Sl 10:00-19:00").
            ParseError
                When something goes wrong during the parsing.
        """
        self.original_field = field
        self.is_valid(self.original_field, raise_exception=True)
        # TODO : Improve.
        if not self.is_parsable(field):
            raise NotImplementedError("This field contains a rule which is not implemented yet.")
        self.sanitized_field = self.sanitize(self.original_field)
        self._splited_field = [part.strip() for part in self.sanitized_field.split(';')]
        year = year if year else datetime.datetime.now().year
        try:
            self.year = parse_field(self._splited_field, year)
        except HOHError:
            raise
        except Exception as e:  # Shouldn't happen.
            raise HOHError("An unexpected error has occured.")
        self.current_year = year
        self.needs_solar_hours_setting = any((
            "sunrise" in self.original_field,
            "sunset" in self.original_field,
            "dawn" in self.original_field,
            "dusk" in self.original_field,
        ))
        self.solar_hours_set = False
        return
    
    @staticmethod
    def is_valid(field, raise_exception=False):
        """Returns whether the field is valid.
        
        /!\ It won't check if periods are overlapping. To check this,
        try to parse the field and catch any PeriodsConflictError.
        
        The field is sanitized by the `sanitize()` method automatically.
        
        Parameters
        ----------
        str
            The field to check.
        raise_exception : bool
            Set to True to raise an exception instead of
            returning a boolean. False default.
        
        Returns
        -------
        bool
            True if the field is valid, False else.
        
        Raises
        ------
        humanized_opening_hours.exceptions.HOHError
            DoesNotExistError
                When a day does not exists ("Sl 10:00-19:00").
            ParseError
                When something goes wrong during the parsing.
        """
        field = OHParser.sanitize(field)
        try:
            validators.validate_field(field)
        except Exception as e:
            if raise_exception:
                raise e
            return False
        return True
    
    @staticmethod
    def is_parsable(field):
        """Returns whether the field is parsable.
        /!\ It does not care if it is valid.
        
        Parameters
        ----------
        str
            The field to check.
        
        Returns
        -------
        bool
            True if the field is parsable, False else.
        """
        # TODO : Improve.
        return not any((
            '[' in field,
            '"' in field,
            "||" in field,
            "year" in field,
        ))
    
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
            "open", "off", "closed"
        )
        splited_field = [part.strip() for part in field.split(';')]
        parts = []
        for part in splited_field:
            # Adds or removes spaces when necessary.
            # "Mo-Su 10:00-19:00;Sa off" => "Mo-Su 10:00-19:00; Sa off"
            part = re.sub("\s*(;)\s*", "\1 ", part)
            # " , " => ","
            part = re.sub(" ?, ?", ",", part)
            # Corrects the case errors.
            # "mo" => "Mo"
            for word in special_words:
                part = re.sub("(?i){}(?!\w+)".format(word), word, part)
            # Adds colons when necessary.
            # "0630" => "06:30"
            for moment in re.findall("[0-9]{4}", part):
                if "year" in part:
                    break
                part = part.replace(moment, moment[:2] + ':' + moment[2:])
            if re.match("[A-Z][a-z]{2} [0-9]{1,2} .+", part):
                part = re.sub("([A-Z][a-z]{2} [0-9]{1,2}) (.+)", "\1: \2", part)
            # Adds zeros when necessary.
            # "7:30" => "07:30"
            for moment in re.findall("( (?<![0-9-])[0-9]:[0-9]{2})", field):
                part = part.replace(moment, ' 0' + moment[1:])
            # Replaces "24" by "24/7".
            if part == "24":
                part = "24/7"
            parts.append(part)
        return '; '.join(parts)
    
    def set_PH(self, dates):
        """Defines a list of days as public holidays.
        
        To do the same thing with school holidays,
        see the "set_SH()" method.
        
        Parameters
        ----------
        list[datetime.datetimes / datetime.date]
            The list of days which are public holidays.
        
        Returns
        -------
        self
            The instance itself.
        """
        concerned_days = [self.year.get_day(dt=date) for date in dates]
        PH = self.year.PH_week
        for day in concerned_days:
            PH_day = PH.days[day.index]
            if PH_day.closed:
                day.periods = []
                day.closed = True
            else:
                day.periods = PH_day.periods
        return self
    
    def set_SH(self, dates):
        """Defines a list of days as school holidays.
        
        To do the same thing with public holidays,
        see the "set_PH()" method.
        
        Parameters
        ----------
        list[datetime.datetimes / datetime.date]
            The list of days which are school holidays.
        
        Returns
        -------
        self
            The instance itself.
        """
        concerned_days = [self.year.get_day(dt=date) for date in dates]
        PH = self.year.SH_week
        for day in concerned_days:
            PH_day = SH.days[day.index]
            if PH_day.closed:
                day.periods = []
                day.closed = True
            else:
                day.periods = SH_day.periods
        return self
    
    def set_year(self, year, default_holidays=True):
        """Defines a year to use for calculations.
        
        Parameters
        ----------
        int
            The year to use (4 digits).
        default_holidays : bool, optional
            Set holiday weeks as similar to the second week of July
            (the 27th, just a guess) if they are not explicitly defined
            in the field. They will be closed else. True default.
        
        Returns
        -------
        self
            The instance itself.
        """
        try:
            self.year = parse_field(self._splited_field, year, default_holidays=default_holidays)
        except HOHError:
            raise
        except Exception as e:  # Shouldn't happen.
            raise HOHError("An unexpected error has occured.")
        self.current_year = year
        return self
    
    def set_solar_hours(self, sunrise_sunset=(), dawn_dusk=()):
        """Defines solar hours.
        
        /!\ Unless the place is near the equator, this setting will only
        be valid for a short time.
        
        Parameters
        ----------
        sunrise_sunset : tuple of tuples of integers
            The sunrise and sunset hours. E.g. ((8, 12), (20, 3))
        dawn_dusk : tuple of tuples of integers
            The dawn and dusk hours. E.g. ((8, 1), (20, 10))
        
        Returns
        -------
        self
            The instance itself.
        """
        if not sunrise_sunset and not dawn_dusk:
            raise ValueError("You must set 'sunrise_sunset' or 'dawn_dusk' at least.")
        
        def tuple_to_time(t):
            return datetime.datetime(2000, 1, 1, t[0], t[1]).timetz()
        
        for day in self.year.all_days:
            for period in day.periods:
                if not period.is_variable():
                    continue
                for moment in (period.beginning, period.end):
                    if sunrise_sunset:
                        if moment.kind == MomentKind.SUNRISE:
                            moment._time = tuple_to_time(sunrise_sunset[0])
                        elif moment.kind == MomentKind.SUNSET:
                            moment._time = tuple_to_time(sunrise_sunset[1])
                    if dawn_dusk:
                        if moment.kind == MomentKind.DAWN:
                            moment._time = tuple_to_time(dawn_dusk[0])
                        elif moment.kind == MomentKind.DUSK:
                            moment._time = tuple_to_time(dawn_dusk[1])
        self.solar_hours_set = True
        return self
    
    def is_open(self, moment=None):
        """Is it open?
        
        Parameters
        ----------
        moment : datetime.datetime, optional
            The moment for which to check the opening. None default,
            meaning use the present time, at the timezone given
            to the constructor.
        
        Returns
        -------
        bool
            True if it's open, False else.
            /!\ Returns False if the concerned day contains an unset
            solar moment.
        """
        if not moment:
            moment = datetime.datetime.now().replace(tzinfo=pytz.UTC)
        elif moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
            moment = pytz.UTC.localize(moment)
        day = self.year.get_day(dt=moment)
        return day.is_open(moment)
    
    def next_change(self, moment=None):
        """Gets the next opening status change.
        
        Parameters
        ----------
        moment : datetime.datetime, optional
            The moment for which to check the opening. None default,
            meaning use the present time, at the timezone given
            to the constructor.
        
        Returns
        -------
        NextChange (collections.namedtuple)
            A namedtuple containing two attributes:
            - dt : datetime.datetime
                The datetime of the next change.
                None if it's always open.
            - moment : Moment
                The moment corresponding to the next change.
                None if it's always open.
        """
        if self.year.always_open:
            # TODO : Improve.
            next_change = NextChange(moment=None, dt=None)
            return next_change
        
        if not moment:
            moment = datetime.datetime.now().replace(tzinfo=pytz.UTC)
        else:
            moment = moment.replace(tzinfo=pytz.UTC)
        
        concerned_day = self.year.get_day(moment)
        # TODO : Optimize.
        initial_day_index = self.year.all_days.index(concerned_day)
        
        right_day = True
        if not concerned_day.opens_today():
            right_day = False
        try:
            if not concerned_day.last_open_hour().time() >= moment.timetz():
                right_day = False
        except AttributeError:  # If "NoneType has no attribute 'time'".
            right_day = False
        
        if not right_day:
            moment = datetime.datetime(2000, 1, 1, 0, tzinfo=pytz.UTC)
        
        concerned_day_index = 0
        while not right_day:
            concerned_day_index += 1
            try:
                concerned_day = self.year.all_days[initial_day_index + concerned_day_index]
                if concerned_day._contains_unknown_times():
                    raise SolarHoursNotSetError("At least one day contains unknown solar hours.")
                if not concerned_day.opens_today():
                    continue
                if concerned_day.last_open_hour().time() >= moment.timetz():
                    right_day = True
                    break
            except IndexError:
                raise InNextYear("The next change is in the next year. The support of such situation is not implemented yet.")
        
        if concerned_day.is_open(moment):
            for period in concerned_day.periods:
                if moment in period:
                    next_change = NextChange(moment=concerned_day.last_open_hour(), dt=datetime.datetime.combine(concerned_day.date, period.end.time()))
                    return next_change
            # Should not come here.
        
        for period in concerned_day.periods:
            # There is no need to check for end of periods as it's closed.
            if moment.timetz() <= period.beginning.time():
                next_change = NextChange(moment=moment, dt=datetime.datetime.combine(concerned_day.date, period.beginning.time()))
                return next_change
    
    def _get_now(self):
        # TODO : Use or remove.
        return datetime.datetime.now().replace(tzinfo=pytz.UTC)
    
    def holidays_status(self):
        """Returns the opening statuses of the holidays.
        
        Returns
        -------
        dict
            The opening statuses of the holidays.
            Shape : {"PH": bool, "SH": bool}
        """
        return {
            "PH": self.year.PH_week.opens_this_week(),
            "SH": self.year.SH_week.opens_this_week()
        }
    
    def render(self, *args, **kwargs):
        """Returns a HOHRenderer object. See its docstring for details."""
        return HOHRenderer(self, *args, **kwargs)
    
    def __repr__(self):
        return self.__str__()
    
    def __str__(self):
        return "<OHParser field: '{}'>".format(self.original_field)

class HOHRenderer:
    """
    A renderer for the OSM opening_hours fields.
    
    >>> hohr = hoh.HOHRenderer(oh_parser_instance)
    OR
    >>> hohr = oh_parser_instance.render()
    
    Parameters
    ----------
    ohparser : OHParser
        An instance of OHParser.
    universal : bool, optional
        Defines whether to print (e.g.) "sunrise" or "21:05".
        True default, meaning "sunrise".
    locale_name : str, optional
        The name of the locale to use. "en" default.
        See HOHRenderer.AVAILABLE_LOCALES to get a tuple of
        available locales.
    
    Attributes
    ----------
    ohparser : OHParser
        The OHParser object given to the constructor.
    universal : bool
        The universal state given to the constructor.
    always_open_str : str
        A translated string saying the place is always open.
    
    Raises
    ------
    ValueError
        When the given 'locale_name' is not available.
    """
    
    def __init__(self, ohparser, universal=True, locale_name="en"):
        self.ohparser = ohparser
        self.universal = universal
        if not locale_name:
            locale_name = "en"
        self.set_locale(locale_name)
        self.always_open_str = _("Open 24 hours a day and 7 days a week.")
        return
    
    @staticmethod
    def available_locales():
        """
        Returns a list of all suported languages.
        
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
            See HOHRenderer.AVAILABLE_LOCALES to get a tuple of
            available locales.
        
        Returns
        -------
        self
            The instance itself.
        """
        if locale_name not in self.available_locales():
            raise ValueError(
                "'locale_name' must be one of the locales given by the "
                "HOHRenderer`available_locales()` method."
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
            days.append(self.get_locale_day(i))
        for i in range(12):
            months.append(self.get_locale_month(i))
        return {"days": days, "months": months}
    
    def get_locale_day(self, index):
        """Returns a day name in the constructor's locale.
        
        Parameters
        ----------
        int
            The day's index, between 0 and 6.
        
        Returns
        -------
        str : The translated day's name.
        """
        return self.babel_locale.days["format"]["wide"][index]
    
    def get_locale_month(self, index):
        """Returns a month name in the constructor's locale.
        
        Parameters
        ----------
        int
            The month's index, between 0 and 11.
        
        Returns
        -------
        str : The translated month's name.
        """
        return self.babel_locale.months['format']['wide'][index+1]
    
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
    
    def humanized_time_before_next_change(self, moment=None, word=True):
        """Returns a human-readable string of the remaining time
        before the next opening status change.
        
        Parameters
        ----------
        moment : datetime.datetime, optional
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
        next_change = self.ohparser.next_change(moment=moment)
        if not moment:
            now = self.ohparser._get_now()
        now = moment
        delta = next_change.dt - now
        # TODO : Check granularity.
        return babel.dates.format_timedelta(
            delta,
            granularity="minute",
            threshold=2,
            locale=self.babel_locale,
            add_direction=word
        )
    
    def humanized_periods_of_day(self, day):
        """Returns a list of human-readable periods of a given day.
        
        Parameters
        ----------
        day : Day
            The day for which to render the periods.
        
        Returns
        -------
        list[str]
            The human-readable strings. The list will be empty if the
            day has no period.
        """
        
        def render_universal_moment(moment):
            if not moment._has_offset():
                string = {
                    MomentKind.SUNRISE: _("sunrise"),
                    MomentKind.SUNSET: _("sunset"),
                    MomentKind.DAWN: _("dawn"),
                    MomentKind.DUSK: _("dusk")
                }.get(moment.kind)
                if string:
                    return string
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
        
        periods = []
        for period in day.periods:
            if not period.is_variable():
                periods.append(str(period))
            else:
                if self.universal:
                    periods.append(
                        "{} - {}".format(
                            render_universal_moment(period.beginning),
                            render_universal_moment(period.end)
                        )
                    )
                else:
                    if self.ohparser.solar_hours_set:
                        periods.append(
                            "{} - {}".format(
                                period.beginning.time().strftime(_("%H:%M")),
                                period.end.time().strftime(_("%H:%M"))
                            )
                        )
                    else:
                        raise SolarHoursNotSetError("The solar hours are not set and need to.")
        return periods
    
    def humanized_periods_of_week(self, week_index):
        """Returns a list of about seven lists of human-readable periods
        of all the days of a week from its index.
        
        Parameters
        ----------
        int
            The index of the week, between 0 and 52 inclusive.
        
        Returns
        -------
        list[list[str]]
            The periods of the days of the week, as for
            the `humanized_periods_of_day()` method.
            A list may be empty if a day has no period.
        """
        week = list(self.ohparser.year.all_weeks())[week_index]
        week_periods = []
        for i, day in enumerate(week.days):
            week_periods.append(self.humanized_periods_of_day(day))
        return week_periods
    
    def humanized_holidays_status(self):
        holidays_status = self.ohparser.holidays_status()
        string = {
            (True, True): _("Open on public and school holidays."),
            (True, False): _("Open on public holidays. Closed on school holidays."),
            (False, True): _("Closed on public holidays. Open on school holidays."),
            (False, False): _("Closed on public and school holidays."),
        }.get((holidays_status["PH"], holidays_status["SH"]))
        return string
    
    def _holidays_description(self, similar_weeks, indent=0):
        PH_similar_week = SimilarWeek._from_week(self.ohparser.year.PH_week)
        SH_similar_week = SimilarWeek._from_week(self.ohparser.year.SH_week)
        weeks = {
            _("Public holidays:"): PH_similar_week,
            _("School holidays:"): SH_similar_week,
        }
        if len(set(weeks.values())) == 1:
            weeks = {_("Public and school holidays:"): PH_similar_week}
            if not list(weeks.values())[0].opens_this_week():
                return []
        for title, holiday in weeks.items():
            if holiday in similar_weeks:
                weeks[title] = None
        weeks = dict((k, v) for k, v in weeks.items() if v is not None)
        if not weeks:
            return []
        descriptions = []
        for title, holiday in weeks.items():
            if holiday.opens_this_week():
                description = self._week_description(holiday, indent=indent, display_week_range=False)
                descriptions.append(title + '\n' + description)
        return descriptions
    
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
    
    def humanized_exceptional_days(self):
        """Returns the description of the exceptional days.
        
        E.g. a field containing "Dec 25 off" will return
        "Closed on 25 december".
        
        Returns
        -------
        str
            The description.
        """
        similar_exceptional_days = []
        similar_exceptional_days.append(SimilarDay._from_day(self.ohparser.year.exceptional_days[0]))
        for day in self.ohparser.year.exceptional_days[1:]:
            temp_day = SimilarDay._from_day(day)
            new = True
            for sed in similar_exceptional_days:
                if temp_day == sed:
                    sed.dates.append(day.date)
                    new = False
                    break
            if new:
                similar_exceptional_days.append(temp_day)
        description = ''
        for i, sec in enumerate(similar_exceptional_days):
            if not sec.opens_today():
                formated_dates = [self._format_date(date) for date in sec.dates]
                title = self._join_list(formated_dates).capitalize()
                description += _("{left}: {right}").format(
                    left=title,
                    right=_("closed")
                ) + '\n'
                similar_exceptional_days.pop(i)
                break  # There should be only one closed SimilarDay.
        for sec in similar_exceptional_days:
            formated_dates = [self._format_date(date) for date in sec.dates]
            title = self._join_list(formated_dates).capitalize()
            schedules = self._join_list(self.humanized_periods_of_day(sec))
            description += _("{left}: {right}").format(
                left=title,
                right=schedules
            ) + '\n'
        return description.rstrip()
    
    def _week_description(self, week, indent=0, display_week_range=True):
        """Returns the description of a SimilarWeek.
        
        Parameters
        ----------
        SimilarWeek
            The week to describe.
        indent : int, optional
            The indentation of day periods. 0 default.
        
        Returns
        -------
        str
            The description.
        """
        days_periods = [self.humanized_periods_of_day(day) for day in week.days]
        days_descriptions = []
        for i, periods in enumerate(days_periods):
            name = self.get_locale_day(i)
            day_periods = self._join_list(periods)
            if not day_periods:
                day_periods = _("closed")
            days_descriptions.append(' '*indent + _("{left}: {right}").format(
                left=name.title(),
                right=day_periods
            ))
        # TODO : Improve.
        week_range = range(min(week.indexes), max(week.indexes)+1)
        if len(list(week_range)) == 1:
            str_week_range = str(week_range[0]+1)
            plural = False
        else:
            str_week_range = _("{range_start} - {range_end}").format(
                range_start=week_range.start+1,
                range_end=week_range.stop+1
            )
            plural = True
        if display_week_range:
            if not plural:
                description = _("Week {week_range}:").format(
                    week_range=str_week_range
                ) + '\n'
            else:
                description = _("Weeks {week_range}:").format(
                    week_range=str_week_range
                ) + '\n'
        else:
            description = ''
        if week.opens_this_week():
            description += '\n'.join(days_descriptions)
        else:
            description += ' ' + _("closed")
        return description
    
    def description(self, holidays=True, indent=0, week_range=True, exceptional_days=True):
        """Returns a full description of the opening hours.
        
        Parameters
        ----------
        holidays : bool, optional
            Defines whether the holidays must be described with the
            `humanized_holidays_status()` method.
        indent : int, optional
            The indentation of day periods. 0 default.
        week_range : bool, optional
            Defines whether the week range must be indicated.
            True default.
        exceptional_days : bool, optional
            Defines whether the exceptional days (e.g. "Dec 25 off")
            must be described. True default.
        
        Returns
        -------
        str
            The description.
        """
        if self.ohparser.year.always_open:
            description = self.always_open_str
            if exceptional_days and self.ohparser.year.exceptional_days:
                description += '\n\n' + self.humanized_exceptional_days()
            if holidays:
                description += '\n\n' + self.humanized_holidays_status()
            return description
        similar_weeks = self.ohparser.year.similar_weeks()
        if len(similar_weeks) == 1:
            display_week_range = week_range
        else:
            display_week_range = True
        holidays_descriptions = []
        descriptions = []
        for week in similar_weeks:
            descriptions.append(self._week_description(week, indent=indent, display_week_range=display_week_range))
        if holidays:
            holidays_descriptions = self._holidays_description(similar_weeks, indent=indent)
            descriptions.extend(holidays_descriptions)
        description = '\n\n'.join(descriptions)
        if exceptional_days and self.ohparser.year.exceptional_days:
            description += '\n\n' + self.humanized_exceptional_days()
        if holidays and not holidays_descriptions:
            description += '\n\n' + self.humanized_holidays_status()
        return description
    
    def __repr__(self):
        return self.__str__()
    
    def __str__(self):
        return "<HOHRenderer>"
