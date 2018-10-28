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
From Monday to Friday: 6:00 AM – 9:00 PM.
From Saturday to Sunday: 8:00 AM – 12:00 PM.
"""
```

**This module is in beta. It should be production ready, but some bugs or minor modifications are still possible. Don't hesitate to create an issue!**

# Table of contents

- [Installation](#installation)
  - [Dependencies](#dependencies)
- [How to use it](#how-to-use-it)
  - [Basic methods](#basic-methods)
  - [Solar hours](#solar-hours)
  - [Have nice schedules](#have-nice-schedules)
- [Supported field formats](#supported-field-formats)
- [Alternatives](#alternatives)
- [Performances](#performances)
- [Licence](#licence)

# Installation

This library is so small, you can include it directly into your project.
Also, it is available on PyPi.

    $ pip3 install osm-humanized-opening-hours

## Dependencies

This module requires the following modules, which should be automatically installed when installing HOH with `pip`.

```python
lark-parser
babel
astral
```

# How to use it

The only mandatory argument to give to the constructor is the field, which must be a string.
It can also take a `locale` argument, which can be any valid locale name. You can change it later by changing the `locale` attribute (which is, in fact, a `property`).
However, to be able to use the most of the rendering methods, it must be in `hoh.AVAILABLE_LOCALES` (a warning will be printed otherwise).

```python
>>> import humanized_opening_hours as hoh
>>> field = "Mo-Fr 06:00-21:00; Sa,Su 07:00-21:00"
>>> oh = hoh.OHParser(field)
```

If you have a GeoJSON, you can use a dedicated classmethod: `from_geojson()`, which returns an `OHParser` instance.
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

To get a list of the opening periods between to dates, you can the use `opening_periods_between()` method.
It takes two arguments, which can be `datetime.date` or `datetime.datetime` objects.
If you pass `datetime.date` objects, it will return all opening periods between these dates (inclusive).
If you pass `datetime.datetime`, the returned opening periods will be "choped" on these times.

The returned opening periods are tuples of two `datetime.datetime` objects, representing the beginning and the end of the period.

```python
>>> oh = hoh.OHParser("Mo-Fr 06:00-21:00; Sa,Su 07:00-21:00")
>>> oh.opening_periods_between(datetime.date(2018, 1, 1), datetime.date(2018, 1, 7))
[
    (datetime.datetime(2018, 1, 1, 6, 0), datetime.datetime(2018, 1, 1, 21, 0)),
    (datetime.datetime(2018, 1, 2, 6, 0), datetime.datetime(2018, 1, 2, 21, 0)),
    (datetime.datetime(2018, 1, 3, 6, 0), datetime.datetime(2018, 1, 3, 21, 0)),
    (datetime.datetime(2018, 1, 4, 6, 0), datetime.datetime(2018, 1, 4, 21, 0)),
    (datetime.datetime(2018, 1, 5, 6, 0), datetime.datetime(2018, 1, 5, 21, 0)),
    (datetime.datetime(2018, 1, 6, 7, 0), datetime.datetime(2018, 1, 6, 21, 0)),
    (datetime.datetime(2018, 1, 7, 7, 0), datetime.datetime(2018, 1, 7, 21, 0))
]
```

You can also set the `merge` parameter to True, to merge continuous opening periods.

-----

You can get a sanitized version of the field given to the constructor with the `sanitize()` function or the `field` attribute.

```python
>>> field = "mo-su 09:30-20h;jan off"
>>> print(hoh.sanitize(field))
"Mo-Su 09:30-20:00; Jan off"
```

If sanitization is the only thing you need, use HOH for this is probably overkill.
You might be interested in the [OH Sanitizer](https://github.com/rezemika/oh_sanitizer) module, or you can copy directly the code of the sanitize function in your project.

-----

If you try to parse a field which is invalid or contains a pattern which is not supported, an `humanized_opening_hours.exceptions.ParseError` (inheriting from `humanized_opening_hours.exceptions.HOHError`) will be raised.

If a field contains only a comment (like `"on appointment"`), a `CommentOnlyField` exception (inheriting from `ParseError`) will be raised.
It contains a `comment` attribute, allowing you to display it instead of the opening hours.

The `OHParser` contains an `is_24_7` attribute, which is true if the field is simply `24/7` or `00:00-24:00`, and false either.
The `next_change()` method won't try recursion if this attribute is true and will directly raise a `NextChangeRecursionError` (except if you set `max_recursion` to zero, in this case it will just return the last time of the current day).

You can check equality between two `OHParser` instances.
It will be true if both have the same field and the same location.

```python
>>> import humanized_opening_hours as hoh
>>> 
>>> oh1 = hoh.OHParser("Mo 10:00-20:00")
>>> oh2 = hoh.OHParser("Mo 10:00-20:00")
>>> oh3 = hoh.OHParser("Mo 09:00-21:00")
>>> oh1 == oh2
True
>>> oh1 == oh3
False
```

-----

The `OHParser` object contains two other attributes: `PH_dates` and `SH_dates`, which are empty lists default.
To indicate a date is a public or a school holiday, you can pass its `datetime.date` into these lists.
You can also use the [python-holidays](https://github.com/dr-prodigy/python-holidays) module to get dynamic dictionnary (which updates the year) to replace these lists.
In fact, any iterable object with a `__contains__` method (receiving `datetime.date` objects) will work.
If you have GPS coordinates and want to have a country name, you can use the [countries](https://github.com/che0/countries) module.

## Solar hours

If the field contains solar hours, here is how to deal with them.

First of all, you can easily know if you need to set them by checking the `OHParser.needs_solar_hours_setting` variable.
If one of its values is `True`, it appears in the field and you should give to HOH a mean to retrive its time.

You have to ways to do this.
The first is to give to the `OHParser` the location of the facility, to allow it to calculate solar hours.
The second is to use the `SolarHours` object (which inherits from `dict`), *via* the `OHParser.solar_hours` attribute.

```python
# First method. You can use either an 'astral.Location' object or a tuple.
location = astral.Location(["Greenwich", "England", 51.168, 0.0, "Europe/London", 24])
location = (51.168, 0.0, "Europe/London", 24)
oh = hoh.OHParser(field, location=location)

# Second method.
solar_hours = {
    "sunrise": datetime.time(8, 0), "sunset": datetime.time(20, 0),
    "dawn": datetime.time(7, 30), "dusk": datetime.time(20, 30)
}
oh.solar_hours[datetime.date.today()] = solar_hours
```

Attention, except if the facility is on the equator, this setting will be valid only for a short period (except if you provide coordinates, because they will be automatically updated).

If you try to do something with a field containing solar hours without providing a location, a `humanized_opening_hours.exceptions.SolarHoursError` exception will be raised.

In some very rare cases, it might be impossible to get solar hours.
For example, in Antactica, the sun may never reach the dawn / dusk location in the sky, so the `astral` module can't return the down time.
So, if you try to get, for example, the next change with a field containing solar hours and located in such location, a `humanized_opening_hours.exceptions.SolarHoursError` exception will also be raised.

-----

Sometimes, especially if you work with numerous fields, you may want to apply the same methods to the same field but for different locations.
To do so, you can use a dedicated method called `this_location()`, which is intended to be used as a context manager.
It allows you to temporarily set a specific location to the OHParser instance.

```python
oh = hoh.OHParser(
    "Mo-Fr sunrise-sunset",
    location=(51.168, 0.0, "Europe/London", 24)
)

str(oh.solar_hours.location) == 'Location/Region, tz=Europe/London, lat=51.17, lon=0.00'

with oh.temporary_location("Paris"):
    str(oh.solar_hours.location) == 'Paris/France, tz=Europe/Paris, lat=48.83, lon=2.33'

str(oh.solar_hours.location) == 'Location/Region, tz=Europe/London, lat=51.17, lon=0.00'
```

## Have nice schedules

You can pass any valid locale name to `OHParser`, it will work for the majority of methods, cause they only need Babel's translations.
However, the `description()` and `plaintext_week_description()` methods need more translations, so it works only with a few locales, whose list is available with `hoh.AVAILABLE_LOCALES`.
Use another one will make methods return inconsistent sentences.

Currently, the following locales are supported:

- `en`: english (default);
- `fr_FR`: french;
- `de`: deutsch;
- `nl`: dutch;
- `pl`: polish;
- `pt`: portuguese;
- `ru_RU`: russian.

-----

The `get_localized_names()` method returns a dict of lists with the names of months and weekdays in the current locale.

Example:

```python
>>> oh.get_localized_names()
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
>>> print(oh.description())
['From Monday to Friday: 10:00 AM – 7:00 PM.', 'On Saturday: 10:00 AM – 12:00 PM.', 'December 25: closed.']
>>> print('\n'.join(oh.description()))
"""
From Monday to Friday: 10:00 AM – 7:00 PM.
On Saturday: 10:00 AM – 12:00 PM.
December 25: closed.
"""
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

`get_day()` returns a `Day` object, which contains opening periods and useful methods for a day.
It can take a `datetime.date` argument to get the day you want.

The returned object contains the following attributes.

- `ohparser` (OHParser) : the OHParser instance where the object come from;
- `date` (datetime.date) : the date of the day;
- `weekday_name` (str) : the name of the day (ex: "Monday");
- `timespans` : (list[ComputedTimeSpan]) : the computed timespans of the day (containing `datetime.datetime` objects);
- `locale` (babel.Locale) : the locale given to OHParser.

Attention, the `datetime.datetime` objects in the computed timespans may be in another day, if it contains a period which spans over midnight (like `Mo-Fr 20:00-02:00`).

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
Mo-Fr 10:00+
Mo-Fr 10:00,12:00,20:00  # Does not support points in time.
```

For fields like `24/7; Su 10:00-13:00 off`, Sundays are considered as entirely closed.
This should be fixed in a later version.

# Alternatives

If you want to parse `opening_hours` fields but HOH doesn't fit your needs, here are a few other libraries which might interest you.

- [opening_hours.js](https://github.com/opening-hours/opening_hours.js/tree/master): The main library to parse these fields, but written in JS.
- [pyopening_hours](https://github.com/opening-hours/pyopening_hours): A Python implementation of the previous library.
- [simple-opening-hours](https://github.com/ubahnverleih/simple-opening-hours): Another small JS library which can parse simple fields.

# Performances

HOH uses the module [Lark](https://github.com/erezsh/lark) (with the Earley parser) to parse the fields.

It is very optimized (about 20 times faster) for the simplest fields (like `Mo-Fr 10:00-20:00`), so their parsing will be very fast:

- 0.0002 seconds for a single field;
- 0.023 seconds for a hundred;
- 0.23 seconds for a thousand.

For more complex fields (like `Jan-Feb Mo-Fr 08:00-19:00`), the parsing is slower:

- 0.006 seconds for a single field;
- 0.57 seconds for a hundred;
- 5.7 seconds for a thousand.

# Licence

This module is published under the AGPLv3 license, the terms of which can be found in the [LICENCE](LICENCE) file.
