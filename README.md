Humanized Opening Hours - A parser for the opening_hours fields from OSM
========================================================================

**Humanized Opening Hours** is a Python 3 module allowing a simple usage of the opening_hours fields used in OpenStreetMap.

Any pull request (following PEP-8) is more than welcome!

```python
>>> import humanized_opening_hours as hoh
>>> field = "Mo-Fr 06:00-21:00; Sa,Su 08:00-12:00"
>>> oh = hoh.OHParser(field, locale="en")
>>> oh.is_open()
True
>>> oh.next_change()
datetime.datetime(2017, 12, 24, 12, 0)
>>> print('\n'.join(oh.description()))
"""
From Monday to Friday: from 06:00 to 21:00.
On Saturday and Sunday: from 08:00 to 12:00.
"""
```

**This module is still in development and bugs may occur. If you discover one, please create an issue.**

# Installation

This library is so small, you can include it directly into your project.
Also, it is available on PyPi.

    $ pip3 install osm-humanized-opening-hours

# How to use it

The only mandatory argument to give to the constructor is the field, which must be a string.
It can also take a `locale` argument, which can be any valid locale name. You can change it later by changing the `locale` attribute (which is, in fact, a `property`).
However, to be able to use the `description()` method, it must be in `hoh.DESCRIPTION_LOCALES` (a warning will be printed otherwise).

```python
>>> import humanized_opening_hours as hoh
>>> field = "Mo-Fr 06:00-21:00; Sa,Su 07:00-21:00"
>>> oh = hoh.OHParser(field)
```

If you have a GeoJSON, you can a dedicated classmethod: `from_geojson()`.
It takes the GeoJSON, and optionally the following arguments:

- `timezone_getter` (callable): A function to call, which takes two arguments (latitude and longitude, as floats), and returns a timezone name or None, allowing to get solar hours for the facility;
- `locale` (str): the locale to use ("en" default).

## Basic methods

To know if the facility is open at the present time. Returns a boolean.
Can take a datetime.datetime moment to check for another time.

```python
>>> oh.is_open()
True
```

-----

To know at which time the facility status (open / closed) will change.
Returns a datetime.datetime object.
It can take a datetime.datetime moment to get next change from another time.
If we are on December 24 before 21:00 / 09:00PM...

```python
>>> oh.next_change()
datetime.datetime(2017, 12, 24, 21, 0)
```

For fields with consecutive days fully open, `next_change()` will try to get the true next change by recursion.
You can change this behavior with the `max_recursion` argument, which is set to `31` default, meaning `next_change()` will try a maximum of 31 recursions (*i.e.* 31 days, or a month) to get the true next change.
If this limit is reached, a `NextChangeRecursionError` will be raised.
You can deny recursion by setting the `max_recursion` argument to `0`.

The `NextChangeRecursionError` has a `last_change` attribute, containing the last change got just before raising of the exception.
You can get it with a `except NextChangeRecursionError as e:` block.

```python
>>> oh = hoh.OHParser("Mo-Fr 00:00-24:00")
>>> oh.next_change(dt=datetime.datetime(2018, 1, 8, 0, 0))
datetime.datetime(2018, 1, 11, 23, 59, 59, 999999)
```

-----

You can get a sanitized version of the field given to the constructor with the `sanitize()` function or the `field` attribute.

```python
>>> field = "mo-su 09:30-20h;jan off"
>>> print(hoh.sanitize(field))
"Mo-Su 09:30-20:00; Jan off"
```

-----

If you try to parse a field which is invalid or contains a pattern which is not supported, an `humanized_opening_hours.exceptions.ParseError` (inheriting from `humanized_opening_hours.exceptions.HOHError`) will be raised.

If a field contains only a comment (like `"on appointment"`), a `CommentOnlyField` exception (inheriting from `ParseError`) will be raised.
It contains a `comment` attribute, allowing you to display it instead of the opening hours.

