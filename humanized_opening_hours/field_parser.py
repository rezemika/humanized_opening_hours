import datetime
import pytz
import re
from collections import namedtuple
import isoweek
import calendar

from exceptions import (
    ParseError,
    DoesNotExistError,
    ImpreciseField,
)

from temporal_objects import (
    WEEKDAYS,
    MONTHS,
    MomentKind,
    Year,
    Week,
    Day,
    Period,
    Moment
)

# A list of the indexes of regular closed days, to override PH and SH.
regular_closed_days = []

def parse_field(splited_field: list, year_int: int, default_holidays : bool = True) -> Year:
    """Parses a splited field and a year, and returns a Year object."""
    days_in_year = 366 if calendar.isleap(year_int) else 365
    year = Year()
    year.year = year_int
    closed_days_indexes = []
    for week_index, week in enumerate(isoweek.Week.weeks_of_year(year_int)):
        for i, day_date in enumerate(week.days()):
            d = Day(day_date.weekday())
            d.date = day_date
            d.week_index = week_index
            d.month_index = d.date.month - 1
            year.all_days.append(d)
    if "24/7" in splited_field:
        index = splited_field.index("24/7")
        year._set_always_open()
        splited_field.pop(index)
    if len(splited_field) and splited_field[0] in ["off", "closed"]:
        return year
    for part in splited_field:
        # "PH off"
        # "SH off"
        if part == "PH off":
            year.PH_week.closed = True
        elif part == "SH off":
            year.SH_week.closed = True
        # "PH *"
        # "SH *"
        elif part.startswith("PH") or part.startswith("SH"):
            year = parse_holiday_week(year, part)
        # "week 1-12/2 *"
        elif part.startswith("week "):
            year = parse_week_part(year, part)
        # "10:00-12:00"
        # "00:00-24:00"
        elif part[:2].isdigit():
            concerned_days = year.all_days
            schedules = parse_schedules(part)
            for day in concerned_days:
                if schedules.closed:
                    day.periods = []
                    continue
                for period in schedules.regular:
                    day._add_period(period, force=True)
        # "Mo-Su *"
        # "Mo,SH *"
        elif part[:2] in WEEKDAYS:
            concerned_days = parse_regular_day_range(year, part.split()[0])
            days_indexes = [day.index for day in concerned_days]
            schedules = parse_schedules(part.split()[1], days_indexes=closed_days_indexes)
            for day in concerned_days:
                if schedules.closed:
                    day.periods = []
                    continue
                for period in schedules.regular:
                    day._add_period(period, force=True)
        elif part[:3] in MONTHS:
            # "Dec 25 off"
            if re.match("[A-Z][a-z]{2} [0-9]{1,2}: .+", part):
                # "Jan1,Dec 25"
                for d in part.split(','):
                    d = d.strip()
                    month_index, day_number = MONTHS.index(d.split()[0]), int(d.split()[1])
                    date = datetime.date(year_int, month_index+1, day_number)
                    schedules = parse_schedules(d.split(' ', 2)[-1])
                    day = Day(date.weekday())
                    day.date = date
                    if schedules.closed:
                        day.periods = []
                    else:
                        for period in schedules.regular:
                            day._add_period(period, force=True)
                    year.exceptional_days.append(day)
            # "Jan *"
            # "Jan-Feb *"
            else:
                concerned_days = parse_month_range(year, part)
                raw_schedules = part.split(' ', 1)[1]
                for word in WEEKDAYS:
                    if raw_schedules.startswith(word):
                        raw_schedules = raw_schedules[len(word):]
                schedules = parse_schedules(raw_schedules)
                for day in concerned_days:
                    if schedules.closed:
                        day.periods = []
                        continue
                    for period in schedules.regular:
                        day._add_period(period, force=True)
        # Invalid days.
        elif part[:2].isalpha():
            raise DoesNotExistError("The day {day!r} does not exist.".format(
                day=part[:2])
            )
    # TODO : Check / improve.
    field = '; '.join(splited_field)
    if default_holidays:
        if not "PH" in field:
            year.PH_week = list(year.iter_weeks())[26]
        if not "SH" in field:
            year.SH_week = list(year.iter_weeks())[26]
    for day in year.all_days:
        if day.date.weekday() in closed_days_indexes:
            day.periods = []
    return year

