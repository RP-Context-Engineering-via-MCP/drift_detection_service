"""Vector operation utilities."""

from typing import List

import numpy as np


def cosine_distance(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine distance between two vectors.
    
    Cosine distance = 1 - cosine similarity
    
    Args:
        vec1: First vector
        vec2: Second vector
    
    Returns:
        Cosine distance (0 = identical, 2 = opposite)
    """
    arr1 = np.array(vec1)
    arr2 = np.array(vec2)
    
    dot_product = np.dot(arr1, arr2)
    norm1 = np.linalg.norm(arr1)
    norm2 = np.linalg.norm(arr2)
    
    if norm1 == 0 or norm2 == 0:
        return 1.0  # Maximum distance if either vector is zero
    
    cosine_sim = dot_product / (norm1 * norm2)
    return 1.0 - cosine_sim


def normalize_vector(vec: List[float]) -> List[float]:
    """
    Normalize a vector to unit length.
    
    Args:
        vec: Input vector
    
    Returns:
        Normalized vector
    """
    arr = np.array(vec)
    norm = np.linalg.norm(arr)
    
    if norm == 0:
        return vec
    
    return (arr / norm).tolist()
