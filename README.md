Humanized Opening Hours - A parser for the opening_hours fields from OSM
========================================================================

**Humanized Opening Hours** is a Python 3 module allowing a simple usage of the opening_hours fields used in OpenStreetMap. It provides especially a function to get a good-looking opening hours description from a field.

Any pull request (following PEP-8) is more than welcome!

```python
>>> import humanized_opening_hours
>>> field = "Mo-Fr 06:00-21:00; Sa,Su 07:00-21:00"
>>> hoh = humanized_opening_hours.HumanizedOpeningHours(field)
>>> hoh.is_open()
True
>>> hoh.next_change()
datetime.datetime(2017, 12, 24, 21, 0)
>>> hohr = humanized_opening_hours.HOHRenderer(hoh)
>>> print(hohr.description())
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

**This module is still in development and bugs may occur. If you discover one, please create an issue.**

# Installation

This library is so small, you can include it directly into your project.
Also, it is available on PyPi.

    $ pip3 install osm-humanized-opening-hours

# How to use it

The only mandatory argument to give to the constructor is the field, which must be a string.
You can also specify:

- `year` (int) : the year for which to parse the field, default the current year.

```python
>>> import humanized_opening_hours as hoh
>>> field = "Mo-Fr 06:00-21:00; Sa,Su 07:00-21:00"
>>> 
>>> oh = hoh.OHParser(field)
>>> oh.is_open()
True
```

## Basic methods

```python
# To know if the facility is open at the present time. Returns a boolean. Can take a datetime.datetime moment to check for another time.
>>> oh.is_open()
True

# To know at which time the facility status (open / closed) will change. Returns a collections.namedtuple object.
# Can take a datetime.datetime moment to check for another time.
# If we are on December 24 before 21:00 / 09:00PM...
>>> oh.next_change()
NextChange(dt=datetime.datetime(2017, 12, 24, 21, 0, tzinfo=<UTC>), moment=<Moment ('21:00')>)
```

You can get a sanitized version of the field given to the constructor with the *sanitize* staticmethod or the **sanitized_field** attribute.

```python
>>> field = "mo-su 0930-2000"
>>> print(hoh.OHParser.sanitize(field))
"Mo-Su 09:30-20:00"
```

## Solar hours

If the field contains solar hours, here is how to deal with them.

First of all, you can easily know if you need to set them by checking the `OHParser.needs_solar_hours_setting` variable. If it is `True`, you need to parse them with a dedicated method which need to know the true solar hours.

**If you try to do something with a field requiring setting without setting it, you will get a "SolarHoursNotSetError".**

Attention, except if the facility is on the equator, this setting will be valid only for a short period. It is recommended to rerun this function regularly changing the its hours if your program is intended to be used over a long period of time.

If you know that the sun rises at six o'clock and sets at ten o'clock, you can set it like this.

```python
# Using a tuple of tuples of integers (hour, minutes) for (sunrise, sunset).
>>> oh.set_solar_hours(self, sunrise_sunset=((6, 0), (10, 0)))
```

You can also set dawn and dusk this way.

```python
# Using a tuple of tuples of integers (hour, minutes) for (sunrise, sunset).
>>> oh.set_solar_hours(self, dawn_dusk=((6, 0), (10, 0)))
```

## Have nice schedules

The `HOHRenderer` class allows you to get various representations of the schedules.
Its *init* method takes an OHParser object in argument, and two optional arguments:

- `universal` (bool) : allows to have human-readable descriptions without having to parse the solar hours (True default).
- `locale_name` (str) : the language to use ("en" default), which can be changed with the `set_locale()` method.

It has several methods to retrieve useful informations.

If the facility is always open, many of the following methods won't be very usefull.
If you want a human-readable description, see the doc of the [description](#description) method or use the *always_open_str* attribute to get a simple string.

This object can also be created from an OHParser instance with its `render()` method.

```python
hohr = oh.render(universal=False)
```

### <a name="set_locale"></a>set_locale

Allows to set a new locale for rendering. Takes a single argument: the locale_name.

To get the available locales, use the static method `HOHRenderer.available_locales()`, which returns a list of strings.

### <a name="description"></a>description

Allows to get a pretty description of the opening hours.

Takes the following arguments:

- `indent` (int) : indentation of the day schedules (in spaces), 0 default.
- `week_range` (bool) : if set to False, it will display week indexes only if necessary (True default).
- `holidays` (bool) : defines whether to display the opening status on holidays (True default).

```python
# Field : "Mo-Fr 06:00-21:00; Sa,Su 07:00-21:00"
>>> hohr = humanized_opening_hours.HOHRenderer(hoh)
>>> print(hohr.description())
'''
Weeks 1 – 53:
Monday: 06:00 - 21:00
Tuesday: 06:00 - 21:00
Wednesday: 06:00 - 21:00
Thursday: 06:00 - 21:00
Friday: 06:00 - 21:00
Saturday: 07:00 - 21:00
Sunday: 07:00 - 21:00
'''

>>> print(hohr.description(week_range=False))
'''
Monday: 06:00 - 21:00
Tuesday: 06:00 - 21:00
Wednesday: 06:00 - 21:00
Thursday: 06:00 - 21:00
Friday: 06:00 - 21:00
Saturday: 07:00 - 21:00
Sunday: 07:00 - 21:00
'''

