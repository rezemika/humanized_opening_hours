"""Provides validators that raise exceptions in case of invalid field."""

import re

from temporal_objects import WEEKDAYS, MONTHS
from exceptions import (
    ParseError,
    DoesNotExistError,
)

ALL_DAYS = WEEKDAYS + ("SH", "PH")

RE_DAYS = '(?:' + '|'.join(ALL_DAYS) + ')'
RE_MONTHS = '(?:' + '|'.join(MONTHS) + ')'

META = ("open", "off", "closed", "24/7")


def validate_field(field):
    splited_field = [part.strip() for part in field.split(';')]
    for part in splited_field:
        # Not supported yet.
        if part.startswith("year"):
            continue
        if part in META:
            continue
        validate_part(part)
    return


def validate_part(part):
    if re.match("{months} [0-9]+: .+".format(months=RE_MONTHS), part):
        rest = re.findall(
            "{months} [0-9]+: (.+)".format(months=RE_MONTHS), part
        )[0]
        if rest in ["open", "closed", "off", "closed"]:
            return
        validate_rest(rest)
        return
    if part[:2].isdigit():
        validate_rest(part)
        return
    concerned_period, rest = part.split(' ', 1)
    # "Jan Mo 10:00-12:00"
    for word in WEEKDAYS:
        if rest.startswith(word):
            rest = rest[len(word):]
    validate_concerned_period(concerned_period, rest)
    if rest in META:
        return
    if '||' in part:
        parts = [p.strip() for p in part.split('||')]
        for p in parts:
            validate_fallback(p)
        return
    if '[' in part:
        return
    validate_rest(rest)
    return


def validate_fallback(fallback):
    if fallback.startswith('"') and fallback.endswith('"'):
        return
    validate_part(fallback)


def validate_concerned_period(field, rest):
    if re.match("{days}(-{days})?(,{days})*".format(days=RE_DAYS), field):
        return
    if re.match(
        "{months}(-{months})?(,{months})*".format(months=RE_MONTHS), field
    ):
        return
    if field.startswith("week"):
        # TODO : Improve.
        if re.match("[1-9][0-9]?(/[1-9][0-9]?)?( .+)?", rest):
            return
        raise ParseError(
            "Error with the part {part!r}: a week indexing must "
            "give a valid index.".format(part=rest)
        )
        return
    raise DoesNotExistError(
        "The part {part!r} does not exist.".format(part=field)
    )


def validate_rest(field):
    for word in ["open", "closed", "off", "closed"]:
        field = rchop(field, word).strip()
    
    if re.match("[0-9]{1,2}(/[0-9]{1,2})?", field):
        return
    for part in field.split(','):
        # Prevents bugs for "(sunrise-02:00)".
        moments = re.split("-(?![^\(]*\))", part)
        for moment in moments:
            validate_moment(moment)
    return


def validate_moment(moment):
    if re.match("([0-9]{2}|sunrise|sunset|dawn|dusk):([0-9]{2}|sunrise|sunset|dawn|dusk)", moment):  # noqa
        return
    if moment in ["(sunrise)", "(sunset)", "(dawn)", "(dusk)"]:
        raise ParseError("The part {part!r} is invalid.".format(part=moment))
    if moment in ["sunrise", "sunset", "dawn", "dusk"]:
        return
    if re.match("\((sunrise|sunset|dawn|dusk)(\+|-)([0-9][0-9]):([0-9][0-9])\)", moment):  # noqa
        return
    raise ParseError("The part {part!r} is invalid.".format(part=moment))


def rchop(string, end):
    # See https://stackoverflow.com/a/3663505
    if string.endswith(end):
        return string[:-len(end)]
    return string
