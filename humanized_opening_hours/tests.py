import unittest
import main, exceptions
import datetime, pytz

class TestGlobal(unittest.TestCase):
    maxDiff = None
    
    def test_1(self):
        field = "Mo-Sa 09:00-19:00"
        oh = main.OHParser(field, year=2017)
        dt = datetime.datetime(2017, 1, 2, 15, 30, tzinfo=pytz.timezone("Europe/Paris"))
        # Is it open?
        self.assertTrue(oh.is_open(dt))
        # Periods per day.
        self.assertEqual(len(oh.year.all_days[0].periods), 1)
        self.assertEqual(len(oh.year.all_days[1].periods), 1)
        self.assertEqual(len(oh.year.all_days[6].periods), 0)
        # Next change.
        self.assertEqual(
            oh.next_change(dt).dt,
            datetime.datetime(2017, 1, 2, 19, 0, tzinfo=pytz.timezone("UTC"))
        )
        # Rendering.
        self.assertEqual(
            str(oh.year.all_days[0].periods[0].beginning),
            "09:00"
        )
        self.assertEqual(
            str(oh.year.all_days[0].periods[0]),
            "09:00 - 19:00"
        )
    
    def test_2(self):
        field = "Mo,Th 09:00-12:00,13:00-19:00"
        oh = main.OHParser(field, year=2016)
        # Is it open?
        dt = datetime.datetime(2016, 2, 1, 15, 30, tzinfo=pytz.timezone("UTC"))
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2016, 2, 1, 19, 30, tzinfo=pytz.timezone("UTC"))
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2016, 2, 1, 12, 10, tzinfo=pytz.timezone("UTC"))
        self.assertFalse(oh.is_open(dt))
        # Periods per day.
        self.assertEqual(len(oh.year.all_days[0].periods), 2)
        self.assertEqual(len(oh.year.all_days[1].periods), 0)
        self.assertEqual(len(oh.year.all_days[3].periods), 2)
        # Next change.
        self.assertEqual(
            oh.next_change(dt).dt,
            datetime.datetime(2016, 2, 1, 13, 0, tzinfo=pytz.timezone("UTC"))
        )
        # Rendering.
        self.assertEqual(
            str(oh.year.all_days[0].periods[0].end),
            "12:00"
        )
        self.assertEqual(
            str(oh.year.all_days[0].periods[0]),
            "09:00 - 12:00"
        )

class TestPatterns(unittest.TestCase):
    # Checks there is no error with regular fields.
    maxDiff = None
    
    def test_regulars(self):
        field = "24/7"
        oh = main.OHParser(field)
        self.assertTrue(oh.year.always_open)
        
        field = "Mo-Sa 09:00-19:00"
        oh = main.OHParser(field)
        self.assertFalse(oh.year.always_open)
        
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
        self.assertEqual(len(oh.year.exceptional_days), 1)
        
        field = "Jan 1 13:00-19:00"
        oh = main.OHParser(field)
        self.assertEqual(len(oh.year.exceptional_days), 1)
        
        field = "Jan 1 13:00-19:00; Dec 25 off"
        oh = main.OHParser(field)
        self.assertEqual(len(oh.year.exceptional_days), 2)

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
        with self.assertRaises(exceptions.DoesNotExistError) as context:
            oh = main.OHParser(field)
        field = "Pl-Mo 09:00-12:00,13:00-19:00"
        with self.assertRaises(exceptions.DoesNotExistError) as context:
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

class TestRenderers(unittest.TestCase):
    maxDiff = None
    
    def test_periods_per_day(self):
        field = "Mo-We 09:00-19:00"
        oh = main.OHParser(field, year=2017)
        expected = ["09:00 - 19:00"]
        self.assertEqual(oh.render().humanized_periods_of_day(oh.year.all_days[0]), expected)
    
    def test_time_before_next_change(self):
        field = "Mo-We 09:00-19:00"
        oh = main.OHParser(field, year=2017)
        dt = datetime.datetime(2017, 1, 2, 15, 30, tzinfo=pytz.timezone("Europe/Paris"))
        self.assertEqual(
            oh.render(locale_name="en").humanized_time_before_next_change(dt),
            "in 4 hours"
        )
    
    def test_description_1(self):
        f = "Mo-Fr 10:00-19:00 ; week 1 Mo 08:00-20:00 ; SH off"
        oh = main.OHParser(f, year=2017)
        ohr = oh.render(locale_name="en")
        expected = """\
Week 1:
    Monday: 08:00 - 20:00
    Tuesday: closed
    Wednesday: closed
    Thursday: closed
    Friday: closed
    Saturday: closed
    Sunday: closed

Weeks 2 - 53:
    Monday: 10:00 - 19:00
    Tuesday: 10:00 - 19:00
    Wednesday: 10:00 - 19:00
    Thursday: 10:00 - 19:00
    Friday: 10:00 - 19:00
    Saturday: closed
    Sunday: closed

Open on public holidays. Closed on school holidays."""
        self.assertEqual(
            ohr.description(indent=4),
            expected
        )
    
    def test_description_2(self):
        f = "Mo-Fr 10:00-19:00 ; week 1 Mo 08:00-20:00 ; SH off"
        oh = main.OHParser(f, year=2017)
        ohr = oh.render(locale_name="en")
        expected = """\
Week 1:
    Monday: 08:00 - 20:00
    Tuesday: closed
    Wednesday: closed
    Thursday: closed
    Friday: closed
    Saturday: closed
    Sunday: closed

Weeks 2 - 53:
    Monday: 10:00 - 19:00
    Tuesday: 10:00 - 19:00
    Wednesday: 10:00 - 19:00
    Thursday: 10:00 - 19:00
    Friday: 10:00 - 19:00
    Saturday: closed
    Sunday: closed"""
        self.assertEqual(
            ohr.description(indent=4, holidays=False),
            expected
        )
    
    def test_description_3(self):
        f = "Mo-Sa 10:00-19:00 ; Su 10:00-sunset"
        oh = main.OHParser(f, year=2017)
        ohr = oh.render(locale_name="en")
        expected = """\
Weeks 1 - 53:
    Monday: 10:00 - 19:00
    Tuesday: 10:00 - 19:00
    Wednesday: 10:00 - 19:00
    Thursday: 10:00 - 19:00
    Friday: 10:00 - 19:00
    Saturday: 10:00 - 19:00
    Sunday: 10:00 - sunset

Open on public and school holidays."""
        self.assertEqual(
            ohr.description(indent=4),
            expected
        )

if __name__ == '__main__':
    unittest.main()
    exit(0)
