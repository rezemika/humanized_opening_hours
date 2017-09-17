import unittest
import humanized_opening_hours
import datetime, pytz

class TestGlobal(unittest.TestCase):
    def test_1(self):
        field = "Mo-Sa 09:00-19:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        dt = datetime.datetime(2017, 1, 2, 15, 30, tzinfo=pytz.timezone("UTC"))
        # Is open?
        self.assertTrue(hoh.is_open(dt))
        # Periods per day.
        self.assertEqual(len(hoh._opening_periods[0].periods), 1)
        self.assertEqual(len(hoh._opening_periods[1].periods), 1)
        self.assertEqual(len(hoh._opening_periods[6].periods), 0)
        # Next change.
        self.assertEqual(
            hoh.next_change(dt),
            datetime.datetime(2017, 1, 2, 19, 0, tzinfo=pytz.timezone("UTC"))
        )
        # Time before next change.
        self.assertEqual(
            hoh.time_before_next_change(dt),
            datetime.timedelta(hours=3, minutes=30)
        )
        # Rendering.
        hohr = humanized_opening_hours.HOHRenderer(hoh)
        self.assertEqual(
            hohr.render_moment(hoh[0].periods[0].m1),
            "09:00"
        )
        self.assertEqual(
            hohr.render_period(hoh[0].periods[0]),
            "09:00 - 19:00"
        )
    
    def test_2(self):
        field = "Mo,Th 09:00-12:00,13:00-19:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        # Is open?
        dt = datetime.datetime(2016, 2, 1, 15, 30, tzinfo=pytz.timezone("UTC"))
        self.assertTrue(hoh.is_open(dt))
        dt = datetime.datetime(2016, 2, 1, 19, 30, tzinfo=pytz.timezone("UTC"))
        self.assertFalse(hoh.is_open(dt))
        dt = datetime.datetime(2016, 2, 1, 12, 10, tzinfo=pytz.timezone("UTC"))
        self.assertFalse(hoh.is_open(dt))
        # Periods per day.
        self.assertEqual(len(hoh._opening_periods[0].periods), 2)
        self.assertEqual(len(hoh._opening_periods[1].periods), 0)
        self.assertEqual(len(hoh._opening_periods[3].periods), 2)
        # Next change.
        self.assertEqual(
            hoh.next_change(dt),
            datetime.datetime(2016, 2, 1, 13, 0, tzinfo=pytz.timezone("UTC"))
        )
        # Time before next change.
        self.assertEqual(
            hoh.time_before_next_change(dt),
            datetime.timedelta(minutes=50)
        )
        # Rendering.
        hohr = humanized_opening_hours.HOHRenderer(hoh)
        self.assertEqual(
            hohr.render_moment(hoh[0].periods[0].m2),
            "12:00"
        )
        self.assertEqual(
            hohr.render_period(hoh[0].periods[0]),
            "09:00 - 12:00"
        )
    
    def test_3(self):
        field = "Mo-Sa 09:00-19:00 ; Su 09:00-12:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        # Is open?
        dt = datetime.datetime(2017, 1, 2, 15, 30, tzinfo=pytz.timezone("UTC"))
        self.assertTrue(hoh.is_open(dt))
        # Periods per day.
        self.assertEqual(len(hoh._opening_periods[0].periods), 1)
        self.assertEqual(len(hoh._opening_periods[1].periods), 1)
        self.assertEqual(len(hoh._opening_periods[6].periods), 1)
        # Next change.
        self.assertEqual(
            hoh.next_change(dt),
            datetime.datetime(2017, 1, 2, 19, 0, tzinfo=pytz.timezone("UTC"))
        )
        # Time before next change.
        dt = datetime.datetime(2017, 1, 8, 15, 30, tzinfo=pytz.timezone("UTC"))
        self.assertEqual(
            hoh.time_before_next_change(dt),
            datetime.timedelta(days=1, hours=3, minutes=30)
        )
        # Rendering.
        hohr = humanized_opening_hours.HOHRenderer(hoh)
        self.assertEqual(
            hohr.render_moment(hoh[6].periods[0].m1),
            "09:00"
        )
        self.assertEqual(
            hohr.render_period(hoh[6].periods[0]),
            "09:00 - 12:00"
        )

