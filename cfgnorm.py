import argparse
from collections import defaultdict, OrderedDict
import itertools as it
from functools import cached_property
from copy import deepcopy


def proper_powerset(iterable):
    s = list(iterable)
    return it.chain.from_iterable(it.combinations(s, r) for r in range(len(s)))


class Grammar:
    VERBOSE = False

    def __init__(
        self,
        rules: dict,
        start: str,
    ):
        self.rules = OrderedDict(rules)
        self.rules.move_to_end(start, last=False)
        self.start = start

    @cached_property
    def nonterminals(self):
        return frozenset(self.rules.keys())

    @cached_property
    def terminals(self):
        return frozenset(
            sym
            for rhs in self.rules.values()
            for opt in rhs
            for sym in opt
            if sym not in self.rules
        )

    @staticmethod
    def from_string(s: str):
        rules = defaultdict(set)
        start = None
        for i, line in enumerate(s.split(";;")):
            line = line.strip()
            if not line:
                continue

            lhs, _, rhs = line.partition("->")
            if not rhs:
                raise ValueError(f'Line {i} <<< {line} >>> contains no "->"')
            lhs = lhs.strip()
            rhs = rhs.strip()

            if start is None:
                start = lhs

            for option in rhs.split("|"):
                option = option.strip()
                option = () if option == "%" else tuple(option)
                rules[lhs].add(option)

        return Grammar(rules, start)

    def to_string(self):
        s = ""

        def format(lhs, rhs):
            rhs_string = " | ".join(
                " ".join(opt) if opt else "%" for opt in sorted(rhs)
            )
            return f"{lhs} -> {rhs_string} ;;\n"

        s += format(self.start, self.rules[self.start])
        for lhs, rhs in sorted(self.rules.items()):
            if lhs != self.start:
                s += format(lhs, rhs)
        return s

    @staticmethod
    def stringof(s, alphabet):
        return all(sym in alphabet for sym in s)

    def _nullable_nonterminals(self):
        nullable = set(
            lhs for lhs, rhs in self.rules.items() if any(not opt for opt in rhs)
        )

        new_nullable = set()
        while new_nullable != nullable:
            nullable = deepcopy(new_nullable)
            for lhs, rhs in self.rules.items():
                if any(Grammar.stringof(opt, new_nullable) for opt in rhs):
                    new_nullable.add(lhs)

        if Grammar.VERBOSE:
            print("Nullable Nonterminals:", nullable)

        return nullable

    def without_epsilon_rules(self):
        nullable = self._nullable_nonterminals()
        new_rules = deepcopy(self.rules)

        for _, rhs in new_rules.items():
            rhs.discard(())

        for lhs, rhs in self.rules.items():
            for opt in rhs:
                indices = [i for i, sym in enumerate(opt) if sym in nullable]
                for kept in proper_powerset(indices):
                    new_opt = tuple(
                        sym
                        for i, sym in enumerate(opt)
                        if sym not in nullable or i in kept
                    )
                    if new_opt and new_opt != (lhs,):
                        new_rules[lhs].add(new_opt)

        start = self.start
        if self.start in nullable:
            start += "'"
            new_rules[start] = set([(), (self.start,)])

        return Grammar(new_rules, start)

    def _unit_pairs(self):
        new_unit_pairs = set(
            (lhs, opt[0])
            for lhs, rhs in self.rules.items()
            for opt in rhs
            if len(opt) == 1 and opt[0] in self.nonterminals
        )
        unit_pairs = set()

        while unit_pairs != new_unit_pairs:
            unit_pairs = deepcopy(new_unit_pairs)
            for x, y in unit_pairs:
                for yy, z in unit_pairs:
                    if y == yy:
                        new_unit_pairs.add((x, z))

        if Grammar.VERBOSE:
            print("Unit Pairs:", unit_pairs)

        return unit_pairs

    def without_unit_rules(self):
        unit_pairs = self._unit_pairs()
        new_rules = deepcopy(self.rules)

        for x, y in unit_pairs:
            new_rules[x].discard((y,))

        for x, y in unit_pairs:
            new_rules[x] |= new_rules[y]

        return Grammar(new_rules, self.start)

    def _reachable_symbols(self):
        reachable = set()
        new_reachable = set([self.start])

        while reachable != new_reachable:
            reachable = deepcopy(new_reachable)

            for X in reachable:
                if X in self.nonterminals:
                    for opt in self.rules[X]:
                        new_reachable.update(opt)

        if Grammar.VERBOSE:
            print("Reachable Symbols:", reachable)

        return reachable

    def _productive_symbols(self):
        productive = set()
        new_productive = self.terminals

        while new_productive != productive:
            productive = deepcopy(new_productive)

            for lhs, rhs in self.rules.items():
                for opt in rhs:
                    if Grammar.stringof(opt, productive):
                        new_productive.add(lhs)

        if Grammar.VERBOSE:
            print("Productive Symbols:", productive)

        return productive

    def with_symbols(self, symbols: set[str]):
        new_rules = defaultdict(set)
        for lhs, rhs in self.rules.items():
            if lhs not in symbols:
                continue
            for opt in rhs:
                if Grammar.stringof(opt, symbols):
                    new_rules[lhs].add(opt)

        return Grammar(new_rules, self.start)

    def with_productive_symbols(self):
        return self.with_symbols(self._productive_symbols())

    def with_reachable_symbols(self):
        return self.with_symbols(self._reachable_symbols())

    def with_pair_rules(self):
        new_rules = defaultdict(set)

        def aux_format(X, i, j):
            return f"{X}_{i}:{j}"

        for lhs, rhs in self.rules.items():
            for i, opt in enumerate(rhs):
                for j in range(len(opt) - 2):
                    aux_lhs = aux_format(lhs, i, j) if j > 0 else lhs
                    aux_sym = aux_format(lhs, i, j + 1)
                    new_rules[aux_lhs].add((opt[j], aux_sym))
                aux_lhs = aux_format(lhs, i, len(opt) - 3) if len(opt) > 2 else lhs
                new_rules[aux_lhs].add(opt[-2:])

        return Grammar(new_rules, self.start)

    def with_unit_terminals(self):
        new_rules = defaultdict(set)

        def aux_format(X):
            return f"{X}#"

        for t in self.terminals:
            aux_sym = aux_format(t)
            new_rules[aux_sym].add((t,))

        for lhs, rhs in self.rules.items():
            for opt in rhs:
                new_opt = tuple(
                    aux_format(sym) if sym in self.terminals else sym for sym in opt
                )
                new_rules[lhs].add(new_opt)

        return Grammar(new_rules, self.start)

    def __str__(self):
        return self.to_string()


