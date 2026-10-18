import sys

# usage: python trim_source.py FILE "START TEXT" "END TEXT" "SOURCE LINE"
# keeps the lines from the first line containing START to the last line
# containing END (ignoring case), and puts the source line on top
path, start, end, source = sys.argv[1:5]

with open(path, encoding="utf-8") as f:
    lines = [l.rstrip() for l in f]

hits = [i for i, l in enumerate(lines) if start.lower() in l.lower()]
tail = [i for i, l in enumerate(lines) if end.lower() in l.lower()]
if not hits or not tail:
    sys.exit("start or end text not found, open the file and check the wording")

body = [l for l in lines[hits[0]:tail[-1] + 1] if l.strip()]
with open(path, "w", encoding="utf-8") as f:
    f.write(source + "\n" + "\n".join(body) + "\n")
print(f"kept {len(body)} lines")