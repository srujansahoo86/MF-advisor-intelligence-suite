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
    SHARED_NOTES_PATH = os.getenv("SHARED_NOTES_PATH", "./data/shared_notes.md")
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
    
    # Verified source manifest with per-URL metadata for the RAG engine.
    # Each entry: url, description, source (publisher), document_type, last_verified.
    SOURCE_MANIFEST = [
        # --- 1. Parag Parikh Liquid Growth Direct Plan ---
        {
            "url": "https://kuvera.in/mutual-funds/fund/parag-parikh-liquid-growth--PPLFGZ-GR",
            "description": "Parag Parikh Liquid Fund — Direct Growth fund profile on Kuvera",
            "source": "Kuvera",
            "document_type": "Fund Profile",
            "last_verified": "2026-06-01",
        },
        {
            "url": "https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-May-2026.pdf?08062026",
            "description": "PPFAS Mutual Fund factsheet for May 2026 (covers all schemes)",
            "source": "PPFAS AMC",
            "document_type": "Factsheet",
            "last_verified": "2026-06-08",
        },
        {
            "url": "https://amc.ppfas.com/downloads/parag-parikh-liquid-fund/kim-parag-parikh-liquid-fund.pdf?21052026",
            "description": "Parag Parikh Liquid Fund — Key Information Memorandum (KIM)",
            "source": "PPFAS AMC",
            "document_type": "KIM",
            "last_verified": "2026-05-21",
        },
        {
            "url": "https://amc.ppfas.com/downloads/parag-parikh-liquid-fund/sid-parag-parikh-liquid-fund.pdf?21042026",
            "description": "Parag Parikh Liquid Fund — Scheme Information Document (SID)",
            "source": "PPFAS AMC",
            "document_type": "SID",
            "last_verified": "2026-04-21",
        },

        # --- 2. Parag Parikh Arbitrage Growth Direct Plan ---
        {
            "url": "https://kuvera.in/mutual-funds/fund/parag-parikh-arbitrage-growth--PPAFDG-GR",
            "description": "Parag Parikh Arbitrage Fund — Direct Growth fund profile on Kuvera",
            "source": "Kuvera",
            "document_type": "Fund Profile",
            "last_verified": "2026-06-01",
        },
        {
            "url": "https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-May-2026.pdf?08062026",
            "description": "PPFAS Mutual Fund factsheet for May 2026 — Arbitrage Fund pages",
            "source": "PPFAS AMC",
            "document_type": "Factsheet",
            "last_verified": "2026-06-08",
        },
        {
            "url": "https://amc.ppfas.com/downloads/parag-parikh-arbitrage-fund/kim-parag-parikh-arbitrage-fund.pdf?21052026",
            "description": "Parag Parikh Arbitrage Fund — Key Information Memorandum (KIM)",
            "source": "PPFAS AMC",
            "document_type": "KIM",
            "last_verified": "2026-05-21",
        },
        {
            "url": "https://amc.ppfas.com/downloads/parag-parikh-arbitrage-fund/scheme-information-document-parag-parikh-arbitrage-fund.pdf?21042026",
            "description": "Parag Parikh Arbitrage Fund — Scheme Information Document (SID)",
            "source": "PPFAS AMC",
            "document_type": "SID",
            "last_verified": "2026-04-21",
        },

        # --- 3. Parag Parikh Conservative Hybrid Growth Direct Plan ---
        {
            "url": "https://kuvera.in/mutual-funds/fund/parag-parikh-conservative-hybrid-growth--PPCHFGZ-GR",
            "description": "Parag Parikh Conservative Hybrid Fund — Direct Growth fund profile on Kuvera",
            "source": "Kuvera",
            "document_type": "Fund Profile",
            "last_verified": "2026-06-01",
        },
        {
            "url": "https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-May-2026.pdf?08062026",
            "description": "PPFAS Mutual Fund factsheet for May 2026 — Conservative Hybrid Fund pages",
            "source": "PPFAS AMC",
            "document_type": "Factsheet",
            "last_verified": "2026-06-08",
        },
        {
            "url": "https://amc.ppfas.com/downloads/parag-parikh-conservative-hybrid-fund/kim-parag-parikh-conservative-hybrid-fund.pdf?21052026",
            "description": "Parag Parikh Conservative Hybrid Fund — Key Information Memorandum (KIM)",
            "source": "PPFAS AMC",
            "document_type": "KIM",
            "last_verified": "2026-05-21",
        },
        {
            "url": "https://amc.ppfas.com/downloads/parag-parikh-conservative-hybrid-fund/sid-parag-parikh-conservative-hybrid-fund.pdf?21042026",
            "description": "Parag Parikh Conservative Hybrid Fund — Scheme Information Document (SID)",
            "source": "PPFAS AMC",
            "document_type": "SID",
            "last_verified": "2026-04-21",
        },

        # --- 4. Parag Parikh Large Cap Growth Direct Plan ---
        {
            "url": "https://kuvera.in/mutual-funds/fund/parag-parikh-large-cap-growth--PPLCFGZ-GR",
            "description": "Parag Parikh Large Cap Fund — Direct Growth fund profile on Kuvera",
            "source": "Kuvera",
            "document_type": "Fund Profile",
            "last_verified": "2026-06-01",
        },
        {
            "url": "https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-May-2026.pdf?08062026",
            "description": "PPFAS Mutual Fund factsheet for May 2026 — Large Cap Fund pages",
            "source": "PPFAS AMC",
            "document_type": "Factsheet",
            "last_verified": "2026-06-08",
        },
        {
            "url": "https://amc.ppfas.com/downloads/parag-parikh-large-cap-fund/kim-parag-parikh-large-cap-fund.pdf?21052026",
            "description": "Parag Parikh Large Cap Fund — Key Information Memorandum (KIM)",
            "source": "PPFAS AMC",
            "document_type": "KIM",
            "last_verified": "2026-05-21",
        },
        {
            "url": "https://amc.ppfas.com/downloads/parag-parikh-large-cap-fund/sid-parag-parikh-large-cap-fund.pdf?21042026",
            "description": "Parag Parikh Large Cap Fund — Scheme Information Document (SID)",
            "source": "PPFAS AMC",
            "document_type": "SID",
            "last_verified": "2026-04-21",
        },

        # --- 5. Parag Parikh Dynamic Asset Allocation Growth Direct Plan ---
        {
            "url": "https://kuvera.in/mutual-funds/fund/parag-parikh-dynamic-asset-allocation-growth--PPDAFGZ-GR",
            "description": "Parag Parikh Dynamic Asset Allocation Fund — Direct Growth fund profile on Kuvera",
            "source": "Kuvera",
            "document_type": "Fund Profile",
            "last_verified": "2026-06-01",
        },
        {
            "url": "https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-May-2026.pdf?08062026",
            "description": "PPFAS Mutual Fund factsheet for May 2026 — Dynamic Asset Allocation Fund pages",
            "source": "PPFAS AMC",
            "document_type": "Factsheet",
            "last_verified": "2026-06-08",
        },
        {
            "url": "https://amc.ppfas.com/downloads/parag-parikh-dynamic-asset-allocation-fund/kim-parag-parikh-dynamic-asset-allocation-fund.pdf?21052026",
            "description": "Parag Parikh Dynamic Asset Allocation Fund — Key Information Memorandum (KIM)",
            "source": "PPFAS AMC",
            "document_type": "KIM",
            "last_verified": "2026-05-21",
        },
        {
            "url": "https://amc.ppfas.com/downloads/parag-parikh-dynamic-asset-allocation-fund/sid-parag-parikh-dynamic-asset-allocation-fund.pdf?21042026",
            "description": "Parag Parikh Dynamic Asset Allocation Fund — Scheme Information Document (SID)",
            "source": "PPFAS AMC",
            "document_type": "SID",
            "last_verified": "2026-04-21",
        },

        # --- Kuvera Help Articles & Blogs ---
        {
            "url": "https://kuvera.freshdesk.com/support/solutions/articles/82000725676-how-do-i-get-my-capital-gains-report-for-filing-taxes-",
            "description": "How to download a Capital Gains report for tax filing on Kuvera",
            "source": "Kuvera",
            "document_type": "Help Article",
            "last_verified": "2026-06-01",
        },
        {
            "url": "https://kuvera.in/blog/how-to-stop-cancel-and-redeem-mutual-fund-sip-kuvera/",
            "description": "Guide to stopping, cancelling, and redeeming a mutual fund SIP on Kuvera",
            "source": "Kuvera",
            "document_type": "Blog",
            "last_verified": "2026-06-01",
        },
        {
            "url": "https://kuvera.in/blog/elss-meaning-lock-in-period-and-advantages/",
            "description": "Explainer on ELSS funds: meaning, 3-year lock-in period, and tax advantages",
            "source": "Kuvera",
            "document_type": "Blog",
            "last_verified": "2026-06-01",
        },
        {
            "url": "https://kuvera.freshdesk.com/support/solutions/articles/82000703085-how-do-i-switch-my-regular-mutual-funds-to-direct-",
            "description": "How to switch regular mutual fund plans to direct plans on Kuvera",
            "source": "Kuvera",
            "document_type": "Help Article",
            "last_verified": "2026-06-01",
        },
        {
            "url": "https://kuvera.freshdesk.com/support/solutions/articles/82000702595-when-will-my-mutual-fund-redemption-amount-get-credited-",
            "description": "Redemption timelines: when the proceeds from a mutual fund sale are credited",
            "source": "Kuvera",
            "document_type": "Help Article",
            "last_verified": "2026-06-01",
        },

        # --- SEBI Regulatory Documents ---
        {
            "url": "https://www.sebi.gov.in/legal/master-circulars/mar-2026/master-circular-for-mutual-funds_100491.html",
            "description": "SEBI Master Circular for Mutual Funds (March 2026) — consolidated regulatory framework",
            "source": "SEBI",
            "document_type": "Regulatory Circular",
            "last_verified": "2026-06-01",
        },
        {
            "url": "https://investor.sebi.gov.in/iematerial.html",
            "description": "SEBI investor education materials — awareness resources for retail investors",
            "source": "SEBI",
            "document_type": "Investor Education",
            "last_verified": "2026-06-01",
        },
        {
            "url": "https://www.sebi.gov.in/sebi_data/attachdocs/1475063737177.pdf",
            "description": "SEBI circular on Total Expense Ratio (TER) and fee structure for mutual funds",
            "source": "SEBI",
            "document_type": "Regulatory Circular",
            "last_verified": "2026-06-01",
        },

        # --- AMFI Documents ---
        {
            "url": "https://www.amfiindia.com/investor/become-mf-distributor?zoneName=InvestorService",
            "description": "AMFI Securities Market booklet — investor service and distributor guidelines",
            "source": "AMFI",
            "document_type": "Investor Education",
            "last_verified": "2026-06-01",
        },
        {
            "url": "https://www.amfiindia.com/uploads/AMFI_Master_Cicular_for_MF_Ds_3c7f5ee44f.pdf",
            "description": "AMFI Master Circular for Mutual Fund Distributors",
            "source": "AMFI",
            "document_type": "Regulatory Circular",
            "last_verified": "2026-06-01",
        },
        {
            "url": "https://www.amfiindia.com/Themes/Theme1/downloads/NewRuleonApplicableNAVeffectivefromFebruary12021.pdf",
            "description": "AMFI circular on applicable NAV rules for mutual fund transactions (effective Feb 2021)",
            "source": "AMFI",
            "document_type": "Regulatory Circular",
            "last_verified": "2026-06-01",
        },
    ]

    # Flat URL list derived from SOURCE_MANIFEST — used by legacy callers and /api/sources.
    SOURCE_MANIFEST_URLS = [entry["url"] for entry in SOURCE_MANIFEST]


def _build_source_url_map():
    """Maps local PDF filenames to their canonical public URL from SOURCE_MANIFEST."""
    mapping = {}
    for entry in Config.SOURCE_MANIFEST:
        url = entry["url"]
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