class Pipeline:
    def __init__(self, *actions):
        self.actions = list(actions)

    def add_actions(self, *actions):
        self.actions.extend(actions)

    def __call__(self, g: Grammar):
        for a in self.actions:
            g = a(g)
            if hasattr(a, "__name__"):
                print(a.__name__.replace("_", " ").title())
                print(g)
        return g

    @staticmethod
    def without_epsilon_rules():
        return Pipeline(Grammar.without_epsilon_rules)

    @staticmethod
    def without_unit_rules():
        return Pipeline(Grammar.without_unit_rules)

    @staticmethod
    def with_productive_symbols():
        return Pipeline(Grammar.with_productive_symbols)

    @staticmethod
    def with_reachable_symbols():
        return Pipeline(Grammar.with_reachable_symbols)

    @staticmethod
    def with_pair_rules():
        return Pipeline(Grammar.with_pair_rules)

    @staticmethod
    def with_unit_terminals():
        return Pipeline(Grammar.with_unit_terminals)

    @staticmethod
    def with_useful_symbols():
        return Pipeline(
            Pipeline.with_productive_symbols(),
            Pipeline.with_reachable_symbols(),
        )

    @staticmethod
    def chomsky_normal_form():
        return Pipeline(
            Pipeline.without_epsilon_rules(),
            Pipeline.without_unit_rules(),
            Pipeline.with_useful_symbols(),
            Pipeline.with_pair_rules(),
            Pipeline.with_unit_terminals(),
        )


def main():
    args = getargs()
    if args.verbose:
        Grammar.VERBOSE = True
    with args.file as f:
        raw_rules = f.read()
    g = Grammar.from_string(raw_rules)

    p = Pipeline()
    if args.null:
        p.add_actions(Pipeline.without_epsilon_rules())
    if args.unit:
        p.add_actions(Pipeline.without_unit_rules())
    if args.reach:
        p.add_actions(Pipeline.with_reachable_symbols())
    if args.prod:
        p.add_actions(Pipeline.with_productive_symbols())
    if args.useless:
        p.add_actions(Pipeline.with_useful_symbols())
    if args.cnf:
        p.add_actions(Pipeline.chomsky_normal_form())

    print("Original")
    print(g)
    p(g)


def getargs():
    parser = argparse.ArgumentParser(
        description="Normalize Context Free Grammars", fromfile_prefix_chars="@"
    )
    parser.add_argument("file", type=argparse.FileType("r"))
    parser.add_argument(
        "-p", "--prod", action="store_true", help="eliminate nonproductive nonterminals"
    )
    parser.add_argument(
        "-r", "--reach", action="store_true", help="eliminate unreachable symbols"
    )
    parser.add_argument(
        "-l", "--useless", action="store_true", help="eliminate useless symbols"
    )
    parser.add_argument(
        "-n", "--null", action="store_true", help="eliminate null rules"
    )
    parser.add_argument(
        "-u", "--unit", action="store_true", help="eliminate unit rules"
    )
    parser.add_argument(
        "-c", "--cnf", action="store_true", help="convert to chomsky normal form"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="print intermediate steps"
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
