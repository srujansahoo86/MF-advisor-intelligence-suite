import os
import pypdf

raw_docs_dir = r"d:\CAPSTONE PROJECT\data\raw_docs"
found = False

for folder in os.listdir(raw_docs_dir):
    if "SEBI AMFI" in folder:
        continue
    folder_path = os.path.join(raw_docs_dir, folder)
    if os.path.isdir(folder_path):
        for file in os.listdir(folder_path):
            if file.lower().endswith(".pdf"):
                path = os.path.join(folder_path, file)
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
    print("Could not find 'flexi' in any non-SEBI PDF.")
