import unittest
import datetime, pytz

import main, exceptions

# flake8: noqa: F841
# "oh" variables unused in TestSolarHours.

# TODO : Add more unit tests for various formats.
# TODO : Test renderer methods.

class TestGlobal(unittest.TestCase):
    maxDiff = None
    
    def test_1(self):
        field = "Mo-Sa 09:00-19:00"
        oh = main.OHParser(field)
        dt = datetime.datetime(2017, 1, 2, 15, 30, tzinfo=pytz.timezone("Europe/Paris"))
        # Is it open?
        self.assertTrue(oh.is_open(dt))
    
    def test_2(self):
        field = "Mo,Th 09:00-12:00,13:00-19:00"
        oh = main.OHParser(field)
        # Is it open?
        dt = datetime.datetime(2016, 2, 1, 15, 30, tzinfo=pytz.timezone("UTC"))
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2016, 2, 1, 19, 30, tzinfo=pytz.timezone("UTC"))
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2016, 2, 1, 12, 10, tzinfo=pytz.timezone("UTC"))
        self.assertFalse(oh.is_open(dt))
        # Next change.
        self.assertEqual(
            oh.next_change(dt),
            datetime.datetime(2016, 2, 1, 13, 0, tzinfo=pytz.timezone("UTC"))
        )
    
    def test_3(self):
        field = "24/7"
        oh = main.OHParser(field)
        # Is it open?
        dt = datetime.datetime(2016, 2, 1, 15, 30, tzinfo=pytz.timezone("UTC"))
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2016, 2, 1, 19, 30, tzinfo=pytz.timezone("UTC"))
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2016, 2, 1, 12, 10, tzinfo=pytz.timezone("UTC"))
        self.assertTrue(oh.is_open(dt))
        # Periods
        self.assertEqual(
            oh.get_day(datetime.date.today()).periods[0].beginning.time(),
            datetime.time.min.replace(tzinfo=pytz.UTC)
        )

class TestPatterns(unittest.TestCase):
    # Checks there is no error with regular fields.
    maxDiff = None
    
    def test_regulars(self):
        field = "Mo-Sa 09:00-19:00"
        oh = main.OHParser(field)
        
        field = "Mo,Th 09:00-sunset"
        oh = main.OHParser(field)
        
        field = "Mo,Th (sunrise+02:00)-sunset"
        oh = main.OHParser(field)
        
        field = "Mo,SH 09:00-19:00"
        oh = main.OHParser(field)
        
        field = "Mo,SH 09:00-19:00"
        oh = main.OHParser(field)
        
        field = "Jan 09:00-19:00"
        oh = main.OHParser(field)
        
        field = "Jan-Feb 09:00-19:00"
        oh = main.OHParser(field)
        
        field = "Jan,Aug 09:00-19:00"
        oh = main.OHParser(field)
    
    def test_exceptional_days(self):
        field = "Dec 25 off"
        oh = main.OHParser(field)
        self.assertEqual(len(oh._tree.exceptional_dates), 1)
        
        field = "Jan 1 13:00-19:00"
        oh = main.OHParser(field)
        self.assertEqual(len(oh._tree.exceptional_dates), 1)
        
        field = "Jan 1 13:00-19:00; Dec 25 off"
        oh = main.OHParser(field)
        self.assertEqual(len(oh._tree.exceptional_dates), 2)

class TestSanitize(unittest.TestCase):
    maxDiff = None
    
    def test_valid_1(self):
        field = "Mo-Sa 09:00-19:00"
        sanitized_field = main.OHParser.sanitize(field)
        self.assertEqual(sanitized_field, field)
    
    def test_valid_2(self):
        field = "Mo,Th 09:00-12:00,13:00-19:00"
        sanitized_field = main.OHParser.sanitize(field)
        self.assertEqual(sanitized_field, field)
    
    def test_invalid_1(self):
        field = "Mo-sa 0900-19:00"
        sanitized_field = "Mo-Sa 09:00-19:00"
        self.assertEqual(main.OHParser.sanitize(field), sanitized_field)
    
    def test_invalid_2(self):
        field = "Mo,th 9:00-1200,13:00-19:00"
        sanitized_field = "Mo,Th 09:00-12:00,13:00-19:00"
        self.assertEqual(main.OHParser.sanitize(field), sanitized_field)
    
    def test_invalid_days(self):
        field = "Mo,Wx 09:00-12:00,13:00-19:00"
        with self.assertRaises(exceptions.ParseError) as context:
            oh = main.OHParser(field)
        field = "Pl-Mo 09:00-12:00,13:00-19:00"
        with self.assertRaises(exceptions.ParseError) as context:
            oh = main.OHParser(field)
        
    def test_holidays(self):
        field = "Mo-Sa,SH 09:00-19:00"
        self.assertEqual(main.OHParser.sanitize(field), field)
        field = "Mo-Sa 09:00-19:00; PH off"
        self.assertEqual(main.OHParser.sanitize(field), field)

class TestSolarHours(unittest.TestCase):
    maxDiff = None
    
    def test_valid_solar(self):
        # Sunrise.
        field = "Mo,Th 09:00-12:00,13:00-sunrise"
        oh = main.OHParser(field)
        # Sunset.
        field = "Mo,Th 09:00-12:00,13:00-sunset"
        oh = main.OHParser(field)
    
    def test_invalid_solar(self):
        # Sunrise.
        field = "Mo,Th 09:00-12:00,13:00-(sunrise)"
        with self.assertRaises(exceptions.ParseError) as context:
            oh = main.OHParser(field)
        # Sunset.
        field = "Mo,Th 09:00-12:00,13:00-(sunset)"
        with self.assertRaises(exceptions.ParseError) as context:
            oh = main.OHParser(field)
    
    def test_valid_solar_offset(self):
        # Sunrise.
        field = "Mo,Th 09:00-12:00,13:00-(sunrise+02:00)"
        oh = main.OHParser(field)
        # Sunset.
        field = "Mo,Th 09:00-12:00,13:00-(sunset-02:00)"
        oh = main.OHParser(field)
    
    def test_invalid_solar_offset(self):
        field = "Mo,Th 09:00-12:00,13:00-(sunrise=02:00)"
        with self.assertRaises(exceptions.ParseError) as context:
            oh = main.OHParser(field)
        field = "Mo,Th 09:00-12:00,13:00-(sunrise02:00)"
        with self.assertRaises(exceptions.ParseError) as context:
            oh = main.OHParser(field)
        field = "Mo,Th 09:00-12:00,13:00-(sunrise+02:00"
        with self.assertRaises(exceptions.ParseError) as context:
            oh = main.OHParser(field)

class TestFunctions(unittest.TestCase):
    maxDiff = None
    
    def test_days_of_week_from_day(self):
        dt = datetime.date(2018, 2, 5)
        self.assertEqual(
            main.days_of_week_from_day(dt),
            [
                datetime.date(2018, 2, 5),
                datetime.date(2018, 2, 6),
                datetime.date(2018, 2, 7),
                datetime.date(2018, 2, 8),
                datetime.date(2018, 2, 9),
                datetime.date(2018, 2, 10),
                datetime.date(2018, 2, 11)
            ]
        )
    
    def test_days_from_week_number(self):
        self.assertEqual(
            main.days_from_week_number(2018, 1),
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

if __name__ == '__main__':
    unittest.main()
    exit(0)
