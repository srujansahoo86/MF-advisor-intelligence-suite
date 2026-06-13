import pypdf

path = r'd:\CAPSTONE PROJECT\data\raw_docs\1. PARAG  PARIKH LIQUID FUND\ppfas-mf-factsheet-for-May-2026.pdf'
reader = pypdf.PdfReader(path)

for p_num in [18, 19]:
    page_text = reader.pages[p_num - 1].extract_text()
    filename = f"data/page{p_num}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(page_text)
    print(f"Page {p_num} text written to {filename}")
