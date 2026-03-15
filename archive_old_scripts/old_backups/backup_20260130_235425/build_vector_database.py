#!/usr/bin/env python3
"""
Build Vector Database for AI Copilot RAG System
===============================================

Embeds all knowledge base documents into ChromaDB vector database
for semantic search and retrieval augmented generation (RAG).

Architecture:
- Reads from knowledge/kb_sources/ (631 MD files)
- Chunks documents (500 chars, 100 overlap)
- Embeds with sentence-transformers (all-MiniLM-L6-v2)
- Stores in ChromaDB at desktop_app/ai_knowledge_db/

Collections:
- database_schema: Table schemas, constraints, indexes
- business_rules: GST calc, HOS regs, reserve_number patterns
- tax_rules: T2/T4, PD7A, WCB, CRA regulations
- session_history: Problem/solution pairs from SESSION_*.md
- code_examples: Python functions, SQL queries
- analysis_reports: Audit findings, reconciliation reports

Usage:
    python scripts/build_vector_database.py --rebuild
    python scripts/build_vector_database.py --update  # incremental
    python scripts/build_vector_database.py --test "What is reserve_number?"
"""
import os
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# Paths
KB_ROOT = Path("knowledge")
KB_SOURCES = KB_ROOT / "kb_sources"
METADATA_FILE = KB_ROOT / "metadata.json"
VECTOR_DB_PATH = Path("desktop_app/ai_knowledge_db")

# Embedding model (384-dim, fast, good quality)
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Chunking parameters
CHUNK_SIZE = 500  # characters
CHUNK_OVERLAP = 100  # characters


