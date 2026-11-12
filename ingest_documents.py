from app.ingest import load_all_documents
from app.vectorstore import add_chunks_to_store

chunks = load_all_documents("documents")
print(f"Loaded {len(chunks)} chunks from your documents folder.")
add_chunks_to_store(chunks)
print("Done — chunks are now embedded and stored.")