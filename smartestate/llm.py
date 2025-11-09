import os
import requests
from typing import List, Dict, Any


def get_ollama_url() -> str:
    """Get Ollama base URL from environment"""
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def generate_answer(query: str, context: List[Dict[str, Any]], model: str = "llama3.2:1b") -> str:
    """
    Generate natural language answer using Ollama LLM

    Args:
        query: User's question
        context: List of relevant properties/documents from vector search
        model: Ollama model to use (default: llama3.2:1b for fast inference)

    Returns:
        Generated answer as string
    """
    ollama_url = get_ollama_url()

    # Build context from search results
    context_text = ""
    for i, item in enumerate(context[:3], 1):  # Top 3 results
        title = item.get('title', 'Property')
        location = item.get('location', 'Unknown')
        price = item.get('price', 'N/A')
        description = item.get('long_description', '')[:300]  # First 300 chars

        context_text += f"\n\nProperty {i}: {title}\n"
        context_text += f"Location: {location}\n"
        context_text += f"Price: ₹{price:,}\n" if isinstance(price, (int, float)) else f"Price: {price}\n"
        context_text += f"Details: {description}\n"

    # Create prompt
    prompt = f"""You are a helpful real estate assistant. Answer the user's question based on the following property information.

Context (Properties from database):
{context_text}

User Question: {query}

Please provide a helpful, natural answer. If the question is about certificates or safety features, look for mentions of certificates in the property descriptions. Be conversational and helpful.

Answer:"""

    try:
        # Call Ollama API
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                }
            },
            timeout=30
        )

        if response.ok:
            result = response.json()
            return result.get('response', '').strip()
        else:
            # Fallback if Ollama fails
            return f"Found {len(context)} relevant properties. Here are the top matches:\n" + \
                   "\n".join([f"- {p.get('title', '')} at {p.get('location', '')}" for p in context[:3]])

    except Exception as e:
        # Fallback response if LLM fails
        return f"Found {len(context)} properties matching your query. The top result is: {context[0].get('title', 'Property')} " + \
               f"located at {context[0].get('location', 'Unknown location')}." if context else "No matching properties found."


def check_ollama_health() -> bool:
    """Check if Ollama service is available"""
    try:
        ollama_url = get_ollama_url()
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        return response.ok
    except Exception:
        return False
