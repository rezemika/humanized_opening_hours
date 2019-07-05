import unittest
import datetime
import copy

from lark import Tree
from lark.lexer import Token
import astral

from humanized_opening_hours import field_parser
from humanized_opening_hours.main import (
    OHParser, sanitize, days_of_week, DayPeriods
)
from humanized_opening_hours.frequent_fields import parse_simple_field
from humanized_opening_hours.temporal_objects import easter_date
from humanized_opening_hours.exceptions import (
    HOHError,
    ParseError,
    SolarHoursError,
    AlwaysClosed,
    CommentOnlyField,
    NextChangeRecursionError
)

# flake8: noqa: F841
# "oh" variables unused in TestSolarHours.

unittest.util._MAX_LENGTH = 1000

PARSER_TREE = field_parser.get_parser()


class TestGlobal(unittest.TestCase):
    maxDiff = None
    SOLAR_HOURS = {
        "dawn": datetime.time(7, 30),
        "sunrise": datetime.time(8, 0),
        "sunset": datetime.time(21, 30),
        "dusk": datetime.time(22, 0),
    }
    
    def test_1(self):
        field = "Mo-Sa 09:00-19:00"
        oh = OHParser(field)
        dt = datetime.datetime(2017, 1, 2, 15, 30)
        # Is it open?
        self.assertTrue(oh.is_open(dt))
        self.assertTrue(oh.rules[0].get_status_at(dt, self.SOLAR_HOURS))
        self.assertFalse(
            oh.rules[0].get_status_at(
                datetime.datetime(2017, 1, 2, 20, 0),
                self.SOLAR_HOURS
            )
        )
        # Day periods.
        day = oh.get_day(datetime.date(2018, 1, 1))
        self.assertEqual(
            day.weekday_name,
            "Monday"
        )
        self.assertEqual(
            day.opening_periods(),
            [(
                datetime.datetime(2018, 1, 1, 9, 0),
                datetime.datetime(2018, 1, 1, 19, 0)
            )]
        )
        self.assertEqual(
            day.render_periods(join=False),
            ["9:00 AM – 7:00 PM"]
        )
        self.assertEqual(
            day.render_periods(join=True),
            "9:00 AM – 7:00 PM"
        )
        # Opening periods
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 7)
            ),
            [
                (datetime.datetime(2018, 1, 1, 9, 0), datetime.datetime(2018, 1, 1, 19, 0)),
                (datetime.datetime(2018, 1, 2, 9, 0), datetime.datetime(2018, 1, 2, 19, 0)),
                (datetime.datetime(2018, 1, 3, 9, 0), datetime.datetime(2018, 1, 3, 19, 0)),
                (datetime.datetime(2018, 1, 4, 9, 0), datetime.datetime(2018, 1, 4, 19, 0)),
                (datetime.datetime(2018, 1, 5, 9, 0), datetime.datetime(2018, 1, 5, 19, 0)),
                (datetime.datetime(2018, 1, 6, 9, 0), datetime.datetime(2018, 1, 6, 19, 0))
            ]
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 7),
                merge=True
            ),
            [
                (datetime.datetime(2018, 1, 1, 9, 0), datetime.datetime(2018, 1, 1, 19, 0)),
                (datetime.datetime(2018, 1, 2, 9, 0), datetime.datetime(2018, 1, 2, 19, 0)),
                (datetime.datetime(2018, 1, 3, 9, 0), datetime.datetime(2018, 1, 3, 19, 0)),
                (datetime.datetime(2018, 1, 4, 9, 0), datetime.datetime(2018, 1, 4, 19, 0)),
                (datetime.datetime(2018, 1, 5, 9, 0), datetime.datetime(2018, 1, 5, 19, 0)),
                (datetime.datetime(2018, 1, 6, 9, 0), datetime.datetime(2018, 1, 6, 19, 0))
            ]
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.datetime(2018, 1, 1, 10, 0),
                datetime.datetime(2018, 1, 3, 18, 0)
            ),
            [
                (datetime.datetime(2018, 1, 1, 10, 0), datetime.datetime(2018, 1, 1, 19, 0)),
                (datetime.datetime(2018, 1, 2, 9, 0), datetime.datetime(2018, 1, 2, 19, 0)),
                (datetime.datetime(2018, 1, 3, 9, 0), datetime.datetime(2018, 1, 3, 18, 0))
            ]
        )
        # Rendering
        self.assertEqual(
            oh.plaintext_week_description(),
            "Monday: 9:00 AM – 7:00 PM\nTuesday: 9:00 AM – 7:00 PM\n"
            "Wednesday: 9:00 AM – 7:00 PM\nThursday: 9:00 AM – 7:00 PM\n"
            "Friday: 9:00 AM – 7:00 PM\nSaturday: 9:00 AM – 7:00 PM\n"
            "Sunday: closed"
        )
    
    def test_2(self):
        field = "Mo,Th 09:00-12:00,13:00-19:00"
        oh = OHParser(field)
        # Is it open?
        dt = datetime.datetime(2016, 2, 1, 15, 30)
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2016, 2, 1, 19, 30)
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2016, 2, 1, 12, 10)
        self.assertFalse(oh.is_open(dt))
        # Next change.  # TODO : Check this.
        dt = datetime.datetime(2018, 6, 4, 12, 10)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 6, 4, 13, 0)
        )
        self.assertEqual(
            oh.time_before_next_change(dt),
            "in 50 minutes"
        )
        self.assertEqual(
            oh.time_before_next_change(dt, word=False),
            "50 minutes"
        )
        # Day periods.
        day = oh.get_day(datetime.date(2018, 1, 1))
        self.assertEqual(
            day.weekday_name,
            "Monday"
        )
        self.assertEqual(
            day.opening_periods(),
            [
                (
                    datetime.datetime(2018, 1, 1, 9, 0),
                    datetime.datetime(2018, 1, 1, 12, 0)
                ),
                (
                    datetime.datetime(2018, 1, 1, 13, 0),
                    datetime.datetime(2018, 1, 1, 19, 0)
                )
            ]
        )
        self.assertEqual(
            day.render_periods(join=False),
            ["9:00 AM – 12:00 PM", "1:00 PM – 7:00 PM"]
        )
        self.assertEqual(
            day.render_periods(join=True),
            "9:00 AM – 12:00 PM and 1:00 PM – 7:00 PM"
        )
        # Opening periods
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 7)
            ),
            [
                (datetime.datetime(2018, 1, 1, 9, 0), datetime.datetime(2018, 1, 1, 12, 0)),
                (datetime.datetime(2018, 1, 1, 13, 0), datetime.datetime(2018, 1, 1, 19, 0)),
                (datetime.datetime(2018, 1, 4, 9, 0), datetime.datetime(2018, 1, 4, 12, 0)),
                (datetime.datetime(2018, 1, 4, 13, 0), datetime.datetime(2018, 1, 4, 19, 0))
            ]
        )
        # Rendering
        self.assertEqual(
            oh.plaintext_week_description(),
            "Monday: 9:00 AM – 12:00 PM and 1:00 PM – 7:00 PM\n"
            "Tuesday: closed\nWednesday: closed\n"
            "Thursday: 9:00 AM – 12:00 PM and 1:00 PM – 7:00 PM\n"
            "Friday: closed\nSaturday: closed\nSunday: closed"
        )
    
    def test_3(self):
        field = "24/7"
        oh = OHParser(field)
        # Is it open?
        dt = datetime.datetime(2016, 2, 1, 15, 30)
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2016, 2, 1, 19, 30)
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2016, 2, 1, 12, 10)
        self.assertTrue(oh.is_open(dt))
        # Next change
        dt = datetime.datetime(2018, 1, 1, 10, 0)
        self.assertEqual(
            oh.next_change(dt, max_recursion=0),
            datetime.datetime.combine(
                datetime.date(2018, 1, 1), datetime.time.max
            )
        )
        with self.assertRaises(NextChangeRecursionError) as context:
            oh.next_change(dt, max_recursion=10)
        # Periods
        now = datetime.datetime.now()
        self.assertEqual(
            (
                oh.get_current_rule(now.date())
                .time_selectors[0].beginning.get_time(self.SOLAR_HOURS, now)
            ),
            datetime.datetime.combine(now.date(), datetime.time.min)
        )
        with self.assertRaises(NextChangeRecursionError) as context:
            _ = oh.next_change()
    
    def test_4(self):
        field = "Mo-Fr 00:00-24:00"
        oh = OHParser(field)
        # Is it open?
        dt = datetime.datetime(2018, 1, 1, 10, 0)
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 5, 10, 0)
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 6, 10, 0)
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 7, 10, 0)
        self.assertFalse(oh.is_open(dt))
        # Opening periods
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 7)
            ),
            [
                (datetime.datetime(2018, 1, 1, 0, 0), datetime.datetime.combine(datetime.date(2018, 1, 1), datetime.time.max)),
                (datetime.datetime(2018, 1, 2, 0, 0), datetime.datetime.combine(datetime.date(2018, 1, 2), datetime.time.max)),
                (datetime.datetime(2018, 1, 3, 0, 0), datetime.datetime.combine(datetime.date(2018, 1, 3), datetime.time.max)),
                (datetime.datetime(2018, 1, 4, 0, 0), datetime.datetime.combine(datetime.date(2018, 1, 4), datetime.time.max)),
                (datetime.datetime(2018, 1, 5, 0, 0), datetime.datetime.combine(datetime.date(2018, 1, 5), datetime.time.max)),
            ]
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 7),
                merge=True
            ),
            [
                (datetime.datetime(2018, 1, 1, 0, 0), datetime.datetime.combine(datetime.date(2018, 1, 5), datetime.time.max))
            ]
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 8),
                merge=True
            ),
            [
                (datetime.datetime(2018, 1, 1, 0, 0), datetime.datetime.combine(datetime.date(2018, 1, 5), datetime.time.max)),
                (datetime.datetime(2018, 1, 8, 0, 0), datetime.datetime.combine(datetime.date(2018, 1, 8), datetime.time.max))
            ]
        )
        # Periods
        dt = datetime.datetime(2018, 1, 1, 10, 0)
        self.assertEqual(
            len(oh.get_current_rule(dt).time_selectors),
            1
        )
        self.assertEqual(
            (
                oh.get_current_rule(dt.date())
                .time_selectors[0].beginning.get_time(self.SOLAR_HOURS, dt)
            ),
            datetime.datetime.combine(dt.date(), datetime.time.min)
        )
        # Next change
        dt = datetime.datetime(2018, 1, 7, 10, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 1, 8, 0, 0)
        )
        
        self.assertEqual(
            oh.time_before_next_change(dt),
            "in 14 hours"
        )
        self.assertEqual(
            oh.time_before_next_change(dt, word=False),
            "14 hours"
        )
        
        dt = datetime.datetime(2018, 1, 8, 10, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime.combine(
                datetime.date(2018, 1, 12), datetime.time.max
            )
        )
        self.assertEqual(
            oh.next_change(dt, max_recursion=0),
            datetime.datetime.combine(
                datetime.date(2018, 1, 8), datetime.time.max
            )
        )
        
        with self.assertRaises(NextChangeRecursionError) as context:
            dt = datetime.datetime(2018, 1, 1, 10, 0)
            oh.next_change(dt, max_recursion=3)
    
    def test_5(self):
        field = "Mo-Fr 19:00-02:00"
        oh = OHParser(field)
        # Is it open?
        dt = datetime.datetime(2018, 1, 1, 10, 0)
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 1, 20, 0)
        self.assertTrue(oh.is_open(dt))
        
        dt = datetime.datetime(2018, 1, 6, 1, 0)
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 6, 3, 0)
        self.assertFalse(oh.is_open(dt))
        # Day periods.
        day = oh.get_day(datetime.date(2018, 1, 1))
        self.assertEqual(
            day.weekday_name,
            "Monday"
        )
        self.assertEqual(
            day.opening_periods(),
            [
                (
                    datetime.datetime(2018, 1, 1, 19, 0),
                    datetime.datetime(2018, 1, 2, 2, 0)
                )
            ]
        )
        self.assertEqual(
            day.render_periods(join=False),
            ["7:00 PM – 2:00 AM"]
        )
        self.assertEqual(
            day.render_periods(join=True),
            "7:00 PM – 2:00 AM"
        )
        # Opening periods
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 7)
            ),
            [
                (datetime.datetime(2018, 1, 1, 19, 0), datetime.datetime(2018, 1, 2, 2, 0)),
                (datetime.datetime(2018, 1, 2, 19, 0), datetime.datetime(2018, 1, 3, 2, 0)),
                (datetime.datetime(2018, 1, 3, 19, 0), datetime.datetime(2018, 1, 4, 2, 0)),
                (datetime.datetime(2018, 1, 4, 19, 0), datetime.datetime(2018, 1, 5, 2, 0)),
                (datetime.datetime(2018, 1, 5, 19, 0), datetime.datetime(2018, 1, 6, 2, 0))
            ]
        )
        # Periods
        dt = datetime.datetime(2018, 1, 1, 10, 0)
        self.assertEqual(
            len(oh.get_current_rule(dt.date()).time_selectors),
            1
        )
        self.assertEqual(
            (
                oh.get_current_rule(dt.date())
                .time_selectors[0].beginning.get_time(self.SOLAR_HOURS, dt)
            ),
            datetime.datetime.combine(dt.date(), datetime.time(19, 0))
        )
        # Next change
        dt = datetime.datetime(2018, 1, 7, 10, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 1, 8, 19, 0)
        )
        
        dt = datetime.datetime(2018, 1, 8, 10, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 1, 8, 19, 0)
        )
        
        dt = datetime.datetime(2018, 1, 8, 21, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 1, 9, 2, 0)
        )
    
    def test_6(self):
        field = "week 1 Mo-Fr 10:00-20:00; week 2-3 Mo-Fr 08:00-19:00"
        oh = OHParser(field)
        # Is it open?
        dt = datetime.datetime(2018, 1, 1, 9, 0)
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 1, 10, 0)
        self.assertTrue(oh.is_open(dt))
        
        dt = datetime.datetime(2018, 1, 8, 7, 0)
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 8, 9, 0)
        self.assertTrue(oh.is_open(dt))
        # Day periods.
        day = oh.get_day(datetime.date(2018, 1, 1))
        self.assertEqual(
            day.weekday_name,
            "Monday"
        )
        self.assertEqual(
            day.opening_periods(),
            [
                (
                    datetime.datetime(2018, 1, 1, 10, 0),
                    datetime.datetime(2018, 1, 1, 20, 0)
                )
            ]
        )
        self.assertEqual(
            day.render_periods(join=False),
            ["10:00 AM – 8:00 PM"]
        )
        self.assertEqual(
            day.render_periods(join=True),
            "10:00 AM – 8:00 PM"
        )
        # Opening periods
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 7)
            ),
            [
                (datetime.datetime(2018, 1, 1, 10, 0), datetime.datetime(2018, 1, 1, 20, 0)),
                (datetime.datetime(2018, 1, 2, 10, 0), datetime.datetime(2018, 1, 2, 20, 0)),
                (datetime.datetime(2018, 1, 3, 10, 0), datetime.datetime(2018, 1, 3, 20, 0)),
                (datetime.datetime(2018, 1, 4, 10, 0), datetime.datetime(2018, 1, 4, 20, 0)),
                (datetime.datetime(2018, 1, 5, 10, 0), datetime.datetime(2018, 1, 5, 20, 0))
            ]
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 8),
                datetime.date(2018, 1, 12)
            ),
            [
                (datetime.datetime(2018, 1, 8, 8, 0), datetime.datetime(2018, 1, 8, 19, 0)),
                (datetime.datetime(2018, 1, 9, 8, 0), datetime.datetime(2018, 1, 9, 19, 0)),
                (datetime.datetime(2018, 1, 10, 8, 0), datetime.datetime(2018, 1, 10, 19, 0)),
                (datetime.datetime(2018, 1, 11, 8, 0), datetime.datetime(2018, 1, 11, 19, 0)),
                (datetime.datetime(2018, 1, 12, 8, 0), datetime.datetime(2018, 1, 12, 19, 0))
            ]
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 22),
                datetime.date(2018, 1, 28)
            ),
            []
        )
        # Periods
        dt = datetime.datetime(2018, 1, 1, 10, 0)
        self.assertEqual(
            len(oh.get_current_rule(dt.date()).time_selectors),
            1
        )
        self.assertEqual(
            (
                oh.get_current_rule(dt.date())
                .time_selectors[0].beginning.get_time(self.SOLAR_HOURS, dt)
            ),
            datetime.datetime.combine(dt.date(), datetime.time(10, 0))
        )
        # Next change
        dt = datetime.datetime(2018, 1, 7, 10, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 1, 8, 8, 0)
        )
        
        dt = datetime.datetime(2018, 1, 8, 10, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 1, 8, 19, 0)
        )
        
        dt = datetime.datetime(2018, 1, 8, 21, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 1, 9, 8, 0)
        )
    
    def test_7(self):
        field = "Mo-Fr 10:00-20:00; Jul-Aug Sa-Su 10:00-12:00; Dec off"
        oh = OHParser(field)
        # Is it open?
        dt = datetime.datetime(2018, 1, 1, 9, 0)
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 1, 10, 0)
        self.assertTrue(oh.is_open(dt))
        
        # TODO: Check in specifications if it's correct.
        dt = datetime.datetime(2018, 7, 2, 9, 0)
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2018, 7, 2, 10, 0)
        self.assertTrue(oh.is_open(dt))
        
        dt = datetime.datetime(2018, 7, 7, 9, 0)
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2018, 7, 7, 10, 0)
        self.assertTrue(oh.is_open(dt))
        # Day periods.
        day = oh.get_day(datetime.date(2018, 1, 1))
        self.assertEqual(
            day.weekday_name,
            "Monday"
        )
        self.assertEqual(
            day.opening_periods(),
            [
                (
                    datetime.datetime(2018, 1, 1, 10, 0),
                    datetime.datetime(2018, 1, 1, 20, 0)
                )
            ]
        )
        self.assertEqual(
            day.render_periods(join=False),
            ["10:00 AM – 8:00 PM"]
        )
        self.assertEqual(
            day.render_periods(join=True),
            "10:00 AM – 8:00 PM"
        )
        # Opening periods
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 7)
            ),
            [
                (datetime.datetime(2018, 1, 1, 10, 0), datetime.datetime(2018, 1, 1, 20, 0)),
                (datetime.datetime(2018, 1, 2, 10, 0), datetime.datetime(2018, 1, 2, 20, 0)),
                (datetime.datetime(2018, 1, 3, 10, 0), datetime.datetime(2018, 1, 3, 20, 0)),
                (datetime.datetime(2018, 1, 4, 10, 0), datetime.datetime(2018, 1, 4, 20, 0)),
                (datetime.datetime(2018, 1, 5, 10, 0), datetime.datetime(2018, 1, 5, 20, 0))
            ]
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 7, 2),
                datetime.date(2018, 7, 8)
            ),
            [
                (datetime.datetime(2018, 7, 2, 10, 0), datetime.datetime(2018, 7, 2, 20, 0)),
                (datetime.datetime(2018, 7, 3, 10, 0), datetime.datetime(2018, 7, 3, 20, 0)),
                (datetime.datetime(2018, 7, 4, 10, 0), datetime.datetime(2018, 7, 4, 20, 0)),
                (datetime.datetime(2018, 7, 5, 10, 0), datetime.datetime(2018, 7, 5, 20, 0)),
                (datetime.datetime(2018, 7, 6, 10, 0), datetime.datetime(2018, 7, 6, 20, 0)),
                (datetime.datetime(2018, 7, 7, 10, 0), datetime.datetime(2018, 7, 7, 12, 0)),
                (datetime.datetime(2018, 7, 8, 10, 0), datetime.datetime(2018, 7, 8, 12, 0))
            ]
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 12, 3),
                datetime.date(2018, 12, 9)
            ),
            []
        )
        # Periods
        dt = datetime.datetime(2018, 1, 1, 10, 0)
        self.assertEqual(
            len(oh.get_current_rule(dt.date()).time_selectors),
            1
        )
        self.assertEqual(
            (
                oh.get_current_rule(dt.date())
                .time_selectors[0].beginning.get_time(self.SOLAR_HOURS, dt)
            ),
            datetime.datetime.combine(dt.date(), datetime.time(10, 0))
        )
        # Next change
        dt = datetime.datetime(2018, 1, 7, 12, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 1, 8, 10, 0)
        )
        
        dt = datetime.datetime(2018, 1, 8, 10, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 1, 8, 20, 0)
        )
        
        dt = datetime.datetime(2018, 1, 8, 21, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 1, 9, 10, 0)
        )
    
    def test_8(self):
        field = "Mo-Fr 10:00-20:00; week 1 Mo-Fr 08:00-20:00; Jan 1 off"
        oh = OHParser(field)
        # Is it open?
        dt = datetime.datetime(2018, 1, 1, 9, 0)
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 2, 7, 0)
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 2, 10, 0)
        self.assertTrue(oh.is_open(dt))
        
        dt = datetime.datetime(2018, 1, 8, 9, 0)
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 8, 10, 0)
        self.assertTrue(oh.is_open(dt))
        # Day periods.
        day = oh.get_day(datetime.date(2018, 1, 1))
        self.assertEqual(
            day.weekday_name,
            "Monday"
        )
        self.assertEqual(
            day.opening_periods(),
            []
        )
        self.assertEqual(
            day.render_periods(join=False),
            ["closed"]
        )
        self.assertEqual(
            day.render_periods(join=True),
            "closed"
        )
        
        day = oh.get_day(datetime.date(2018, 1, 2))
        self.assertEqual(
            day.weekday_name,
            "Tuesday"
        )
        self.assertEqual(
            day.opening_periods(),
            [
                (
                    datetime.datetime(2018, 1, 2, 8, 0),
                    datetime.datetime(2018, 1, 2, 20, 0)
                )
            ]
        )
        self.assertEqual(
            day.render_periods(join=False),
            ["8:00 AM – 8:00 PM"]
        )
        self.assertEqual(
            day.render_periods(join=True),
            "8:00 AM – 8:00 PM"
        )
        # Opening periods
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 7)
            ),
            [
                (datetime.datetime(2018, 1, 2, 8, 0), datetime.datetime(2018, 1, 2, 20, 0)),
                (datetime.datetime(2018, 1, 3, 8, 0), datetime.datetime(2018, 1, 3, 20, 0)),
                (datetime.datetime(2018, 1, 4, 8, 0), datetime.datetime(2018, 1, 4, 20, 0)),
                (datetime.datetime(2018, 1, 5, 8, 0), datetime.datetime(2018, 1, 5, 20, 0))
            ]
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 8),
                datetime.date(2018, 1, 14)
            ),
            [
                (datetime.datetime(2018, 1, 8, 10, 0), datetime.datetime(2018, 1, 8, 20, 0)),
                (datetime.datetime(2018, 1, 9, 10, 0), datetime.datetime(2018, 1, 9, 20, 0)),
                (datetime.datetime(2018, 1, 10, 10, 0), datetime.datetime(2018, 1, 10, 20, 0)),
                (datetime.datetime(2018, 1, 11, 10, 0), datetime.datetime(2018, 1, 11, 20, 0)),
                (datetime.datetime(2018, 1, 12, 10, 0), datetime.datetime(2018, 1, 12, 20, 0))
            ]
        )
        # Next change
        dt = datetime.datetime(2018, 1, 1, 12, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 1, 2, 8, 0)
        )
        
        dt = datetime.datetime(2018, 1, 7, 20, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 1, 8, 10, 0)
        )
    
    def test_9(self):
        field = "08:00-19:00; May 1,Dec 25 off"
        oh = OHParser(field)
        # Is it open?
        dt = datetime.datetime(2018, 1, 1, 10, 0)
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2018, 5, 1, 10, 0)
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2018, 12, 25, 10, 0)
        self.assertFalse(oh.is_open(dt))
        # Day periods.
        day = oh.get_day(datetime.date(2018, 1, 1))
        self.assertEqual(
            day.weekday_name,
            "Monday"
        )
        self.assertEqual(
            day.opening_periods(),
            [
                (datetime.datetime(2018, 1, 1, 8, 0), datetime.datetime(2018, 1, 1, 19, 0))
            ]
        )
        self.assertEqual(
            day.render_periods(join=False),
            ["8:00 AM – 7:00 PM"]
        )
        self.assertEqual(
            day.render_periods(join=True),
            "8:00 AM – 7:00 PM"
        )
        
        day = oh.get_day(datetime.date(2018, 1, 2))
        self.assertEqual(
            day.weekday_name,
            "Tuesday"
        )
        self.assertEqual(
            day.opening_periods(),
            [
                (datetime.datetime(2018, 1, 2, 8, 0), datetime.datetime(2018, 1, 2, 19, 0))
            ]
        )
        self.assertEqual(
            day.render_periods(join=False),
            ["8:00 AM – 7:00 PM"]
        )
        self.assertEqual(
            day.render_periods(join=True),
            "8:00 AM – 7:00 PM"
        )
        # Opening periods
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 4, 30),
                datetime.date(2018, 5, 6)
            ),
            [
                (datetime.datetime(2018, 4, 30, 8, 0), datetime.datetime(2018, 4, 30, 19, 0)),
                (datetime.datetime(2018, 5, 2, 8, 0), datetime.datetime(2018, 5, 2, 19, 0)),
                (datetime.datetime(2018, 5, 3, 8, 0), datetime.datetime(2018, 5, 3, 19, 0)),
                (datetime.datetime(2018, 5, 4, 8, 0), datetime.datetime(2018, 5, 4, 19, 0)),
                (datetime.datetime(2018, 5, 5, 8, 0), datetime.datetime(2018, 5, 5, 19, 0)),
                (datetime.datetime(2018, 5, 6, 8, 0), datetime.datetime(2018, 5, 6, 19, 0))
            ]
        )
        # Next change
        dt = datetime.datetime(2018, 1, 1, 12, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 1, 1, 19, 0)
        )
        
        dt = datetime.datetime(2018, 4, 30, 12, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 4, 30, 19, 0)
        )
        dt = datetime.datetime(2018, 4, 30, 20, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 5, 2, 8, 0)
        )
    
    def test_10(self):
        field = "Mo-Fr 00:00-24:00; Sa 08:00-12:00"
        oh = OHParser(field)
        # Is it open?
        dt = datetime.datetime(2018, 1, 1, 10, 0)
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 5, 10, 0)
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 6, 7, 0)
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 6, 10, 0)
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 7, 10, 0)
        self.assertFalse(oh.is_open(dt))
        # Next change
        dt = datetime.datetime(2018, 1, 4, 10, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime.combine(
                datetime.date(2018, 1, 5),
                datetime.time.max
            )
        )
        dt = datetime.datetime(2018, 1, 5, 10, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime.combine(
                datetime.date(2018, 1, 5),
                datetime.time.max
            )
        )
        dt = datetime.datetime(2018, 1, 7, 10, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2018, 1, 8, 0, 0)
        )

    def test_11(self):
        field = "Jan-Feb 10:00-20:00"
        oh = OHParser(field)

        dt = datetime.datetime(2018, 1, 1, 12, 0)
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 1, 22, 0)
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2018, 3, 1, 12, 0)
        self.assertFalse(oh.is_open(dt))
        # Next change
        dt = datetime.datetime(2018, 1, 1, 12, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime.combine(
                datetime.date(2018, 1, 1),
                datetime.time(20, 0)
            )
        )
        dt = datetime.datetime(2018, 1, 1, 22, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime.combine(
                datetime.date(2018, 1, 2),
                datetime.time(10, 0)
            )
        )
        dt = datetime.datetime(2018, 6, 1, 12, 0)
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime.combine(
                datetime.date(2019, 1, 1),
                datetime.time(10, 0)
            )
        )
    
    def test_closed(self):
        oh = OHParser("24/7; Su off")
        # Was "24/7; Su 10:00-13:00 off".
        dt = datetime.datetime(2018, 1, 6, 10, 0)
        self.assertTrue(oh.is_open(dt))
        # TODO: This doesn't work because there can only be one rule per day.
        # Check '_get_day_timespans()' and 'get_current_rule()'.
        #dt = datetime.datetime(2018, 1, 7, 9, 0)
        #self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 7, 11, 0)
        self.assertFalse(oh.is_open(dt))
    
    def test_equality(self):
        oh1 = OHParser("Mo 10:00-20:00")
        oh2 = OHParser("Mo 10:00-20:00")
        oh3 = OHParser("Mo 09:00-21:00")
        
        self.assertEqual(oh1, oh2)
        self.assertNotEqual(oh1, oh3)
        self.assertNotEqual(oh1, '')
        
        oh4 = OHParser("Mo 10:00-20:00", location=(59.9, 10.7, "Europe/Oslo", 0))
        oh5 = OHParser("Mo 10:00-20:00", location=(59.9, 10.7, "Europe/Oslo", 0))
        oh6 = OHParser("Mo 10:00-20:00", location=(59.3, 18, "Europe/Stockholm", 0))
        
        self.assertNotEqual(oh1, oh4)
        self.assertEqual(oh4, oh5)
        self.assertNotEqual(oh5, oh6)
    
    def test_geojson_1(self):
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [0.1, 51.5]
            },
            "properties": {
                "name": "A great bakery",
                "shop": "bakery",
                "opening_hours": "Mo-Fr 08:00-19:00; Sa 09:00-19:00"
            }
        }
        oh1 = OHParser.from_geojson(geojson)
        oh2 = OHParser("Mo-Fr 08:00-19:00; Sa 09:00-19:00")
        self.assertEqual(oh1, oh2)
        
        timezone_getter = lambda lat, lon: "UTC"
        oh3 = OHParser.from_geojson(geojson, timezone_getter=timezone_getter)
        oh4 = OHParser(
            "Mo-Fr 08:00-19:00; Sa 09:00-19:00",
            location=(51.5, 0.1, "UTC", 0)
        )
        self.assertEqual(oh3, oh4)
        self.assertNotEqual(oh1, oh3)
        self.assertNotEqual(oh2, oh4)
    
    def test_geojson_2(self):
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [-0.124, 51.531, -0.1227, 51.533]
            },
            "properties": {
                "name": "A great bakery",
                "shop": "bakery",
                "opening_hours": "Mo-Fr 08:00-19:00; Sa 09:00-19:00"
            }
        }
        oh1 = OHParser.from_geojson(geojson)
        oh2 = OHParser("Mo-Fr 08:00-19:00; Sa 09:00-19:00")
        self.assertEqual(oh1, oh2)
        
        timezone_getter = lambda lat, lon: "UTC"
        oh3 = OHParser.from_geojson(geojson, timezone_getter=timezone_getter)
        oh4 = OHParser(
            "Mo-Fr 08:00-19:00; Sa 09:00-19:00",
            location=(51.532, -0.12335, "UTC", 0)
        )
        self.assertEqual(oh3, oh4)
        self.assertNotEqual(oh1, oh3)
        self.assertNotEqual(oh2, oh4)
    
    def test_locales_handling(self):
        field = "Mo-Fr 10:00-20:00"
        with self.assertWarns(Warning):
            oh = OHParser(field, locale="ja")
    
    def test_monthday_year_spanning(self):
        oh = OHParser("Oct-Mar 07:30-19:30; Apr-Sep 07:00-21:00")
        self.assertTrue(oh.is_open(datetime.datetime(2018, 12, 1, 12, 30)))
        self.assertTrue(oh.is_open(datetime.datetime(2019, 1, 1, 12, 30)))
        self.assertFalse(oh.is_open(datetime.datetime(2018, 12, 1, 23, 59)))
        self.assertTrue(oh.is_open(datetime.datetime(2018, 9, 1, 20, 59)))

        #explicit year spanning
        oh = OHParser("2019 Oct- 2020 Feb 07:30-19:30")
        self.assertFalse(oh.is_open(datetime.datetime(2019, 1, 1, 12, 30)))

        with self.assertRaises(NextChangeRecursionError):
            oh.next_change(datetime.datetime(2020,6,1))

