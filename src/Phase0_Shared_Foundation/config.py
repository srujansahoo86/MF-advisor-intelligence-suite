import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Centralized configuration for the MF Advisor Intelligence Suite."""
    
    # API Keys
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    
    # Storage Paths
    CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", "./data/vectorstore")
    SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/app.db")
    DATA_DIR = os.getenv("DATA_DIR", "./data/raw_docs")
    REVIEWS_CSV_PATH = os.getenv("REVIEWS_CSV_PATH", "./data/reviews.csv")

    # Phase 2 — Official source URLs for Fee Explainer (AMFI + SEBI)
    FEE_EXPLAINER_AMFI_URL = "https://www.amfiindia.com/investor-corner"
    FEE_EXPLAINER_SEBI_URL = "https://www.sebi.gov.in/sebi_data/attachdocs/1475063737177.pdf"
    
    # Phase 3 — Voice Scheduler
    ADVISOR_SECURE_LINK = "https://kuvera.in/secure-profile"
    AVAILABLE_SLOTS = [
        "Monday 10:00 AM", "Monday 2:00 PM",
        "Tuesday 10:00 AM", "Tuesday 3:00 PM",
        "Wednesday 11:00 AM", "Wednesday 4:00 PM",
        "Thursday 9:00 AM", "Thursday 2:00 PM",
        "Friday 10:00 AM", "Friday 3:00 PM",
    ]
    
    # Models
    LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
    # Using FastEmbed default BGE model
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    
    # List of verified source URLs for the RAG engine
    SOURCE_MANIFEST_URLS = [
        # --- 1. Parag Parikh Liquid Growth Direct Plan ---
        "https://kuvera.in/mutual-funds/fund/parag-parikh-liquid-growth--PPLFGZ-GR",
        "https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-May-2026.pdf?08062026",
        "https://amc.ppfas.com/downloads/parag-parikh-liquid-fund/kim-parag-parikh-liquid-fund.pdf?21052026",
        "https://amc.ppfas.com/downloads/parag-parikh-liquid-fund/sid-parag-parikh-liquid-fund.pdf?21042026",

        # --- 2. Parag Parikh Arbitrage Growth Direct Plan ---
        "https://kuvera.in/mutual-funds/fund/parag-parikh-arbitrage-growth--PPAFDG-GR",
        "https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-May-2026.pdf?08062026",
        "https://amc.ppfas.com/downloads/parag-parikh-arbitrage-fund/kim-parag-parikh-arbitrage-fund.pdf?21052026",
        "https://amc.ppfas.com/downloads/parag-parikh-arbitrage-fund/scheme-information-document-parag-parikh-arbitrage-fund.pdf?21042026",

        # --- 3. Parag Parikh Conservative Hybrid Growth Direct Plan ---
        "https://kuvera.in/mutual-funds/fund/parag-parikh-conservative-hybrid-growth--PPCHFGZ-GR",
        "https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-May-2026.pdf?08062026",
        "https://amc.ppfas.com/downloads/parag-parikh-conservative-hybrid-fund/kim-parag-parikh-conservative-hybrid-fund.pdf?21052026",
        "https://amc.ppfas.com/downloads/parag-parikh-conservative-hybrid-fund/sid-parag-parikh-conservative-hybrid-fund.pdf?21042026",

        # --- 4. Parag Parikh Large Cap Growth Direct Plan ---
        "https://kuvera.in/mutual-funds/fund/parag-parikh-large-cap-growth--PPLCFGZ-GR",
        "https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-May-2026.pdf?08062026",
        "https://amc.ppfas.com/downloads/parag-parikh-large-cap-fund/kim-parag-parikh-large-cap-fund.pdf?21052026",
        "https://amc.ppfas.com/downloads/parag-parikh-large-cap-fund/sid-parag-parikh-large-cap-fund.pdf?21042026",

        # --- 5. Parag Parikh Dynamic Asset Allocation Growth Direct Plan ---
        "https://kuvera.in/mutual-funds/fund/parag-parikh-dynamic-asset-allocation-growth--PPDAFGZ-GR",
        "https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-May-2026.pdf?08062026",
        "https://amc.ppfas.com/downloads/parag-parikh-dynamic-asset-allocation-fund/kim-parag-parikh-dynamic-asset-allocation-fund.pdf?21052026",
        "https://amc.ppfas.com/downloads/parag-parikh-dynamic-asset-allocation-fund/sid-parag-parikh-dynamic-asset-allocation-fund.pdf?21042026",

        # --- Kuvera Public Docs Links ---
        "https://kuvera.freshdesk.com/support/solutions/articles/82000725676-how-do-i-get-my-capital-gains-report-for-filing-taxes-",
        "https://kuvera.in/blog/how-to-stop-cancel-and-redeem-mutual-fund-sip-kuvera/",
        "https://kuvera.in/blog/elss-meaning-lock-in-period-and-advantages/",
        "https://kuvera.freshdesk.com/support/solutions/articles/82000703085-how-do-i-switch-my-regular-mutual-funds-to-direct-",
        "https://kuvera.freshdesk.com/support/solutions/articles/82000702595-when-will-my-mutual-fund-redemption-amount-get-credited-",

        # --- SEBI / AMFI Docs Links ---
        "https://www.sebi.gov.in/legal/master-circulars/mar-2026/master-circular-for-mutual-funds_100491.html",
        "https://investor.sebi.gov.in/iematerial.html",
        "https://www.amfiindia.com/investor/become-mf-distributor?zoneName=InvestorService",
        "https://www.amfiindia.com/uploads/AMFI_Master_Cicular_for_MF_Ds_3c7f5ee44f.pdf",
        "https://www.amfiindia.com/Themes/Theme1/downloads/NewRuleonApplicableNAVeffectivefromFebruary12021.pdf",
        "https://www.sebi.gov.in/sebi_data/attachdocs/1475063737177.pdf"
    ]


def _build_source_url_map():
    """Maps local PDF filenames to their canonical public URL from SOURCE_MANIFEST_URLS."""
    mapping = {}
    for url in Config.SOURCE_MANIFEST_URLS:
        basename = url.split("?")[0].rsplit("/", 1)[-1]
        if basename.lower().endswith(".pdf"):
            mapping[basename] = url

    # Manual overrides for local filenames that don't match the manifest URL's basename
    mapping.update({
        "parag_parikh_liquid_fund.pdf": "https://kuvera.in/mutual-funds/fund/parag-parikh-liquid-growth--PPLFGZ-GR",
        "parag_parikh_arbitrage_kuvera.pdf": "https://kuvera.in/mutual-funds/fund/parag-parikh-arbitrage-growth--PPAFDG-GR",
        "Parag_Parikh_Conservative_Hybrid_Direct_Kuvera.pdf": "https://kuvera.in/mutual-funds/fund/parag-parikh-conservative-hybrid-growth--PPCHFGZ-GR",
        "parag_parikh_large_cap_growth_profile.pdf": "https://kuvera.in/mutual-funds/fund/parag-parikh-large-cap-growth--PPLCFGZ-GR",
        "Parag_Parikh_Dynamic_Asset_Allocation_Fund_Factsheet.pdf": "https://kuvera.in/mutual-funds/fund/parag-parikh-dynamic-asset-allocation-growth--PPDAFGZ-GR",
        "How do I get my Capital Gains report for filing taxes_ _ Kuvera.pdf": "https://kuvera.freshdesk.com/support/solutions/articles/82000725676-how-do-i-get-my-capital-gains-report-for-filing-taxes-",
        "How do I switch my regular mutual funds to direct_ _ Kuvera.pdf": "https://kuvera.freshdesk.com/support/solutions/articles/82000703085-how-do-i-switch-my-regular-mutual-funds-to-direct-",
        "When will my mutual fund redemption amount get credited_ _ Kuvera.pdf": "https://kuvera.freshdesk.com/support/solutions/articles/82000702595-when-will-my-mutual-fund-redemption-amount-get-credited-",
        "elss_meaning_lock_in_period_advantages.pdf": "https://kuvera.in/blog/elss-meaning-lock-in-period-and-advantages/",
        "kuvera_sip_guide.pdf": "https://kuvera.in/blog/how-to-stop-cancel-and-redeem-mutual-fund-sip-kuvera/",
        "Securities Market Booklet.pdf": "https://www.amfiindia.com/investor/become-mf-distributor?zoneName=InvestorService",
        "SEBI MASTER CIRCULAR FOR MUTUAL FUNDS.pdf": "https://www.sebi.gov.in/legal/master-circulars/mar-2026/master-circular-for-mutual-funds_100491.html",
        "SEBI REGULATORY INFORMATION FOR MUTUAL FUNDS.pdf": "https://investor.sebi.gov.in/iematerial.html",
        "SEBI FEE AND REGULATORY INFORMATION 1.pdf": "https://www.sebi.gov.in/sebi_data/attachdocs/1475063737177.pdf",
    })
    return mapping


Config.SOURCE_URL_MAP = _build_source_url_map()
