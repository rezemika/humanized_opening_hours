# -*- coding: utf-8 -*-
#
#  A parser for the opening_hours fields from OpenStreetMap.
#  
#  Published under the AGPLv3 license by rezemika.
#  

"""
    A parser for the opening_hours fields from OpenStreetMap.
    
    Provides Day objects, containing (among others) datetime.time objects
    representing the beginning and the end of all the opening periods.
    Can handle solar hours with "sunrise" or "sunset", including with
    offset like "(sunrise+02:00)".
    
    Sanitizes the fields to prevent some common mistakes.
    
    ```python
    >>> import humanized_opening_hours
    
    >>> field = "Mo-Fr 06:00-21:00; Sa,Su 07:00-21:00"
    >>> hoh = humanized_opening_hours.HumanizedOpeningHours(field)
    >>> hoh.is_open()
    True
    
    >>> hoh.next_change()
    datetime.datetime(2017, 12, 24, 21, 0)
    
    >>> print(hoh.stringify_week_schedules())
    Monday: 06:00 - 21:00
    Tuesday: 06:00 - 21:00
    Wednesday: 06:00 - 21:00
    Thursday: 06:00 - 21:00
    Friday: 06:00 - 21:00
    Saturday: 07:00 - 21:00
    Sunday: 07:00 - 21:00
    ```
"""

import os
import re
import json
import datetime
import pytz
import astral
import locale

__all__ = ["HumanizedOpeningHours"]

# HOH Exceptions

class HOHError(Exception):
    """
        Base class for HOH errors.
    """
    pass

class DoesNotExistError(HOHError):
    """
        Raised when something in the field does not exist (e.g. a wrong day).
    """
    pass

class NotParsedError(HOHError):
    """
        Raised when trying to get something which has not been parsed.
    """
    pass

class PeriodsConflictError(HOHError):
    """
        Raised when trying to add a period which covers another.
    """
    pass

# Translation

class HOHTranslate():
    
    def __init__(self, lang, langs_dir):
        """
            A translater for HumanizedOpeningHours.
        """
        if not langs_dir:
            filename = os.path.join(
                os.path.dirname(__file__),
                "hoh_{}.json".format(lang)
            )
        else:
            filename = "{}/hoh_{}.json".format(langs_dir, lang)
        with open(filename, 'r', encoding='utf-8') as lang_file:
            self.f = json.load(lang_file)
    
    def sentence(self, s):
        """
            Translate a sentence.
        """
        return self.f["sentences"].get(s)
    
    def word(self, word):
        """
            Translate a regular word.
        """
        return self.f["words"].get(word)
    
    def month(self, index):
        """
            Return a month name from his index.
            (0 : January - 11 : December)
        """
        return self.f["months"][index]
    
    def weekday(self, index):
        """
            Return a weekday name from his index.
            (0 : Monday - 6 : Sunday)
        """
        return self.f["weekdays"][index]

# Meta-classes

