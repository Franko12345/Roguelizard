"""Every source path a doc names must exist (issue #71).

The T1-T16 refactor moved almost all of lagarto/ into subpackages and the docs
kept citing the old flat paths, so 30 of 37 rows in the architecture table
pointed at files that were gone. This is the guard against that drifting again.
"""
import os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

PATH_RE = re.compile(r'`(lagarto/[A-Za-z0-9_./]+\.py)`|`(tools/[A-Za-z0-9_./]+\.py)`')
bad, seen = [], 0
for dirpath, _, files in os.walk('docs'):
    for fn in files:
        if not fn.endswith('.md'):
            continue
        p = os.path.join(dirpath, fn)
        head = open(p, encoding='utf-8').read(400)
        if 'LEGADO' in head:
            continue        # historical record: it cites pre-refactor paths on purpose
        for i, line in enumerate(open(p, encoding='utf-8'), 1):
            for m in PATH_RE.finditer(line):
                path = m.group(1) or m.group(2)
                seen += 1
                if not os.path.exists(path):
                    bad.append(f"{p}:{i}: {path}")
for extra in ('CONTEXT.md', 'CLAUDE.md'):
    if os.path.exists(extra):
        for i, line in enumerate(open(extra, encoding='utf-8'), 1):
            for m in PATH_RE.finditer(line):
                path = m.group(1) or m.group(2)
                seen += 1
                if not os.path.exists(path):
                    bad.append(f"{extra}:{i}: {path}")

print(f"checked {seen} source paths cited in docs")
if bad:
    print(f"\n{len(bad)} point at files that do not exist:")
    for b in bad:
        print("  " + b)
    sys.exit(1)
print("ALL OK")