class TestSolarHours(unittest.TestCase):
    maxDiff = None
    
    def test_tuple_1(self):
        oh = OHParser(
            "Mo-Fr sunrise-sunset",
            location=(51.168, 0.0, "Europe/London", 24)
        )
        
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 7)
            ),
            [
                (datetime.datetime(2018, 1, 1, 8, 4, 1), datetime.datetime(2018, 1, 1, 16, 2, 37)),
                (datetime.datetime(2018, 1, 2, 8, 3, 55), datetime.datetime(2018, 1, 2, 16, 3, 39)),
                (datetime.datetime(2018, 1, 3, 8, 3, 46), datetime.datetime(2018, 1, 3, 16, 4, 44)),
                (datetime.datetime(2018, 1, 4, 8, 3, 34), datetime.datetime(2018, 1, 4, 16, 5, 51)),
                (datetime.datetime(2018, 1, 5, 8, 3, 18), datetime.datetime(2018, 1, 5, 16, 7, 1))
            ]
        )
    
    def test_tuple_2(self):
        oh = OHParser(
            "Mo-Fr (sunrise-01:00)-(sunset+02:15)",
            location=(51.168, 0.0, "Europe/London", 24)
        )
        
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 7)
            ),
            [
                (datetime.datetime(2018, 1, 1, 7, 4, 1), datetime.datetime(2018, 1, 1, 18, 17, 37)),
                (datetime.datetime(2018, 1, 2, 7, 3, 55), datetime.datetime(2018, 1, 2, 18, 18, 39)),
                (datetime.datetime(2018, 1, 3, 7, 3, 46), datetime.datetime(2018, 1, 3, 18, 19, 44)),
                (datetime.datetime(2018, 1, 4, 7, 3, 34), datetime.datetime(2018, 1, 4, 18, 20, 51)),
                (datetime.datetime(2018, 1, 5, 7, 3, 18), datetime.datetime(2018, 1, 5, 18, 22, 1))
            ]
        )
    
    def test_location_1(self):
        oh = OHParser(
            "Mo-Fr sunrise-sunset",
            location=astral.Location((
                "Greenwich",
                "England",
                51.168, 0.0,
                "Europe/London",
                24
            ))
        )
        
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 7)
            ),
            [
                (datetime.datetime(2018, 1, 1, 8, 4, 1), datetime.datetime(2018, 1, 1, 16, 2, 37)),
                (datetime.datetime(2018, 1, 2, 8, 3, 55), datetime.datetime(2018, 1, 2, 16, 3, 39)),
                (datetime.datetime(2018, 1, 3, 8, 3, 46), datetime.datetime(2018, 1, 3, 16, 4, 44)),
                (datetime.datetime(2018, 1, 4, 8, 3, 34), datetime.datetime(2018, 1, 4, 16, 5, 51)),
                (datetime.datetime(2018, 1, 5, 8, 3, 18), datetime.datetime(2018, 1, 5, 16, 7, 1))
            ]
        )
    
    def test_location_2(self):
        oh = OHParser(
            "Mo-Fr (sunrise-01:00)-(sunset+02:15)",
            location=astral.Location((
                "Greenwich",
                "England",
                51.168, 0.0,
                "Europe/London",
                24
            ))
        )
        
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 7)
            ),
            [
                (datetime.datetime(2018, 1, 1, 7, 4, 1), datetime.datetime(2018, 1, 1, 18, 17, 37)),
                (datetime.datetime(2018, 1, 2, 7, 3, 55), datetime.datetime(2018, 1, 2, 18, 18, 39)),
                (datetime.datetime(2018, 1, 3, 7, 3, 46), datetime.datetime(2018, 1, 3, 18, 19, 44)),
                (datetime.datetime(2018, 1, 4, 7, 3, 34), datetime.datetime(2018, 1, 4, 18, 20, 51)),
                (datetime.datetime(2018, 1, 5, 7, 3, 18), datetime.datetime(2018, 1, 5, 18, 22, 1))
            ]
        )
    
    def test_location_name(self):
        oh = OHParser(
            "Mo-Fr sunrise-sunset",
            location="London"
        )
        
        self.assertEqual(
            oh.opening_periods_between(
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 7)
            ),
            [
                (datetime.datetime(2018, 1, 1, 8, 6, 6), datetime.datetime(2018, 1, 1, 16, 1, 27)),
                (datetime.datetime(2018, 1, 2, 8, 6), datetime.datetime(2018, 1, 2, 16, 2, 30)),
                (datetime.datetime(2018, 1, 3, 8, 5, 50), datetime.datetime(2018, 1, 3, 16, 3, 35)),
                (datetime.datetime(2018, 1, 4, 8, 5, 37), datetime.datetime(2018, 1, 4, 16, 4, 43)),
                (datetime.datetime(2018, 1, 5, 8, 5, 21), datetime.datetime(2018, 1, 5, 16, 5, 54))
            ]
        )
    
    def test_temporary_location(self):
        oh = OHParser(
            "Mo-Fr sunrise-sunset",
            location="London"
        )
        
        current_location = vars(oh.solar_hours.location)
        del current_location["astral"]
        expected_location = vars(astral.Astral()["London"])
        del expected_location["astral"]
        self.assertEqual(current_location, expected_location)
        
        with oh.temporary_location(astral.Astral()["Paris"]):
            current_location = vars(oh.solar_hours.location)
            del current_location["astral"]
            expected_location = vars(astral.Astral()["Paris"])
            del expected_location["astral"]
            self.assertEqual(current_location, expected_location)
        
        current_location = vars(oh.solar_hours.location)
        expected_location = vars(astral.Astral()["London"])
        del expected_location["astral"]
        self.assertEqual(current_location, expected_location)


