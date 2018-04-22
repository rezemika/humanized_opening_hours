import datetime


def easter_date(year):
    """Returns the datetime.date of easter for a given year (int)."""
    # Code from https://github.com/ActiveState/code/tree/master/recipes/Python/576517_Calculate_Easter_Western_given  # noqa
    a = year % 19
    b = year // 100
    c = year % 100
    d = (19 * a + b - b // 4 - ((b - (b + 8) // 25 + 1) // 3) + 15) % 30
    e = (32 + 2 * (b % 4) + 2 * (c // 4) - d - (c % 4)) % 7
    f = d + e - 7 * ((a + 11 * d + 22 * e) // 451) + 114
    month = f // 31
    day = f % 31 + 1
    return datetime.date(year, month, day)


def days_of_week_from_day(dt):
    """
        Returns a list of seven datetime.date days representing a week
        from a day in this week.
    """
    if isinstance(dt, datetime.datetime):
        dt = dt.date()
    start = dt - datetime.timedelta(days=dt.weekday())
    return [start+datetime.timedelta(days=i) for i in range(7)]


def days_from_week_number(year, week):
    """
        Returns a list of seven datetime.date days representing a week
        from a year and a week number.
    """
    # Code inspired of https://code.activestate.com/recipes/521915-start-date-and-end-date-of-given-week/#c5  # noqa
    dt = datetime.date(year, 1, 1)
    dt = dt - datetime.timedelta(dt.weekday())
    delta = datetime.timedelta(days=(week-1)*7)
    return days_of_week_from_day(dt + delta)
