import lark

import unittest
import datetime

import sanitization
from sanitization import sanitize_field
from rules_parsing import MainTransformer

import logging
logging.basicConfig(level=logging.DEBUG)


# THIS(?=(?:(?:[^"]*+"){2})*+[^"]*+\z)

def get_parser():
    with open("field.ebnf", 'r') as f:
        grammar = f.read()
    return lark.Lark(grammar, start="time_domain", parser="earley")

PARSER = get_parser()


class OHParser:
    def __init__(self, field):
        if not isinstance(field, str):
            raise TypeError("The field must be a string.")
        self.field = field
        sanitization.pre_check_field(field)
        tree = PARSER.parse(field)
        self.sanitized_field = sanitization.sanitize_tree(tree)
        self.rules = MainTransformer().transform(tree)
        self.PH = []
        self.SH = []
    
    def is_open(self, dt=None):
        if not dt:
            dt = datetime.datetime.now()
        for rule in self.rules[::-1]:
            match = rule.match_dt(dt, self.PH, self.SH)
            if match:
                return rule.is_open(dt, self.PH, self.SH)
        return False
    
    def period(self, dt=None):
        if not dt:
            dt = datetime.datetime.now()
        periods = []
        for rule in self.rules[::-1]:
            period = rule.period(dt, self.PH, self.SH)
            if period != (None, None):
                periods.append(period)
        if not periods:
            return None
        
        print(periods, self.is_open(dt))
        if self.is_open(dt):
            beginning = min(
                [p[1] for p in periods if p[1] != None and p[1] <= dt],
                key=lambda d: d - dt
            )
        else:
            beginning = min(
                [p[0] for p in periods if p[0] != None and p[0] <= dt],
                key=lambda d: d - dt
            )
        
        #closest_last_ending = min(
        #    [p[1] for p in periods if p[1] != None and p[1] <= dt],
        #    key=lambda d: d - dt
        #)
        if self.is_open(dt):
            ending = min(
                [p[1] for p in periods if p[1] != None and p[1] >= dt],
                key=lambda d: dt - d
            )
        else:
            ending = min(
                [p[0] for p in periods if p[0] != None and p[0] >= dt],
                key=lambda d: dt - d
            )
        
        return (beginning, ending)


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
        
        field = "easter +2 days 09:00-19:00"
        oh = OHParser(field)