class TestPatterns(unittest.TestCase):
    # Checks there is no error with regular fields.
    maxDiff = None
    
    def test_regulars(self):
        field = "Mo-Sa 09:00-19:00"
        oh = OHParser(field)
        
        field = "Mo-Sa 09:00-19:00; Su off"
        oh = OHParser(field)
        
        field = "Mo-Sa 09:00-19:00; Su closed"
        oh = OHParser(field)
        
        field = "Mo-Sa 09:00-19:00 open"
        oh = OHParser(field)
        
        field = "Fr-Mo 09:00-19:00"
        oh = OHParser(field)
        
        field = "Mo,Th 09:00-sunset"
        oh = OHParser(field)
        
        field = "Mo,Th (sunrise+02:00)-sunset"
        oh = OHParser(field)
        
        field = "SH,Mo 09:00-19:00"
        oh = OHParser(field)
        
        field = "PH,Mo 09:00-19:00"
        oh = OHParser(field)
        
        field = "Jan 09:00-19:00"
        oh = OHParser(field)
        
        field = "Jan-Feb 09:00-19:00"
        oh = OHParser(field)
        
        field = "Jan,Aug 09:00-19:00"
        oh = OHParser(field)
        
        field = "Jan Mo 09:00-19:00"
        oh = OHParser(field)
        
        field = "Jan Mo-Fr 09:00-19:00"
        oh = OHParser(field)
        
        field = "Jan,Feb Mo 09:00-19:00"
        oh = OHParser(field)
        
        field = "Jan-Feb Mo 09:00-19:00"
        oh = OHParser(field)
        
        field = "Jan-Feb Mo-Fr 09:00-19:00"
        oh = OHParser(field)
        
        field = "SH Mo 09:00-19:00"
        oh = OHParser(field)
        
        field = "SH Mo-Fr 09:00-19:00"
        oh = OHParser(field)
        
        field = "easter 09:00-19:00"
        oh = OHParser(field)
        
        field = "SH,PH Mo-Fr 10:00-20:00"
        oh = OHParser(field)
        
        field = "SH,PH Mo-Fr,Su 10:00-20:00"
        oh = OHParser(field)
        
        field = "Jan-Feb,Aug Mo-Fr,Su 10:00-20:00"
        oh = OHParser(field)
        
        field = "week 1-53/2 Fr 09:00-12:00"
        oh = OHParser(field)
        
        field = "2010 Mo-Fr 09:00-12:00"
        oh = OHParser(field)
        
        field = "2010-2020 Mo-Fr 09:00-12:00"
        oh = OHParser(field)
        
        field = "2010-2020/2 Mo-Fr 09:00-12:00"
        oh = OHParser(field)
        
        #field = "easter +2 days 09:00-19:00"
        #oh = OHParser(field)
    
    def test_invalid_days(self):
        field = "Mo,Wx 09:00-12:00,13:00-19:00"
        with self.assertRaises(ParseError) as context:
            oh = OHParser(field)
        
        field = "Pl-Mo 09:00-12:00,13:00-19:00"
        with self.assertRaises(ParseError) as context:
            oh = OHParser(field)
        
        field = "Su[1] 10:00-20:00"
        with self.assertRaises(ParseError) as context:
            oh = OHParser(field)
        
        field = "Mo-Fr"
        with self.assertRaises(ParseError) as context:
            oh = OHParser(field)
    
    def test_always_closed(self):
        field = "closed"
        with self.assertRaises(AlwaysClosed) as context:
            oh = OHParser(field)
        
        field = "off"
        with self.assertRaises(AlwaysClosed) as context:
            oh = OHParser(field)
    
    def test_comment_only_fields(self):
        field = '"on appointement"'
        with self.assertRaises(CommentOnlyField) as context:
            oh = OHParser(field)