The `OHParser` contains an `is_24_7` attribute, which is true if the field is simply `24/7` or `00:00-24:00`, and false either.
The `next_change()` method won't try recursion if this attribute is true and will directly raise a `NextChangeRecursionError` (except if you set `max_recursion` to zero, in this case it will just return the last time of the current day).

## Solar hours

If the field contains solar hours, here is how to deal with them.

First of all, you can easily know if you need to set them by checking the `OHParser.needs_solar_hours_setting` variable.
If one of its values is `True`, it appears in the field and you should give to HOH a mean to retrive its time.

You have to ways to do this.
The first is to give to the `OHParser` the location of the facility, to allow it to calculate solar hours.
The second is to use the `SolarHours` object (which inherits from `dict`), *via* the `OHParser.solar_hours` attribute.

```python
# First method. You can use either an 'astral.Location' object or a tuple.
location = astral.Location(["Greenwich", "England", 51.168, 0.0, "Europe/London", 0, 24])
location = (51.168, 0.0, "Europe/London", 0, 24)
oh = hoh.OHParser(field, location=location)

# Second method.
solar_hours = {
    "sunrise": datetime.time(8, 0), "sunset": datetime.time(20, 0),
    "dawn": datetime.time(7, 30), "dusk": datetime.time(20, 30)
}
oh.solar_hours[datetime.date.today()] = solar_hours
```

Attention, except if the facility is on the equator, this setting will be valid only for a short period (except if you provide coordinates, because they will be automatically updated).

## Have nice schedules

You can pass any valid locale name to `OHParser`, it will work for the majority of methods, cause they only need Babel's translations.
However, the `description()` method needs more translations, so it works only with a few locales, whose list is available with `hoh.DESCRIPTION_LOCALE`. Use another one will raise an exception.

-----

The `get_human_names()` method returns a dict of lists with the names of months and weekdays in the current locale.

Example:

