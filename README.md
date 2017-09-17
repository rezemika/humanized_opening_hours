Humanized Opening Hours - A parser for the opening_hours fields from OSM
========================================================================

**Humanized Opening Hours** is a Python 3 module allowing a simple usage of the opening_hours fields used in OpenStreetMap. It provides especially a function to get a good-looking opening hours description from a field.

Any pull request (following PEP-8) is more than welcome!

```python
>>> import humanized_opening_hours
>>> field = "Mo-Fr 06:00-21:00; Sa,Su 07:00-21:00"
>>> hoh = HumanizedOpeningHours(field)
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

- `tz` (pytz.timezone) : the timezone to use, UTC default.
- `sanitize_only` (bool) : set it to True to not parse the field (usefull when you want only get its sanitized version).

```python
import humanized_opening_hours, pytz

field = "Mo-Fr 06:00-21:00; Sa,Su 07:00-21:00"

hoh = HumanizedOpeningHours(field, tz=pytz.timezone("Europe/Paris"))
```

## Basic methods

```python
# To know if the facility is open at the present time. Returns a boolean. Can take a datetime.datetime moment to check for another time.
>>> hoh.is_open()
True

# To know at which time the facility status (open / closed) will change. Returns a datetime.datetime object. Can take a datetime.datetime moment to check for another time.
# If we are on December 24 before 21:00 / 09:00PM...
>>> hoh.next_change()
datetime.datetime(2017, 12, 24, 21, 0)

# To know how long the facility status (open / closed) will change. Returns a datetime.timedelta object. Can take a datetime.datetime moment to check for another time.
# If we are on December 24 at 20:00 / 08:00PM...
>>> hoh.time_before_next_change()
datetime.timedelta(0, 3600)
```

You can get a sanitized version of the field given to the constructor with the *sanitize* method or the **field** attribute.

```python
# Field : "mo-su 0930-2000"
>>> print(hoh.sanitize())
Mo-Su 09:30-20:00
```

## Solar hours

If the field contains solar hours (only "sunrise" or "sunset", the others are not yet supported), here is how to deal with them.

First of all, you can easily know if you need to parse them by checking the `hoh.need_solar_hours_parsing` variable. If it is `True`, you need to parse them with a dedicated method which need to know the true solar hours.

**If you try to do something with a field requiring parsing without parse it, you will get a "NotParsedError".**

Attention, except if the facility is on the equator, this parsing will be valid only for a short period. It is recommended to rerun this function changing its "moment" argument (or its hours).

If you know that the sun rises at six o'clock and sets at ten o'clock, you can set it like this.

```python
# Using a tuple of tuples of integers (hour, minutes) for (sunrise, sunset).
>>> hoh.parse_solar_hours(hours=((6, 0), (10, 0)))
```

If you don't know solar hours, you have two methods to set them.

```python
# Using the GPS coordinates of the facility.
>>> hoh.parse_solar_hours(coords=(38.506, -28.454))  # Pico island (in the Azores islands).

# Using the astral module. You can pass to the "moment" argument a datetime.datetime object if you want to parse the solar hours for another date.
>>> import astral, pytz
>>> location = astral.Astral.Location("Pico Island", "Atlantic Ocean", (38.506, -28.454), pytz.timezone("Atlantic/Azores"), 100)
>>> hoh.parse_solar_hours(astral_location=location)
```

## Have nice schedules

The `HOHRenderer` class allows you to get various representations of the schedules.
Its *init* method takes an HOH object in argument, and two optional argument:

- `universal` (bool) : allows to have human-readable descriptions without having to parse the solar hours (True default).
- `lang` (str) : the language to use **(only "en" (default) and "fr" are supported for now)**.

It has several methods to retrieve useful informations.

If the facility is always open, many of the following methods won't be very usefull.
If you want a human-readable description, see the doc of the *description* method or use the *always_open_str* to get a simple string.

### description

```python
# Field : "Mo-Fr 06:00-21:00; Sa,Su 07:00-21:00"
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

