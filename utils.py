from itertools import islice, chain, repeat
import re

import parsley

o_re = "(<=|<|>=|>|~|\^){0,1}"
v_re = "(?P<version>[^-+]+)(?:\-|\+){0,1}"
t_re = "(?P<type>alpha|beta|rc|build){0,1}"
n_re = "(?P<num>\d+){0,1}"
version_re = re.compile(o_re + v_re + t_re + n_re)
META_RANKING = {
    'alpha': 0,
    'beta': 1,
    'rc': 2,
    'build': 3
}

version_grammar = """
N = (<digit+> | 'x' | '*')
N1 = '.' N
V = <O N N1{0,2} (META | BUILD){0,1}>:version -> version
V1 = <O>:op <N N1{0,3}>:version <(META1 | BUILD1){0,1}>:type_and_num ->  op, version, type_and_num[0] , type_and_num[1]
DASHED = V:l '-' V:r -> map(VersionMatcher, [">="+ l,  "<=" + r])
O = ('~' | '^' | '<=' | '<' | '>=' | '>' ){0,1}
O1 = <('~' | '^' | '<=' | '<' | '>=' | '>' ){0,1}>:op -> op
BUILD = '+build' N+
BUILD1 = '+build' <N+>:num -> 'build', num
META = ('-alpha' | '-beta' | '-rc') digit*
META1 = ('-alpha' | '-beta' | '-rc'):type <digit*>:num -> type[1:], num
RULE = V:rule -> VersionMatcher(rule)
RULES = V+:rules -> map(VersionMatcher, rules)
RANGE = (RULES:z RANGE1*:y) -> [z] + y
RANGE1 = '||' RULES:x -> x
LOL = RANGE | DASHED | RULE
"""


def pad(v):
    return list(islice(chain(v, repeat(0)), 3))


class VersionMatcher:
    def __init__(self, version_string):
        self.version_string = version_string
        self.op, self.version, self.vtype, self.vnum = version_re.match(
            version_string.replace(' ', '')
        ).groups()
        if self.version.startswith('='):
            self.version = self.version[1:]

    def relative_eq(self, other):
        meta_compare = self.compare_meta_version(other)
        return self.version == other.version and meta_compare == 0

    def __eq__(self, other):
        if self.op is None:
            if all(x.isdigit() for x in self.version.split('.')):
                return self.relative_eq(other)
            elif 'x' in self.version.lower():
                return self.wild_card_compare(other)
            elif self.version.startswith('*'):
                return True
        elif '~' == self.op:
            return self.compare_approximate(other)
        elif '<=' == self.op:
            return self.relative_lte(other)
        elif '<' == self.op:
            return self.relative_lt(other)
        elif '>=' == self.op:
            return self.relative_gte(other)
        elif '>' == self.op:
            return self.relative_gt(other)
        elif '^' == self.op:
            return self.compare_compatible(other)
        raise Exception(
            "invalid comparison between {0} {1}".format(self, other)
        )

    def __str__(self):
        return self.version_string

    def __repr__(self):
        return self.__str__()

    def relative_lt(self, other):
        v = map(int, self.version.split('.'))
        v_other = map(int, other.version.split('.'))
        meta_compare = self.compare_meta_version(other)
        return v_other < v or (v_other == v and meta_compare < 0)

    def relative_lte(self, other):
        return self.relative_lt(other) or self.relative_eq(other)

    def relative_gt(self, other):
        return not (self.relative_lt(other) or self.relative_eq(other))

    def relative_gte(self, other):
        return self.relative_gt(other) or self.relative_eq(other)

    def wild_card_compare(self, other):
        v_other = other.version.lower().split('.')
        v = self.version.split('.')
        matched = all(
            e1 == e2 or e1 == 'x' for e1, e2 in zip(v, v_other)
        )
        meta_compare = self.compare_meta_version(other)
        return matched and meta_compare == 0

    def compare_meta_version(self, other):
        if self.vtype == 'build' and other.vtype == 'build':
            return 0
        elif self.vtype == other.vtype:
            return int(self.vnum or 0) - int(other.vnum or 0)
        return META_RANKING[self.vtype] - META_RANKING[other.vtype]

    def compare_approximate(self, other):
        other = map(int, other.version.split('.'))
        lower = map(int, self.version.split('.'))
        if len(lower) >= 2:
            upper = [lower[0], lower[1] + 1]
        other = pad(other)
        lower = pad(lower)
        upper = pad(upper)
        return lower <= other < upper

    def compare_compatible(self, other):
        other = map(int, other.version.split('.'))
        lower = map(int, self.version.split('.'))
        upper = []
        for e in lower:
            if e != 0:
                upper.append(e + 1)
                break
            upper.append(e)
        return pad(lower) <= pad(other) < pad(upper)

parser = parsley.makeGrammar(
    version_grammar, {'VersionMatcher': VersionMatcher}
)

print parser("<3.2.4~4.4.4").RULES()
print parser("2.3.4-3.3.3").DASHED()
print parser("*").RULES()
print parser("2.3.4~3||~2||<6||~1||^3.2||~1").RANGE()
print "2.3.4-beta3"
print parser("~2.3.4-beta3").V1()
