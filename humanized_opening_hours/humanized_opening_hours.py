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
    
    >>> hohr = humanized_opening_hours.HOHRenderer(hoh)
    >>> print(hohr.full_description())
    '''
    Monday: 06:00 - 21:00
    Tuesday: 06:00 - 21:00
    Wednesday: 06:00 - 21:00
    Thursday: 06:00 - 21:00
    Friday: 06:00 - 21:00
    Saturday: 07:00 - 21:00
    Sunday: 07:00 - 21:00
    '''
    ```
"""

# TODO : Handle 24:00.

import os
import re
import json
import datetime
import pytz
import astral
import gettext

__all__ = [
    "HumanizedOpeningHours",
    "HOHRenderer",
    "HOHError",
    "DoesNotExistError",
    "NotParsedError",
    "PeriodsConflictError"
]

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

class ParseError(HOHError):
    """
        Raised when field parsing fails.
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

def _(message): return message

WEEKDAYS = (
    _("Monday"),
    _("Tuesday"),
    _("Wednesday"),
    _("Thursday"),
    _("Friday"),
    _("Saturday"),
    _("Sunday")
)

MONTHS = (
    _("January"),
    _("February"),
    _("March"),
    _("April"),
    _("May"),
    _("June"),
    _("July"),
    _("August"),
    _("September"),
    _("October"),
    _("November"),
    _("December")
)

del _

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
            try:
                moment_type, sign, differential = result.group(1), result.group(2), result.group(3)
            except AttributeError:
                raise ParseError("Field parsing has failed on '{}'.".format(field))
            hours = int(differential.split(':')[0])
            minutes = int(differential.split(':')[1])
            if sign == '-':
                hours *= -1
                minutes *= -1
            timedelta = datetime.timedelta(hours=hours, minutes=minutes)
            m2 = Moment(moment_type, timedelta=timedelta)
        # Sanity precaution.
        for period in self.periods:
            if m1.type in ["sunrise", "sunset"] or m2.type in ["sunrise", "sunset"]:
                continue
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
        if type(moment) is Moment:
            return self.m1.time() <= moment.time() <= self.m2.time()
        elif type(moment) is datetime.time:
            return self.m1.time() <= moment <= self.m2.time()
        else:
            raise ValueError("'in <Period>' requires datetime.time or Moment object as left operand.")
    
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
            return "<Moment {} {}>".format(self.type, self.time().strftime("%H:%M"))
        else:
            return "<Moment {} : timedelta {}s>".format(self.type, self.timedelta.seconds)

# Main class

class HumanizedOpeningHours:
    def __init__(self, field, tz=pytz.timezone("UTC"), sanitize_only=False):
        """
            A parser for the OSM opening_hours field.
            
            >>> hoh = HumanizedOpeningHours("Th-Sa 10:00-19:00", "en", pytz.timezone("UTC"))
            
            Parameters
            ----------
            field : str
                The opening_hours field.
            tz : pytz.timezone object, optional
                The timezone to use (UTC default).
            sanitize_only : bool, optional
                False default. Set to True to only do the sanitizing.
                The sanitized field is available in the 'field'
                attribute. The other methods will not work.
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
        if sanitize_only:
            return
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
                    datetime.date(2000, self.months.index(month), int(day))
                )
            # Fr 08:30-20:00
            # Mo 10:00-12:00,12:30-15:00
            # Sa,Su 10:00-12:00
            # Sa,Su 10:00-12:00,12:30-15:00
            if re.match("^[A-Za-z]{2}(,\w+)*? (,?[\w():+-]+-[\w():+-]+)+", part):
                days, periods = part.split()
                periods = periods.split(',')
                for day in days.split(','):
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
            # Fr-Su 10:00-12:00
            # Fr-Su 10:00-12:00,12:30-15:00
            # Th-Su,Mo 10:00-12:00
            elif re.match(
                "[A-Za-z]{2}-[A-Za-z]{2}(,\w+)*? "
                "(,?[\w():+-]+-[\w():+-]+)+", part):
                slice_days = re.search("([A-Za-z]{2})-([A-Za-z]{2})", part)
                for day in (slice_days.group(1).title(), slice_days.group(2).title()):
                    if day not in self.days:
                        raise DoesNotExistError(
                                "Field error: the day '{}' does not exists."
                                .format(day)
                            )
                covered_days = self.days[
                        self.days.index(slice_days.group(1).title()):
                        self.days.index(slice_days.group(2).title())+1
                    ]
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
        for day in self.days + self.months + ("sunrise", "sunset", "dawn", "dusk", "PH", "SH"):
            field = re.sub("(?i){}(?!\w+)".format(day), day, field)
        # Adds colons when necessary.
        # 0630 => 06:30
        for moment in re.findall("[0-9]{4}", field):
            field = field.replace(moment, moment[:2] + ':' + moment[2:])
        # Adds zeros when necessary.
        # 7:30 => 07:30
        for moment in re.findall("( (?<![0-9-])[0-9]:[0-9]{2})", field):
            field = field.replace(moment, ' 0' + moment[1:])
        # Removes spaces after commas.
        # 07:00-13:30, 15:30-19:30 => 07:00-13:30,15:30-19:30
        for period in re.findall("[0-9], [0-9]", field):
            field = field.replace(period, period.replace(' ', ''))
        # Replaces commas by semicolons if necessary.
        # Mo-Fr 06:30-20:00, Sa 07:30-14:30 => Mo-Fr 06:30-20:00;Sa 07:30-14:30
        for part in re.findall("[0-9], [A-Z][a-z]", field):
            field = field.replace(part, part.replace(', ', ';'))
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
        if self.need_solar_hours_parsing and not self._solar_hours_parsed:
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
        if self.need_solar_hours_parsing and not self._solar_hours_parsed:
            raise NotParsedError("Solar hours have not been parsed and need to.")
        if self.always_open:
            return
        if not moment:
            moment = datetime.datetime.now(self.tz)
        time_moment = moment.time().replace(tzinfo=self.tz)
        days = self[moment.weekday():] + self[0:moment.weekday()]
        td_days = 0
        for td_days, day in enumerate(days):
            if not day.opens_today():
                continue
            for period in day.periods:
                if time_moment in period:
                    return self._couple2moment(td_days, period.m2, moment)
                if time_moment < period.m1.time() or td_days > 0:
                    return self._couple2moment(td_days, period.m1, moment)
                if time_moment > period.m2.time():
                    continue
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
        else:
            return self._opening_periods[index]

    def render(self, *args, **kwargs):
        """
            Returns the HOHRenderer object. Can take HOHRenderer's parameters.
        """
        return HOHRenderer(self, *args, **kwargs)


class HOHRenderer:  # TODO : lang_dir
    """
        A renderer for HOH objects into various output formats.
    """
    def __init__(self, hoh, universal=True, lang="en", lang_dir="locales/"):
        """
            A renderer for HOH objects into various output formats.
            
            Parameters
            ----------
            hoh : HumanizedOpeningHours object
                An HOH object from where it will use
                the information for rendering.
            universal : bool, optional
                Outputs "sunrise" or "sunset" instead of their hours.
                Supports offsets like "(sunrise+02:00)". True default.
            lang : str, optional
                The language to use for rendering. Must be available.
                Default: "en".
            lang_dir : str, optional
                The absolute path to a directory where HOHR will find
                .mo translation files, if you want a custom translation.
        """
        self.hoh = hoh
        self.lang = lang
        self.universal = self.set_universal(universal)
        self.always_open_str = ''
        if self.hoh.always_open:
            self.always_open_str = _("Open 24 hours a day and 7 days a week.")
        # TODO : Check.
        gettext.install("HOH", lang_dir)
        self.language = gettext.translation("HOH", lang_dir, languages=[lang], fallback=True)
        self.language.install()
    
    def available_languages(self):
        """
            Returns a list of all suported languages.
        """
        return gettext.find('HOH', 'locales/', all=True)
    
    def set_universal(self, state):
        """
            Defines the "universal" state of HOHR. This variable can be
            changed manually, but this method will ensure that this
            won't pose problems (it will raise a NotParsedError otherwise).
            
            Parameters
            ----------
            state : bool
                Defines whether the outputs will follow a universal
                format (True default on init).
            
            Returns
            -------
            self
                This method returns the class itself, allowing chaining.
        """
        self.universal = True
        if not state and self.hoh.need_solar_hours_parsing and not self.hoh._solar_hours_parsed:
            raise NotParsedError("Solar hours have not been parsed and need to.")
        self.universal = state
        return self
    
    def _render_timedelta(self, moment):
        """
            Returns a human-readable delay from a Moment's timedelta.
        """
        hours, remainder = divmod(moment.timedelta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return datetime.time(hours, minutes).strftime("%H:%M")
    
    def _days_periods(self, day):
        """
            Returns a list of formated periods (str) from a Day object.
        """
        periods = []
        for period in day.periods:
            periods.append(self.render_period(period))
        return periods
    
    def render_moment(self, moment):
        """
            Renders to a human readable string a Moment object.
        """
        # TODO : Check / review.
        gettext.install("HOH", "locales/")
        self.language.install()
        if type(moment) != Moment:
            raise ValueError("The first argument must be a Period or a Moment object.")
        if moment.type == "normal":
            return moment.time_object.strftime("%H:%M")
        else:
            if self.universal:
                time = self._render_timedelta(moment)
                if moment.timedelta.seconds > 0:
                    if moment.type == "sunrise":
                        return _("{time} after sunrise").format(time=time)
                    else:
                        return _("{time} after sunset").format(time=time)
                elif moment.timedelta.seconds < 0:
                    if moment.type == "sunrise":
                        return _("{time} before sunrise").format(time=time)
                    else:
                        return _("{time} before sunset").format(time=time)
                else:
                    if moment.type == "sunrise":
                        return _("sunrise")
                    else:
                        return _("sunset")
            elif self.hoh._solar_hours_parsed:
                return moment.time().strftime("%H:%M")
            else:
                raise NotParsedError("Solar hours have not been parsed and need to.")
    
    def render_period(self, period):
        """
            Renders to a human readable string a Period object.
        """
        if type(period) != Period:
            raise ValueError("The first argument must be a Period or a Moment object.")
        return "{} - {}".format(
            self.render_moment(period.m1), self.render_moment(period.m2)
        )
    
    def periods_per_day(self):
        """
            Returns a dict of seven items with day indexes as keys and
            tuples of name of the day and a list of its periods
            (str, like those returned by "render_period()") as values.
        """
        # TODO : Check / review.
        gettext.install("HOH", "locales/")
        self.language.install()
        output_periods = {}
        for i in range(7):
            day = self.hoh.get_day(i)
            output_periods[i] = (_(WEEKDAYS[i]), self._days_periods(day))
        return output_periods
    
    def closed_days(self):
        """
            Returns a list of human-readable exceptional closed days (str).
        """
        # TODO : Check / review.
        gettext.install("HOH", "locales/")
        self.language.install()
        days = []
        for day in self.hoh.exceptional_closed_days:
            # TODO : Improve.
            if day.day == 1:
                days.append(
                    _("1st {month_name}").format(month_name=_(MONTHS[day.month]))
                )
            else:
                days.append(
                    _("{day} {month_name}").format(
                        day=day.day, month_name=_(MONTHS[day.month])
                    )
                )
        return days
    
    def holidays(self):
        """
            Returns a dict describing the schedules during the holidays.
            
            Dict shape:
            {
                "main": <str>,  # A string indicating whether it's open during holidays.
                "PH": (
                    <bool or None>,  # True : open ; False : closed ; None : unknown.
                    <periods list (str)>  # Periods list, like those of "periods_per_day()".
                ),
                "SH": (
                    <bool or None>,  # True : open ; False : closed ; None : unknown.
                    <periods list (str)>  # Periods list, like those of "periods_per_day()".
                ),
            }
        """
        # TODO : Check / review.
        gettext.install("HOH", "locales/")
        self.language.install()
        ph_state = self.hoh.PH.opens_today() or None
        if ph_state is None and self.hoh.PH.closed is True:
            ph_state = False
        sh_state = self.hoh.SH.opens_today() or None
        if sh_state is None and self.hoh.SH.closed is True:
            sh_state = False
        ph_descriptor = {
            True: _("Open on public holidays."),
            False: _("Closed on public holidays."),
            None: '',
        }.get(ph_state)
        sh_descriptor = {
            True: _("Open on school holidays."),
            False: _("Closed on school holidays."),
            None: '',
        }.get(sh_state)
        default_descriptor = ' '.join(
            [d for d in (ph_descriptor, sh_descriptor) if d != '']
        )
        main_descriptor = {
            ph_state is sh_state is True: _("Open on public and school holidays."),
            ph_state is sh_state is False: _("Closed on public and school holidays."),
            ph_state is sh_state is None: '',
        }.get(True, default_descriptor)
        # TODO : Check / review.
        ph_schedules = []
        sh_schedules = []
        if ph_state:
            ph_schedules = self._days_periods(self.hoh.PH)
        if sh_state:
            sh_schedules = self._days_periods(self.hoh.SH)
        return {
            "main": main_descriptor,
            "PH": (ph_state, ph_schedules),
            "SH": (sh_state, sh_schedules),
        }
    
    def _join(self, l, separator, final_separator):
        """
            Returns a string from a list, a separator an a final separator.
            For example: hohr._join(['A', 'B', 'C'], ' ; ', ' and')
            will return "A ; B and C".
        """
        if separator == final_separator:
            return separator.join(l)
        else:
            if len(l) == 1:
                return separator.join(l)
            else:
                return separator.join(l[1:]) + final_separator + l[-1]
    
    def _format_day_periods(self, day, periods):
        """
            Returns a string describing the schedules of a day from
            a Day object and its list of periods.
        """
        # TODO : Check / review.
        gettext.install("HOH", "locales/")
        self.language.install()
        if periods:
            day_periods = self._join(periods, ', ', _(" and "))
        else:
            day_periods = _("closed")
        return _("{day}: {periods}").format(
            day=day, periods=day_periods
        )
    
    def description(self, holidays=True):
        """
            Returns a multiline string describing the whole schedules.
            
            Parameters
            ----------
            holidays : bool, optional
                Defines whether the holiday schedules will be described.
                True default.
        """
        periods = self.periods_per_day().values()
        output = ''
        if self.hoh.always_open:
            output += _("Open 24 hours a day and 7 days a week.")
        else:
            for i, day in enumerate(periods):
                output += self._format_day_periods(day[0], day[1])
                if i != len(periods):
                    output += '\n'
        all_holidays = self.holidays()
        if holidays and all_holidays["SH"][0] or all_holidays["PH"][0]:
            output += '\n'
            if all_holidays["SH"][0]:
                output += self._format_day_periods(_("School holidays"), all_holidays["SH"][1])
                output += '\n'
            if all_holidays["PH"][0]:
                output += self._format_day_periods(_("Public holidays"), all_holidays["PH"][1])
                output += '\n'
            output += all_holidays["main"]
        if output[-1] == '\n':
            # Fixes a bug making the translation inoperative when removing
            # the last linebreak (if i != len(periods)-1:).
            output = output[:-1]
        return output
