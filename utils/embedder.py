from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import os
import pickle
from sklearn.metrics.pairwise import cosine_similarity
from config import Config

class Embedder:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # Local cache path for sentence transformers
        model_name = Config.EMBEDDING_MODEL_NAME
        model_path = os.path.join(Config.MODEL_CACHE_FOLDER, model_name)
        
        # Load the model, downloading if not cached
        if os.path.exists(model_path):
            print(f"Loading cached embedding model from {model_path}...")
            self.model = SentenceTransformer(model_path)
        else:
            print(f"Downloading embedding model '{model_name}' and caching locally...")
            self.model = SentenceTransformer(model_name)
            self.model.save(model_path)
            print("Model cached successfully.")

    def get_embedding(self, text):
        """Generate embedding for a single text string."""
        if not text or not text.strip():
            # Return zero vector if text is empty
            return np.zeros(384, dtype=np.float32)
        
        # Sentence Transformer MiniLM produces 384 dimensional embeddings
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding

    def get_embeddings_batch(self, texts):
        """Generate embeddings for a list of text strings."""
        if not texts:
            return []
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings

    def compute_similarity(self, text_emb1, text_emb2):
        """Calculate cosine similarity between two embeddings."""
        # Reshape to 2D arrays for sklearn
        emb1 = text_emb1.reshape(1, -1)
        emb2 = text_emb2.reshape(1, -1)
        return float(cosine_similarity(emb1, emb2)[0][0])

class FaissSearchIndex:
    """Helper class to build and query FAISS indices for candidate retrieval."""
    def __init__(self, dimension=384):
        self.dimension = dimension
        # Flat Index (L2 distance or Inner Product for Cosine Similarity)
        # We normalize embeddings to use L2 flat index for Cosine similarity
        self.index = faiss.IndexFlatL2(dimension)
        self.candidate_ids = []

    def add_candidates(self, cids, embeddings):
        """Add candidate embeddings to the index.
        cids: List of Candidate DB IDs (or Candidate IDs like CAND_XXX)
        embeddings: numpy array of shape (N, 384)
        """
        if len(embeddings) == 0:
            return
        
        # Convert to float32 numpy array
        embs = np.array(embeddings).astype('float32')
        # L2 index measures squared Euclidean distance.
        # If we normalize vectors first, L2 distance is monotonically related to cosine similarity:
        # ||u - v||^2 = ||u||^2 + ||v||^2 - 2(u.v) = 2 - 2*cosine_similarity
        faiss.normalize_L2(embs)
        
        self.index.add(embs)
        self.candidate_ids.extend(cids)

    def query(self, query_embedding, k=100):
        """Retrieve top k matches.
        Returns: List of tuples (candidate_id, score)
        """
        if self.index.ntotal == 0:
            return []
            
        q_emb = np.array([query_embedding]).astype('float32')
        faiss.normalize_L2(q_emb)
        
        # Search index
        # D: distances (squared L2 distance), I: indices
        D, I = self.index.search(q_emb, min(k, self.index.ntotal))
        
        results = []
        for i in range(len(I[0])):
            idx = I[0][i]
            if idx == -1:
                continue
            dist = D[0][i]
            # Convert L2 distance back to cosine similarity score:
            # cos_sim = 1 - (dist / 2)
            cosine_score = float(1.0 - (dist / 2.0))
            results.append((self.candidate_ids[idx], cosine_score))
            
        return results
