import os
import sys

# Ensure the project root is in the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from src.Phase0_Shared_Foundation.config import Config
from src.Phase1_FAQ_Chatbot.document_loader import DocumentLoader, get_page_context

def run_incremental_index():
    print("Initialising real embeddings...")
    embeddings = HuggingFaceEmbeddings(
        model_name=Config.EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    
    print(f"Connecting to ChromaDB at {Config.CHROMA_DB_DIR}...")
    db = Chroma(
        persist_directory=Config.CHROMA_DB_DIR,
        embedding_function=embeddings,
    )
    
    pp_folders = [
        "1. PARAG  PARIKH LIQUID FUND",
        "2.PARAG PARIKH ARBITRAGE FUND",
        "3.PARAG PARIKH CONSERVATIVE HYBRID GROWTH FUND",
        "4.PARAG PARIKH LARGE CAP GROWTH FUND",
        "5.PARAG PARIKH DYNAMIC ASSET ALLOCATION GROWTH FUND",
    ]
    
    # Identify files to re-index
    pp_files = []
    for folder in pp_folders:
        folder_path = os.path.join(Config.DATA_DIR, folder)
        if os.path.isdir(folder_path):
            for f in os.listdir(folder_path):
                if f.lower().endswith(".pdf"):
                    pp_files.append(f)
                    
    print(f"Found {len(pp_files)} Parag Parikh PDF files to re-index.")
    
    # Delete old chunks
    for filename in pp_files:
        print(f"Deleting existing chunks for source: {filename}...")
        try:
            db.delete(where={"source": filename})
        except Exception as e:
            print(f"Error deleting {filename}: {e}")
            
    # Load and split only the Parag Parikh files
    print("Loading and splitting files with updated context loader...")
    loader = DocumentLoader(Config.DATA_DIR)
    documents = []
    
    loaded_filenames = set()
    for folder in pp_folders:
        folder_path = os.path.join(Config.DATA_DIR, folder)
        if not os.path.exists(folder_path):
            continue
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(".pdf"):
                    if file in loaded_filenames:
                        continue
                    loaded_filenames.add(file)
                    
                    file_path = os.path.join(root, file)
                    print(f"[IncrementalLoader] Loading: {file_path}", flush=True)
                    pdf_loader = PyPDFLoader(file_path)
                    docs = pdf_loader.load()
                    
                    parent_folder = os.path.basename(root)
                    for doc in docs:
                        doc.metadata["source"] = file
                        context = get_page_context(file, doc.page_content)
                        if not context:
                            context = parent_folder
                        doc.metadata["context"] = context
                    documents.extend(docs)
                    
    chunks = loader.text_splitter.split_documents(documents)
    for chunk in chunks:
        context = chunk.metadata.get("context", "Unknown")
        chunk.page_content = f"[{context}] {chunk.page_content}"

    print(f"Generated {len(chunks)} chunks for Parag Parikh files.")
    
    # Index new chunks in batches
    batch_size = 200
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        print(f"[Indexer] Processing batch {i//batch_size + 1}/{(len(chunks) - 1)//batch_size + 1} ({len(batch)} chunks)...", flush=True)
        db.add_documents(batch)
        
    print("Incremental indexing complete.")

if __name__ == "__main__":
    run_incremental_index()
