import os
import pypdf

known_funds = {
    "liquid": "Parag Parikh Liquid Fund",
    "arbitrage": "Parag Parikh Arbitrage Fund",
    "conservative": "Parag Parikh Conservative Hybrid Fund",
    "large cap": "Parag Parikh Large Cap Fund",
    "dynamic": "Parag Parikh Dynamic Asset Allocation Fund",
    "flexi": "Parag Parikh Flexi Cap Fund",
    "elss": "Parag Parikh ELSS Tax Saver Fund",
}

def get_page_context(file_name: str, page_text: str) -> str:
    text_lower = page_text.lower()
    file_lower = file_name.lower()
    
    # 1. Check for exact full names first
    full_names = {
        "parag parikh liquid fund": "Parag Parikh Liquid Fund",
        "parag parikh arbitrage fund": "Parag Parikh Arbitrage Fund",
        "parag parikh conservative hybrid fund": "Parag Parikh Conservative Hybrid Fund",
        "parag parikh large cap fund": "Parag Parikh Large Cap Fund",
        "parag parikh dynamic asset allocation fund": "Parag Parikh Dynamic Asset Allocation Fund",
        "parag parikh flexi cap fund": "Parag Parikh Flexi Cap Fund",
        "parag parikh elss tax saver fund": "Parag Parikh ELSS Tax Saver Fund",
    }
    for full_name, canonical_name in full_names.items():
        if full_name in text_lower:
            return canonical_name

    # 2. Check for unique abbreviations / shorter specific names
    short_names = {
        "flexi cap": "Parag Parikh Flexi Cap Fund",
        "arbitrage fund": "Parag Parikh Arbitrage Fund",
        "conservative hybrid": "Parag Parikh Conservative Hybrid Fund",
        "large cap fund": "Parag Parikh Large Cap Fund",
        "dynamic asset allocation": "Parag Parikh Dynamic Asset Allocation Fund",
        "elss tax saver": "Parag Parikh ELSS Tax Saver Fund",
        "liquid fund": "Parag Parikh Liquid Fund",
    }
    for short_name, canonical_name in short_names.items():
        if short_name in text_lower:
            return canonical_name

    # 3. Check for single keywords with order of specificity
    keywords = {
        "flexi": "Parag Parikh Flexi Cap Fund",
        "arbitrage": "Parag Parikh Arbitrage Fund",
        "conservative": "Parag Parikh Conservative Hybrid Fund",
        "large cap": "Parag Parikh Large Cap Fund",
        "dynamic": "Parag Parikh Dynamic Asset Allocation Fund",
        "elss": "Parag Parikh ELSS Tax Saver Fund",
        "liquid": "Parag Parikh Liquid Fund",
    }
    is_ppfas = "parag" in text_lower or "ppfas" in text_lower or "ppfas" in file_lower or "parag" in file_lower
    if is_ppfas:
        for kw, canonical_name in keywords.items():
            if kw in text_lower:
                return canonical_name

    # 4. Fall back to filename keywords
    for kw, canonical_name in keywords.items():
        if kw in file_lower:
            return canonical_name
            
    return None


path = r'd:\CAPSTONE PROJECT\data\raw_docs\1. PARAG  PARIKH LIQUID FUND\ppfas-mf-factsheet-for-May-2026.pdf'
reader = pypdf.PdfReader(path)
for idx, page in enumerate(reader.pages):
    text = page.extract_text()
    context = get_page_context(os.path.basename(path), text)
    print(f"Page {idx+1}: detected context = {context}")
