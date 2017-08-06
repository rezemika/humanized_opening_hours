Humanized Opening Hours - A parser for the opening_hours fields from OSM
========================================================================

**Humanized Opening Hours** is a Python 3 module allowing a simple usage of the opening_hours fields used in OpenStreetMap. It provides especially a function to get a good-looking opening hours description from a field.

```python
>>> import humanized_opening_hours
>>> field = "Mo-Fr 06:00-21:00; Sa,Su 07:00-21:00"
>>> hoh = HumanizedOpeningHours(field)
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

**Current version : 0.1.1**

# Installation

    $ pip3 install osm-humanized-opening-hours

# How to use it

The only mandatory argument to give to the constructor is the field, which must be a string.
You can also specify:

- `lang` (str, "en" default) : the language to use, following the ISO 639-1 standard (currently, only english and french are supported);
- `langs_dir` (str, None default) : a directory path, where you can put JSON files to have a custom translation;
- `tz` (pytz.timezone) : the timezone to use, UTC default.

```python
import humanized_opening_hours, pytz

field = "Mo-Fr 06:00-21:00; Sa,Su 07:00-21:00"

# Uses the French language and the French timezone.
hoh = HumanizedOpeningHours(field, lang="fr", tz=pytz.timezone("Europe/Paris"))
# Uses a custom translation in Kirundi.
hoh = HumanizedOpeningHours(field, lang="run", langs_dir="translation_files")
```

If you want to create a custom translation, copy and modify one of the JSON files, then name it "hoh_LANG.json" (where "LANG" is the language code, to use for the `lang` argument).

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

You can get a sanitized version of the field given to the constructor with the *sanitize* function.

```python
>>> field = "mo-su 0930-2000"
>>> print(hoh.sanitize())
Mo-Su 09:30-20:00
```

## Solar hours

If the field contains solar hours (only "sunrise" or "sunset", the others are not yet supported), here is how to deal with them.

First of all, you can easily know if you need to parse them by checking the `hoh.need_solar_hours_parsing` variable. If it is `True`, you need to parse them with a dedicated method which need to know the true solar hours.

**If you try to do something with a field requiring parsing without parse it, you will get a "NotParsedError".**

Attention, except if the facility is on the equator, this parsing will be valid only for a short period. It is recommended to rerun this function while changing its "moment" argument (or its hours).

If you know that the sun rises at six o'clock and sets at ten o'clock, you can set it like this.

```python
# Using a tuple of tuples of integers (hour, minutes) for (sunrise, sunset).
>>> hoh.parse_solar_hours(hours=((6, 0), (10, 0)))
```

If you don't know solar hours, you have two methods to set them.

```python
# If you are on Pico island (in the Azores islands)...
# Using the GPS coordinates of the facility.
>>> hoh.parse_solar_hours(coords=(38.506, -28.454))

# Using the astral module. You can pass to the "moment" argument a datetime.datetime object if you want to parse the solar hours for another date.
>>> import astral, pytz
>>> location = astral.Astral.Location("Pico Island", "Atlantic Ocean", (38.506, -28.454), pytz.timezone("Atlantic/Azores"), 100)
>>> hoh.parse_solar_hours(astral_location=location)
```

## Have nice schedules

The `stringify_week_schedules` method allows you to have a well-formated multiline string describing the opening hours of the facility.

It has a few parameters you need to know:
- `compact` (bool, False default) : not available yet (will raise an NotImplementedError), will give you a compact result;
- `holidays` (bool, True default) : will also display the opening hours on holidays (public and school ones), a blank line after the regular ones;
- `universal` (bool, True default) : will display something like "two hours before sunset" in place of "20:00" (if the sun sets at 22:00), allowing to use this function without having parsed solar hours.

```python
# Field : "Mo-Fr 06:00-21:00; Sa,Su 07:00-21:00"
>>> print(hoh.stringify_week_schedules())
Monday: 06:00 - 21:00
Tuesday: 06:00 - 21:00
Wednesday: 06:00 - 21:00
Thursday: 06:00 - 21:00
Friday: 06:00 - 21:00
Saturday: 07:00 - 21:00
Sunday: 07:00 - 21:00

# Field : "Mo-Fr 06:00-sunset; Sa,Su 07:00-21:00"
>>> print(hoh.stringify_week_schedules())
Monday: 06:00 - sunset
Tuesday: 06:00 - sunset
Wednesday: 06:00 - sunset
Thursday: 06:00 - sunset
Friday: 06:00 - sunset
Saturday: 07:00 - 21:00
Sunday: 07:00 - 21:00

# Field : "Mo-Fr 06:00-sunset; Sa,Su 07:00-21:00"
# Solar hours parsed. Sunset at 21:04.
>>> print(hoh.stringify_week_schedules(universal=False))
Monday: 06:00 - 21:04
Tuesday: 06:00 - 21:04
Wednesday: 06:00 - 21:04
Thursday: 06:00 - 21:04
Friday: 06:00 - 21:04
Saturday: 07:00 - 21:00
Sunday: 07:00 - 21:00

# Field : "Mo-Fr 06:00-(sunset+02:00); Sa,Su 07:00-21:00"
# Solar hours parsed. Sunset at 21:04.
>>> print(hoh.stringify_week_schedules())
Monday: 06:00 - 02:00 after sunset
Tuesday: 06:00 - 02:00 after sunset
Wednesday: 06:00 - 02:00 after sunset
Thursday: 06:00 - 02:00 after sunset
Friday: 06:00 - 02:00 after sunset
Saturday: 07:00 - 21:00
Sunday: 07:00 - 21:00

# Field : "Mo-Fr 06:00-(sunset+02:00); Sa,Su 07:00-21:00"
# Solar hours parsed. Sunset at 21:04.
>>> print(hoh.stringify_week_schedules(universal=False))
Monday: 06:00 - 23:04
Tuesday: 06:00 - 23:04
Wednesday: 06:00 - 23:04
Thursday: 06:00 - 23:04
Friday: 06:00 - 23:04
Saturday: 07:00 - 21:00
Sunday: 07:00 - 21:00
```

## Rendering

HOH provides a method dedicated to render into a nice string any Period or Moment object (described below).

It has three arguments:
- the object to render;
- `universal` (bool, optional, False default): as for method `stringify_week_schedules`, returns a translated string instead of an hour for solar hours.

Here are some examples.

```python
>>> hoh.render(day, universal=True)
'02:00 before sunset'

>>> hoh.render(day)
'20:30'

>>> hoh.render(moment)
'09:30 - 20:30'

>>> hoh.render(moment, universal=True)
'09:30 - 02:00 before sunset'
```

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