class Day:
    def __init__(self, index):
        """
            A regular Day object, containing opening periods.
            
            Parameters
            ----------
            index : str
                The OSM-like day or a special day (Mo, Tu, PH, SH...).
        """
        self.index = index
        if index in ["PH", "SH"]:
            self.name = index
        else:
            self.name = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")[index]
        self.periods = []
        self.closed = False
        return
    
    def opens_today(self):
        """
            Returns True if there is a period for this day. False else.
        """
        return len(self.periods) > 0
    
    def has_same_periods(self, day):
        """
            Returns True if the given Day object has the same
            opening periods (i.e. they are similars).
        """
        return self.periods == day.periods
    
    def set_closed(self):
        self.closed = True
        self.periods = []
        return
    
    def total_duration(self):
        """
            Returns a datetime.timedelta object, representing
            the duration of all the opening periods of the day.
            Raises a NotParsedError when solar hours have not
            been parsed.
        """
        td = datetime.timedelta()
        for period in self.periods:
            new_td = period.duration()
            if new_td is None:
                raise NotParsedError("Solar hours have not been parsed and need to.")
            else:
                td += new_td
        return td
    
    def add_period_from_field(self, field, tz):
        """
            Adds a period to the Day from an OSM-like period
            (e.g. 12:30-19:00). Supports sunrises and sunsets,
            with or without offset.
        """
        # Prevents bugs for "(sunrise-02:00)".
        moments = re.split("-(?![^\(]*\))", field)
        m1, m2 = moments[0], moments[1]
        if re.match("[0-9][0-9]:[0-9][0-9]", m1):
            m1 = datetime.datetime.strptime(m1, "%H:%M").time().replace(tzinfo=tz)
            m1 = Moment("normal", m1)
        elif m1 == "sunrise":
            m1 = Moment("sunrise")
        elif m1 == "sunset":
            m1 = Moment("sunset")
        else:
            result = re.search("\((sunrise|sunset)(\+|-)([0-9][0-9]:[0-9][0-9])\)", m1)
            moment_type, sign, differential = result.group(1), result.group(2), result.group(3)
            hours = int(differential.split(':')[0])
            minutes = int(differential.split(':')[1])
            if sign == '-':
                hours *= -1
                minutes *= -1
            timedelta = datetime.timedelta(hours=hours, minutes=minutes)
            m1 = Moment(moment_type, timedelta=timedelta)
        if re.match("[0-9][0-9]:[0-9][0-9]", m2):
            m2 = datetime.datetime.strptime(m2, "%H:%M").time().replace(tzinfo=tz)
            m2 = Moment("normal", m2)
        elif m2 == "sunrise":
            m2 = Moment("sunrise")
        elif m2 == "sunset":
            m2 = Moment("sunset")
        else:
            result = re.search("\((sunrise|sunset)(\+|-)([0-9][0-9]:[0-9][0-9])\)", m2)
            moment_type, sign, differential = result.group(1), result.group(2), result.group(3)
            hours = int(differential.split(':')[0])
            minutes = int(differential.split(':')[1])
            if sign == '-':
                hours *= -1
                minutes *= -1
            timedelta = datetime.timedelta(hours=hours, minutes=minutes)
            m2 = Moment(moment_type, timedelta=timedelta)
        # Sanity precaution.
        for period in self.periods:
            if m1 in period or m2 in period:
                raise PeriodsConflictError(
                    "The period '{field}' is in conflict with this one: "
                    "'{period}' in the day '{day}'.".format(
                        field=field, period=period, day=self.name
                    )
                )
        self.periods.append(Period(m1, m2))
        return
    
    def _set_solar_hours(self, sunrise_time, sunset_time):
        """
            Sets sunrise and sunset hours for each Moment of each Period
            of the day from their datetime.time representation.
        """
        for period in self.periods:
            for moment in [period.m1, period.m2]:
                if moment.type == "sunrise":
                    moment.time_object = sunrise_time
                elif moment.type == "sunset":
                    moment.time_object = sunset_time
        return
    
    def __str__(self):
        return "<'{}' Day object ({} periods)>".format(self.name, len(self.periods))
    
    def __repr__(self):
        return self.__str__()

class Period:
    def __init__(self, m1, m2):
        """
            A regular Period object, containing two Moments objects
            (a beginning and an end).
            
            Parameters
            ----------
            m1 : Moment object
                The beginning of the period.
            m2 : Moment object
                The end of the period.
        """
        self.m1 = m1
        self.m2 = m2
        return
    
    def duration(self):
        """
            Returns a datetime.timedelta object, representing
            the duration of the period. Returns None when solar
            hours have not been parsed.
        """
        if not self.m1.time() or not self.m2.time():
            return
        dummydate = datetime.date(2000, 1, 1)
        dt1 = datetime.datetime.combine(dummydate, self.m1.time())
        dt2 = datetime.datetime.combine(dummydate, self.m2.time())
        return dt2 - dt1
    
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
        """
            Returns True if the given datetime.time object is between
            the beginning and the end of the period. Returns False else.
            Returns None if solar hours have not been parsed.
        """
        if not self.m1.time() or not self.m2.time():
            return
        return self.m1.time() <= moment <= self.m2.time()
    
    def __str__(self):
        return "{} - {}".format(str(self.m1), str(self.m2))
    
    def __repr__(self):
        return "<Period from {} to {}>".format(str(self.m1), str(self.m2))

