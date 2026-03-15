"""
LLM Engine - Local Language Model Interface

Provides interface to local Ollama LLM running llama3.1:8b model.
Handles prompt construction, context injection, and response parsing.

Requirements:
    1. Download Ollama: https://ollama.com/download/windows
    2. Run: ollama pull llama3.1:8b (4.7GB)
    3. Start: ollama serve (runs on http://127.0.0.1:11434)

Usage:
    from llm_engine import LLMEngine
    
    llm = LLMEngine()
    response = llm.generate(
        prompt="What is our trial balance for December?",
        context="Retrieved knowledge about general ledger..."
    )
"""

import os
import json
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """LLM response structure"""
    text: str
    model: str
    tokens_generated: int
    functions_called: List[str] = None
    confidence: float = 0.8
    error: Optional[str] = None


class LLMEngine:
    """Interface to local Ollama LLM"""
    
    def __init__(self, model: str = "llama3.1:8b", 
                 base_url: str = "http://127.0.0.1:11434",
                 timeout: int = 120):
        """
        Initialize LLM engine
        
        Args:
            model: Model name (must be pulled via ollama pull)
            base_url: Ollama server URL
            timeout: Request timeout in seconds
        """
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.available = False
        self.system_prompt = self._get_system_prompt()
        
        # Check if Ollama is running
        self.available = self._check_connection()
    
    def _check_connection(self) -> bool:
        """Check if Ollama server is available"""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=2
            )
            if response.status_code == 200:
                return True
        except Exception as e:
            print(f"⚠️ Ollama not available: {e}")
        return False
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for AI Copilot"""
        return """You are an AI Copilot for Arrow Limousine Management System (ALMS).

Your role:
- Help users understand their limousine business data
- Answer questions about charters, payments, payroll, taxes
- Suggest optimizations based on financial data
- Format responses clearly with specific numbers and facts

Important rules:
1. Always reference the knowledge base context provided
2. Use reserve_number (not charter_id) for identifying charters
3. Mention specific dates and amounts from data
4. For financial queries, suggest running specific functions
5. When uncertain, ask clarifying questions

If you need to call a function, format it as:
CALL_FUNCTION: function_name(arg1, arg2)

