import gettext
import os

import babel.lists


AVAILABLE_LOCALES = ["en", "fr"]

BASE_DIR = os.path.dirname(os.path.realpath(__file__))


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


def join_list(l: list, babel_locale) -> str:  # pragma: no cover
    """Returns a string from a list and a locale."""
    if not l:
        return ''
    values = [str(value) for value in l]
    return babel.lists.format_list(values, locale=babel_locale)


def translate_open_closed(babel_locale):
    set_locale(babel_locale)
    return (_("open"), _("closed"))


def translate_colon(babel_locale):
    set_locale(babel_locale)
    return _("{}: {}")


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
            time.t[2], locale=babel_locale, format="long", threshold=2
        )
        return {
            "sunrise": _("{time} after sunrise"),
            "sunset": _("{time} after sunset"),
            "dawn": _("{time} after dawn"),
            "dusk": _("{time} after dusk")
        }.get(time.t[0]).format(time=delta_str)
    else:
        delta_str = babel.dates.format_timedelta(
            time.t[2], locale=babel_locale, format="long", threshold=2
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