class TestSanitize(unittest.TestCase):
    maxDiff = None
    
    def test_valid_1(self):
        field = "Mo-Sa 09:00-19:00"
        sanitized_field = sanitize(field)
        self.assertEqual(sanitized_field, field)
    
    def test_valid_2(self):
        field = "Mo,Th 09:00-12:00,13:00-19:00"
        sanitized_field = sanitize(field)
        self.assertEqual(sanitized_field, field)
    
    def test_valid_3(self):
        field = "2010-2020 Jan-Feb Mo-Fr 09:30-(sunrise+01:00)"
        sanitized_field = sanitize(field)
        self.assertEqual(sanitized_field, field)
    
    def test_valid_4(self):
        field = "week 1-12/2 08:00-19:00"
        sanitized_field = "week 1-12/2 08:00-19:00"
        self.assertEqual(sanitize(field), sanitized_field)
    
    def test_valid_5(self):
        field = 'Mo-Fr 10:00-20:00 "on appointement"'
        sanitized_field = 'Mo-Fr 10:00-20:00 "on appointement"'
        self.assertEqual(sanitize(field), sanitized_field)
    
    def test_invalid_1(self):
        field = "mo-sa 09:00-19:00"
        sanitized_field = "Mo-Sa 09:00-19:00"
        self.assertEqual(sanitize(field), sanitized_field)
    
    def test_invalid_2(self):
        field = "Mo,th 9:00-12:00, 13:00-19:00"
        sanitized_field = "Mo,Th 09:00-12:00,13:00-19:00"
        self.assertEqual(sanitize(field), sanitized_field)
    
    def test_invalid_3(self):
        field = "Mo 09:00 - 12:00 , 13:00 - 19:00;    "
        sanitized_field = "Mo 09:00-12:00,13:00-19:00"
        self.assertEqual(sanitize(field), sanitized_field)
    
    def test_invalid_4(self):
        field = "Mo 10h00-12h00 14:00-19:00; Tu-Sa 10:00-19:00"
        sanitized_field = "Mo 10:00-12:00,14:00-19:00; Tu-Sa 10:00-19:00"
        self.assertEqual(sanitize(field), sanitized_field)
    
    def test_invalid_5(self):
        field = "mo-fr,su 10h - 20h"
        sanitized_field = "Mo-Fr,Su 10:00-20:00"
        self.assertEqual(sanitize(field), sanitized_field)
    
    def test_invalid_6(self):
        field = "jan-feb SUNRISE-SUNSET"
        sanitized_field = "Jan-Feb sunrise-sunset"
        self.assertEqual(sanitize(field), sanitized_field)
    
    def test_holidays(self):
        field = "Mo-Sa,SH 09:00-19:00"
        self.assertEqual(sanitize(field), field)
        
        field = "Mo-Sa 09:00-19:00; PH off"
        self.assertEqual(sanitize(field), field)