Example: CALL_FUNCTION: calculate_wcb_owed(2024-01-01, 2024-12-31)
"""
    
    def generate(self, prompt: str, context: str = "", 
                 max_tokens: int = 500) -> LLMResponse:
        """
        Generate response from LLM
        
        Args:
            prompt: User question/prompt
            context: Knowledge base context to inject
            max_tokens: Maximum tokens to generate
        
        Returns:
            LLMResponse with generated text
        """
        if not self.available:
            return LLMResponse(
                text="",
                model=self.model,
                tokens_generated=0,
                error="Ollama server not available. Start with: ollama serve"
            )
        
        # Build full prompt with context
        full_prompt = self._build_prompt(prompt, context)
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.3,  # Lower = more factual
                        "top_p": 0.9,
                    }
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                text = data.get('response', '').strip()
                
                # Extract any function calls
                functions_called = self._extract_function_calls(text)
                
                return LLMResponse(
                    text=text,
                    model=self.model,
                    tokens_generated=data.get('eval_count', 0),
                    functions_called=functions_called,
                    confidence=0.85
                )
            else:
                return LLMResponse(
                    text="",
                    model=self.model,
                    tokens_generated=0,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
        
        except requests.Timeout:
            return LLMResponse(
                text="",
                model=self.model,
                tokens_generated=0,
                error=f"Request timeout after {self.timeout}s"
            )
        except Exception as e:
            return LLMResponse(
                text="",
                model=self.model,
                tokens_generated=0,
                error=str(e)
            )
    
    def _build_prompt(self, user_prompt: str, context: str) -> str:
        """Build complete prompt with system instruction and context"""
        prompt_parts = [
            self.system_prompt,
            "\n" + "=" * 80 + "\n",
        ]
        
        if context:
            prompt_parts.append("KNOWLEDGE BASE CONTEXT:\n")
            prompt_parts.append(context)
            prompt_parts.append("\n" + "-" * 80 + "\n")
        
        prompt_parts.append("USER QUESTION:\n")
        prompt_parts.append(user_prompt)
        prompt_parts.append("\n\nRESPONSE:\n")
        
        return "".join(prompt_parts)
    
    def _extract_function_calls(self, text: str) -> List[str]:
        """Extract function calls from LLM response"""
        functions = []
        lines = text.split('\n')
        
        for line in lines:
            if 'CALL_FUNCTION:' in line:
                func_call = line.split('CALL_FUNCTION:')[1].strip()
                functions.append(func_call)
        
        return functions
    
    def chat(self, conversation: List[Dict[str, str]], 
             context: str = "") -> LLMResponse:
        """
        Multi-turn conversation support
        
        Args:
            conversation: List of {"role": "user|assistant", "content": "text"}
            context: Knowledge base context
        
        Returns:
            LLMResponse
        """
        # Convert conversation to prompt
        prompt_parts = [self.system_prompt]
        
        if context:
            prompt_parts.append("\nKNOWLEDGE CONTEXT:\n" + context + "\n")
        
        for msg in conversation:
            role = msg.get('role', 'user').upper()
            content = msg.get('content', '')
            prompt_parts.append(f"\n{role}:\n{content}")
        
        prompt_parts.append("\n\nASSISTANT:\n")
        
        return self.generate("\n".join(prompt_parts), context="")
    
    def is_available(self) -> bool:
        """Check if LLM is available"""
        return self.available
    
    def get_status(self) -> Dict[str, Any]:
        """Get LLM status information"""
        status = {
            "available": self.available,
            "model": self.model,
            "server": self.base_url,
        }
        
        if self.available:
            try:
                response = requests.get(
                    f"{self.base_url}/api/show",
                    params={"name": self.model},
                    timeout=5
                )
                if response.status_code == 200:
                    info = response.json()
                    status["parameters"] = info.get('parameters', {})
                    status["modelfile"] = info.get('modelfile', '')
            except Exception as e:
                status["error"] = str(e)
        
        return status


def test_llm():
    """Test LLM functionality"""
    print("=" * 80)
    print("LLM ENGINE TEST")
    print("=" * 80)
    
    llm = LLMEngine()
    
    # Test 1: Check availability
    print("\n[TEST 1] Ollama Connection")
    print("-" * 80)
    status = llm.get_status()
    print(f"Available: {status['available']}")
    print(f"Model: {status.get('model', 'N/A')}")
    print(f"Server: {status.get('server', 'N/A')}")
    
    if not llm.available:
        print("\n[INFO] Ollama not running. To test LLM:")
        print("  1. Download: https://ollama.com/download/windows")
        print("  2. Run: ollama pull llama3.1:8b")
        print("  3. Start: ollama serve")
        print("  4. Re-run this test")
        return
    
    # Test 2: Simple generation
    print("\n[TEST 2] Simple Generation")
    print("-" * 80)
    response = llm.generate(
        "What is GST in Canada?",
        max_tokens=100
    )
    print(f"Response: {response.text[:200]}...")
    print(f"Tokens: {response.tokens_generated}")
    
    # Test 3: With context
    print("\n[TEST 3] Generation with Context")
    print("-" * 80)
    context = """
    DATABASE CONTEXT:
    - Arrow Limousine operates in Alberta
    - GST rate: 5% (tax included in prices)
    - Financial year: Jan 1 - Dec 31
    - Primary bank: CIBC account 0228362
    """
    
    response = llm.generate(
        "How much GST should we collect on $1000 revenue?",
        context=context,
        max_tokens=150
    )
    print(f"Response: {response.text[:200]}...")
    if response.functions_called:
        print(f"Functions to call: {response.functions_called}")
    
    # Test 4: Function call detection
    print("\n[TEST 4] Function Call Detection")
    print("-" * 80)
    response = llm.generate(
        "Calculate our WCB liability for 2024",
        context="WCB function available: calculate_wcb_owed(start_date, end_date)",
        max_tokens=200
    )
    if response.functions_called:
        print(f"[SUCCESS] Detected function calls: {response.functions_called}")
    else:
        print(f"[INFO] No function calls in response")
        print(f"Response preview: {response.text[:150]}...")


if __name__ == "__main__":
    test_llm()