class TestSanitize(unittest.TestCase):
    def test_valid_1(self):
        field = "Mo-Sa 09:00-19:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        self.assertEqual(hoh.field, field)
    
    def test_valid_2(self):
        field = "Mo,Th 09:00-12:00,13:00-19:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        self.assertEqual(hoh.field, field)
    
    def test_invalid_1(self):
        field = "Mo-sa 0900-19:00"
        sanitized_field = "Mo-Sa 09:00-19:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        self.assertEqual(hoh.field, sanitized_field)
    
    def test_invalid_2(self):
        field = "Mo,th 9:00-1200,13:00-19:00"
        sanitized_field = "Mo,Th 09:00-12:00,13:00-19:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        self.assertEqual(hoh.field, sanitized_field)
    
    def test_invalid_days(self):
        field = "Mo,Wx 09:00-12:00,13:00-19:00"
        with self.assertRaises(humanized_opening_hours.DoesNotExistError) as context:
            hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        field = "Pl-Mo 09:00-12:00,13:00-19:00"
        with self.assertRaises(humanized_opening_hours.DoesNotExistError) as context:
            hoh = humanized_opening_hours.HumanizedOpeningHours(field)
    
    def test_holidays(self):
        field = "Mo-Sa,SH 09:00-19:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        self.assertEqual(hoh.field, field)
        
        field = "Mo-Sa 09:00-19:00 ; PH off"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        self.assertEqual(hoh.field, field)

class TestSolarHours(unittest.TestCase):
    def test_valid_solar(self):
        # Sunrise.
        field = "Mo,Th 09:00-12:00,13:00-sunrise"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        # Sunset.
        field = "Mo,Th 09:00-12:00,13:00-sunset"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
    
    def test_invalid_solar(self):
        # Sunrise.
        field = "Mo,Th 09:00-12:00,13:00-(sunrise)"
        with self.assertRaises(humanized_opening_hours.ParseError) as context:
            hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        # Sunset.
        field = "Mo,Th 09:00-12:00,13:00-(sunset)"
        with self.assertRaises(humanized_opening_hours.ParseError) as context:
            hoh = humanized_opening_hours.HumanizedOpeningHours(field)
    
    def test_valid_solar_offset(self):
        # Sunrise.
        field = "Mo,Th 09:00-12:00,13:00-(sunrise+02:00)"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        # Sunset.
        field = "Mo,Th 09:00-12:00,13:00-(sunset-02:00)"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
    
    def test_invalid_solar_offset(self):
        field = "Mo,Th 09:00-12:00,13:00-(sunrise=02:00)"
        with self.assertRaises(humanized_opening_hours.ParseError) as context:
            hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        field = "Mo,Th 09:00-12:00,13:00-(sunrise02:00)"
        with self.assertRaises(humanized_opening_hours.ParseError) as context:
            hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        field = "Mo,Th 09:00-12:00,13:00-(sunrise+02:00"
        with self.assertRaises(humanized_opening_hours.ParseError) as context:
            hoh = humanized_opening_hours.HumanizedOpeningHours(field)

class TestMethods(unittest.TestCase):
    def test_get_day(self):
        field = "Mo,Th 09:00-12:00,13:00-19:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        self.assertEqual(hoh.get_day(0), hoh[0])
        self.assertEqual(hoh.get_day(6), hoh[6])
        self.assertEqual(hoh.get_day("SH"), hoh["SH"])