# See https://stackoverflow.com/a/952952
flatten = lambda l: [item for sublist in l for item in sublist]

def parse_regular_day_range(year, day_range: str) -> list:
    """Returns a list of days."""
    days_ranges = day_range.split(',')
    concerned_day_names = []
    for days_range in days_ranges:
        splited_range = days_range.split('-')
        if len(splited_range) == 1:  # "PH" and "SH" are supposed to be here.
            concerned_day_names.append(splited_range[0])
        else:
            concerned_day_names.extend(
                WEEKDAYS[WEEKDAYS.index(splited_range[0]):WEEKDAYS.index(splited_range[1])+1]
            )
    days = []
    for day_name in concerned_day_names:
        if day_name in WEEKDAYS:
            for day in year.all_days:
                if day.index == WEEKDAYS.index(day_name):
                    days.append(day)
        elif day_name == "PH":
            days.extend(year.PH_week.days)
        elif day_name == "SH":
            days.extend(year.SH_week.days)
        else:
            raise DoesNotExistError("The day {day!r} does not exist.".format(day=day_name))
    return days

def parse_days_range(days_range: str) -> list:
    """Returns a list of Day objects from a day range."""
    days_ranges = days_range.split(',')
    concerned_day_names = []
    for days_range in days_ranges:
        splited_range = days_range.split('-')
        if len(splited_range) == 1:  # "PH" and "SH" are supposed to be here.
            concerned_day_names.append(splited_range[0])
        else:
            concerned_day_names.extend(
                WEEKDAYS[WEEKDAYS.index(splited_range[0]):WEEKDAYS.index(splited_range[1])+1]
            )
    return concerned_day_names

def parse_month_range(year, part: str) -> list:
    month_range = part.split()[0]
    if '-' not in month_range:
        concerned_days = []
        for month in month_range.split(','):
            concerned_days.extend(
                [m for m in year.all_months()][MONTHS.index(month)]
            )
    else:
        month_range_start, month_range_stop = month_range.split('-')
        month_range_start, month_range_stop = (
            MONTHS.index(month_range_start),
            MONTHS.index(month_range_stop)
        )
        concerned_days = [m for m in year.all_months()][month_range_start:month_range_stop+1]
        concerned_days = flatten(concerned_days)
    days = part.split()[1]
    if days[0:2] in WEEKDAYS:
        day_names = parse_days_range(days)
        days_indexes = [WEEKDAYS.index(day_name) for day_name in day_names]
        new_concerned_days = []
        for day in concerned_days:
            if day.date.weekday() in days_indexes:
                new_concerned_days.append(day)
            else:
                day.periods = []
        return new_concerned_days
    return concerned_days

def parse_month_part(year, part: str) -> Year:
    """Returns a list of Day objects from a month range."""
    concerned_days = parse_month_range(year, part)
    schedules = parse_schedules(part.split()[1])
    for day in concerned_days:
        if schedules.closed:
            day.periods = []
            continue
        for period in schedules.regular:
            day._add_period(period, force=True)
    return year

def parse_holiday_week(year, part):
    if part.startswith("PH "):
        concerned_days = year.PH_week.days
    elif part.startswith("SH "):
        concerned_days = year.SH_week.days
    elif part[:5] in ["PH,SH", "SH,PH"]:
        concerned_days = year.PH_week.days + year.SH_week.days
    else:
        raise ParseError("The part {part!r} is invalid.".format(part=part))
    part = part[3:]
    schedules = parse_schedules(part.split()[1])
    for day in concerned_days:
        if schedules.closed:
            day.periods = []
            continue
        for period in schedules.regular:
            day._add_period(period, force=True)
    return year