```python
>>> ohr.get_human_names()
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

-----

`time_before_next_change()` returns a humanized delay before the next change in opening status.
Like `next_change()`, it can take a `datetime.datetime` moment to get next change from another time.

```python
>>> oh.time_before_next_change()
"in 3 hours"
>>> oh.time_before_next_change(word=False)
"3 hours"
```

-----

`description()` returns a list of strings (sentences) describing the whole field.

```python
# Field: "Mo-Fr 10:00-19:00; Sa 10:00-12:00; Dec 25 off"
>>> print(' '.join(oh.description()))
"Monday to Friday: 10:00 to 19:00. Saturday: 10:00 to 12:00. 25 December: closed."
```

-----

`plaintext_week_description()` returns a plaintext description of the opening periods of a week.
This method takes a `year` and a `weeknumber` (both `int`).
You can also specify the first day of the week with the `first_weekday` parameter (as `int`).
Its default value is `0`, meaning "Monday".

It can also take no parameter, so the described week will be the current one.

```python
>>> print(oh.plaintext_week_description(year=2018, weeknumber=1, first_weekday=0))
"""
Monday: 8:00 AM – 7:00 PM
Tuesday: 8:00 AM – 7:00 PM
Wednesday: 8:00 AM – 7:00 PM
Thursday: 8:00 AM – 7:00 PM
Friday: 8:00 AM – 7:00 PM
Saturday: 8:00 AM – 12:00 PM
Sunday: closed
"""
```

This method uses the `days_of_week()` function to get the datetimes of the days of the requested week.
It is accessible directly through the HOH namespace, and takes the same parameters.

-----

`get_day_periods()` returns a `DayPeriods` object, which is in fact a `collections.namedtuple`, which contains opening periods for a day.
It can take a `datetime.date` argument to get the day you want.

The returned namedtuple contains the following attributes.

- `weekday_name` (str) : the name of the day (ex: "Monday");
- `date` (datetime.date) : the date of the day;
- `periods` : (list[tuple(datetime.datetime, datetime.datetime)]) : the opening periods of the day, of the shape (beginning, end);
- `rendered_periods` (list[str]) : a list of strings describing the opening periods of the day;
- `joined_rendered_periods` (str) : the same list, but joined to string by comas and a terminal word (ex: "09:00 - 12:00 and 13:00 - 19:00").

Attention, the `datetime.datetime` objects in `periods` may be in another day, if it contains a period which spans over midnight (like `Mo-Fr 20:00-02:00`).

## Objects

Apart the main OHParser class, HOH provides other objects representing the parts of the field. Their names are based on the official specifications, available [here](https://wiki.openstreetmap.org/wiki/Key:opening_hours/specification).

Here are the most useful:
- `Rule` : a rule, a part of the field delimited by semicolons;
- `TimeSpan` : an opening period, containing two `Time` objects (the beginning and the end of the period);
- `Time` : a moment in time, which can be a beginning or an end of a `TimeSpan`.

### Rule

Attributes:
- `status` (str) : a string which can be `open` or `closed` (**the handling of this is not yet fully implemented**);
- `range_selectors` (RangeSelector) : an object representing the moments concerned by opening periods;
- `time_selectors` (bool) : a list of `TimeSpan` objects;
- `always_open` (bool) : True if it's open from 00:00 to 24:00, False else.

You can get a rule by two ways. The first is to access to the `rules` attribute of `OHParser`, containing all the rules of the field. The second is to use the `get_current_rule()` method, which can take a `datetime.date` object, and returns the rule corresponding to this date.

### TimeSpan

Attributes:
- `beginning` (Time object) : the beginning of the TimeSpan;
- `end` (Time object) : the end of the TimeSpan.

A TimeSpan is an opening period, with a beginning and an end. It provides an `is_open()` method, which takes a `datetime.time` object and the dict of solar hours, and returns whether it's open at the given time.

### Time

Attributes:
- `t` (tuple) : a tuple containing raw informations, probably not useful for you.

A `Time` object provides a `get_time()` method, which takes the dict of solar hours in argument and returns a not localized `datetime.time`.

# Supported field formats

Here are the field formats officialy supported and tested (examples).

```
24/7
Mo 10:00-20:00
Mo-Fr 10:00-20:00
Sa,Su 10:00-20:00
Su,PH off  # or "closed"
10:00-20:00
20:00-02:00
sunrise-sunset  # or "dawn" / "dusk"
(sunrise+01:00)-20:00
Jan 10:00-20:00
Jan-Feb 10:00-20:00
Jan,Dec 10:00-20:00
Jan Mo 10:00-20:00
Jan,Feb Mo 10:00-20:00
Jan-Feb Mo 10:00-20:00
Jan Mo-Fr 10:00-20:00
Jan,Feb Mo-Fr 10:00-20:00
Jan-Feb Mo-Fr 10:00-20:00
SH Mo 10:00-20:00
SH Mo-Fr 10:00-20:00
easter 10:00-20:00
SH,PH Mo-Fr 10:00-20:00
SH,PH Mo-Fr,Su 10:00-20:00
Jan-Feb,Aug Mo-Fr,Su 10:00-20:00
week 1 Mo 09:00-12:00
week 1-10 Su 09:00-12:00
week 1-10/2 Sa-Su 09:00-12:00
2018 Mo-Fr 10:00-20:00
2018-2022 Mo-Fr 10:00-20:00
2018-2022/2 Mo-Fr 10:00-20:00
```

The following formats are NOT supported yet and their parsing will raise a ParseError.

```
Su[1] 10:00-20:00
easter +1 day 10:00-20:00
easter +2 days 10:00-20:00
```

# Performances

HOH uses the module [Lark](https://github.com/erezsh/lark) (with the Earley parser) to parse the fields.
It takes about 0.003 seconds to parse a basic field, 0.3 seconds to parse a hundred, and 3.4 for a thousand.

# Dependencies

This module requires the following modules, which can be installed with `pip3`.

```python
lark-parser
pytz
babel
astral
```

# Licence

This module is published under the AGPLv3 license, the terms of which can be found in the [LICENCE](LICENCE) file.