class VectorDatabaseBuilder:
    def __init__(self):
        # Load metadata
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            self.metadata = json.load(f)
        
        # Initialize embedding model
        print(f"📥 Loading embedding model: {EMBEDDING_MODEL}...")
        self.embedder = SentenceTransformer(EMBEDDING_MODEL)
        print(f"  ✅ Model loaded (dim={self.embedder.get_sentence_embedding_dimension()})")
        
        # Initialize ChromaDB
        VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(VECTOR_DB_PATH),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Collection names
        self.collections = {
            'database_schema': None,
            'business_rules': None,
            'tax_rules': None,
            'session_history': None,
            'code_examples': None,
            'analysis_reports': None,
        }
    
    def chunk_text(self, text: str, metadata: Dict) -> List[Tuple[str, Dict]]:
        """Split text into overlapping chunks with metadata"""
        chunks = []
        text_len = len(text)
        
        # Skip empty or very short texts
        if text_len < 50:
            return chunks
        
        start = 0
        chunk_id = 0
        
        while start < text_len:
            end = start + CHUNK_SIZE
            
            # Try to break at sentence boundary
            if end < text_len:
                # Look for sentence end in last 100 chars
                search_start = max(start, end - 100)
                period_pos = text.rfind('.', search_start, end)
                if period_pos > start:
                    end = period_pos + 1
            
            chunk_text = text[start:end].strip()
            
            # Skip chunks that are too short or just whitespace
            if len(chunk_text) < 50:
                break
            
            # Build chunk metadata
            chunk_meta = {
                'chunk_id': chunk_id,
                'chunk_start': start,
                'chunk_end': end,
                'source_file': metadata.get('kb_path', ''),
                'domain': metadata.get('domain', 'general'),
                'type': metadata.get('type', 'documentation'),
                'priority': metadata.get('priority', 'medium'),
                'concepts': ','.join(metadata.get('concepts', [])),
                'tables': ','.join(metadata.get('tables', [])),
            }
            
            chunks.append((chunk_text, chunk_meta))
            
            chunk_id += 1
            start = end - CHUNK_OVERLAP if end < text_len else text_len
        
        return chunks
    
    def determine_collection(self, metadata: Dict) -> str:
        """Determine which collection a document belongs to"""
        doc_type = metadata.get('type', 'documentation')
        domain = metadata.get('domain', 'general')
        
        if doc_type == 'schema':
            return 'database_schema'
        elif doc_type == 'rule' or 'copilot-instructions' in metadata.get('source_path', ''):
            return 'business_rules'
        elif domain == 'tax' or 't2' in metadata.get('source_path', '').lower():
            return 'tax_rules'
        elif doc_type == 'session_log':
            return 'session_history'
        elif doc_type == 'code':
            return 'code_examples'
        else:
            return 'analysis_reports'
    
    def get_or_create_collection(self, name: str):
        """Get existing collection or create new one"""
        if self.collections[name] is None:
            try:
                self.collections[name] = self.client.get_collection(name)
                print(f"  📂 Loaded existing collection: {name}")
            except:
                self.collections[name] = self.client.create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"}  # Use cosine similarity
                )
                print(f"  ✨ Created new collection: {name}")
        
        return self.collections[name]
    
    def embed_document(self, source_key: str, force: bool = False):
        """Embed single document into appropriate collection"""
        if source_key in ['source_hashes', 'last_updated', 'total_sources', 'statistics']:
            return None
        
        meta = self.metadata[source_key]
        kb_path = KB_ROOT / meta['kb_path']
        
        # Skip if file doesn't exist
        if not kb_path.exists():
            return None
        
        # Read content
        try:
            with open(kb_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  ⚠️  Error reading {kb_path.name}: {e}")
            return None
        
        # Chunk text
        chunks = self.chunk_text(content, meta)
        if not chunks:
            return None
        
        # Determine collection
        collection_name = self.determine_collection(meta)
        collection = self.get_or_create_collection(collection_name)
        
        # Embed chunks
        chunk_texts = [c[0] for c in chunks]
        embeddings = self.embedder.encode(chunk_texts, show_progress_bar=False)
        
        # Generate unique IDs
        base_id = f"{source_key}_{meta.get('hash', '')[:8]}"
        ids = [f"{base_id}_chunk{i}" for i in range(len(chunks))]
        
        # Prepare metadatas (ChromaDB format)
        metadatas = [c[1] for c in chunks]
        
        # Add to collection
        try:
            collection.add(
                ids=ids,
                embeddings=embeddings.tolist(),
                documents=chunk_texts,
                metadatas=metadatas
            )
            return {
                'source': source_key,
                'collection': collection_name,
                'chunks': len(chunks),
                'file': kb_path.name
            }
        except Exception as e:
            print(f"  ⚠️  Error adding {kb_path.name} to {collection_name}: {e}")
            return None
    
    def rebuild(self):
        """Full rebuild: delete all collections and re-embed everything"""
        print("🔨 REBUILDING VECTOR DATABASE")
        print("=" * 60)
        
        # Reset collections (clears data but keeps client)
        print("\n🗑️  Resetting all collections...")
        try:
            self.client.reset()
            print("  ✅ Collections reset")
        except Exception as e:
            print(f"  ⚠️  Reset warning: {e}")
        
        # Embed all documents
        print(f"\n📊 Embedding {self.metadata.get('total_sources', 0)} documents...")
        
        stats = {
            'database_schema': 0,
            'business_rules': 0,
            'tax_rules': 0,
            'session_history': 0,
            'code_examples': 0,
            'analysis_reports': 0,
        }
        
        total_chunks = 0
        processed = 0
        
        for source_key in self.metadata.keys():
            if source_key in ['source_hashes', 'last_updated', 'total_sources', 'statistics']:
                continue
            
            result = self.embed_document(source_key, force=True)
            if result:
                stats[result['collection']] += 1
                total_chunks += result['chunks']
                processed += 1
                
                if processed % 50 == 0:
                    print(f"  ⏳ Processed {processed} documents ({total_chunks} chunks)...")
        
        print(f"\n✅ Embedded {processed} documents into {total_chunks} chunks")
        print("\n📊 Collection Statistics:")
        for coll_name, count in stats.items():
            if count > 0:
                collection = self.get_or_create_collection(coll_name)
                chunk_count = collection.count()
                print(f"  {coll_name:20} {count:3} docs, {chunk_count:5} chunks")
        
        # Save build metadata
        build_info = {
            'built_at': datetime.now().isoformat(),
            'total_documents': processed,
            'total_chunks': total_chunks,
            'embedding_model': EMBEDDING_MODEL,
            'chunk_size': CHUNK_SIZE,
            'chunk_overlap': CHUNK_OVERLAP,
            'collections': stats,
        }
        
        build_file = VECTOR_DB_PATH / "build_info.json"
        with open(build_file, 'w', encoding='utf-8') as f:
            json.dump(build_info, f, indent=2)
        
        print(f"\n💾 Build info saved: {build_file}")
        print("\n✅ Vector database rebuild complete!")
    
    def test_search(self, query: str, n_results: int = 5):
        """Test semantic search across all collections"""
        print(f"\n🔍 Testing search: \"{query}\"")
        print("=" * 60)
        
        # Embed query
        query_embedding = self.embedder.encode([query])[0]
        
        # Search each collection
        for coll_name in self.collections.keys():
            try:
                collection = self.client.get_collection(coll_name)
                results = collection.query(
                    query_embeddings=[query_embedding.tolist()],
                    n_results=min(n_results, collection.count())
                )
                
                if results['documents'][0]:
                    print(f"\n📂 {coll_name}:")
                    for i, (doc, meta, dist) in enumerate(zip(
                        results['documents'][0],
                        results['metadatas'][0],
                        results['distances'][0]
                    )):
                        print(f"\n  {i+1}. [{meta.get('source_file', 'unknown')}] (similarity: {1-dist:.3f})")
                        print(f"     {doc[:200]}...")
            except Exception as e:
                print(f"  ⚠️  {coll_name}: {e}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Build Vector Database")
    parser.add_argument('--rebuild', action='store_true', help='Full rebuild (delete + re-embed)')
    parser.add_argument('--test', type=str, help='Test search with query')
    
    args = parser.parse_args()
    
    builder = VectorDatabaseBuilder()
    
    if args.test:
        builder.test_search(args.test)
    else:
        builder.rebuild()


if __name__ == "__main__":
    main()
