#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Pre-download the HuggingFace embedding model during build phase
# so it doesn't download on the first request (which would timeout)
python -c "
from sentence_transformers import SentenceTransformer
print('[build] Downloading embedding model...')
SentenceTransformer('BAAI/bge-small-en-v1.5')
print('[build] Embedding model cached successfully.')
"
