import datetime
import gettext
import os

import lark
import babel
import babel.lists

from humanized_opening_hours.temporal_objects import WEEKDAYS, MONTHS


BASE_DIR = os.path.dirname(os.path.realpath(__file__))

LOCALES = {
    "en": gettext.translation(
        "HOH", os.path.join(BASE_DIR, "locales"), languages=["en"]
    ),
    "fr": gettext.translation(
        "HOH", os.path.join(BASE_DIR, "locales"), languages=["fr"]
    )
}

ON_WEEKDAY = True  # TODO : Relevant?


# TODO : Put these functions into a unique class?
# TODO : Handle "datetime.time.max" (returns "23:59" instead of "24:00").
def render_time(time, babel_locale):
    """Returns a string from a Time object."""
    LOCALES.get(babel_locale.language).install()
    if time.t[0] == "normal":
        return babel.dates.format_time(
            time.t[1], locale=babel_locale, format="short"
        )
    if time.t[2].total_seconds() == 0:
        return {
            "sunrise": _("sunrise"),
            "sunset": _("sunset"),
            "dawn": _("dawn"),
            "dusk": _("dusk")
        }.get(time.t[0])
    if time.t[1] == '+':
        delta_str = babel.dates.format_time(
            time.t[2], locale=babel_locale, format="short"
        )
        return {
            "sunrise": _("{time} after sunrise"),
            "sunset": _("{time} after sunset"),
            "dawn": _("{time} after dawn"),
            "dusk": _("{time} after dusk")
        }.get(time.t[0]).format(time=delta_str)
    else:
        delta_str = babel.dates.format_time(
            time.t[2], locale=babel_locale, format="short"
        )
        return {
            "sunrise": _("{time} before sunrise"),
            "sunset": _("{time} before sunset"),
            "dawn": _("{time} before dawn"),
            "dusk": _("{time} before dusk")
        }.get(time.t[0]).format(time=delta_str)


def render_timespan(timespan, babel_locale):
    """Returns a string from a TimeSpan object and a locale."""
    return babel_locale.interval_formats[None].format(
        render_time(timespan.beginning, babel_locale),
        render_time(timespan.end, babel_locale)
    )


def join_list(l: list, babel_locale) -> str:
    """Returns a string from a list and a locale."""
    if not l:
        return ''
    values = [str(value) for value in l]
    return babel.lists.format_list(l, locale=babel_locale)


def translate_open_closed(babel_locale):
    LOCALES.get(babel_locale.language).install()
    return (_("open"), _("closed"))


def translate_colon(babel_locale):
    LOCALES.get(babel_locale.language).install()
    return _("{left}: {right}")


