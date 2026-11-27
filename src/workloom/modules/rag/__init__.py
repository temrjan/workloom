"""RAG-based modules for WORKLOOM.

RAG modules search the Qdrant knowledge base and generate
responses based on retrieved context.
"""

from workloom.modules.rag.base import BaseRAGService

__all__ = ["BaseRAGService"]
