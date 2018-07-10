import unittest
import datetime

from lark import Tree
from lark.lexer import Token
import astral

from humanized_opening_hours import field_parser
from humanized_opening_hours.main import (
    OHParser, sanitize, days_of_week, DayPeriods
)
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

# TODO : Add more unit tests for various formats.

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
        # Day periods.
        self.assertEqual(
            oh.get_day_periods(datetime.date(2018, 1, 1)),
            DayPeriods(
                "Monday", datetime.date(2018, 1, 1),
                [(
                    datetime.datetime(2018, 1, 1, 9, 0),
                    datetime.datetime(2018, 1, 1, 19, 0)
                )],
                ["9:00 AM – 7:00 PM"], "9:00 AM – 7:00 PM"
            )
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
        self.assertEqual(
            oh.get_day_periods(datetime.date(2018, 1, 1)),
            DayPeriods(
                "Monday", datetime.date(2018, 1, 1),
                [
                    (
                        datetime.datetime(2018, 1, 1, 9, 0),
                        datetime.datetime(2018, 1, 1, 12, 0)
                    ),
                    (
                        datetime.datetime(2018, 1, 1, 13, 0),
                        datetime.datetime(2018, 1, 1, 19, 0)
                    )
                ],
                ["9:00 AM – 12:00 PM", "1:00 PM – 7:00 PM"],
                "9:00 AM – 12:00 PM and 1:00 PM – 7:00 PM"
            )
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
        self.assertEqual(
            oh.get_day_periods(datetime.date(2018, 1, 1)),
            DayPeriods(
                "Monday", datetime.date(2018, 1, 1),
                [
                    (
                        datetime.datetime(2018, 1, 1, 19, 0),
                        datetime.datetime(2018, 1, 2, 2, 0)
                    )
                ],
                ["7:00 PM – 2:00 AM"],
                "7:00 PM – 2:00 AM"
            )
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
        self.assertEqual(
            oh.get_day_periods(datetime.date(2018, 1, 1)),
            DayPeriods(
                "Monday", datetime.date(2018, 1, 1),
                [
                    (
                        datetime.datetime(2018, 1, 1, 10, 0),
                        datetime.datetime(2018, 1, 1, 20, 0)
                    )
                ],
                ["10:00 AM – 8:00 PM"],
                "10:00 AM – 8:00 PM"
            )
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
        self.assertEqual(
            oh.get_day_periods(datetime.date(2018, 1, 1)),
            DayPeriods(
                "Monday", datetime.date(2018, 1, 1),
                [
                    (
                        datetime.datetime(2018, 1, 1, 10, 0),
                        datetime.datetime(2018, 1, 1, 20, 0)
                    )
                ],
                ["10:00 AM – 8:00 PM"],
                "10:00 AM – 8:00 PM"
            )
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
        self.assertEqual(
            oh.get_day_periods(datetime.date(2018, 1, 1)),
            DayPeriods(
                "Monday", datetime.date(2018, 1, 1),
                [], ["closed"], "closed"
            )
        )
        self.assertEqual(
            oh.get_day_periods(datetime.date(2018, 1, 2)),
            DayPeriods(
                "Tuesday", datetime.date(2018, 1, 2),
                [
                    (
                        datetime.datetime(2018, 1, 2, 8, 0),
                        datetime.datetime(2018, 1, 2, 20, 0)
                    )
                ],
                ["8:00 AM – 8:00 PM"],
                "8:00 AM – 8:00 PM"
            )
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
        self.assertEqual(
            oh.get_day_periods(datetime.date(2018, 1, 1)),
            DayPeriods(
                "Monday", datetime.date(2018, 1, 1),
                [
                    (datetime.datetime(2018, 1, 1, 8, 0), datetime.datetime(2018, 1, 1, 19, 0))
                ],
                ["8:00 AM – 7:00 PM"],
                "8:00 AM – 7:00 PM"
            )
        )
        self.assertEqual(
            oh.get_day_periods(datetime.date(2018, 5, 1)),
            DayPeriods(
                "Tuesday", datetime.date(2018, 5, 1),
                [], ["closed"], "closed"
            )
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
    
    def test_locales_handling(self):
        field = "Mo-Fr 10:00-20:00"
        with self.assertWarns(Warning):
            oh = OHParser(field, locale="ja")


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


class TestPatterns(unittest.TestCase):
    # Checks there is no error with regular fields.
    maxDiff = None
    
    def test_regulars(self):
        field = "Mo-Sa 09:00-19:00"
        oh = OHParser(field)
        
        field = "Fr-Mo 09:00-19:00"
        oh = OHParser(field)
        
        field = "Mo,Th 09:00-sunset"
        oh = OHParser(field)
        
        field = "Mo,Th (sunrise+02:00)-sunset"
        oh = OHParser(field)
        
        field = "SH,Mo 09:00-19:00"
        oh = OHParser(field)
        
        field = "SH,Mo 09:00-19:00"
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


class TestFieldDescription(unittest.TestCase):
    maxDiff = None
    
    def test_regulars(self):
        field = "Mo-Fr 10:00-19:00; Sa 10:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            [
                "From Monday to Friday: from 10:00 AM to 7:00 PM.",
                "On Saturday: from 10:00 AM to 12:00 PM."
            ]
        )
        
        field = "sunrise-sunset"
        self.assertEqual(
            OHParser(field).description(),
            ["Every days: from sunrise to sunset."]
        )
        
        field = "sunrise-sunset; Su off; PH 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            [
                "Every days: from sunrise to sunset.",
                "On Sunday: closed.",
                "Public holidays: from 10:00 AM to 8:00 PM."
            ]
        )
        
        field = "10:00-(sunset+02:00)"
        self.assertEqual(
            OHParser(field).description(),
            ["Every days: from 10:00 AM to 2 hours after sunset."]
        )
        
        field = "Jan-Feb 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From January to February: from 10:00 AM to 8:00 PM."]
        )
        
        field = "Jan-Feb Mo-Fr 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From January to February, from Monday to Friday: from 10:00 AM to 8:00 PM."]
        )
        
        field = "Jan 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["January: from 10:00 AM to 8:00 PM."]
        )
        
        field = "Jan,Dec 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["January and December: from 10:00 AM to 8:00 PM."]
        )
        
        field = "Jan,Dec 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["January and December: from 10:00 AM to 8:00 PM."]
        )
        
        field = "Dec 25 09:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            ["December 25: from 9:00 AM to 12:00 PM."]
        )
        
        field = "Dec 25,Jan 1 09:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            ["December 25 and January 1: from 9:00 AM to 12:00 PM."]
        )
        
        field = "Dec 24-26 09:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From December 24 to December 26: from 9:00 AM to 12:00 PM."]
        )
        
        field = "Dec Mo 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["December, Monday: from 10:00 AM to 8:00 PM."]
        )
        
        field = "Jan-Feb Mo 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From January to February, Monday: from 10:00 AM to 8:00 PM."]
        )
        
        field = "Jan-Feb Mo-Fr 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From January to February, from Monday to Friday: from 10:00 AM to 8:00 PM."]
        )
        
        field = "easter 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["On easter: from 10:00 AM to 8:00 PM."]
        )
        
        field = "PH,SH 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["Public and school holidays: from 10:00 AM to 8:00 PM."]
        )
        
        field = "PH Sa 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["Public holidays, on Saturday: from 10:00 AM to 8:00 PM."]
        )
        
        field = "SH Mo-Fr 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["School holidays, from Monday to Friday: from 10:00 AM to 8:00 PM."]
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
                "Public holidays: closed."
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


if __name__ == '__main__':
    unittest.main()
    exit(0)