class TestSolarHoursParsing(unittest.TestCase):
    maxDiff = None
    
    def test_valid_solar(self):
        # Sunrise.
        field = "Mo,Th 09:00-12:00,13:00-sunrise"
        oh = OHParser(field)
        # Sunset.
        field = "Mo,Th 09:00-12:00,13:00-sunset"
        oh = OHParser(field)
    
    def test_invalid_solar(self):
        # Sunrise.
        field = "Mo,Th 09:00-12:00,13:00-(sunrise)"
        with self.assertRaises(ParseError) as context:
            oh = OHParser(field)
        # Sunset.
        field = "Mo,Th 09:00-12:00,13:00-(sunset)"
        with self.assertRaises(ParseError) as context:
            oh = OHParser(field)
    
    def test_valid_solar_offset(self):
        # Sunrise.
        field = "Mo,Th 09:00-12:00,13:00-(sunrise+02:00)"
        oh = OHParser(field)
        # Sunset.
        field = "Mo,Th 09:00-12:00,13:00-(sunset-02:00)"
        oh = OHParser(field)
    
    def test_invalid_solar_offset(self):
        field = "Mo,Th 09:00-12:00,13:00-(sunrise=02:00)"
        with self.assertRaises(ParseError) as context:
            oh = OHParser(field)
        field = "Mo,Th 09:00-12:00,13:00-(sunrise02:00)"
        with self.assertRaises(ParseError) as context:
            oh = OHParser(field)
        field = "Mo,Th 09:00-12:00,13:00-(sunrise+02:00"
        with self.assertRaises(ParseError) as context:
            oh = OHParser(field)
    
    def test_antarctica(self):
        # On Antactica, the sun may never reach low positions in sky,
        # so dawn / dusk hours can't be get.
        location = (-77.85, 166.72, "UTC", 0)
        oh = OHParser("Mo-Fr sunrise-sunset", location=location)
        dt = datetime.datetime(2018, 1, 1, 10, 0)
        with self.assertRaises(SolarHoursError) as context:
            oh.is_open(dt)