class TestRenderers(unittest.TestCase):
    def test_periods_per_day(self):
        field = "Mo-We 09:00-19:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        hohr = humanized_opening_hours.HOHRenderer(hoh)
        field_dict = {
            0: ("Monday", ["09:00 - 19:00"]),
            1: ("Tuesday", ["09:00 - 19:00"]),
            2: ("Wednesday", ["09:00 - 19:00"]),
            3: ('Thursday', []),
            4: ('Friday', []),
            5: ('Saturday', []),
            6: ('Sunday', []),
        }
        self.assertDictEqual(hohr.periods_per_day(), field_dict)
    
    def test_periods_per_day_not_universal(self):
        field = "Mo-We 09:00-19:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        hohr = humanized_opening_hours.HOHRenderer(hoh, universal=False)
        field_dict = {
            0: ("Monday", ["09:00 - 19:00"]),
            1: ("Tuesday", ["09:00 - 19:00"]),
            2: ("Wednesday", ["09:00 - 19:00"]),
            3: ('Thursday', []),
            4: ('Friday', []),
            5: ('Saturday', []),
            6: ('Sunday', []),
        }
        self.assertDictEqual(hohr.periods_per_day(), field_dict)
    
    def test_periods_per_day_solar_not_universal(self):
        field = "Mo-We sunrise-19:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        with self.assertRaises(humanized_opening_hours.NotParsedError) as context:
            hohr = humanized_opening_hours.HOHRenderer(hoh, universal=False)
    
    def test_periods_per_day_solar_universal(self):
        field = "Mo-We sunrise-19:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        hohr = humanized_opening_hours.HOHRenderer(hoh)
        field_dict = {
            0: ("Monday", ["sunrise - 19:00"]),
            1: ("Tuesday", ["sunrise - 19:00"]),
            2: ("Wednesday", ["sunrise - 19:00"]),
            3: ('Thursday', []),
            4: ('Friday', []),
            5: ('Saturday', []),
            6: ('Sunday', []),
        }
        self.assertDictEqual(hohr.periods_per_day(), field_dict)
    
    def test_closed_days(self):
        field = "Mo-We 09:00-19:00 ; Dec 25 off ; May 1 off"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        hohr = humanized_opening_hours.HOHRenderer(hoh)
        self.assertEqual(hohr.closed_days(), ["25 December", "1st May"])
        return
    
    def test_holidays(self):
        field = "Mo-We 09:00-19:00 ; SH off ; PH 09:00-12:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        hohr = humanized_opening_hours.HOHRenderer(hoh)
        self.assertEqual(
            hohr.holidays(),
            {
                "main": "Open on public holidays. Closed on school holidays.",
                "PH": (True, ["09:00 - 12:00"]),
                "SH": (False, []),
            }
        )
        return
    
    def test_description(self):
        field = "Mo-We 09:00-19:00 ; SH off ; PH 09:00-12:00"
        description = """\
Monday: 09:00 - 19:00
Tuesday: 09:00 - 19:00
Wednesday: 09:00 - 19:00
Thursday: closed
Friday: closed
Saturday: closed
Sunday: closed

Public holidays: 09:00 - 12:00
Open on public holidays. Closed on school holidays."""
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        hohr = humanized_opening_hours.HOHRenderer(hoh)
        self.assertEqual(
            hohr.description(),
            description
        )
        
        # With translation.
        field = "Mo,SH 09:00-19:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        hohr = humanized_opening_hours.HOHRenderer(hoh, lang="fr")
        description = """\
Lundi : 09:00 - 19:00
Mardi : fermé
Mercredi : fermé
Jeudi : fermé
Vendredi : fermé
Samedi : fermé
Dimanche : fermé

Vacances scolaires : 09:00 - 19:00
Ouvert durant les vacances scolaires."""
        self.assertEqual(
            hohr.description(),
            description
        )
        
        # Without holidays.
        field = "Mo,SH 09:00-19:00"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        hohr = humanized_opening_hours.HOHRenderer(hoh, lang="fr")
        description = """\
Lundi : 09:00 - 19:00
Mardi : fermé
Mercredi : fermé
Jeudi : fermé
Vendredi : fermé
Samedi : fermé
Dimanche : fermé"""
        self.assertEqual(
            hohr.description(holidays=False),
            description
        )
        
        # 24/7.
        field = "24/7"
        hoh = humanized_opening_hours.HumanizedOpeningHours(field)
        hohr = humanized_opening_hours.HOHRenderer(hoh)
        description = "Open 24 hours a day and 7 days a week."
        self.assertEqual(
            hohr.description(),
            description
        )
        return

if __name__ == '__main__':
    unittest.main()
    exit(0)
