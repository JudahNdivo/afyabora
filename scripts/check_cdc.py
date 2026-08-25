with open("data/sti/cleaned/cdc_syphilis_about.txt", "r", encoding="utf-8") as f:
    text = f.read()

# Search for toilet seat mention
if "toilet" in text.lower():
    idx = text.lower().index("toilet")
    print("Found 'toilet' at index:", idx)
    print(text[idx-200:idx+300])
else:
    print("'toilet' NOT found in document")
    print("\nFull text:")
    print(text)