class TestFrequentFields(unittest.TestCase):
    maxDiff = None
    
    def test_valid_fields(self):
        field = "Mo-Fr 10:00-20:00"
        tree = Tree("time_domain", [Tree("rule_sequence", [Tree("range_selectors", [Tree("weekday_or_holiday_sequence_selector", [Tree("weekday_sequence", [Tree("weekday_range", [Token("WDAY", 'Mo'), Token("WDAY", 'Fr')])])])]), Tree("time_selector", [Tree("timespan", [Tree("time", [Tree("hour_minutes", [Token("TWO_DIGITS", '10'), Token("TWO_DIGITS", '00')])]), Tree("time", [Tree("hour_minutes", [Token("TWO_DIGITS", '20'), Token("TWO_DIGITS", '00')])])])])])])
        self.assertEqual(parse_simple_field(field), tree)
        
        field = "Mo 10:00-20:00"
        tree = Tree("time_domain", [Tree("rule_sequence", [Tree("range_selectors", [Tree("weekday_or_holiday_sequence_selector", [Tree("weekday_sequence", [Tree("weekday_range", [Token("WDAY", 'Mo')])])])]), Tree("time_selector", [Tree("timespan", [Tree("time", [Tree("hour_minutes", [Token("TWO_DIGITS", '10'), Token("TWO_DIGITS", '00')])]), Tree("time", [Tree("hour_minutes", [Token("TWO_DIGITS", '20'), Token("TWO_DIGITS", '00')])])])])])])
        self.assertEqual(parse_simple_field(field), tree)
        
        field = "Mo off"
        tree = Tree("time_domain", [Tree("range_modifier_rule", [Tree("range_selectors", [Tree("weekday_or_holiday_sequence_selector", [Tree("weekday_sequence", [Tree("weekday_range", [Token("WDAY", 'Mo')])])])]), Tree("rule_modifier_closed", [Token("CLOSED", ' off')])])])
        self.assertEqual(parse_simple_field(field), tree)
        
        field = "10:00-20:00"
        tree = Tree("time_domain", [Tree("rule_sequence", [Tree("time_selector", [Tree("timespan", [Tree("time", [Tree("hour_minutes", [Token("TWO_DIGITS", '10'), Token("TWO_DIGITS", '00')])]), Tree("time", [Tree("hour_minutes", [Token("TWO_DIGITS", '20'), Token("TWO_DIGITS", '00')])])])])])])
        self.assertEqual(parse_simple_field(field), tree)
    
    def test_invalid_fields(self):
        field = "Mo-We,Fr 10:00-20:00"
        self.assertEqual(parse_simple_field(field), None)
        
        field = "Mo 10:00-12:00,13:00-20:00"
        self.assertEqual(parse_simple_field(field), None)
        
        field = "Ma off"
        self.assertEqual(parse_simple_field(field), None)
        
        field = "Ma-Ju 10:00-12:00,13:00-20:00"
        self.assertEqual(parse_simple_field(field), None)
        
        field = "Ma-Ju 10:00-20:00"
        self.assertEqual(parse_simple_field(field), None)
        
        field = "Ma 10:00-12:00"
        self.assertEqual(parse_simple_field(field), None)
        
        field = "Jan-Feb 10:00-20:00"
        self.assertEqual(parse_simple_field(field), None)
        
        field = "2010-2020 10:00-20:00"
        self.assertEqual(parse_simple_field(field), None)
        
        field = "sunrise-sunset"
        self.assertEqual(parse_simple_field(field), None)


