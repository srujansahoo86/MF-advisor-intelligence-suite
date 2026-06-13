import os
import pypdf

raw_docs_dir = r"d:\CAPSTONE PROJECT\data\raw_docs"
found = False

for root, _, files in os.walk(raw_docs_dir):
    for file in files:
        if file.lower().endswith(".pdf"):
            path = os.path.join(root, file)
            try:
                reader = pypdf.PdfReader(path)
                for i, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    if "flexi" in text.lower():
                        print(f"Found 'flexi' in {path} on Page {i+1}")
                        found = True
            except Exception as e:
                print(f"Error reading {path}: {e}")

if not found:
    print("Could not find 'flexi' in any PDF in raw_docs_dir.")