>>> print(hohr.description(indent=4))
'''
Weeks 1 – 53:
    Monday: 06:00 - 21:00
    Tuesday: 06:00 - 21:00
    Wednesday: 06:00 - 21:00
    Thursday: 06:00 - 21:00
    Friday: 06:00 - 21:00
    Saturday: 07:00 - 21:00
    Sunday: 07:00 - 21:00
'''

# Field : "Mo-Fr 06:00-sunset; Sa,Su 07:00-21:00"
>>> print(hohr.description())
'''
Weeks 1 – 53:
Monday: 06:00 - sunset
Tuesday: 06:00 - sunset
Wednesday: 06:00 - sunset
Thursday: 06:00 - sunset
Friday: 06:00 - sunset
Saturday: 07:00 - 21:00
Sunday: 07:00 - 21:00
'''

# Field : "Mo-Fr 06:00-sunset; Sa,Su 07:00-21:00"
# Solar hours parsed. Sunset at 21:04.
>>> hohr = humanized_opening_hours.HOHRenderer(hoh, universal=False)
>>> print(hohr.description(week_range=False))
'''
Monday: 06:00 - 21:04
Tuesday: 06:00 - 21:04
Wednesday: 06:00 - 21:04
Thursday: 06:00 - 21:04
Friday: 06:00 - 21:04
Saturday: 07:00 - 21:00
Sunday: 07:00 - 21:00
'''

# Field : "Mo-Fr 06:00-(sunset+02:00); Sa,Su 07:00-21:00"
# Solar hours parsed. Sunset at 21:04.
>>> print(hohr.description(week_range=False))
'''
Monday: 06:00 - 02:00 after sunset
Tuesday: 06:00 - 02:00 after sunset
Wednesday: 06:00 - 02:00 after sunset
Thursday: 06:00 - 02:00 after sunset
Friday: 06:00 - 02:00 after sunset
Saturday: 07:00 - 21:00
Sunday: 07:00 - 21:00
'''

# Field : "Mo-Fr 06:00-(sunset+02:00); Sa,Su 07:00-21:00"
# Solar hours parsed. Sunset at 21:04.
>>> print(hohr.description(universal=False, week_range=False))
'''
Monday: 06:00 - 23:04
Tuesday: 06:00 - 23:04
Wednesday: 06:00 - 23:04
Thursday: 06:00 - 23:04
Friday: 06:00 - 23:04
Saturday: 07:00 - 21:00
Sunday: 07:00 - 21:00
'''

# Field : "24/7"
>>> hohr = humanized_opening_hours.HOHRenderer(hoh)
>>> print(hohr.description())
'''
Open 24 hours a day and 7 days a week.
'''
```

### <a name="get_human_names"></a>get_human_names

Returns a dict of lists with the names of months and weekdays in the current locale.

Example:

```python
>>> hohr.get_human_names()
{
    'months': [
        'January', 'February', 'March',
        'April', 'May', 'June', 'July',
        'August', 'September', 'October',
        'November', 'December'
    ],
    'days': [
        'Monday', 'Tuesday', 'Wednesday',
        'Thursday', 'Friday', 'Saturday',
        'Sunday'
    ]
}
```

### <a name="humanized_time_before_next_change"></a>humanized_time_before_next_change

Returns a humanized delay before the next change in opening status.

```python
>>> hohr.humanized_time_before_next_change()
"in 3 hours"
>>> hohr.humanized_time_before_next_change(word=False)
"3 hours"
```

## Objects

Apart the main HumanizedOpeningHours class, HOH provides four other objects:
- `Year` : the main year, containing 364 or 365 days;
- `Day` : a weekday, or public or schoold holidays;
- `Period` : a period with two `Moment` objects : a beginning and an end;
- `MomentKind` : the kind of a period;
- `Moment` : a moment in time, which can be a beginning or an end of a period.

### <a name="day"></a>Day

Attributes:
- `index` (int or str) : an integer from 0 to 6 (index in a week) or "PH" or "SH" for public or school holidays;
- `periods` (list) : a list of `Period` objects included in this day;
- `date` (datetime.date) : the date of the day;
- `month_index` (int) : the index of the month of the day (between 0 and 11).

```python
# Know whether there is / are opening period(s) in this day.
>>> day.opens_today()
True
```

### <a name="period"></a>Period

Attributes:
- `beginning` (Moment object) : the beginning of the period;
- `end` (Moment object) : the end of the period.

```python
# To know if a period contains a solar hour, use the `is_variable()` method.
>>> period.is_variable()
datetime.timedelta(0, 10800)

# Know if a datetime.time object is between the beginning and the end of this period (i.e. it is open at this time).
>>> moment = datetime.time(18, 30)
>>> moment in period
True
```

### <a name="momentkind"></a>MomentKind

A simple Enum with the following values:
- `NORMAL`;
- `SUNRISE`;
- `SUNSET`;
- `DAWN`;
- `DUSK`.

### <a name="moment"></a>Moment

Attributes:
- `kind` (MomentKind) : the kind of this moment;

```python
# Gets a datetime.time object (localized on UTC), or None if the moment is variable.
>>> moment.time()
datetime.time(18, 30, tzinfo=<UTC>)
```

# Dependencies

This module requires the following modules, which can be installed with `pip3`.

```python
pytz
isoweek
babel
copy
```

# Licence

This module is published under the AGPLv3 license, the terms of which can be found in the [LICENCE](LICENCE) file.