class TestFieldDescription(unittest.TestCase):
    maxDiff = None
    
    def test_regulars(self):
        field = "Mo-Fr 10:00-19:00; Sa 10:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            [
                "From Monday to Friday: 10:00 AM – 7:00 PM.",
                "On Saturday: 10:00 AM – 12:00 PM."
            ]
        )
        
        field = "sunrise-sunset"
        self.assertEqual(
            OHParser(field).description(),
            ["Every days: sunrise – sunset."]
        )
        
        # TODO: Improve this.
        field = "00:00-24:00"
        self.assertEqual(
            OHParser(field).description(),
            ["Every days: 12:00 AM – 11:59 PM."]
        )
        
        field = "sunrise-sunset; Su off; PH 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            [
                "Every days: sunrise – sunset.",
                "On Sunday: closed.",
                "On public holidays: 10:00 AM – 8:00 PM."
            ]
        )
        
        field = "10:00-(sunset+02:00)"
        self.assertEqual(
            OHParser(field).description(),
            ["Every days: 10:00 AM – 2 hours after sunset."]
        )
        
        field = "Jan-Feb 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From January to February: 10:00 AM – 8:00 PM."]
        )
        
        field = "Jan-Feb Mo-Fr 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From January to February, from Monday to Friday: 10:00 AM – 8:00 PM."]
        )
        
        field = "Jan 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["January: 10:00 AM – 8:00 PM."]
        )
        
        field = "Jan,Dec 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["January and December: 10:00 AM – 8:00 PM."]
        )
        
        field = "Jan,Dec 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["January and December: 10:00 AM – 8:00 PM."]
        )
        
        field = "Dec 25 09:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            ["December 25: 9:00 AM – 12:00 PM."]
        )
        
        field = "Dec 25,Jan 1 09:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            ["December 25 and January 1: 9:00 AM – 12:00 PM."]
        )
        
        field = "Dec 24-26 09:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From December 24 to 26: 9:00 AM – 12:00 PM."]
        )
        
        field = "2020 Dec 24-26 09:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            ["In 2020, from December 24 to 26: 9:00 AM – 12:00 PM."]
        )
        
        field = "2010 Dec 25 09:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            ["In 2010, December 25: 9:00 AM – 12:00 PM."]
        )
        
        field = "Dec Mo 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["December, on Monday: 10:00 AM – 8:00 PM."]
        )
        
        field = "Jan-Feb Mo 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From January to February, on Monday: 10:00 AM – 8:00 PM."]
        )
        
        field = "Jan-Feb Mo-Fr 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From January to February, from Monday to Friday: 10:00 AM – 8:00 PM."]
        )
        
        field = "2010-2020 Mo-Fr 10:00-19:00; 2010-2020 Sa 10:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            [
                "From 2010 to 2020, from Monday to Friday: 10:00 AM – 7:00 PM.",
                "From 2010 to 2020, on Saturday: 10:00 AM – 12:00 PM."
            ]
        )
        
        field = "2010-2020/2 Mo-Fr 10:00-19:00"
        self.assertEqual(
            OHParser(field).description(),
            [
                "From 2010 to 2020, every 2 years, from Monday to Friday: 10:00 AM – 7:00 PM.",
            ]
        )
        
        field = "easter 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["On easter: 10:00 AM – 8:00 PM."]
        )
        
        field = "PH,SH 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["On public and school holidays: 10:00 AM – 8:00 PM."]
        )
        
        field = "PH,Sa 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["On public holidays and on Saturday: 10:00 AM – 8:00 PM."]
        )
        
        field = "PH,Sa,Su 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["On public holidays and from Saturday to Sunday: 10:00 AM – 8:00 PM."]
        )
        
        field = "PH Sa 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["On public holidays, on Saturday: 10:00 AM – 8:00 PM."]
        )
        
        field = "SH Mo-Fr 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["On school holidays, from Monday to Friday: 10:00 AM – 8:00 PM."]
        )
        
        field = "week 1 Mo-Fr 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["In week 1, from Monday to Friday: 10:00 AM – 8:00 PM."]
        )
        
        field = "week 1-5 Mo-Fr 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From week 1 to week 5, from Monday to Friday: 10:00 AM – 8:00 PM."]
        )
        
        field = "week 1-10/2 Mo-Fr 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From week 1 to week 10, every 2 weeks, from Monday to Friday: 10:00 AM – 8:00 PM."]
        )
        
        field = "24/7"
        self.assertEqual(
            OHParser(field).description(),
            ["Open 24 hours a day and 7 days a week."]
        )
        
        field = "24/7; PH closed"
        self.assertEqual(
            OHParser(field).description(),
            [
                "Open 24 hours a day and 7 days a week.",
                "On public holidays: closed."
            ]
        )


