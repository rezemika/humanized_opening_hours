import unittest
import datetime

import pytz
from lark import Tree
from lark.lexer import Token

from humanized_opening_hours import main, exceptions, field_parser

# flake8: noqa: F841
# "oh" variables unused in TestSolarHours.

# TODO : Add more unit tests for various formats.
# TODO : Test renderer methods.

PARSER_TREE = field_parser.get_parser(include_transformer=False)

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
    
    def test_4(self):
        field = "Mo-Fr 00:00-24:00"
        oh = main.OHParser(field)
        # Is it open?
        dt = datetime.datetime(2018, 1, 1, 10, 0, tzinfo=pytz.timezone("UTC"))
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 5, 10, 0, tzinfo=pytz.timezone("UTC"))
        self.assertTrue(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 6, 10, 0, tzinfo=pytz.timezone("UTC"))
        self.assertFalse(oh.is_open(dt))
        dt = datetime.datetime(2018, 1, 7, 10, 0, tzinfo=pytz.timezone("UTC"))
        self.assertFalse(oh.is_open(dt))
        # Periods
        dt = datetime.datetime(2018, 1, 1, 10, 0, tzinfo=pytz.timezone("UTC"))
        self.assertEqual(
            len(oh.get_day(dt).periods),
            1
        )
        self.assertEqual(
            oh.get_day(dt).periods[0].beginning.time(),
            datetime.time.min.replace(tzinfo=pytz.UTC)
        )
        # Handling of 'next_change()'
        dt = datetime.datetime(2018, 1, 7, 10, 0, tzinfo=pytz.timezone("UTC"))
        self.assertEqual(
            oh.next_change(dt, allow_recursion=False),
            datetime.datetime(2018, 1, 8, 0, 0, tzinfo=pytz.timezone("UTC"))
        )
        self.assertEqual(
            oh.next_change(dt, allow_recursion=True),
            datetime.datetime.combine(
                datetime.date(2018, 1, 11),
                datetime.time.max.replace(tzinfo=pytz.timezone("UTC"))
            )
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
        
        field = "Jan Mo 09:00-19:00"
        oh = main.OHParser(field)
        
        field = "Jan Mo-Fr 09:00-19:00"
        oh = main.OHParser(field)
        
        field = "Jan,Feb Mo 09:00-19:00"
        oh = main.OHParser(field)
        
        field = "Jan-Feb Mo 09:00-19:00"
        oh = main.OHParser(field)
        
        field = "Jan-Feb Mo-Fr 09:00-19:00"
        oh = main.OHParser(field)
        
        field = "SH Mo 09:00-19:00"
        oh = main.OHParser(field)
        
        field = "SH Mo-Fr 09:00-19:00"
        oh = main.OHParser(field)
        
        field = "easter 09:00-19:00"
        oh = main.OHParser(field)
        
        field = "easter +2 days 09:00-19:00"
        oh = main.OHParser(field)
        
    
    def test_exceptional_days(self):
        field = "Dec 25 off"
        oh = main.OHParser(field)
        self.assertEqual(len(oh._tree.get_exceptional_dates()), 1)
        
        field = "Jan 1 13:00-19:00"
        oh = main.OHParser(field)
        self.assertEqual(len(oh._tree.get_exceptional_dates()), 1)
        
        field = "Jan 1 13:00-19:00; Dec 25 off"
        oh = main.OHParser(field)
        self.assertEqual(len(oh._tree.get_exceptional_dates()), 2)
    
    def test_invalid_days(self):
        field = "Mo,Wx 09:00-12:00,13:00-19:00"
        with self.assertRaises(exceptions.ParseError) as context:
            oh = main.OHParser(field)
        field = "Pl-Mo 09:00-12:00,13:00-19:00"
        with self.assertRaises(exceptions.ParseError) as context:
            oh = main.OHParser(field)
    
    def test_invalid_patterns(self):
        field = "Mo-Fr 20:00-02:00"
        with self.assertRaises(exceptions.SpanOverMidnight) as context:
            oh = main.OHParser(field)
        
        field = "Su[1] 10:00-20:00"
        with self.assertRaises(exceptions.ParseError) as context:
            oh = main.OHParser(field)
        
        field = "SH,PH Mo-Fr 10:00-20:00"
        with self.assertRaises(exceptions.ParseError) as context:
            oh = main.OHParser(field)
        
        field = "SH,PH Mo-Fr,Su 10:00-20:00"
        with self.assertRaises(exceptions.ParseError) as context:
            oh = main.OHParser(field)
        
        field = "Jan-Feb,Aug Mo-Fr,Su 10:00-20:00"
        with self.assertRaises(exceptions.ParseError) as context:
            oh = main.OHParser(field)
        
        field = "week 1-53/2 Fr 09:00-12:00"
        with self.assertRaises(exceptions.ParseError) as context:
            oh = main.OHParser(field)

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
    
    def test_invalid_3(self):
        field = "Mo 09:00 - 12:00 , 13:00 - 19:00;"
        sanitized_field = "Mo 09:00-12:00,13:00-19:00"
        self.assertEqual(main.OHParser.sanitize(field), sanitized_field)
    
    def test_invalid_4(self):
        field = "Mo 10:00-12:00 14:00-19:00; Tu-Sa 10:00-19:00"
        sanitized_field = "Mo 10:00-12:00,14:00-19:00; Tu-Sa 10:00-19:00"
        self.assertEqual(main.OHParser.sanitize(field), sanitized_field)
    
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
    
    def test_easter_date(self):
        self.assertEqual(
            field_parser.easter_date(2000),
            datetime.date(2000, 4, 23)
        )
        self.assertEqual(
            field_parser.easter_date(2010),
            datetime.date(2010, 4, 4)
        )
        self.assertEqual(
            field_parser.easter_date(2020),
            datetime.date(2020, 4, 12)
        )

class TestParsing(unittest.TestCase):
    maxDiff = None
    
    def test_1(self):
        field = "Mo-Sa 09:00-19:00"
        expected_tree = Tree('field', [
            Tree('field_part', [
                Tree('consecutive_day_range', [
                    Tree('raw_consecutive_day_range', [
                        Token('DAY', 'Mo'), Token('DAY', 'Sa')
                    ])
                ]),
                Tree('day_periods', [
                    Tree('period', [
                        Tree('digital_moment', [
                            Token('DIGITAL_MOMENT', '09:00')
                        ]),
                        Tree('digital_moment', [
                            Token('DIGITAL_MOMENT', '19:00')
                        ])
                    ])
                ])
            ])
        ])
        
        tree = PARSER_TREE.parse(field)
        self.assertEqual(tree, expected_tree)
    
    def test_2(self):
        field = "24/7"
        expected_tree = Tree('field', [Tree('always_open', [])])
        
        tree = PARSER_TREE.parse(field)
        self.assertEqual(tree, expected_tree)
    
    def test_3(self):
        field = "sunrise-sunset"
        expected_tree = Tree('field', [
            Tree('everyday_periods', [
                Tree('day_periods', [
                    Tree('period', [
                        Tree('solar_moment', [
                            Token('SOLAR', 'sunrise')
                        ]),
                        Tree('solar_moment', [
                            Token('SOLAR', 'sunset')
                        ])
                    ])
                ])
            ])
        ])
        
        tree = PARSER_TREE.parse(field)
        self.assertEqual(tree, expected_tree)
    
    def test_4(self):
        field = "Jan-Feb 08:00-20:00"
        expected_tree = Tree('field', [
            Tree('field_part', [
                Tree('consecutive_month_range', [
                    Tree('raw_consecutive_month_range', [
                        Token('MONTH', 'Jan'), Token('MONTH', 'Feb')
                    ])
                ]),
                Tree('day_periods', [
                    Tree('period', [
                        Tree('digital_moment', [
                            Token('DIGITAL_MOMENT', '08:00')
                        ]),
                        Tree('digital_moment', [
                            Token('DIGITAL_MOMENT', '20:00')
                        ])
                    ])
                ])
            ])
        ])
        
        tree = PARSER_TREE.parse(field)
        self.assertEqual(tree, expected_tree)
    
    def test_5(self):
        field = "08:00-20:00; SH off"
        expected_tree = Tree('field', [
            Tree('everyday_periods', [
                Tree('day_periods', [
                    Tree('period', [
                        Tree('digital_moment', [
                            Token('DIGITAL_MOMENT', '08:00')
                        ]),
                        Tree('digital_moment', [
                            Token('DIGITAL_MOMENT', '20:00')
                        ])
                    ])
                ])
            ]),
            Tree('field_part', [
                Tree('holiday', [
                    Token('SCHOOL_HOLIDAYS', 'SH')
                ]),
                Tree('period_closed', [])
            ])
        ])
        
        tree = PARSER_TREE.parse(field)
        self.assertEqual(tree, expected_tree)

if __name__ == '__main__':
    unittest.main()
    exit(0)