# Field : "Mo-Fr 06:00-sunset; Sa,Su 07:00-21:00"
>>> print(hohr.description())
'''
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
>>> print(hohr.description())
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
>>> print(hohr.description())
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
>>> print(hohr.description(universal=False))
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

### render_moment

Takes a *Moment* (see the *Objects* section) object as argument and returns a human-readable string describing it.

### render_period

Same as *render_moment*, but for a *Period* object.

### periods_per_day

Returns a dict of seven items with tuples containing the translated name of the day and its periods.

```python
# Field : "Mo-We 09:00-19:00"
>>> hohr.periods_per_day()
'''
{
    0: ("Monday", ["09:00 - 19:00"]),
    1: ("Tuesday", ["09:00 - 19:00"]),
    2: ("Wednesday", ["09:00 - 19:00"]),
    3: ('Thursday', []),
    4: ('Friday', []),
    5: ('Saturday', []),
    6: ('Sunday', []),
}
'''
```

### closed_days

Returns a list of human-readable exceptional closed days.

```python
# Field : "Mo-We 09:00-19:00 ; Dec 25 off ; May 1 off"
>>> hohr.closed_days()
["25 December", "1st May"]
```

### holidays

Returns a dict describing the status of the facility during holidays.

Here is the dict shape.

```
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
```

Example :

```python
# Field : "Mo-We 09:00-19:00 ; SH off ; PH 09:00-12:00"
>>> hohr.holidays()
{
    "main": "Open on public holidays. Closed on school holidays.",
    "PH": (True, ["09:00 - 12:00"]),
    "SH": (False, []),
}
```

### set_universal

This method takes a boolean argument and allows you to update the *universal* argument of HOHR. If solar hours have not been parsed, it will raise a "NotParsedError". If you're brave enough, you can also update directly the *universal* attribute of HOHR.

## Objetcs

Apart the main HumanizedOpeningHours class, HOH provides three other objects:
- `Day` : a weekday, or public or schoold holidays;
- `Period` : a period with two `Moment` objects : a beginning and an end;
- `Moment` : a moment in time, which can be a beginning or an end of a period.

### Day

Attributes:
- `index` (int or str) : an integer from 0 to 6 (index in a week) or "PH" or "SH" for public or school holidays;
- `name` (str) : the OSM-like name of the day ("Mo", "Su", etc) or "PH" or "SH".
- `periods` (list) : a list of `Period` objects included in this day;
- `closed` (bool) : a boolean which is True if this day is explicitly set closed in the field.

```python
# Know whether there is / are opening period(s) in this day.
>>> day.opens_today()
True

# Know if a day has same periods as another (i.e. they are similars).
>>> day.has_same_periods(<day object>)
True

# Gets a datetime.timedelta indicating the total opening time on this day.
>>> day.total_duration()
datetime.timedelta(0, 21600)
```

All the days can be get by getting their index directly from the HOH object, or via the `get_day()` method.

```python
# To get the first day of the week.
>>> hoh[0]
<'Mo' Day object (1 periods)>

# To get all the days of the week.
>>> hoh[0:7]
[<'Mo' Day object (1 periods)>, <'Tu' Day object (1 periods)>, <'We' Day object (1 periods)>, <'Th' Day object (1 periods)>, <'Fr' Day object (1 periods)>, <'Sa' Day object (1 periods)>, <'Su' Day object (1 periods)>]

# To get the day representing public holidays.
>>> hoh["PH"]
<'PH' Day object (0 periods)>

# Same thing for school holidays.
>>> hoh["SH"]
<'SH' Day object (0 periods)>

# With the "get_day() method.
>>> hoh.get_day(0)
<'Mo' Day object (1 periods)>
```

### Period

Attributes:
- `m1` (Moment object) : the beginning of the period;
- `m2` (Moment object) : the end of the period.

```python
# Gets a datetime.timedelta indicating the total duration of this period.
>>> period.duration()
datetime.timedelta(0, 10800)

# Know if a datetime.time object is between the beginning and the end of this period (i.e. it is open at this time).
>>> moment = datetime.time(18, 30)
>>> moment in period
True
```

### Moment

Attributes:
- `type` (str) : the type of this moment, which can be "normal", "sunrise" or "sunset";
- `time_object` (datetime.time object or None) : the moment itself, not None if type is "normal", **not intended to be used directly**;
- `timedelta` (datetime.timedelta object or None) : a time offset, which equals 0 if type is "normal" or if the solar hour has no offset.

```python
# Know if the moment can vary in time (i.e. it is a solar hour).
>>> moment.is_variable()
True

# Gets a datetime.time object, or None if the moment is variable.
>>> moment.time()
datetime.time(18, 30)
```

# Dependencies

This module requires the following modules, which can be installed with `pip3`.

```python
pytz # To handle timezones
astral # To computer solar hours
```

# Licence

This module is published under the AGPLv3 license, the terms of which can be found in the [LICENCE](LICENCE) file.
