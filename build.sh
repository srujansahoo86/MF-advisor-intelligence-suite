#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Pre-download the fastembed ONNX model during build so first request doesn't timeout
python -c "
from fastembed import TextEmbedding
print('[build] Downloading embedding model...')
TextEmbedding(model_name='BAAI/bge-small-en-v1.5')
print('[build] Embedding model cached successfully.')
"