class TestFunctions(unittest.TestCase):
    maxDiff = None
    
    def test_easter_date(self):
        self.assertEqual(
            easter_date(2000),
            datetime.date(2000, 4, 23)
        )
        self.assertEqual(
            easter_date(2010),
            datetime.date(2010, 4, 4)
        )
        self.assertEqual(
            easter_date(2020),
            datetime.date(2020, 4, 12)
        )
    
    def test_cycle_slice(self):
        l = "ABCDEFGHIJ"
        self.assertEqual(
            field_parser.cycle_slice(l, 0, 3),
            "ABCD"
        )
        self.assertEqual(
            field_parser.cycle_slice(l, 7, 2),
            "HIJABC"
        )
    
    def test_days_of_week(self):
        self.assertEqual(
            days_of_week(2018, 1, first_weekday=0),
            [
                datetime.date(2018, 1, 1),
                datetime.date(2018, 1, 2),
                datetime.date(2018, 1, 3),
                datetime.date(2018, 1, 4),
                datetime.date(2018, 1, 5),
                datetime.date(2018, 1, 6),
                datetime.date(2018, 1, 7)
            ]
        )
        self.assertEqual(
            days_of_week(2018, 1, first_weekday=6),
            [
                datetime.date(2018, 1, 2),
                datetime.date(2018, 1, 3),
                datetime.date(2018, 1, 4),
                datetime.date(2018, 1, 5),
                datetime.date(2018, 1, 6),
                datetime.date(2018, 1, 7),
                datetime.date(2018, 1, 8)
            ]
        )
        self.assertEqual(
            days_of_week(2018, 30, first_weekday=0),
            [
                datetime.date(2018, 7, 23),
                datetime.date(2018, 7, 24),
                datetime.date(2018, 7, 25),
                datetime.date(2018, 7, 26),
                datetime.date(2018, 7, 27),
                datetime.date(2018, 7, 28),
                datetime.date(2018, 7, 29)
            ]
        )
        self.assertEqual(
            days_of_week(2018, 30, first_weekday=1),
            [
                datetime.date(2018, 7, 22),
                datetime.date(2018, 7, 23),
                datetime.date(2018, 7, 24),
                datetime.date(2018, 7, 25),
                datetime.date(2018, 7, 26),
                datetime.date(2018, 7, 27),
                datetime.date(2018, 7, 28)
            ]
        )
        self.assertEqual(
            days_of_week(2018, 30, first_weekday=6),
            [
                datetime.date(2018, 7, 24),
                datetime.date(2018, 7, 25),
                datetime.date(2018, 7, 26),
                datetime.date(2018, 7, 27),
                datetime.date(2018, 7, 28),
                datetime.date(2018, 7, 29),
                datetime.date(2018, 7, 30)
            ]
        )


class TestOpeningPeriodsBetween(unittest.TestCase):
    def test_simple(self):
        oh = OHParser("09:00-19:00")
        # completely before
        self.assertEqual(
            oh.opening_periods_between(
                datetime.datetime(2019, 1, 20, 23),
                datetime.datetime(2019, 1, 21, 1),
            ),
            [],
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.datetime(2019, 1, 21, 5),
                datetime.datetime(2019, 1, 21, 7),
            ),
            [],
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.datetime(2019, 1, 21, 7),
                datetime.datetime(2019, 1, 21, 9),
            ),
            [],
        )
        # partly before
        self.assertEqual(
            oh.opening_periods_between(
                datetime.datetime(2019, 1, 21, 8),
                datetime.datetime(2019, 1, 21, 10),
            ),
            [
                (datetime.datetime(2019, 1, 21, 9), datetime.datetime(2019, 1, 21, 10)),
            ],
        )
        # between
        self.assertEqual(
            oh.opening_periods_between(
                datetime.datetime(2019, 1, 21, 9),
                datetime.datetime(2019, 1, 21, 11),
            ),
            [
                (datetime.datetime(2019, 1, 21, 9), datetime.datetime(2019, 1, 21, 11)),
            ],
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.datetime(2019, 1, 21, 17),
                datetime.datetime(2019, 1, 21, 19),
            ),
            [
                (datetime.datetime(2019, 1, 21, 17), datetime.datetime(2019, 1, 21, 19)),
            ],
        )
        # partly after
        self.assertEqual(
            oh.opening_periods_between(
                datetime.datetime(2019, 1, 21, 18),
                datetime.datetime(2019, 1, 21, 20),
            ),
            [
                (datetime.datetime(2019, 1, 21, 18), datetime.datetime(2019, 1, 21, 19)),
            ],
        )
        # completely after
        self.assertEqual(
            oh.opening_periods_between(
                datetime.datetime(2019, 1, 21, 19),
                datetime.datetime(2019, 1, 21, 21),
            ),
            [],
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.datetime(2019, 1, 21, 21),
                datetime.datetime(2019, 1, 21, 23),
            ),
            [],
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.datetime(2019, 1, 21, 23),
                datetime.datetime(2019, 1, 22, 1),
            ),
            [],
        )

    def test_complex(self):
        oh = OHParser("09:00-11:00,13:00-15:00,17:00-19:00")
        self.assertEqual(
            oh.opening_periods_between(
                datetime.datetime(2019, 1, 21, 10),
                datetime.datetime(2019, 1, 21, 18),
            ),
            [
                (datetime.datetime(2019, 1, 21, 10), datetime.datetime(2019, 1, 21, 11)),
                (datetime.datetime(2019, 1, 21, 13), datetime.datetime(2019, 1, 21, 15)),
                (datetime.datetime(2019, 1, 21, 17), datetime.datetime(2019, 1, 21, 18)),
            ],
        )
        self.assertEqual(
            oh.opening_periods_between(
                datetime.datetime(2019, 1, 21, 11),
                datetime.datetime(2019, 1, 21, 17),
            ),
            [
                (datetime.datetime(2019, 1, 21, 13), datetime.datetime(2019, 1, 21, 15)),
            ],
        )


if __name__ == '__main__':
    unittest.main()
    exit(0)