class Moment:
    def __init__(self, moment_type, time_object=None, timedelta=None):
        """
            A moment in time, which can be fixed or variable, if based
            on sunrise or sunset. Defined either with a time_object
            either with a 'sunrise' or 'sunset' type and a timedelta
            relative to the sunrise or the sunset.
            
            Parameters
            ----------
            moment_type : str
                The type of the moment, which can be "normal", "sunrise"
                or "sunset".
            time_object : datetime.time object, optional
                The moment itself, required only if 'moment_type'
                is "normal".
            timedelta : datetime.timedelta, optional
                The timedelta relative to the sunrise or the sunset,
                required only if 'moment_type' is not "normal".
        """
        if moment_type not in ["normal", "sunrise", "sunset"]:
            raise ValueError("The type must be 'normal', 'sunrise' or 'sunset'.")
        if moment_type == "normal" and time_object is None:
            raise ValueError("The 'time_object' argument must be given when type is 'normal'.")
        if moment_type == "normal" and timedelta is not None:
            raise ValueError("The 'timedelta' argument musn't be given when type is 'normal'.")
        self.type = moment_type
        self.time_object = time_object
        if not timedelta:
            self.timedelta = datetime.timedelta()
        else:
            self.timedelta = timedelta
        return
    
    def is_variable(self):
        return self.type in ["sunrise", "sunset"]
    
    def time(self):
        if self.time_object:
            return (
                (datetime.datetime.combine(datetime.date.today(), self.time_object) +
                self.timedelta).time().replace(tzinfo=self.time_object.tzinfo)
            )
        else:
            return
    
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
        if self.type == "normal" or self.time():
            return "<{} {}>".format(self.type, self.time().strftime("%H:%M"))
        else:
            return "<{} : timedelta {}s>".format(self.type, self.timedelta.seconds)

# Main class

