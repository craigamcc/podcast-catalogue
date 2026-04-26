"""
Conversational Intent Router for Podcast Catalogue.
Classifies user intent and dispatches to the appropriate engine.
"""
from __future__ import annotations

import json
import aiohttp
from typing import Dict, Any, Optional, List

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3:14b"

# Lightweight system prompt for fast intent classification
ROUTER_SYSTEM_PROMPT = """
You are a podcast assistant intent classifier. Given a user message, classify the intent and extract parameters.
Return ONLY a valid JSON object. No markdown, no explanation.
"""


async def classify_intent(
    session: aiohttp.ClientSession,
    user_message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Classifies user intent and extracts structured parameters.
    
    Returns:
    {
        "intent": "recommend" | "search" | "query" | "clip" | "similar",
        "params": { ... extracted parameters ... },
        "response_hint": "Brief suggestion for how to frame the response"
    }
    """
    history_context = ""
    if conversation_history:
        recent = conversation_history[-3:]  # Last 3 turns
        history_context = "\n".join([f"{m['role']}: {m['content']}" for m in recent])
        history_context = f"\nConversation so far:\n{history_context}\n"

    prompt = f"""
    {history_context}
    User message: "{user_message}"
    
    Classify the intent and extract parameters. Output a JSON object EXACTLY matching this schema:
    {{
        "intent": "recommend | search | query | clip | similar",
        "params": {{
            "interests": ["topic1", "topic2"],
            "scenario": "Morning Commute",
            "tone": "Inspirational",
            "pace": "Slow",
            "genres": ["Science"],
            "keyword": "search term",
            "podcast_title": "show name if mentioned",
            "max_complexity": 0.5
        }},
        "response_hint": "Suggest 3 calming podcasts for evening listening"
    }}
    
    Rules:
    - "recommend": User wants podcast suggestions based on preferences
    - "search": User wants to find specific content or topics in episodes
    - "query": User asks factual questions about shows (episode count, rating, etc.)
    - "clip": User wants to hear a specific part/quote from an episode
    - "similar": User wants "more like this" based on a previous result
    - Only include params that are relevant to the intent
    - Leave irrelevant params as null
    """

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "system": ROUTER_SYSTEM_PROMPT,
        "stream": False,
        "format": "json"
    }

    try:
        async with session.post(OLLAMA_API_URL, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                raw_text = data.get("response", "{}")
                return json.loads(raw_text)
    except Exception as e:
        print(f"[ERR ROUTER] {e}")
    
    # Fallback: treat as search
    return {
        "intent": "search",
        "params": {"keyword": user_message},
        "response_hint": f"Search for: {user_message}"
    }


async def format_conversational_response(
    session: aiohttp.ClientSession,
    intent: str,
    results: Any,
    response_hint: str
) -> str:
    """
    Takes raw results and formats them into a natural conversational response.
    Uses Qwen to synthesise a friendly summary.
    """
    # For small result sets, format directly without LLM overhead
    if not results or (isinstance(results, list) and len(results) == 0):
        return "I couldn't find anything matching that. Could you try rephrasing or being more specific?"
    
    # Build a concise summary for the LLM
    if isinstance(results, list):
        results_summary = json.dumps(results[:3], indent=2, default=str)
    else:
        results_summary = json.dumps(results, indent=2, default=str)
    
    # Truncate if too long
    if len(results_summary) > 3000:
        results_summary = results_summary[:3000] + "\n..."

    prompt = f"""
    You are a friendly podcast assistant. Based on the user's intent and the data below,
    write a brief conversational response (2-4 sentences max).
    
    Intent: {intent}
    Hint: {response_hint}
    Data:
    {results_summary}
    
    Rules:
    - Be concise and enthusiastic
    - Mention specific show titles and why they match
    - If there are audio clips available, mention the user can listen to a specific segment
    - Do NOT output JSON, just natural text
    """

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "system": "You are a helpful, concise podcast assistant. Reply in plain text only.",
        "stream": False
    }

    try:
        async with session.post(OLLAMA_API_URL, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("response", "Here are some results.")
    except Exception:
        pass
    
    return f"I found {len(results) if isinstance(results, list) else 1} result(s). Check the data for details."
