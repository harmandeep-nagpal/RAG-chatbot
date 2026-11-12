import chromadb
from app.embeddings import embed_texts

client = chromadb.PersistentClient(path="./chroma_data")
collection = client.get_or_create_collection(name="documents")


def add_chunks_to_store(chunks: list[dict]):
    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)
    ids = [str(i) for i in range(len(texts))]
    metadatas = [{"source": c["source"]} for c in chunks]
    collection.add(documents=texts, embeddings=embeddings, ids=ids, metadatas=metadatas)


def search_similar_chunks(query: str, top_k: int = 3) -> list[dict]:
    query_embedding = embed_texts([query])[0]
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k)

    matches = []
    for text, metadata, distance in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        matches.append({
            "text": text,
            "source": metadata["source"],
            "distance": distance,
        })
    return matches