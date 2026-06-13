import os
import sys
import shutil

# Ensure the project root is in the path so imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from src.Phase0_Shared_Foundation.config import Config
from src.Phase1_FAQ_Chatbot.document_loader import DocumentLoader

def build_index():
    """Reads raw PDFs and indexes them into ChromaDB using real semantic embeddings."""
    print(f"Loading documents from: {Config.DATA_DIR}")
    loader = DocumentLoader(Config.DATA_DIR)
    chunks = loader.load_and_split()
    
    if not chunks:
        print("No documents found to index. Please ensure PDFs are in the data/raw_docs folder.")
        return
        
    print(f"Loaded {len(chunks)} chunks.")

    # Wipe old vectorstore (built with fake embeddings — incompatible with real ones)
    if os.path.exists(Config.CHROMA_DB_DIR):
        print(f"Wiping old vectorstore at {Config.CHROMA_DB_DIR}...")
        shutil.rmtree(Config.CHROMA_DB_DIR)

    print(f"Initialising real embeddings: {Config.EMBEDDING_MODEL}")
    embeddings = HuggingFaceEmbeddings(
        model_name=Config.EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    print(f"Indexing {len(chunks)} chunks into ChromaDB at {Config.CHROMA_DB_DIR} in batches of 200...")
    db = Chroma(
        persist_directory=Config.CHROMA_DB_DIR,
        embedding_function=embeddings,
    )
    
    batch_size = 200
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        print(f"[Indexer] Processing batch {i//batch_size + 1}/{(len(chunks) - 1)//batch_size + 1} ({len(batch)} chunks)...", flush=True)
        db.add_documents(batch)
        
    print("Indexing complete with real semantic embeddings.")

if __name__ == "__main__":
    build_index()
