"""
Artifact Store Service

Manages artifact storage, retrieval, and metadata.
Supports local filesystem and S3-compatible object storage.
"""

import hashlib
import os
from typing import Optional, BinaryIO, Dict, Any
from pathlib import Path
import json
from datetime import datetime


class ArtifactStore:
    """Manages artifact storage and retrieval."""
    
    def __init__(self, storage_path: str = "/tmp/artifacts"):
        """
        Initialize artifact store.
        
        Args:
            storage_path: Base path for artifact storage
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def store_artifact(
        self,
        artifact_id: str,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store an artifact.
        
        Returns:
            {storage_path, content_hash, size_bytes, metadata}
        """
        # Compute content hash
        content_hash = hashlib.sha256(content).hexdigest()
        
        # Create storage directory structure: artifacts/{first_2_chars}/{next_2_chars}/{id}
        prefix = content_hash[:2]
        subdir = content_hash[2:4]
        storage_dir = self.storage_path / prefix / subdir
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Storage path
        storage_file = storage_dir / f"{artifact_id}.bin"
        
        # Write content
        with open(storage_file, 'wb') as f:
            f.write(content)
        
        # Store metadata alongside
        metadata = metadata or {}
        metadata['stored_at'] = datetime.utcnow().isoformat()
        
        metadata_file = storage_dir / f"{artifact_id}.meta.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            'storage_path': str(storage_file.relative_to(self.storage_path)),
            'content_hash': content_hash,
            'size_bytes': len(content),
            'metadata': metadata
        }
    
    def retrieve_artifact(
        self,
        storage_path: str
    ) -> Optional[bytes]:
        """
        Retrieve artifact content.
        
        Args:
            storage_path: Relative path from storage root
            
        Returns:
            Artifact content or None if not found
        """
        full_path = self.storage_path / storage_path
        
        if not full_path.exists():
            return None
        
        with open(full_path, 'rb') as f:
            return f.read()
    
    def retrieve_metadata(
        self,
        storage_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve artifact metadata.
        
        Args:
            storage_path: Relative path from storage root
            
        Returns:
            Metadata dict or None if not found
        """
        # Convert .bin path to .meta.json path
        base_path = self.storage_path / storage_path
        meta_path = base_path.with_suffix('.meta.json')
        
        if not meta_path.exists():
            return None
        
        with open(meta_path, 'r') as f:
            return json.load(f)
    
    def verify_hash(
        self,
        storage_path: str,
        expected_hash: str
    ) -> bool:
        """
        Verify artifact content hash.
        
        Args:
            storage_path: Relative path from storage root
            expected_hash: Expected SHA-256 hash
            
        Returns:
            True if hash matches, False otherwise
        """
        content = self.retrieve_artifact(storage_path)
        
        if content is None:
            return False
        
        actual_hash = hashlib.sha256(content).hexdigest()
        return actual_hash == expected_hash
    
    def delete_artifact(
        self,
        storage_path: str
    ) -> bool:
        """
        Delete an artifact and its metadata.
        
        Args:
            storage_path: Relative path from storage root
            
        Returns:
            True if deleted, False if not found
        """
        full_path = self.storage_path / storage_path
        meta_path = full_path.with_suffix('.meta.json')
        
        deleted = False
        
        if full_path.exists():
            full_path.unlink()
            deleted = True
        
        if meta_path.exists():
            meta_path.unlink()
            deleted = True
        
        return deleted


class S3ArtifactStore(ArtifactStore):
    """
    S3-compatible artifact store.
    
    For production use with AWS S3, MinIO, or other S3-compatible storage.
    """
    
    def __init__(self, bucket_name: str, endpoint_url: Optional[str] = None):
        """
        Initialize S3 artifact store.
        
        Args:
            bucket_name: S3 bucket name
            endpoint_url: Optional custom endpoint (e.g., for MinIO)
        """
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        
        # Lazy import boto3
        try:
            import boto3
            self.s3_client = boto3.client(
                's3',
                endpoint_url=endpoint_url
            )
        except ImportError:
            raise ImportError("boto3 required for S3 storage. Install with: pip install boto3")
    
    def store_artifact(
        self,
        artifact_id: str,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Store artifact in S3."""
        content_hash = hashlib.sha256(content).hexdigest()
        
        # S3 key structure
        prefix = content_hash[:2]
        subdir = content_hash[2:4]
        s3_key = f"artifacts/{prefix}/{subdir}/{artifact_id}.bin"
        
        # Upload to S3
        metadata = metadata or {}
        metadata['stored_at'] = datetime.utcnow().isoformat()
        metadata['content_hash'] = content_hash
        
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=content,
            Metadata={k: str(v) for k, v in metadata.items()}
        )
        
        return {
            'storage_path': s3_key,
            'content_hash': content_hash,
            'size_bytes': len(content),
            'metadata': metadata
        }
    
    def retrieve_artifact(self, storage_path: str) -> Optional[bytes]:
        """Retrieve artifact from S3."""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=storage_path
            )
            return response['Body'].read()
        except self.s3_client.exceptions.NoSuchKey:
            return None
    
    def retrieve_metadata(self, storage_path: str) -> Optional[Dict[str, Any]]:
        """Retrieve artifact metadata from S3."""
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=storage_path
            )
            return response.get('Metadata', {})
        except self.s3_client.exceptions.NoSuchKey:
            return None
    
    def delete_artifact(self, storage_path: str) -> bool:
        """Delete artifact from S3."""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=storage_path
            )
            return True
        except Exception:
            return False


# Factory function
def get_artifact_store(storage_type: str = "local", **kwargs) -> ArtifactStore:
    """
    Get an artifact store instance.
    
    Args:
        storage_type: "local" or "s3"
        **kwargs: Additional arguments for the store
        
    Returns:
        ArtifactStore instance
    """
    if storage_type == "local":
        return ArtifactStore(storage_path=kwargs.get('storage_path', '/tmp/artifacts'))
    elif storage_type == "s3":
        return S3ArtifactStore(
            bucket_name=kwargs['bucket_name'],
            endpoint_url=kwargs.get('endpoint_url')
        )
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")
