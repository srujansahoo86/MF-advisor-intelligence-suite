import pypdf

path = r'd:\CAPSTONE PROJECT\data\raw_docs\1. PARAG  PARIKH LIQUID FUND\ppfas-mf-factsheet-for-May-2026.pdf'
reader = pypdf.PdfReader(path)
print(f"Total pages: {len(reader.pages)}")
page_text = reader.pages[19].extract_text()
with open("data/page20.txt", "w", encoding="utf-8") as f:
    f.write(page_text)
print("Page 20 text successfully written to data/page20.txt")
