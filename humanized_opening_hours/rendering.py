import datetime
import gettext
import os

import lark
import babel
import babel.lists
import babel.dates

from humanized_opening_hours.temporal_objects import WEEKDAYS, MONTHS


BASE_DIR = os.path.dirname(os.path.realpath(__file__))

AVAILABLE_LOCALES = ["en", "fr"]

gettext.install("hoh", "locales")

ON_WEEKDAY = True  # TODO : Relevant?


def set_locale(babel_locale):
    try:
        lang = gettext.translation(
            'hoh',
            localedir=os.path.join(BASE_DIR, "locales"),
            languages=[babel_locale.language]
        )
    except FileNotFoundError:
        lang = gettext.NullTranslations()
    lang.install()


# TODO : Put these functions into a unique class?
# TODO : Handle "datetime.time.max" (returns "23:59" instead of "24:00").
def render_time(time, babel_locale):
    """Returns a string from a Time object."""
    set_locale(babel_locale)
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
    if time.t[1] == 1:
        delta_str = babel.dates.format_timedelta(
            time.t[2], locale=babel_locale, format="short"
        )
        return {
            "sunrise": _("{time} after sunrise"),
            "sunset": _("{time} after sunset"),
            "dawn": _("{time} after dawn"),
            "dusk": _("{time} after dusk")
        }.get(time.t[0]).format(time=delta_str)
    else:
        delta_str = babel.dates.format_timedelta(
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


def join_list(l: list, babel_locale) -> str:  # pragma: no cover
    """Returns a string from a list and a locale."""
    if not l:
        return ''
    values = [str(value) for value in l]
    return babel.lists.format_list(values, locale=babel_locale)


def translate_open_closed(babel_locale):  # pragma: no cover
    set_locale(babel_locale)
    return (_("open"), _("closed"))


def translate_colon(babel_locale):  # pragma: no cover
    set_locale(babel_locale)
    return _("{}: {}")


class DescriptionTransformer(lark.Transformer):  # TODO : Specify "every days".
    # Meta
    def _install_locale(self):
        set_locale(self._locale)
    
    def _get_wday(self, wday_index: int) -> str:
        return self._human_names["days"][wday_index]
    
    def _get_month(self, month_index: int) -> str:
        return self._human_names["months"][month_index]
    
    # Main
    def time_domain(self, args):
        # TODO: Fix this creepy hack for this WTF bug with "00:00-24:00".
        if isinstance(args[0], tuple) and args[0][0] == 'TS_ONLY':
            return [_("{}: {}").format(_("Every days"), args[0][1]) + '.']
        return args
    
    def rule_sequence(self, args):
        if len(args) == 1 and not isinstance(args[0], tuple):
            return args[0][0].upper() + args[0][1:] + '.'
        elif args[0][0] == 'NO_TS':
            range_selectors = args[0][1]
            time_selector = args[1]
        else:  # "TS_ONLY"
            range_selectors = _("Every days")
            time_selector = args[0][1]
        return _("{}: {}").format(
            range_selectors, time_selector
        ) + '.'
    
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
        return _("{}: {}").format(args[0][1], args[1])
    
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
        # TODO: The year is not passed to monthday. Check 'field.ebnf'.
        month = MONTHS.index(args[0].value)+1
        monthday = int(args[1].value)
        dt = datetime.date(2000, month, monthday)
        return dt.strftime(_("%B %-d"))
    
    def monthday_date_day_to_day(self, args):
        # TODO: The year is not passed to monthday. Check 'field.ebnf'.
        month = MONTHS.index(args[0].value)+1
        monthday_from = int(args[1].value)
        monthday_to = int(args[2].value)
        dt_from = datetime.date(2000, month, monthday_from)
        dt_to = datetime.date(2000, month, monthday_to)
        return _("from {monthday1} to {monthday2}").format(
            monthday1=dt_from.strftime(_("%B %-d")),
            monthday2=dt_to.strftime(_("%B %-d"))
        )
    
    def monthday_date_month(self, args):
        # TODO: The year is not passed to monthday. Check 'field.ebnf'.
        return self._get_month(MONTHS.index(args[0].value))
    
    def monthday_date_easter(self, args):
        # TODO: The year is not passed to monthday. Check 'field.ebnf'.
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
        return args
    
    def weekday_or_holiday_sequence_selector(self, args):
        if len(args) == 1:
            return args[0]
        else:
            return _("Public and school holidays")
    
    def holiday_and_weekday_sequence_selector(self, args):
        if len(args[1]) == 1:
            return babel.lists.format_list(
                [args[0], args[1][0][1]],
                locale=self._locale
            )
        return babel.lists.format_list(
            [
                args[0],
                args[1][0][1],
                args[1][1][1]
            ],
            locale=self._locale
        )
    
    def holiday_in_weekday_sequence_selector(self, args):
        if len(args[1][0]) == 2:
            wd = args[1][0][0].format(wd=args[1][0][1])
        else:
            wd = args[1][0][0].format(wd1=args[1][0][1], wd2=args[1][0][2])
        # Translators: Example: "Public holidays, on Monday".
        return _("{holiday}, {wd}").format(holiday=args[0], wd=wd)
    
    def holiday(self, args):
        if args[0].value == "PH":
            return _("public holidays")
        else:
            return _("school holidays")
    
    # Time
    def hour_minutes(self, args):
        # Returns a tuple like (format_time, format_timedelta).
        h, m = int(args[0].value), int(args[1].value)
        if (h, m) == (24, 0):
            dt = datetime.time.max
        else:
            dt = datetime.time(h, m)
        dt = datetime.datetime.combine(
            datetime.date.today(),
            dt
        ).time()
        return (
            babel.dates.format_time(dt, locale=self._locale, format="short"),
            babel.dates.format_timedelta(
                datetime.timedelta(hours=h, minutes=m),
                locale=self._locale
            )
        )
    
    def time(self, args):
        if type(args[0]) is tuple:
            return args[0][0]
        else:
            return args[0]
    
    def timespan(self, args):
        # TODO: Use 'render_timespan'?
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
            }.get(kind).format(time=args[2][1])
        else:
            return {
                "sunrise": _("{time} before sunrise"),
                "sunset": _("{time} before sunset"),
                "dawn": _("{time} before dawn"),
                "dusk": _("{time} before dusk")
            }.get(kind).format(time=args[2][1])
    
    # Rule modifiers
    def rule_modifier_open(self, args):
        return translate_open_closed(self._locale)[0]  # TODO: Remove?
    
    def rule_modifier_closed(self, args):
        return translate_open_closed(self._locale)[1]
