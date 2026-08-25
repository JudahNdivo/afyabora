with open("data/sti/cleaned/who_sti_general_factsheet.txt", "r", encoding="utf-8") as f:
    text = f.read()

lines = text.split("\n")
for i, line in enumerate(lines):
    if any(word in line.lower() for word in ["toilet", "casual", "seat", "contact"]):
        print(f"Line {i}: {line}")