class HumanizedOpeningHours:
    def __init__(self, field, lang="en", langs_dir=None, tz=pytz.timezone("UTC")):
        """
            A parser for the OSM opening_hours field.
            
            >>> hoh = HumanizedOpeningHours("Th-Sa 10:00-19:00", "en", pytz.timezone("UTC"))
            
            Parameters
            ----------
            field : str
                The opening_hours field.
            lang : str
                The destination language, following the ISO 639-1
                standard (the appropriate JSON file must exist).
            langs_dir : str, optionnal
                The directory where the translation json files are
                (without final slash). Module's directory default.
                Allows to use another language or custom sentences.
            tz : pytz.timezone object, optionnal
                The timezone to use (UTC default).
        """
        # Checks the field can be parsed.
        if "dawn" in field or "dusk" in field:
            raise NotImplementedError(
                "The support of 'dawn' and 'dusk' is not yet implemented."
            )
        if re.search("\[-?[\:\d-]+\]", field):
            raise NotImplementedError(
                "The support of rank in months is not yet implemented."
            )
        if "week" in field:
            raise NotImplementedError(
                "The support of specific weeks in year is not yet implemented."
            )
        # Static variables.
        self.days = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")
        self.months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        # Get parameters.
        self._t = HOHTranslate(lang, langs_dir)
        self.lang = lang
        locale.setlocale(locale.LC_TIME, (self.lang, "UTF-8"))
        self.tz = tz
        self.field = self.sanitize(field)
        # Prepares the parsing of the field.
        self._split_field = list(map(str.strip, self.field.split(";")))
        self._opening_periods = []
        self.always_open = "24/7" in self._split_field
        self.need_solar_hours_parsing = (
            "sunrise" in self.field or
            "sunset" in self.field
        )
        self._solar_hours_parsed = False
        self.exceptional_closed_days = []
        # Handles the "24/7" specificity.
        if "24/7" in self.field:
            self.always_open = True
        else:
            self.always_open = False
        # Creates a list of the days.
        for i in range(0, 7):
            self._opening_periods.append(Day(i))
        # Handles closed days.
        self.PH = Day("PH")
        self.SH = Day("SH")
        if "PH off" in self._split_field:
            self.PH.set_closed()
            self._split_field.remove("PH off")
        if "SH off" in self._split_field:
            self.SH.set_closed()
            self._split_field.remove("SH off")
        # Parses the field.
        for part in self._split_field:
            # We off
            # Su,Sa off
            # PH,SH off
            if re.match("\w+[,\w+]* off", part):
                days = re.findall("(\w+[,\w+]*) off", part)[0]
                for day in map(str.title, days.split(',')):
                    if day not in self.days:
                        if day == "SH":
                            self.SH.set_closed()
                        elif day == "PH":
                            self.PH.set_closed()
                        else:
                            raise DoesNotExistError(
                                "Field error: the day '{}' does not exists."
                                .format(day)
                            )
                    else:
                        self[day].set_closed()
            # Dec 25 off
            elif re.match("[A-Z][a-z][a-z] [0-9]+ off", part):
                result = re.search("(\w{3}) ([0-9]+) off", part)
                month = result.group(1)
                day = result.group(2)
                if month not in self.months:
                    raise DoesNotExistError(
                        "Field error: the month '{}' "
                        "does not exists.".format(day)
                    )
                self.exceptional_closed_days.append(
                    datetime.date(2000, self.months.index(month)+1, int(day))
                )
        for part in self._split_field:
            # Fr 08:30-20:00
            # Mo 10:00-12:00,12:30-15:00
            # Sa,Su 10:00-12:00
            # Sa,Su 10:00-12:00,12:30-15:00
            if re.match("^[A-Za-z]{2}(,\w+)*? (,?[\w():+-]+-[\w():+-]+)+", part):
                days, periods = part.split()
                periods = periods.split(',')
                for day in map(str.title, days.split(',')):
                    if day not in self.days:
                        if day == "PH":
                            for period in periods:
                                self.PH.add_period_from_field(period, self.tz)
                        elif day == "SH":
                            for period in periods:
                                self.SH.add_period_from_field(period, self.tz)
                        else:
                            raise DoesNotExistError(
                                "Field error: the day '{}' does not exists."
                                .format(day)
                            )
                    for period in periods:
                        self[day].add_period_from_field(period, self.tz)
            # Fr-Su 10:00-12:00
            # Fr-Su 10:00-12:00,12:30-15:00
            # Th-Su,Mo 10:00-12:00
            elif re.match(
                "[A-Za-z]{2}-[A-Za-z]{2}(,\w+)*? "
                "(,?[\w():+-]+-[\w():+-]+)+", part):
                slice_days = re.search("([A-Za-z]{2})-([A-Za-z]{2})", part)
                covered_days = self.days[self.days.index(slice_days.group(1).title()):self.days.index(slice_days.group(2).title())+1]
                others_days = tuple(part.split()[0].split(',')[1:])
                periods = part.split()[1].split(',')
                for day in covered_days + others_days:
                    if day not in self.days:
                        if day == "PH":
                            for period in periods:
                                self.PH.add_period_from_field(period, self.tz)
                        elif day == "SH":
                            for period in periods:
                                self.SH.add_period_from_field(period, self.tz)
                        else:
                            raise DoesNotExistError(
                                "Field error: the day '{}' does not exists."
                                .format(day)
                            )
                    else:
                        for period in periods:
                            self[day].add_period_from_field(period, self.tz)
        return
    
    def sanitize(self, field):
        """
            Sanitizes the given field by correcting the case of
            the words and fixing the most common errors.
            
            Parameters
            ----------
            field : str
                The field to sanitize.
            
            Returns
            -------
            str
                The field after being sanitized.
        """
        # Corrects the case errors.
        # mo => Mo
        for day in self.days + self.months + ("sunrise", "sunset", "dawn", "dusk"):
            field = re.sub("(?i){}(?!\w+)".format(day), day, field)
        # Adds colons when necessary.
        # 0630 => 06:30
        for moment in re.findall("[0-9]{4}", field):
            field = field.replace(moment, moment[:2] + ':' + moment[2:])
        return field
    
    def parse_solar_hours(self, coords=None, astral_location=None, hours=None, moment=None):
        """
            Parses the solar hours, allowing them to be used and displayed.
            Solar hours can be parsed for any date.
            
            Parameters
            ----------
            /!\ Only one of the three following arguments must be given.
            coords : tuple of two floats, optionnal
                A set of GPS coordinates (latitude, longitude).
            astral_location : astral.Astral.Location object, optionnal
                The astral location of the point.
            hours : tuple of tuples of integers, optionnal
                A set of hours of sunrise and sunset.
                Ex : ((h1, m1), (h2, m2)).
            moment : datetime.date object, optionnal
                A date for which to parse the solar hours.
                Required only when using 'astral_location' or 'coords'.
            
            Returns
            -------
            datetime.time object
                The hour of sunrise.
            datetime.time object
                The hour of sunset.
        """
        if not moment:
            moment = datetime.datetime.now(self.tz)
        sunrise_time = None
        sunset_time = None
        if hours is not None:
            sunrise_time = datetime.time(hours[0][0], hours[0][1])
            sunset_time = datetime.time(hours[1][0], hours[1][1])
        elif coords is not None:
            a_loc = astral.Location((
                "HOHCity",
                "HOHRegion",
                coords[0], coords[1],
                self.tz.zone,
                100
            ))
            sunrise_time = a_loc.sun(moment, local=True)["sunrise"].time()
            sunset_time = a_loc.sun(moment, local=True)["sunset"].time()
        elif astral_location:
            sunrise_time = astral_location.sun(moment, local=True)["sunrise"].time()
            sunset_time = astral_location.sun(moment, local=True)["sunset"].time()
        else:
            raise ValueError(
                "One keyword argument (coords, astral location or "
                "solar hours) must be given."
            )
        sunrise_time = sunrise_time.replace(tzinfo=self.tz)
        sunset_time = sunset_time.replace(tzinfo=self.tz)
        for day in self._opening_periods + [self.PH, self.SH]:
            day._set_solar_hours(sunrise_time, sunset_time)
        self._solar_hours_parsed = True
        return sunrise_time, sunset_time
    
    def is_open(self, moment=None):
        """
            Determines whether the location is open at the present time
            or at a given time.
            
            Take in account exceptionnal closed days (Dec 25 off).
            
            Parameters
            ----------
            moment : datetime.datetime object, optionnal
                The moment for which to check the opening. None default,
                meaning using the present time, at the timezone given
                to the constructor.
            
            Returns
            -------
            bool
                A boolean indicating if the location is open.
                True if so, False else.
        """
        if self.need_solar_hours_parsing and self._solar_hours_parsed:
            raise NotParsedError("Solar hours have not been parsed and need to.")
        if not moment:
            moment = datetime.datetime.now(self.tz)
            time_moment = moment.time().replace(tzinfo=self.tz)
        else:
            tz = moment.tzinfo
            time_moment = moment.time().replace(tzinfo=tz)
        for day in self.exceptional_closed_days:
            if day.day == moment.day and day.month == moment.month:
                return False
        if self.always_open:
            return True
        day = self[moment.weekday()]
        if not day.periods:
            return False
        for period in day.periods:
            if time_moment in period:
                return True
        return False
    
    def next_change(self, moment=None):
        """
            Returns the moment (datetime.datetime object) of the next
            status change. Returns None if it's always open (24/7).
            
            Parameters
            ----------
            moment : datetime.datetime object, optionnal
                The moment for which to check status relatively.
                None default, meaning using the present time, at the
                timezone given to the constructor.
        """
        if self.need_solar_hours_parsing and self._solar_hours_parsed:
            raise NotParsedError("Solar hours have not been parsed and need to.")
        if self.always_open:
            return
        if not moment:
            moment = datetime.datetime.now(self.tz)
        time_moment = moment.time().replace(tzinfo=self.tz)
        days = self[moment.weekday():-1] + self[0:moment.weekday()]
        td_days = 0
        for day in days:
            if not day.opens_today():
                td_days += 1
                continue
            for period in day.periods:
                if time_moment in period:
                    return self._couple2moment(td_days, period.m2, moment)
                if time_moment < period.m1.time() or td_days > 0:
                    return self._couple2moment(td_days, period.m1, moment)
                if time_moment > period.m2.time():
                    continue
            td_days += 1
        # Should not come here.
        return
    
    def _couple2moment(self, td_days, moment_object, moment):
        """
            Returns a datetime.datetime object from td_days,
            a Moment object and a datetime.datetime object.
            Used by self.next_change(), not intended to be
            used separately.
        """
        date_moment = moment.date()
        return datetime.datetime.combine(
            date_moment + datetime.timedelta(days=td_days),
            moment_object.time()
        )
    
    def time_before_next_change(self, moment=None):
        """
            Returns a datetime.timedelta() object before the next
            status change. Can take a "moment" argument which
            must be a datetime.datetime() object.
            
            Returns datetime.timedelta(0) if it's always open.
        """
        if not moment:
            moment = datetime.datetime.now(self.tz)
        next_change = self.next_change(moment)
        return next_change - moment
    
    def get_day(self, day):
        """
            Returns the Day object according to its index in the week
            or its name. The argument can be an integer (between 0 and
            6) or a string like 'Mo' or 'Th' (OSM like).
        """
        return self[day]
    
    def __getitem__(self, index):
        """
            Returns the Day object according to its index in the week.
            'index' can be an integer (between 0 and 6) or a string
            like 'Mo' or 'Th' (OSM like). Supports slicing.
        """
        if type(index) is int:
            return self._opening_periods[index]
        elif type(index) is str:
            if index == "PH":
                return self.PH
            elif index == "SH":
                return self.SH
            else:
                return self._opening_periods[self.days.index(index)]
        elif type(index) is slice and type(index.start) is type(index.stop) is int:
            return self._opening_periods[index.start:index.stop:index.step]
        elif type(index) is slice and type(index.start) is type(index.stop) is str:
            return self._opening_periods[
                self.days.index(index.start):self.days.index(index.stop):index.step
            ]
        else:
            raise ValueError("Index must be an integer, a string or a slice object..")
    
    def render(self, obj, universal=False):
        """
            Renders to a human readable string a Period or a Moment object.
            
            Parameters
            ----------
            t : HOHTranslate object, optionnal
                Allows the use of 'universal'. None default.
                Should stay to None only for Period objects
                containing only "normal" typed Moments.
            universal : bool, optionnal
                Outputs 'sunrise' or 'sunset' instead of their hours.
                Supports offsets like '(sunrise+02:00)'.
        """
        if type(obj) is Period:
            return "{} - {}".format(self.render(obj.m1, universal), self.render(obj.m2, universal))
        elif type(obj) is Moment:
            if obj.type == "normal":
                return obj.time().strftime(self._t.sentence("time_format"))
            else:
                if universal is True:
                    if obj.timedelta and obj.time() is None:
                        hours, remainder = divmod(obj.timedelta.seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        if obj.timedelta.days > 0:
                            hours = str(24 - hours)
                        else:
                            hours = str(24)
                        minutes = str(minutes)
                        if len(hours) == 1:
                            hours = '0' + hours
                        if len(minutes) == 1:
                            minutes = '0' + minutes
                        string_time = self._t.sentence("time_format")
                        string_time = string_time.replace('%H', hours).replace('%M', minutes)
                        if obj.timedelta.seconds > 0:
                            offset = self._t.sentence("after_solar")
                        else:
                            offset = self._t.sentence("before_solar")
                        # TODO : Test this more in depth.
                        return "{time} {offset} {type}".format(time=string_time, offset=offset, type=t.sentence(obj.type))
                    else:
                        return self._t.word(obj.type)
                else:
                    if obj.time() is not None:
                        return obj.time().strftime(self._t.sentence("time_format"))
                    else:
                        raise NotParsedError("Solar hours have not been parsed. Can't be rendered.")
        else:
            raise ValueError("The first argument must be a Period or a Moment object.")
    
    def stringify_week_schedules(self, compact=False, holidays=True, universal=True):
        """
            Returns a human-readable string describing the opening hours
            on a regular week.
            
            Parameters
            ----------
            compact : bool, optionnal : TODO
                Defines if schedules should be shortened if possible.
                False default.
            holidays : bool, optionnal
                Defines if holidays must be indicated. True default.
            universal : bool, optionnal
                Sets whether the solar hours should be rendered like
                "sunrise" or like "22:00" (depending on the date).
            
            Returns
            -------
            str
                A human readable multiline string describing the
                opening hours on a regular week.
        """
        if self.need_solar_hours_parsing and not self._solar_hours_parsed and not universal:
            raise NotParsedError("Solar hours have not been parsed and need to.")
        compacted = False
        output = ""
        if self.always_open:
            output += self._t.sentence("always_open")
            compacted = True
        # TODO.
        if compact and not compacted:
            raise NotImplementedError("Sorry, this functionality is not yet implemented.")
        if not compact and not compacted:
            i = 0
            for day in self._opening_periods:
                day_periods = [self.render(period, universal) for period in day.periods]
                day_periods = " {} ".format(self._t.word("and")).join(day_periods)
                if not day_periods:
                    day_periods = self._t.word("closed")
                output += self._t.sentence("day_periods").format(
                    day=self._t.weekday(day.index).title(),
                    periods=day_periods
                )
                i += 1
                if i < 7:
                    output += "\n"
        # TODO : Improve.
        if holidays and (self.PH.periods or self.SH.periods):
            if self.PH.closed and self.SH.closed:
                output += "\n\n" + self._t.sentence("closed_public_school_holidays")
            elif self.PH.closed:
                output += "\n\n" + self._t.sentence("closed_public_holidays")
            elif self.SH.closed:
                output += "\n\n" + self._t.sentence("closed_school_holidays")
            elif self.PH.has_same_periods(self.SH) and self.PH.opens_today() and self.SH.closed.opens_today():
                day = "\n\n{} {} {}".format(
                    self._t.sentence("public_holidays").capitalize(),
                    self._t.word("and"),
                    self._t.sentence("school_holidays")
                )
                day_periods = [self.render(period, universal) for period in self.PH.periods]
                day_periods = " {} ".format(self._t.word("and")).join(day_periods)
                output += self._t.sentence("day_periods").format(
                    day=day,
                    periods=day_periods
                )
            else:
                output += "\n\n"
                for holiday in [(self.PH, "public_holidays"), (self.SH, "school_holidays")]:
                    if not holiday[0].opens_today():
                        continue
                    day_periods = [self.render(period, universal) for period in holiday[0].periods]
                    day_periods = " {} ".format(self._t.word("and")).join(day_periods)
                    output += self._t.sentence("day_periods").format(
                        day=self._t.sentence(holiday[1]).capitalize(),
                        periods=day_periods
                    )
            if self.exceptional_closed_days:
                output += '\n' + self._t.sentence("closed_days")
                closed_days = [date.strftime(self._t.sentence("date_format")) for date in self.exceptional_closed_days]
                if len(closed_days) == 1:
                    output += closed_days[0]
                else:
                    output += ', '.join(closed_days[:-1]) + ' ' + self._t.word("and") + ' ' + closed_days[-1]
        return output
