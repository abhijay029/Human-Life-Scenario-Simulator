import chromadb
import os
import threading
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv
import re
import unicodedata

load_dotenv()

# One lock to serialize all ChromaDB access across threads
_chroma_lock = threading.Lock()
_client_instance = None

def get_chroma_client():
    global _client_instance
    if _client_instance is None:
        _client_instance = chromadb.PersistentClient(path="./chroma_store")
    return _client_instance

class PersonaMemory:
    def __init__(self, persona_name: str):
        self.persona_name = persona_name

        # Normalise unicode → decompose accents, then encode to ASCII dropping
        # anything that doesn't map (handles curly apostrophes, em-dashes, etc.)
        sanitised = unicodedata.normalize("NFKD", persona_name)
        sanitised = sanitised.encode("ascii", errors="ignore").decode("ascii")

        sanitised = sanitised.lower()
        sanitised = sanitised.replace(" ", "_")
        # Strip everything ChromaDB won't accept: only [a-zA-Z0-9._-] allowed
        sanitised = re.sub(r"[^a-zA-Z0-9._\-]", "", sanitised)
        # ChromaDB requires start and end to be [a-zA-Z0-9]
        sanitised = sanitised.strip("._-")
        # Fallback if name collapsed to fewer than 3 chars
        if len(sanitised) < 3:
            sanitised = f"p_{abs(hash(persona_name)) % 10**8}"
        self.collection_name = f"persona_{sanitised}"

        with _chroma_lock:
            self.client = get_chroma_client()
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )

        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=os.getenv("GEMINI_API_KEY")
        )

    def store_memories_batch(self, memories: list[str], id_prefix: str):
        """Embed and store all memories in a single API call."""
        vectors = self.embeddings.embed_documents(memories)
        ids = [f"{id_prefix}_{i}" for i in range(len(memories))]
        with _chroma_lock:
            self.collection.upsert(
                ids=ids,
                embeddings=vectors,
                documents=memories,
            )
        print(f"[Memory] Stored {len(memories)} memories for {self.persona_name} in one batch.")

    def recall(self, query: str, n_results: int = 2) -> list[str]:
        """Retrieve the most relevant memories for a given situation."""
        with _chroma_lock:
            count = self.collection.count()
        
        if count == 0:
            return []   # nothing indexed yet — skip the query entirely
        query_vector = self.embeddings.embed_query(query)
        
        with _chroma_lock:
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=min(n_results, count)  # can't request more results than documents
            )
        
        return results["documents"][0] if results["documents"] else []

    def store_persona_facts(self, persona):
        """Load all persona traits into memory in one batched embedding call."""
        facts = [
            f"{persona.name} is {persona.age} years old and works as a {persona.occupation}.",
            f"{persona.name}'s personality: {', '.join(persona.personality_traits)}.",
            f"{persona.name} deeply values: {', '.join(persona.values)}.",
            f"{persona.name} gets triggered by: {', '.join(persona.emotional_triggers)}.",
            f"{persona.name}'s background: {persona.background}",
            f"{persona.name}'s goals here: {', '.join(persona.goals)}.",
            f"{persona.name} communicates in a {persona.communication_style} style.",
        ]
        self.store_memories_batch(facts, id_prefix=f"{self.persona_name}_fact")

    def count(self):
        with _chroma_lock:
            return self.collection.count()