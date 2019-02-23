import lark

import os

from humanized_opening_hours.exceptions import InconsistentField


def get_parser():
    base_dir = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(base_dir, "field.ebnf"), 'r') as f:
        grammar = f.read()
    return lark.Lark(grammar, start="time_domain", parser="earley", debug=True)

PARSER = get_parser()


class SanitizerTransformer(lark.Transformer):
    def __init__(self, raise_exception=False):
        super().__init__()
        self.raise_exception = raise_exception  # TODO
    
    # time_domain
    def time_domain(self, args):
        parts = []
        for arg in args:
            if isinstance(arg, lark.lexer.Token):
                parts.append(
                    {';': '; ', ',': ', ', '||': ' || '}.get(arg.value.strip())
                )
            else:
                parts.append(arg.strip())
        return ''.join(parts)
    
    def wide_range_selectors(self, args):
        return ' '.join(args)
    
    def small_range_selectors(self, args):
        return ' '.join(args)
    
    def rule_sequence(self, args):
        return ' '.join(args)
    
    def selector_sequence_always_open(self, args):
        return "24/7"
    
    def selector_sequence_with_colon(self, args):
        args = [a for a in args if a]
        if len(args) == 1:
            return args[0] + ':'
        return args[0] + ': ' + ' '.join(args[1:])
    
    def selector_sequence_without_colon(self, args):
        return ' '.join([a for a in args if a])
    
    def selector_sequence_comment_time_selector(self, args):
        return args[0].value + ': ' + args[1]
    
    # weekday_selector
    def weekday_selector(self, args):
        return args[0]
    
    def weekday_selector_wd_and_holiday(self, args):
        return ','.join(args)
    
    def weekday_selector_wd_and_holiday_wrong(self, args):
        return ','.join(args[::-1])
    
    def weekday_selector_wd_in_holiday(self, args):
        return ' '.join(args)
    
    def weekday_sequence(self, args):
        return ','.join(args)
    
    def holiday_sequence(self, args):
        return ','.join(args)
    
    def weekday_range(self, args):
        return '-'.join([a.capitalize() for a in args])
    
    def weekday_range_nth(self, args):
        wday = args[0].capitalize()
        return wday + ''.join(args[1:])
    
    def holiday(self, args):
        if len(args) == 1:
            return args[0].value.upper()
        return args[0].value.upper() + args[1]
    
    def nth(self, args):
        return '[' + ','.join(args) + ']'
    
    def nth_entry(self, args):
        return '-'.join(args)
    
    def nth_entry_negative(self, args):
        return '-' + args[0]
    
    # week_selector
    def week_selector(self, args):
        return "week " + ','.join(args)
    
    def week(self, args):
        if len(args) == 1:
            return args[0].zfill(2)
        elif len(args) == 2:
            return args[0].zfill(2) + '-' + args[1].zfill(2)
        else:
            return "{}-{}/{}".format(args[0].zfill(2), args[1].zfill(2), args[2])
    
    # monthday_selector
    def monthday_selector(self, args):
        return ','.join(args)
    
    def monthday_range_ym(self, args):
        if len(args) == 2:
            return args[0] + ' ' + args[1].value.capitalize()
        return args[0].value.capitalize()
    
    def monthday_range_ymm(self, args):
        if len(args) == 2:
            return '-'.join([a.value.capitalize() for a in args])
        return args[0] + ' ' + args[1].value.capitalize() + '-' + args[2].value.capitalize()
    
    def monthday_range_date(self, args):
        return args[0]
    
    def monthday_range_date_plus(self, args):
        return args[0] + '+'
    
    def monthday_range_dd(self, args):
        return args[0] + '-' + args[1]
    
    def monthday_range_date_to(self, args):
        return args[0] + '-' + args[1]
    
    def date(self, args):
        if args[0].type == "VARIABLE_DATE":
            return ''.join(args)
        if isinstance(args[0], str):
            return args[0] + ' ' + args[1].value.capitalize() + ' '.join(args[2:])
        return args[0].value + ' '.join(args[1:])
    
    def date_offset(self, args):
        if len(args) == 1:
            return args[0]
        return args[0].value + args[1].value.capitalize() + args[2]
    
    def day_offset(self, args):
        offset_sign = args[0].value
        days = args[1].value
        if days == '1':
            return " {} 1 day".format(offset_sign)
        return " {}{} days".format(offset_sign, days)
    
    # year_selector
    def year_selector(self, args):
        return ','.join(args)
    
    def year_range(self, args):
        if len(args) == 1:
            return args[0]
        elif len(args) == 2:
            return args[0] + '-' + args[1]
        else:
            return args[0] + '-' + args[1] + '/' + args[2]
    
    def year_range_plus(self, args):
        return args[0] + '+'
    
    def year(self, args):
        return args[0]
    
    # time_selector
    def time_selector(self, args):
        return ','.join(args)
    
    def timespan_normal(self, args):
        return args[0]
    
    def timespan_plus(self, args):
        return args[0] + '+'
    
    def timespan_tt(self, args):
        return args[0] + '-' + args[1]
    
    def timespan_tt_plus(self, args):
        return args[0] + '-' + args[1] + '+'
    
    def timespan_tt_minute(self, args):
        return args[0] + '-' + args[1] + '/' + args[2]
    
    def timespan_tt_hm(self, args):
        return args[0] + '-' + args[1] + '/' + args[2]
    
    def time(self, args):
        return args[0]
    
    def hour_minutes(self, args):
        return args[0].value.zfill(2) + ':' + args[1].value.zfill(2)
    
    def variable_time_event(self, args):
        return args[0].value.lower()
    
    def variable_time_event_plus_time(self, args):
        event = args[0].value.lower()
        time = args[1]
        return "({}+{})".format(event, time)
    
    def variable_time_event_minus_time(self, args):
        event = args[0].value.lower()
        time = args[1]
        return "({}-{})".format(event, time)
    
    # rule_modifier
    def rule_modifier_open(self, args):
        if len(args) == 2:
            return "open " + args[1].value
        return "open"
    
    def rule_modifier_closed(self, args):
        if len(args) == 2:
            return args[0].value.lower() + ' ' + args[1].value
        return args[0].value.lower()
    
    def rule_modifier_unknown(self, args):
        if len(args) == 2:
            return "unknown " + args[1].value
        return "unknown"
    
    def rule_modifier_comment(self, args):
        return args[0].value


def pre_check_field(field):
    if field.count('"') % 2 != 0:
        raise InconsistentField("This field contains an odd number of quotes.")
    return field


def sanitize_field(field):
    tree = PARSER.parse(field)
    return SanitizerTransformer().transform(tree)


def sanitize_tree(tree):
    return SanitizerTransformer().transform(tree)
