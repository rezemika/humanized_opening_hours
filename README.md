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
On Saturday: from 08:00 to 12:00.
"""
```

**This module is still in development and bugs may occur. If you discover one, please create an issue.**

# Installation

This library is so small, you can include it directly into your project.
Also, it is available on PyPi.

    $ pip3 install osm-humanized-opening-hours

# How to use it

The only mandatory argument to give to the constructor is the field, which must be a string.
It can also take a `locale` argument, which can be any valid locale name.
However, to be able to use the `description()` method, it must be in `hoh.DESCRIPTION_LOCALES` (a warning will be printed otherwise).

```python
>>> import humanized_opening_hours as hoh
>>> field = "Mo-Fr 06:00-21:00; Sa,Su 07:00-21:00"
>>> oh = hoh.OHParser(field)
```

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
Can take a datetime.datetime moment to check for another time.
If we are on December 24 before 21:00 / 09:00PM...

```python
>>> oh.next_change()
datetime.datetime(2017, 12, 24, 21, 0)
```

For consecutive days fully open ("Mo-Fr 00:00-24:00"), it will return the first hour of the next day instead of the true next change. This should be fixed in a later version.

```python
>>> oh = hoh.OHParser("Mo-Fr 00:00-24:00")
>>> oh.next_change()
datetime.datetime(2018, 1, 8, 0, 0)
```

-----

You can get a sanitized version of the field given to the constructor with the *sanitize* staticmethod or the **sanitized_field** attribute.

```python
>>> field = "mo-su 0930-2000;jan off"
>>> print(hoh.OHParser.sanitize(field))
"Mo-Su 09:30-20:00; Jan off"
```

If you try to parse a field which is invalid or contains a pattern which is not supported, an `humanized_opening_hours.exceptions.ParseError` (inheriting from `humanized_opening_hours.exceptions.HOHError`) will be raised.

## Solar hours

If the field contains solar hours, here is how to deal with them.

First of all, you can easily know if you need to set them by checking the `OHParser.needs_solar_hours_setting` variable.
If one of its values is `True`, it appears in the field and you should give to HOH a mean to retrive its time.

You have to ways to do this.
The first is to give to the `OHParser` the location of the facility, to allow it to calculate solar hours.
The second is to use the `SolarHoursManager` object, *via* the `OHParser.solar_hours_manager` attribute.

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
oh.solar_hours_manager[datetime.date.today()] = solar_hours
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
```

The following formats are NOT supported yet and their parsing will raise a ParseError.

```
years
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
