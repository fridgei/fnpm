from itertools import islice, chain, repeat

import parsley

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
V1 = <O>:op <N N1{0,3}>:version (META1 | BUILD1){0,1}:type_and_num ->  VersionMatcher( op, version.split('.'), type_and_num[0][0] if type_and_num else '', type_and_num[0][1] if type_and_num else '')
DASHED = V:l '-' V:r -> map(VersionMatcher, [">="+ l,  "<=" + r])
O = ('~' | '^' | '<=' | '<' | '>=' | '>' ){0,1}
O1 = <('~' | '^' | '<=' | '<' | '>=' | '>' ){0,1}>:op -> op
BUILD = '+build' N+
BUILD1 = '+build' <N+>:num -> 'build', num
META = ('-alpha' | '-beta' | '-rc') digit*
META1 = ('-alpha' | '-beta' | '-rc'):type <digit*>:num -> type[1:] if type else type, num
RULES = V1+:rules -> rules
RANGE = (RULES:z RANGE1*:y) -> [z] + y
RANGE1 = '||' RULES:x -> x
LOL = RANGE | DASHED | RULES
"""


def pad(v):
    return list(islice(chain(v, repeat(0)), 3))


class VersionMatcher:
    def __init__(self, op, version, build_type, build_number):
        self.op = op or None
        self.version = version
        self.build_type = build_type or None
        self.build_number = int(build_number or 0)

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
        return "".join(
            map(
                lambda x: str(x or ''),
                (
                    self.op,
                    ".".join(self.version or []),
                    self.build_type,
                    self.build_number
                )
            )
        )

    def __repr__(self):
        return self.__str__()

    def relative_lt(self, other):
        v = map(int, self.version)
        v_other = map(int, other.version)
        meta_compare = self.compare_meta_version(other)
        return v_other < v or (v_other == v and meta_compare < 0)

    def relative_lte(self, other):
        return self.relative_lt(other) or self.relative_eq(other)

    def relative_gt(self, other):
        return not (self.relative_lt(other) or self.relative_eq(other))

    def relative_gte(self, other):
        return self.relative_gt(other) or self.relative_eq(other)

    def wild_card_eq(self, other):
        v_other = other.version.lower()
        v = self.version
        matched = all(
            e1 == e2 or e1 == 'x' for e1, e2 in zip(v, v_other)
        )
        meta_compare = self.compare_meta_version(other)
        return matched and meta_compare == 0

    def compare_meta_version(self, other):
        if self.build_type == 'build' and other.build_type == 'build':
            return 0
        elif self.build_type == other.build_type:
            return int(self.build_num or 0) - int(other.build_num or 0)
        return META_RANKING[self.build_type] - META_RANKING[other.build_type]

    def compare_approximate(self, other):
        other = map(int, other.version)
        lower = map(int, self.version)
        if len(lower) >= 2:
            upper = [lower[0], lower[1] + 1]
        other = pad(other)
        lower = pad(lower)
        upper = pad(upper)
        return lower <= other < upper

    def compare_compatible(self, other):
        other = map(int, other.version)
        lower = map(int, self.version)
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

print parser('~3.4.3-alpha4||3.2.4||3.2<3.3.3').LOL()