def parse_week_part(year, part: str) -> Year:
    """Returns a list of Day objects from a week range."""
    week_range = part.split()[1]
    if '/' not in week_range:
        week_range += '/1'
    week_range, week_periodicity = week_range.split('/')
    concerned_days = []
    if '-' not in week_range:
        for i, week in enumerate(year.iter_weeks_as_lists()):
            if int(week_range) == i+1:
                concerned_weeks = week
                break
    else:
        week_range_start, week_range_stop = week_range.split('-')
        if week_range_start == "01":
            week_range_start = "1"
        week_range_start = int(week_range_start) - 1
        week_range_iter = range(
            int(week_range_start),
            int(week_range_stop),
            int(week_periodicity)
        )
        all_weeks = list(year.iter_weeks_as_lists())
        concerned_weeks = [all_weeks[i] for i in list(week_range_iter)]
    concerned_days_names = parse_days_range(part.split()[2])
    concerned_days_indexes = [WEEKDAYS.index(day_name) for day_name in concerned_days_names]
    concerned_days = []
    for week in concerned_weeks:
        for day in week:
            if day.index in concerned_days_indexes:
                concerned_days.append(day)
            else:
                day.periods = []
    
    part = part[5:]
    schedules = parse_schedules(part.split(' ', 2)[-1])
    for day in concerned_days:
        if schedules.closed:
            day.periods = []
            continue
        for period in schedules.regular:
            day._add_period(period, force=True)
    return year

Schedules = namedtuple("Schedules", ["regular", "closed"])

def parse_schedules(schedules: str, days_indexes : list = None) -> Schedules:
    #if schedules == "open":
    if schedules.startswith("open "):  # "open 12:00-19:00"
        schedules = schedules[10:]  # Strips the "open ".
    elif schedules in ["off", "closed"]:
        if days_indexes:
            regular_closed_days.extend(days_indexes)
        return Schedules(
            regular=[],
            closed=True
        )
    elif schedules == "24/7":
        return Schedules(
            regular=[Period(datetime.time.min, datetime.time.max)],
            closed=False
        )
    
    periods = []
    for schedule_period in schedules.split(','):
        schedule_period = schedule_period.strip()
        if schedule_period.endswith('+'):
            raise ImpreciseField("The part '{}' is valid but not precise enough to allow parsing.".format(schedules))
        period_start, period_end = re.split("-(?![^\(]*\))", schedule_period)
        period_start, period_end = (
            parse_moment(period_start),
            parse_moment(period_end)
        )
        period = Period(period_start, period_end)
        periods.append(period)
    
    return Schedules(
            regular=periods,
            closed=False
        )

def parse_moment(raw: str) -> Moment:
    """Parses a moment and returns a Moment object."""
    if re.match("[0-9][0-9]:[0-9][0-9]", raw):
        if raw == "24:00":
            moment_time = datetime.time.max.replace(tzinfo=pytz.UTC)
        else:
            moment_time = datetime.datetime.strptime(raw, "%H:%M").time().replace(tzinfo=pytz.UTC)
        return Moment(MomentKind.NORMAL, time=moment_time)
    
    if raw == "sunrise":
        return Moment(MomentKind.SUNRISE, delta=datetime.timedelta())
    elif raw == "sunset":
        return Moment(MomentKind.SUNSET, delta=datetime.timedelta())
    elif raw == "dawn":
        return Moment(MomentKind.DAWN, delta=datetime.timedelta())
    elif raw == "dusk":
        return Moment(MomentKind.DUSK, delta=datetime.timedelta())
    
    parsed = re.search(
        "\((sunrise|sunset|dawn|dusk)(\+|-)([0-9][0-9]):([0-9][0-9])\)",
        raw
    )
    if parsed is None:
        raise ParseError("The field part '{}' could not be parsed.".format(raw))
    parsed = parsed.groups()
    try:
        kind = MomentKind[parsed[0].upper()]
    except KeyError:
        raise ParseError("'{}' is not a valid kind of moment.".format(parsed[0].upper()))
    if parsed[1] not in '+-':
        raise ParseError("'{}' is not a valid sign for offset.".format(parsed[1]))
    offset_sign = 1 if parsed[1] == '+' else -1
    offset_hours, offset_minutes = int(parsed[2]), int(parsed[3])
    offset_seconds = (
        offset_hours * 60 * 60 +
        offset_minutes * 60
    ) * offset_sign
    offset = datetime.timedelta(seconds=offset_seconds)
    return Moment(kind, delta=offset)