class DescriptionTransformer(lark.Transformer):  # TODO : Specify "every days".
    # Meta
    def _install_locale(self):
        LOCALES.get(self._locale.language).install()
    
    def _get_wday(self, wday_index: int) -> str:
        return self._human_names["days"][wday_index]
    
    def _get_month(self, month_index: int) -> str:
        return self._human_names["months"][month_index]
    
    # Main
    def time_domain(self, args):
        return args
    
    def rule_sequence(self, args):  # TODO : Handle "Mo-Fr" (raises IndexError).
        if len(args) == 1 and not isinstance(args[0], tuple):
            return args[0][0].upper() + args[0][1:] + '.'
        else:
            if isinstance(args[0], tuple):
                if args[0][0] == 'NO_TS':
                    range_selectors = args[0][1]
                    time_selector = args[1]
                else:
                    range_selectors = _("Every days")
                    time_selector = args[0][1]
            else:
                range_selectors = args[0][0].upper()+args[0][1:]
                time_selector = args[0][1:]
            return _("{range_selectors}: {time_selector}.").format(
                range_selectors=range_selectors,
                time_selector=time_selector
            )
    
    def always_open(self, args):
        return _("open 24 hours a day and 7 days a week")
    
    def range_selectors(self, args):
        descriptions = []
        for i, selector in enumerate(args):
            if type(selector) is list:  # TODO : Clean.
                selector = selector[0]
            if isinstance(selector, tuple):
                if len(selector) == 3:
                    descriptions.append(selector[0].format(
                        wd1=selector[1], wd2=selector[2]
                    ))
                elif i == 0 and ON_WEEKDAY:
                    descriptions.append(selector[0].format(wd=selector[1]))
                else:
                    descriptions.append(selector[1])
            else:
                descriptions.append(selector)
        # TODO: Use 'babel.lists.format_list(style="unit")'?
        output = ', '.join(descriptions)
        output = output[0].upper() + output[1:]
        return ('RS', output)
    
    def selector_sequence(self, args):
        if len(args) == 1:
            if isinstance(args[0], tuple):
                return ('NO_TS', args[0][1])
            else:
                return ('TS_ONLY', args[0])
        return args[0][1] + _(': ') + args[1]
    
    # Monthday range
    def monthday_selector(self, args):
        return join_list(args, self._locale)
    
    def monthday_range(self, args):
        if len(args) == 1:  # "Dec 25"
            return args[0]
        else:  # "Jan 1-Feb 1"
            return _("from {monthday1} to {monthday2}").format(
                monthday1=args[0],
                monthday2=args[1]
            )
    
    # Dates
    def monthday_date_monthday(self, args):
        year = args.pop(0) if len(args) == 3 else None
        month = MONTHS.index(args[0].value)+1
        monthday = int(args[1].value)
        if year:
            dt = datetime.date(year, month, monthday)
            return dt.strftime(_("%B %-d %Y"))
        else:
            dt = datetime.date(2000, month, monthday)
            return dt.strftime(_("%B %-d"))
    
    def monthday_date_day_to_day(self, args):
        year = args.pop(0) if len(args) == 4 else None
        month = MONTHS.index(args[0].value)+1
        monthday_from = int(args[1].value)
        monthday_to = int(args[2].value)
        dt_from = datetime.date(2000, month, monthday_from)
        dt_to = datetime.date(2000, month, monthday_to)
        if year:
            return _("in {year}, from {monthday1} to {monthday2}").format(
                year=year,
                monthday1=dt_from.strftime(_("%B %-d")),
                monthday2=dt_to.strftime(_("%B %-d"))
            )
        else:
            return _("from {monthday1} to {monthday2}").format(
                monthday1=dt_from.strftime(_("%B %-d")),
                monthday2=dt_to.strftime(_("%B %-d"))
            )
    
    def monthday_date_month(self, args):
        year = args.pop(0) if len(args) == 3 else None
        month = self._get_month(MONTHS.index(args[0].value))
        if year:
            return _("in {year}, in {month}").format(
                year=year, month=month
            )
        else:
            return month
    
    def monthday_date_easter(self, args):
        year = args.pop(0) if len(args) == 3 else None
        if year:
            return _("in {year}, on easter").format(year=year)
        else:
            return _("on easter")
    
    # Week
    def week_selector(self, args):
        return join_list(args[1:], self._locale)
    
    def week(self, args):
        if len(args) == 1:
            return _("week {n}").format(n=args[0])
        elif len(args) == 2:
            return _("from week {week1} to week {week2}").format(
                week1=args[0], week2=args[1]
            )
        elif len(args) == 3:
            return _(
                "from week {week1} to week {week2}, every {n} weeks"
            ).format(
                week1=args[0], week2=args[1], n=args[2].value
            )
    
    def weeknum(self, args):
        return args[0].value
    
    # Year
    def year(self, args):
        return args[0].value
    
    def year_range(self, args):
        if len(args) == 1:
            return args[0]
        elif len(args) == 2:
            return _("from {year1} to {year2}").format(
                year1=args[0], year2=args[1]
            )
        elif len(args) == 3:
            return _("from {year1} to {year2}, every {n} years").format(
                year1=args[0], year2=args[1], n=args[2].value
            )
    
    def year_selector(self, args):
        return join_list(args, self._locale)
    
    # Weekdays
    def weekday_range(self, args):
        if len(args) == 1:
            return (  # ("On weekday", "weekday")
                _("on {wd}"),
                self._get_wday(WEEKDAYS.index(args[0]))
            )
        first_day = self._get_wday(WEEKDAYS.index(args[0]))
        last_day = self._get_wday(WEEKDAYS.index(args[1]))
        return (_("from {wd1} to {wd2}"), first_day, last_day)
    
    def weekday_sequence(self, args):
        # TODO : Fix this hack.
        if len(args) != 1:
            weekdays = [t[1] for t in args]
            return (_("on {wd}"), join_list(weekdays, self._locale))
        return args
    
    def weekday_or_holiday_sequence_selector(self, args):
        if len(args) == 1:
            return args[0]
        else:
            return _("Public and school holidays")
    
    def holiday_and_weekday_sequence_selector(self, args):
        if type(args[0]) == str:
            return args[0] + _(" and ") + args[1]
        else:
            return args[0][0][0].format(wd=args[0][0][1]) + _(" and ") + args[1]
    
    def holiday_in_weekday_sequence_selector(self, args):
        if len(args[1][0]) == 2:
            wd = args[1][0][0].format(wd=args[1][0][1])
        else:
            wd = args[1][0][0].format(wd1=args[1][0][1], wd2=args[1][0][2])
        return _("{holiday}, {wd}").format(holiday=args[0], wd=wd)
    
    def holiday(self, args):
        if args[0].value == "PH":
            return _("public holidays")
        else:
            return _("school holidays")
    
    # Time
    def hour_minutes(self, args):
        h, m = int(args[0].value), int(args[1].value)
        if (h, m) == (24, 0):
            dt = datetime.time.max
        else:
            dt = datetime.time(h, m)
        dt = datetime.datetime.combine(
            datetime.date.today(),
            dt
        )
        return dt.strftime("%H:%M")
    
    def time(self, args):
        return args[0]
    
    def timespan(self, args):
        return _("from {} to {}").format(args[0], args[1])
    
    def time_selector(self, args):
        return join_list(args, self._locale)
    
    def variable_time(self, args):
        # ("event", "offset_sign", "hour_minutes")
        kind = args[0].value
        if len(args) == 1:
            return {
                "sunrise": _("sunrise"),
                "sunset": _("sunset"),
                "dawn": _("dawn"),
                "dusk": _("dusk")
            }.get(kind)
        offset_sign = 1 if args[1].value == '+' else -1
        if offset_sign:
            return {
                "sunrise": _("{time} after sunrise"),
                "sunset": _("{time} after sunset"),
                "dawn": _("{time} after dawn"),
                "dusk": _("{time} after dusk")
            }.get(kind).format(time=args[2])
        else:
            return {
                "sunrise": _("{time} before sunrise"),
                "sunset": _("{time} before sunset"),
                "dawn": _("{time} before dawn"),
                "dusk": _("{time} before dusk")
            }.get(kind).format(time=args[2])
    
    # Rule modifiers
    def rule_modifier_open(self, args):
        return translate_open_closed(self._locale)[0]  # TODO: Remove?
    
    def rule_modifier_closed(self, args):
        return translate_open_closed(self._locale)[1]
