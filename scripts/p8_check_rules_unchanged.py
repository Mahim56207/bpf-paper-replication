#!/usr/bin/env python3
"""Phase 8.0: show that amendment A3 left the C1 verdict rules, primary pairing and grid unchanged.
Compares, by AST, the rule functions and constants of scripts/c1_summarize.py at git HEAD (Phase 6c) with the
working tree, and checks that docs/phase6c_design.md changed only by added lines (no deleted or edited line).
Usage: python3 -I scripts/p8_check_rules_unchanged.py | tee logs/p8/p8_rules_unchanged.log"""
import ast, re, subprocess, sys

PATH = "scripts/c1_summarize.py"
RULE_FUNCS = ("ratio", "evaluate", "verdict", "paper_fig8", "load_m1", "fmt")
RULE_CONSTS = ("T975", "FILTERS", "MIXES", "BPFS", "SMS", "PRIMARY")


def parse(src):
    t = ast.parse(src)
    funcs = {n.name: ast.dump(n) for n in t.body if isinstance(n, ast.FunctionDef)}
    consts = {}
    for n in t.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            consts[n.targets[0].id] = ast.dump(n.value)
    return funcs, consts


old = parse(subprocess.run(["git", "show", "HEAD:" + PATH], capture_output=True, text=True, check=True).stdout)
new = parse(open(PATH).read())
bad = 0
for n in RULE_FUNCS:
    same = old[0][n] == new[0][n]
    bad += not same
    print("%-10s function %-11s %s" % ("RULE", n, "IDENTICAL to HEAD (AST)" if same else "CHANGED"))
for n in RULE_CONSTS:
    same = old[1][n] == new[1][n]
    bad += not same
    print("%-10s constant %-11s %s" % ("RULE", n, "IDENTICAL to HEAD (AST)" if same else "CHANGED"))
changed = sorted(n for n in set(old[0]) | set(new[0]) if old[0].get(n) != new[0].get(n))
print("functions that differ from HEAD (all outside the rule set above):", ", ".join(changed))
d = subprocess.run(["git", "diff", "--numstat", "HEAD", "--", "docs/phase6c_design.md"], capture_output=True, text=True).stdout.split()
print("docs/phase6c_design.md vs HEAD: %s added lines, %s deleted lines" % (d[0], d[1]))
bad += d[1] != "0"
sec7 = lambda s: s[s.index("## 7. Verdict rules"):s.index("## 8. Files")]
head = subprocess.run(["git", "show", "HEAD:docs/phase6c_design.md"], capture_output=True, text=True, check=True).stdout
print("design section 7 (verdict rules) text identical to HEAD:", sec7(head) == sec7(open("docs/phase6c_design.md").read()))
bad += sec7(head) != sec7(open("docs/phase6c_design.md").read())
print("rules-unchanged check: %d problem(s)" % bad)
sys.exit(1 if bad else 0)
