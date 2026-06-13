import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.Phase0_Shared_Foundation.config import Config

def get_page_context(file_name: str, page_text: str) -> str:
    text_lower = page_text.lower()
    file_lower = file_name.lower()
    
    # 0. Check for shared/common pages listing multiple funds
    fund_keywords = ["liquid", "arbitrage", "conservative", "large cap", "dynamic", "flexi", "elss"]
    mentioned_count = sum(1 for kw in fund_keywords if kw in text_lower)
    if mentioned_count >= 3:
        return "Parag Parikh Mutual Fund"
        
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

class DocumentLoader:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        # Standard chunking for RAG
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )

    def load_and_split(self):
        """Loads all PDFs in data_dir and splits them into chunks."""
        documents = []
        if not os.path.exists(self.data_dir):
            return documents
            
        loaded_filenames = set()
        for root, _, files in os.walk(self.data_dir):
            for file in files:
                if file.lower().endswith(".pdf"):
                    if file in loaded_filenames:
                        continue
                    loaded_filenames.add(file)
                    
                    file_path = os.path.join(root, file)
                    print(f"[DocumentLoader] Loading: {file_path}", flush=True)
                    loader = PyPDFLoader(file_path)
                    docs = loader.load()
                    
                    parent_folder = os.path.basename(root)
                    for doc in docs:
                        doc.metadata["source"] = file
                        doc.metadata["source_url"] = Config.SOURCE_URL_MAP.get(file, Config.FEE_EXPLAINER_AMFI_URL)
                        context = get_page_context(file, doc.page_content)
                        if not context:
                            context = parent_folder
                        doc.metadata["context"] = context
                    
                    documents.extend(docs)
                    
        chunks = self.text_splitter.split_documents(documents)
        for chunk in chunks:
            context = chunk.metadata.get("context", "Unknown")
            chunk.page_content = f"[{context}] {chunk.page_content}"
            
        return chunks


