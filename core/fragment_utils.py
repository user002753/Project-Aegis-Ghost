"""
Fragment Extraction Utilities for Project Aegis Ghost
Handles extraction of secret fragments from ZIP archives and secret reconstruction.
"""

import zipfile
import os
from typing import Optional, List

try:
    from secretsharing import PlaintextToHexSecretSharer
    SECRET_SHARING_AVAILABLE = True
except ImportError:
    SECRET_SHARING_AVAILABLE = False


def extract_fragments(zip_path: str, out_dir: str) -> bool:
    """
    Extract fragments from a ZIP file to a specified output directory.
    
    Args:
        zip_path: Path to the ZIP file containing fragments
        out_dir: Directory to extract fragments to
        
    Returns:
        bool: True if extraction successful, False otherwise
    """
    if not os.path.exists(zip_path):
        print(f"Error: ZIP file not found at {zip_path}")
        return False
    
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(out_dir)
        
        print("Fragments extracted successfully")
        return True
    except zipfile.BadZipFile:
        print(f"Error: {zip_path} is not a valid ZIP file")
        return False
    except Exception as e:
        print(f"Error extracting fragments: {str(e)}")
        return False


def get_fragment_count(zip_path: str) -> Optional[int]:
    """
    Get the number of fragments in a ZIP file.
    
    Args:
        zip_path: Path to the ZIP file
        
    Returns:
        int: Number of fragments, or None if error
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            return len(z.namelist())
    except Exception:
        return None


def reconstruct_secret(shares: List[str], threshold: int = 5) -> str:
    """
    Reconstruct a secret from Shamir secret shares.
    
    Uses the PlaintextToHexSecretSharer from the secretsharing library
    to recover the original secret from a list of shares.
    
    Args:
        shares: List of Shamir secret shares (hex format)
        threshold: Minimum number of shares needed to reconstruct (default: 5)
        
    Returns:
        str: The reconstructed secret
        
    Raises:
        ImportError: If secretsharing library is not installed
        ValueError: If insufficient shares provided
    """
    if not SECRET_SHARING_AVAILABLE:
        raise ImportError("secretsharing library is not installed")
    
    if len(shares) < threshold:
        raise ValueError(f"Need at least {threshold} shares to reconstruct, got {len(shares)}")
    
    valid_shares = shares[:threshold]
    
    secret = PlaintextToHexSecretSharer.recover_secret(valid_shares)
    
    return secret
