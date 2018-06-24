import unittest
import datetime

from lark import Tree
from lark.lexer import Token

from humanized_opening_hours import field_parser
from humanized_opening_hours.main import OHParser, sanitize, DayPeriods
from humanized_opening_hours.temporal_objects import easter_date
from humanized_opening_hours.exceptions import (
    HOHError,
    ParseError,
    SolarHoursError,
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


class TestSolarHours(unittest.TestCase):
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


class TestFieldDescription(unittest.TestCase):
    maxDiff = None
    
    def test_regulars(self):
        field = "Mo-Fr 10:00-19:00; Sa 10:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From Monday to Friday: from 10:00 to 19:00.", "On Saturday: from 10:00 to 12:00."]
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
                "Public holidays: from 10:00 to 20:00."
            ]
        )
        
        field = "10:00-(sunset+02:00)"
        self.assertEqual(
            OHParser(field).description(),
            ["Every days: from 10:00 to 02:00 after sunset."]
        )
        
        field = "Jan-Feb 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From January to February: from 10:00 to 20:00."]
        )
        
        field = "Jan-Feb Mo-Fr 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From January to February, from Monday to Friday: from 10:00 to 20:00."]
        )
        
        field = "Jan 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["January: from 10:00 to 20:00."]
        )
        
        field = "Jan,Dec 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["January and December: from 10:00 to 20:00."]
        )
        
        field = "Jan,Dec 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["January and December: from 10:00 to 20:00."]
        )
        
        field = "Dec 25 09:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            ["December 25: from 09:00 to 12:00."]
        )
        
        field = "Dec 25,Jan 1 09:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            ["December 25 and January 1: from 09:00 to 12:00."]
        )
        
        field = "Dec 24-26 09:00-12:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From December 24 to December 26: from 09:00 to 12:00."]
        )
        
        field = "Dec Mo 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["December, Monday: from 10:00 to 20:00."]
        )
        
        field = "Jan-Feb Mo 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From January to February, Monday: from 10:00 to 20:00."]
        )
        
        field = "Jan-Feb Mo-Fr 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["From January to February, from Monday to Friday: from 10:00 to 20:00."]
        )
        
        field = "easter 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["On easter: from 10:00 to 20:00."]
        )
        
        field = "PH,SH 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["Public and school holidays: from 10:00 to 20:00."]
        )
        
        field = "PH Sa 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["Public holidays, on Saturday: from 10:00 to 20:00."]
        )
        
        field = "SH Mo-Fr 10:00-20:00"
        self.assertEqual(
            OHParser(field).description(),
            ["School holidays, from Monday to Friday: from 10:00 to 20:00."]
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


if __name__ == '__main__':
    unittest.main()
    exit(0)