class TestSanitize(unittest.TestCase):
    maxDiff = None
    
    def test_valid_fields(self):
        self.assertEqual(sanitize_field("Mo-Fr 10:00-20:00"), "Mo-Fr 10:00-20:00")
        self.assertEqual(sanitize_field("Mo 10:00-20:00"), "Mo 10:00-20:00")
        self.assertEqual(sanitize_field("Mo,We 10:00-20:00"), "Mo,We 10:00-20:00")
        self.assertEqual(sanitize_field("SH,Mo-Fr 10:00-20:00"), "SH,Mo-Fr 10:00-20:00")
        self.assertEqual(sanitize_field("PH,Mo-Fr 10:00-20:00"), "PH,Mo-Fr 10:00-20:00")
        self.assertEqual(sanitize_field("Mo-Fr,SH 10:00-20:00"), "SH,Mo-Fr 10:00-20:00")
        self.assertEqual(sanitize_field("Mo-Fr,PH 10:00-20:00"), "PH,Mo-Fr 10:00-20:00")
        self.assertEqual(sanitize_field("Mo-Fr 10:00-12:00,13:00-20:00"), "Mo-Fr 10:00-12:00,13:00-20:00")
        
        self.assertEqual(sanitize_field("PH 10:00-20:00"), "PH 10:00-20:00")
        self.assertEqual(sanitize_field("SH 10:00-20:00"), "SH 10:00-20:00")
        self.assertEqual(sanitize_field("SH,PH 10:00-20:00"), "SH,PH 10:00-20:00")
        
        self.assertEqual(sanitize_field("10:00-12:00,13:00-20:00"), "10:00-12:00,13:00-20:00")
        self.assertEqual(sanitize_field("10:00-20:00"), "10:00-20:00")
        
        self.assertEqual(sanitize_field("sunrise-sunset"), "sunrise-sunset")
        self.assertEqual(sanitize_field("(sunrise-01:00)-(sunset+01:00)"), "(sunrise-01:00)-(sunset+01:00)")
        
        self.assertEqual(sanitize_field("Jan-Feb 10:00-20:00"), "Jan-Feb 10:00-20:00")
        self.assertEqual(sanitize_field("Jan 10:00-20:00"), "Jan 10:00-20:00")
        self.assertEqual(sanitize_field("Jan,Aug 10:00-20:00"), "Jan,Aug 10:00-20:00")
        self.assertEqual(sanitize_field("Mo-Su 08:00-18:00; Apr 10-15 off; Jun 08:00-14:00; Aug off; Dec 25 off"), "Mo-Su 08:00-18:00; Apr 10-15 off; Jun 08:00-14:00; Aug off; Dec 25 off")
        
        self.assertEqual(sanitize_field("2010 10:00-20:00"), "2010 10:00-20:00")
        self.assertEqual(sanitize_field("2010-2020 10:00-20:00"), "2010-2020 10:00-20:00")
        self.assertEqual(sanitize_field("2010-2020/2 10:00-20:00"), "2010-2020/2 10:00-20:00")
        self.assertEqual(sanitize_field("2010-2020/2 Mo-Fr 10:00-20:00"), "2010-2020/2 Mo-Fr 10:00-20:00")
        
        self.assertEqual(sanitize_field("week 1 10:00-20:00"), "week 01 10:00-20:00")
        self.assertEqual(sanitize_field("week 1-10 10:00-20:00"), "week 01-10 10:00-20:00")
        self.assertEqual(sanitize_field("week 1-20/2 10:00-20:00"), "week 01-20/2 10:00-20:00")
        self.assertEqual(sanitize_field("week 1-20/2 Mo-Fr 10:00-20:00"), "week 01-20/2 Mo-Fr 10:00-20:00")
        
        self.assertEqual(sanitize_field("2010-2020/2 week 1-12/2 Mo-Fr 10:00-12:00,13:00-20:00"), "2010-2020/2 week 01-12/2 Mo-Fr 10:00-12:00,13:00-20:00")
        
        self.assertEqual(sanitize_field("Mo-Fr off"), "Mo-Fr off")
        self.assertEqual(sanitize_field("10:00-20:00 off"), "10:00-20:00 off")
        self.assertEqual(sanitize_field("PH off"), "PH off")
        self.assertEqual(sanitize_field("off"), "off")
        self.assertEqual(sanitize_field("closed"), "closed")
        
        self.assertEqual(sanitize_field("Dec 25: 09:00-12:00"), "Dec 25: 09:00-12:00")
        self.assertEqual(sanitize_field("Dec 25: closed"), "Dec 25: closed")
        self.assertEqual(sanitize_field('Dec 25: closed "except if there is snow"'), 'Dec 25: closed "except if there is snow"')
        
        self.assertEqual(sanitize_field('"on appointement"'), '"on appointement"')
        self.assertEqual(sanitize_field('Mo-Fr "on appointement"'), 'Mo-Fr "on appointement"')
        self.assertEqual(sanitize_field('Mo-Fr 10:00-20:00 "on appointement"'), 'Mo-Fr 10:00-20:00 "on appointement"')
        
        self.assertEqual(sanitize_field("Mo[1] 10:00-20:00"), "Mo[1] 10:00-20:00")
        self.assertEqual(sanitize_field("Mo[-1] 10:00-20:00"), "Mo[-1] 10:00-20:00")
        self.assertEqual(sanitize_field("Mo[1,3] 10:00-20:00"), "Mo[1,3] 10:00-20:00")
    
    def test_invalid_fields(self):
        # Case correction
        self.assertEqual(sanitize_field("mo-fr 10:00-20:00"), "Mo-Fr 10:00-20:00")
        self.assertEqual(sanitize_field("jan-feb 10:00-20:00"), "Jan-Feb 10:00-20:00")
        self.assertEqual(sanitize_field("jan-feb,aug 10:00-20:00"), "Jan-Feb,Aug 10:00-20:00")
        self.assertEqual(sanitize_field("SUNRISE-SUNSET"), "sunrise-sunset")
        self.assertEqual(sanitize_field("(SUNrISE-01:00)-(SUnsET+01:00)"), "(sunrise-01:00)-(sunset+01:00)")
        self.assertEqual(sanitize_field("su,sh off"), "SH,Su off")
        self.assertEqual(sanitize_field("mo-fr CLOSED"), "Mo-Fr closed")
        
        # Time correction
        self.assertEqual(sanitize_field("9:00-12:00"), "09:00-12:00")
        
        # Timespan correction
        self.assertEqual(sanitize_field("09 : 00 - 12 : 00 , 13 : 00 - 19 : 00"), "09:00-12:00,13:00-19:00")
        
        # Global
        self.assertEqual(sanitize_field("sunrise-( sunset+ 01h10)"), "sunrise-(sunset+01:10)")
        self.assertEqual(sanitize_field("Dec 25 : OFF"), "Dec 25: off")


if __name__ == '__main__':
    unittest.main()
    exit(0)
