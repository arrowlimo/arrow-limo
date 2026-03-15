"""
RAG (Retrieval Augmented Generation) Engine

Provides intelligent retrieval of knowledge base information for AI Copilot.
Combines vector similarity search with semantic understanding.

Usage:
    from rag_engine import KnowledgeRetriever
    
    rag = KnowledgeRetriever()
    results = rag.search("How do I calculate GST on a charter?")
    print(results)
"""

import os
import json
from typing import Dict, List, Any, Optional
from pathlib import Path

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("⚠️ ChromaDB not available - vector search disabled")


class KnowledgeRetriever:
    """Retrieve relevant knowledge from vector database and documentation"""
    
    def __init__(self, db_path: str = None, collection_names: List[str] = None):
        """
        Initialize knowledge retriever
        
        Args:
            db_path: Path to ChromaDB (default: desktop_app/ai_knowledge_db)
            collection_names: Collections to search (default: all)
        """
        if not CHROMADB_AVAILABLE:
            self.client = None
            self.collections = {}
            return
        
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "ai_knowledge_db")
        
        try:
            self.client = chromadb.PersistentClient(path=self.db_path)
            
            # Available collections
            all_collections = [
                'database_schema',
                'business_rules',
                'tax_rules',
                'session_history',
                'code_examples',
                'analysis_reports'
            ]
            
            self.collection_names = collection_names or all_collections
            self.collections = {}
            
            for coll_name in self.collection_names:
                try:
                    self.collections[coll_name] = self.client.get_collection(coll_name)
                except Exception as e:
                    print(f"⚠️ Collection {coll_name} not found: {e}")
        
        except Exception as e:
            print(f"⚠️ ChromaDB initialization failed: {e}")
            self.client = None
            self.collections = {}
    
    def search(self, query: str, domain_filter: str = None, 
               top_k: int = 5) -> Dict[str, Any]:
        """
        Search knowledge base for relevant information
        
        Args:
            query: Natural language search query
            domain_filter: Optional domain filter (tax, payroll, charter, banking, etc.)
            top_k: Number of results per collection
        
        Returns:
            {
                "query": str,
                "total_results": int,
                "collections": {
                    "database_schema": [...],
                    "business_rules": [...],
                    ...
                }
            }
        """
        if not self.client or not self.collections:
            return {
                "error": "Knowledge base not available",
                "query": query,
                "total_results": 0,
                "collections": {}
            }
        
        results = {
            "query": query,
            "total_results": 0,
            "collections": {}
        }
        
        try:
            # Search each collection
            for coll_name, collection in self.collections.items():
                try:
                    # Query the collection
                    query_results = collection.query(
                        query_texts=[query],
                        n_results=top_k,
                        where={"domain": domain_filter} if domain_filter else None
                    )
                    
                    # Format results
                    coll_results = []
                    if query_results['documents'] and len(query_results['documents']) > 0:
                        for i, doc in enumerate(query_results['documents'][0]):
                            if query_results['distances']:
                                distance = query_results['distances'][0][i]
                                similarity = 1 - (distance / 2)  # Convert distance to similarity
                            else:
                                similarity = 0.0
                            
                            metadata = {}
                            if query_results['metadatas'] and len(query_results['metadatas']) > 0:
                                if i < len(query_results['metadatas'][0]):
                                    metadata = query_results['metadatas'][0][i]
                            
                            coll_results.append({
                                "text": doc,
                                "similarity": round(similarity, 3),
                                "source": metadata.get('source_file', 'unknown'),
                                "domain": metadata.get('domain', 'general'),
                                "type": metadata.get('type', 'unknown')
                            })
                    
                    if coll_results:
                        results["collections"][coll_name] = coll_results
                        results["total_results"] += len(coll_results)
                
                except Exception as e:
                    results["collections"][coll_name] = {"error": str(e)}
        
        except Exception as e:
            results["error"] = str(e)
        
        return results
    
    def get_schema_info(self, table_name: str) -> Dict[str, Any]:
        """
        Get database schema information for a specific table
        
        Args:
            table_name: Table name (e.g., 'charters', 'payments')
        
        Returns:
            Schema information with columns, relationships, business rules
        """
        if not self.collections:
            return {"error": "Knowledge base not available"}
        
        query = f"Schema and columns for {table_name} table with all fields and relationships"
        return self.search(query, domain_filter="database", top_k=3)
    
    def get_business_rule(self, rule_name: str) -> Dict[str, Any]:
        """
        Get critical business rules
        
        Args:
            rule_name: Rule name (e.g., 'reserve_number', 'GST calculation', 'WCB')
        
        Returns:
            Business rule definition and implementation details
        """
        if not self.collections:
            return {"error": "Knowledge base not available"}
        
        query = f"Business rule for {rule_name}: definition, examples, and implementation"
        return self.search(query, domain_filter="business_rules", top_k=3)
    
    def find_similar_session(self, problem_description: str) -> Dict[str, Any]:
        """
        Find similar problems from past sessions
        
        Args:
            problem_description: Description of problem encountered
        
        Returns:
            Similar problems and how they were solved
        """
        if not self.collections:
            return {"error": "Knowledge base not available"}
        
        query = f"Problem troubleshooting: {problem_description}"
        return self.search(query, domain_filter="session_history", top_k=5)
    
    def get_code_example(self, topic: str) -> Dict[str, Any]:
        """
        Get working code examples
        
        Args:
            topic: Code topic (e.g., 'GST calculation', 'charter query', 'payroll')
        
        Returns:
            Working code examples with explanations
        """
        if not self.collections:
            return {"error": "Knowledge base not available"}
        
        query = f"Python or SQL code example for {topic} with working implementation"
        return self.search(query, domain_filter="code_examples", top_k=3)
    
    def search_all(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search all collections and return consolidated results
        
        Args:
            query: Search query
            top_k: Results per collection
        
        Returns:
            List of all results sorted by similarity
        """
        results = self.search(query, top_k=top_k)
        
        # Consolidate all results
        all_results = []
        for coll_name, coll_results in results.get("collections", {}).items():
            if isinstance(coll_results, list):
                all_results.extend(coll_results)
        
        # Sort by similarity
        all_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        
        return all_results
    
    def format_context(self, query: str, top_k: int = 3) -> str:
        """
        Format search results as context string for LLM
        
        Args:
            query: Search query
            top_k: Top results to include
        
        Returns:
            Formatted context string
        """
        results = self.search_all(query, top_k=top_k)
        
        context = f"Knowledge Base Context for: {query}\n"
        context += "=" * 80 + "\n\n"
        
        for i, result in enumerate(results[:top_k], 1):
            context += f"{i}. [{result['source']}] (similarity: {result['similarity']:.2%})\n"
            context += f"   Domain: {result['domain']} | Type: {result['type']}\n"
            context += f"   {result['text'][:200]}...\n\n"
        
        return context


def test_retriever():
    """Test the knowledge retriever"""
    print("=" * 80)
    print("KNOWLEDGE RETRIEVER TEST")
    print("=" * 80)
    
    rag = KnowledgeRetriever()
    
    if not rag.client:
        print("[FAIL] Knowledge base not available")
        return
    
    # Test 1: General search
    print("\n[TEST 1] General Search")
    print("-" * 80)
    query = "How do I calculate GST on a charter?"
    results = rag.search(query, top_k=2)
    print(f"Query: {query}")
    print(f"Total Results: {results['total_results']}")
    for coll, items in results.get('collections', {}).items():
        if isinstance(items, list):
            print(f"\n  {coll}:")
            for item in items[:2]:
                print(f"    - Similarity: {item['similarity']:.2%}")
                print(f"      Source: {item['source']}")
                print(f"      Text: {item['text'][:80]}...")
    
    # Test 2: Business rule search
    print("\n\n[TEST 2] Business Rule Search")
    print("-" * 80)
    results = rag.get_business_rule("reserve_number")
    print(f"Business Rule: reserve_number")
    print(f"Total Results: {results['total_results']}")
    
    # Test 3: Code example search
    print("\n\n[TEST 3] Code Example Search")
    print("-" * 80)
    results = rag.get_code_example("payroll calculation")
    print(f"Code Topic: payroll calculation")
    print(f"Total Results: {results['total_results']}")
    
    # Test 4: Consolidated search
    print("\n\n[TEST 4] Consolidated Search")
    print("-" * 80)
    query = "unpaid charters and receivables"
    results = rag.search_all(query, top_k=3)
    print(f"Query: {query}")
    print(f"Top Results (sorted by similarity):")
    for item in results[:3]:
        print(f"  - {item['similarity']:.2%}: [{item['source']}] {item['text'][:70]}...")


if __name__ == "__main__":
    test_retriever()
