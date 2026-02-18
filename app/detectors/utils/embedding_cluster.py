"""
Embedding-based topic clustering utilities.

Uses sentence transformers to encode topics into embeddings,
then applies DBSCAN clustering to identify semantically similar topic groups.
"""

import logging
from functools import lru_cache
from typing import Set, List
from collections import defaultdict

from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_model():
    """
    Load and cache the sentence transformer model.
    
    Returns:
        SentenceTransformer model instance
    """
    settings = get_settings()
    model_name = settings.embedding_model
    
    logger.info(f"Loading sentence transformer model: {model_name}")
    model = SentenceTransformer(model_name)
    logger.info("Model loaded successfully")
    
    return model


def cluster_topics(topics: Set[str]) -> List[Set[str]]:
    """
    Cluster topics based on semantic similarity using embeddings.
    
    Uses sentence transformers to encode topics into vector embeddings,
    then applies DBSCAN clustering to group semantically similar topics.
    
    Args:
        topics: Set of topic strings to cluster
        
    Returns:
        List of topic clusters (sets), where each cluster contains
        semantically similar topics. Only returns clusters meeting
        the minimum size threshold. Topics not in any cluster are omitted.
        
    Example:
        >>> topics = {'pytorch', 'tensorflow', 'keras', 'cooking', 'baking'}
        >>> clusters = cluster_topics(topics)
        >>> # Might return: [{'pytorch', 'tensorflow', 'keras'}, {'cooking', 'baking'}]
    """
    if not topics:
        logger.debug("No topics provided for clustering")
        return []
    
    if len(topics) < 2:
        logger.debug("Insufficient topics for clustering (need at least 2)")
        return []
    
    settings = get_settings()
    
    # Convert set to list for indexing
    topic_list = list(topics)
    
    logger.debug(f"Clustering {len(topic_list)} topics: {topic_list}")
    
    try:
        # Load model (cached)
        model = _get_model()
        
        # Encode topics into embeddings
        logger.debug("Encoding topics into embeddings...")
        embeddings = model.encode(topic_list, show_progress_bar=False)
        logger.debug(f"Encoded {len(embeddings)} embeddings, shape: {embeddings.shape}")
        
        # Apply DBSCAN clustering
        logger.debug(
            f"Applying DBSCAN with eps={settings.embedding_cluster_eps}, "
            f"min_samples={settings.embedding_cluster_min_samples}"
        )
        clustering = DBSCAN(
            eps=settings.embedding_cluster_eps,
            min_samples=settings.embedding_cluster_min_samples,
            metric="cosine"
        ).fit(embeddings)
        
        labels = clustering.labels_
        logger.debug(f"Clustering complete. Labels: {labels}")
        
        # Group topics by cluster label
        clusters_dict = defaultdict(set)
        noise_topics = []
        
        for idx, label in enumerate(labels):
            if label == -1:
                # DBSCAN marks outliers as -1 (noise)
                noise_topics.append(topic_list[idx])
            else:
                clusters_dict[label].add(topic_list[idx])
        
        if noise_topics:
            logger.debug(f"Noise topics (not in any cluster): {noise_topics}")
        
        # Filter clusters by minimum size
        min_size = settings.emergence_cluster_min_size
        valid_clusters = [
            cluster for cluster in clusters_dict.values()
            if len(cluster) >= min_size
        ]
        
        logger.info(
            f"Found {len(valid_clusters)} clusters "
            f"(min_size={min_size}): {valid_clusters}"
        )
        
        return valid_clusters
        
    except Exception as e:
        logger.error(f"Error during topic clustering: {e}", exc_info=True)
        # Return empty list on error rather than failing
        return []


def get_cluster_center_topic(cluster: Set[str]) -> str:
    """
    Find the most representative topic in a cluster.
    
    Returns the topic whose embedding is closest to the cluster centroid.
    Useful for naming or summarizing a cluster.
    
    Args:
        cluster: Set of topics in the cluster
        
    Returns:
        The most central topic string
    """
    if not cluster:
        return ""
    
    if len(cluster) == 1:
        return list(cluster)[0]
    
    try:
        model = _get_model()
        topic_list = list(cluster)
        embeddings = model.encode(topic_list, show_progress_bar=False)
        
        # Calculate centroid
        import numpy as np
        centroid = np.mean(embeddings, axis=0)
        
        # Find topic closest to centroid
        from sklearn.metrics.pairwise import cosine_similarity
        similarities = cosine_similarity([centroid], embeddings)[0]
        most_central_idx = np.argmax(similarities)
        
        return topic_list[most_central_idx]
        
    except Exception as e:
        logger.error(f"Error finding cluster center: {e}")
        # Fallback: return first topic alphabetically
        return sorted(cluster)[0]
