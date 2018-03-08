Humanized Opening Hours - A parser for the opening_hours fields from OSM
========================================================================

**Humanized Opening Hours** is a Python 3 module allowing a simple usage of the opening_hours fields used in OpenStreetMap.

Any pull request (following PEP-8) is more than welcome!

```python
>>> import humanized_opening_hours as hoh
>>> field = "Mo-Fr 06:00-21:00; Sa,Su 08:00-12:00"
>>> oh = hoh.HumanizedOpeningHours(field)
>>> oh.is_open()
True
>>> oh.next_change()
datetime.datetime(2017, 12, 24, 12, 0)
>>> print(oh.render().plaintext_week_description())
"""
Monday: 06:00 - 21:00
Tuesday: 06:00 - 21:00
Wednesday: 06:00 - 21:00
Thursday: 06:00 - 21:00
Friday: 06:00 - 21:00
Saturday: 08:00 - 12:00
Sunday: 08:00 - 12:00
"""
```

**This module is still in development and bugs may occur. If you discover one, please create an issue.**

# Installation

This library is so small, you can include it directly into your project.
Also, it is available on PyPi.

    $ pip3 install osm-humanized-opening-hours

# How to use it

The only mandatory argument to give to the constructor is the field, which must be a string.

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

# To know at which time the facility status (open / closed) will change. Returns a datetime.datetime object.
# Can take a datetime.datetime moment to check for another time.
# If we are on December 24 before 21:00 / 09:00PM...
>>> oh.next_change()
datetime.datetime(2017, 12, 24, 21, 0, tzinfo=<UTC>)
```

You can get a sanitized version of the field given to the constructor with the *sanitize* staticmethod or the **sanitized_field** attribute.

```python
>>> field = "mo-su 0930-2000;jan off"
>>> print(hoh.OHParser.sanitize(field))
"Mo-Su 09:30-20:00; Jan off"
```

## Solar hours

If the field contains solar hours, here is how to deal with them.

First of all, you can easily know if you need to set them by checking the `OHParser.needs_solar_hours_setting` variable.
If one of its values is `True`, you need to set them in the `solar_hours` dict with `datetime.time` objects.

For example, if you know that the sunrise is at 08:00 and the sunset at 20:00, you can do this:

```python
oh.solar_hours["sunrise"] = datetime.time(8, 0)
oh.solar_hours["sunset"] = datetime.time(20, 0)
```

**If you try to do something with a field requiring setting without setting it, you will get a "SolarHoursNotSetError".**

Attention, except if the facility is on the equator, this setting will be valid only for a short period.

## Have nice schedules

The `HOHRenderer` class allows you to get various representations of the schedules.
Its *init* method takes an OHParser object in argument, and two optional arguments:

- `universal` (bool) : allows to have human-readable descriptions without having to parse the solar hours (True default).
- `locale_name` (str) : the language to use ("en" default), which can be changed with the `set_locale()` method.

It has several methods to retrieve useful informations.

This object can also be created from an OHParser instance with its `render()` method.

```python
hohr = oh.render(universal=False)
```

### <a name="available_locales"></a>available_locales

Returns a list of the available locales (strings).

### <a name="set_locale"></a>set_locale

Allows to set a new locale for rendering. Takes a single argument: the locale_name.

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

### <a name="plaintext_week_description"></a>plaintext_week_description

Returns a plaintext description of the schedules of a week.
This method takes either a `datetime.date` object or a list of `datetime.date` objects.
In the first case, it is converted into a list of the days in the same week.
It can also take no parameter, so the described week will be the current one.

```python
>>> hohr.plaintext_week_description()
"""
Monday: 08:00 - 19:00
Tuesday: 08:00 - 19:00
Wednesday: 08:00 - 19:00
Thursday: 08:00 - 19:00
Friday: 08:00 - 19:00
Saturday: 08:00 - 12:00
Sunday: closed
"""
```

## Objects

Apart the main HumanizedOpeningHours class, HOH provides four other objects:
- `Day` : a weekday, or public or schoold holidays;
- `Period` : a period with two `Moment` objects : a beginning and an end;
- `MomentKind` : the kind of a period;
- `Moment` : a moment in time, which can be a beginning or an end of a period.

### <a name="day"></a>Day

Attributes:
- `periods` (list) : a list of `Period` objects included in this day;
- `date` (datetime.date) : the date of the day.

```python
# To know whether there is / are opening period(s) in this day.
>>> day.opens_today()
True
```

You can get a Day in two ways. Firstly with the `get_day()` method of OHParser, which takes a `datetime.date` object.
You can also use slicing with `datetime.date` object(s). It also supports stepping (with an integer).

```python
>>> oh[datetime.date.today()]
'<Day 'Mo' (2 periods)>'

>>> oh[datetime.date(2018, 1, 1):datetime.date(2018, 1, 3)]
['<Day 'Mo' (2 periods)>', '<Day 'Tu' (2 periods)>', '<Day 'We' (2 periods)>']
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

# Supported field formats

Here are the field formats officialy supported and tested (examples).

```
24/7
Mo 10:00-20:00
Mo-Fr 10:00-20:00
Sa,Su 10:00-20:00
Su,PH off  # or "closed"
10:00-20:00
sunrise-sunset  # or "dawn" / "dusk"
(sunrise+01:00)-20:00
Jan 10:00-20:00
Jan-Feb 10:00-20:00
Jan,Dec 10:00-20:00
```

The following formats are NOT supported yet and their parsing will raise ParseErrors.

```
Jan Mo 10:00-20:00
years
weeks
easter 10:00-20:00
Su[1] 10:00-20:00
SH Mo 10:00-20:00
```

# Performances

HOH uses the module [Lark](https://github.com/erezsh/lark) (with the LALR parser) to parse the fields.
It takes about 0.0007 seconds to parse a basic field, 0.08 seconds to parse a hundred, and 0.6 for a thousand.

# Dependencies

This module requires the following modules, which can be installed with `pip3`.

```python
lark-parser
pytz
babel
```

# Licence

This module is published under the AGPLv3 license, the terms of which can be found in the [LICENCE](LICENCE) file.
