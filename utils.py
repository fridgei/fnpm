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
V = <O>:op <N N1{0,3}>:version (META | BUILD){0,1}:type_and_num -> op, version.split('.'), type_and_num[0] if type_and_num else '', type_and_num[1] if type_and_num and len(type_and_num) == 2 else ''
V1 = <O>:op <N N1{0,3}>:version (META | BUILD){0,1}:type_and_num ->  VersionMatcher( op, version.split('.'), type_and_num[0][0] if type_and_num else '', type_and_num[0][1] if type_and_num else '')
DASHED = V:l '-' V:r -> [VersionMatcher(">=", *l[1:]) , VersionMatcher("<=", *r[1:])]
O = ('~' | '^' | '<=' | '<' | '>=' | '>' ){0,1}
BUILD = '+build' <N+>:num -> 'build', num
META = ('-alpha' | '-beta' | '-rc'):type <digit*>:num -> type[1:] if type else type, num
RULES = V1+:rules -> rules
RANGE = (RULES:z RANGE1*:y) -> [z] + y
RANGE1 = '||' RULES:x -> x
LOL = DASHED | RANGE | RULES
"""


def pad(v):
    # pad lists to 3 zeros
    return list(islice(chain(v, repeat(0)), 3))


class VersionMatcher:
    """
    This class wraps versions and allows you to compare version definitions.
    Versions are treated as an operator, a list of version elements, a build
    type and the build number.
    ex:
        1.2.3-beta3
        op='', version=[1, 2, 3], build_type='beta', buld_num=3
        ~1.3
        op='~', version[1, 3] build_type='', build_num=0

    __eq__ does the heavy listing of determining how to compare version
    matchers.  __lt__ can be implemented and we can use
    functools.totalordering to generate the rest of the comparators so we can
    sort lists of versions without operators.  This is useful for determining
    the latest version out of a list of versions.
    """
    def __init__(self, op, version, build_type, build_number):
        self.op = op or None
        self.version = version
        self.build_type = build_type or None
        self.build_number = int(build_number or 0)

    def relative_eq(self, other):
        """
        Used for checking if two versions are equal comapres the build numbers
        and build type to make sure that alpha < beta < rc < build and that
        rc1 < rc3 and things like that.
        """
        meta_compare = self.compare_meta_version(other)
        return self.version == other.version and meta_compare == 0

    def __eq__(self, other):
        """
        Determine what type of comparison to do based on the version matchers
        operator
        """
        if self.op is None:
            if all(x.isdigit() for x in self.version):
                return self.relative_eq(other)
            elif 'x' in self.version:
                return self.compare_wild_card(other)
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

    def compare_wild_card(self, other):
        matched = all(
            a == b or a == 'x' for a, b in zip(self.version, other.version)
        )
        meta_compare = self.compare_meta_version(other)
        return matched and meta_compare == 0

    def compare_meta_version(self, other):
        if self.build_type == 'build' and other.build_type == 'build':
            return 0
        elif self.build_type == other.build_type:
            return self.build_num - other.build_num
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
"""
This creates a parser from the grammar that creates lists of VersionMatchers.
For a list of depth 1 all patterns must match for a list of lists one of the
lists must match completely.  This is used to represented range version
matchers.
ex:
    <1.2.3 >5.3.3 -> [<1.2.3, >5.3.3]
    <1.2.3 >5.3.3||~2||x.x.x-rc4 -> [[<1.2.3, >5.3.3], [~2], [x.x.x-rc4]]
"""
parser = parsley.makeGrammar(
    version_grammar, {'VersionMatcher': VersionMatcher}
)

print parser('~3.4.3-alpha4||3.2.4||3.2<3.3.3').LOL()
print parser("1.1.1-2.2.2").LOL()
