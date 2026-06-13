import pypdf

path = r'd:\CAPSTONE PROJECT\data\raw_docs\1. PARAG  PARIKH LIQUID FUND\ppfas-mf-factsheet-for-May-2026.pdf'
reader = pypdf.PdfReader(path)
page_text = reader.pages[1].extract_text()
with open("data/page2.txt", "w", encoding="utf-8") as f:
    f.write(page_text)
print("Page 2 text written to data/page2.txt")
