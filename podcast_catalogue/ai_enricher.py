import os
import json
import asyncio
import re
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from .models import TranscriptSegment

load_dotenv()

def extract_json_from_text(text: str) -> Optional[Dict]:
    """Extracts the first JSON object found in a string, ignoring everything else."""
    if not text:
        return None
    try:
        # 1. Attempt direct parse
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # 2. Try to find content between first { and last }
        try:
            match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except (json.JSONDecodeError, AttributeError):
            pass
    return None

# --- Models & Schemas ---

class VibeSchema(BaseModel):
    tone: List[str] # Changed from str to List[str]
    complexity: float
    pace: str

class LocationSchema(BaseModel):
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None

class TargetAudienceSchema(BaseModel):
    interests: List[str]
    ageGroups: List[str]
    location: Optional[LocationSchema] = None

class GuestSchema(BaseModel):
    name: str
    expertise: str
    bio: str

class EngagementSchema(BaseModel):
    takeaway: str
    keyStatistics: List[str]
    bestQuotes: List[str]
    whyListen: str
    socialPost: str

class PodcastAnalysisSchema(BaseModel):
    narrative_hook: str
    vibe: VibeSchema
    targetAudience: TargetAudienceSchema
    recommendationScenarios: List[str]
    originLocation: Optional[LocationSchema] = None
    geographicCoverage: List[LocationSchema] = []

class EpisodeAnalysisSchema(BaseModel):
    narrative_hook: str
    vibe: VibeSchema
    engagement: EngagementSchema
    entities: List[str]
    contentLocations: List[LocationSchema] = []
    guests: List[GuestSchema] = []

class ChapterSchema(BaseModel):
    title: str
    summary: Optional[str] = ""
    startTime: Optional[float] = Field(None, alias="startTime")
    endTime: Optional[float] = Field(None, alias="endTime")
    # Handle Gemini returning 'start'/'end' or 'start_time'/'end_time' instead
    start: Optional[str] = Field(None, exclude=True)
    end: Optional[str] = Field(None, exclude=True)
    start_time: Optional[str] = Field(None, exclude=True)
    end_time: Optional[str] = Field(None, exclude=True)

    class Config:
        populate_by_name = True

    def model_post_init(self, __context):
        def _parse_time(val) -> float:
            if val is None: return 0.0
            if isinstance(val, (int, float)): return float(val)
            s = str(val).strip().rstrip('s')
            try: return float(s)
            except ValueError: return 0.0
        if self.startTime is None:
            self.startTime = _parse_time(self.start or self.start_time or 0)
        if self.endTime is None:
            self.endTime = _parse_time(self.end or self.end_time or 0)

class HighlightSchema(BaseModel):
    title: str
    reason: str
    category: str  # QUOTE, STAT, PEAK, INSIGHT, GENERAL
    startTime: float
    endTime: float

class EngagementSchema(BaseModel):
    model_config = {"populate_by_name": True}
    takeaway: Optional[str] = None
    key_statistics: List[str] = Field(default_factory=list, alias="keyStatistics")
    best_quotes: List[str] = Field(default_factory=list, alias="bestQuotes")
    why_listen: Optional[str] = Field(None, alias="whyListen")
    social_post: Optional[str] = Field(None, alias="socialPost")
    audiogram_captions: List[Dict[str, Any]] = Field(default_factory=list, alias="audiogramCaptions")

# --- Provider Interfaces ---

class AIEngine:
    async def analyze_podcast(self, description: str, title: str) -> Optional[Dict[str, Any]]: pass
    async def analyze_episode(self, description: str, title: str) -> Optional[Dict[str, Any]]: pass
    async def generate_chapters(self, transcript_text: str, title: str) -> List[Dict[str, Any]]: pass
    async def extract_highlights(self, transcript_text: str, title: str) -> List[Dict[str, Any]]: pass

    async def analyze_episode_transcript(self, segments: List[TranscriptSegment], title: str) -> Optional[Dict]:
        """Deep analysis of full transcript for engagement deliverables."""
        # Bundle segments into text chunks
        transcript_text = "\n".join([f"[{s.speaker or '??'}] {s.text}" for s in segments])
        
        prompt = f"""You are GoldMine, a High-Intensity Content Scout. 
Analyze the full transcript for the episode: '{title}'

Transcript Excerpt:
{transcript_text[:12000]}

Your task is to extract the 'Engagement Layer'—the high-value signals that drive discovery.
Return a structured JSON object with these EXACT fields:

1. 'highlights': A list of objects containing:
   - 'title': A punchy title for the moment.
   - 'reason': Why this moment is significant.
   - 'category': One of ["PEAK", "QUOTE", "STAT", "INSIGHT"].
   - 'startTime' / 'endTime': The exact float timestamps for the moment.
2. 'engagement': An object containing:
   - 'takeaway': The #1 counter-intuitive or essential lesson (Max 25 words).
   - 'keyStatistics': A list of notable data points (numbers, dates, or percentages).
   - 'bestQuotes': A list of verbatim, speaker-attributed excerpts (e.g., "[Name]: '...'").
   - 'whyListen': A compelling 'Industrial-Noir' style value proposition.
   - 'socialPost': A provocative social media draft designed for the Connect PRISM feed.
   - 'audiogramCaptions': A list of objects {{"text": str, "start": float, "end": float}} for the TOP highlight.

Return ONLY valid JSON.
"""
        
        class DeepEngagementResp(BaseModel):
            highlights: List[HighlightSchema]
            engagement: EngagementSchema
            
        return await self._generate(prompt, DeepEngagementResp)

# --- Gemini Provider (Cloud) ---

class GeminiEngine(AIEngine):
    def __init__(self, api_key: str = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self.client = None
        if api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=api_key)
            except Exception as e:
                print(f"       [ERR GEMINI INIT] {e}")
        self.model = model

    async def _generate(self, prompt: str, schema: type[BaseModel]) -> Optional[Dict]:
        from google.genai import types
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3
                )
            )
            return extract_json_from_text(response.text)
        except Exception as e:
            print(f"       [ERR GEMINI] {e}")
            return None

    async def analyze_podcast(self, description: str, title: str) -> Optional[Dict]:
        prompt = f"Analyze show: {title}\nDesc: {description}"
        return await self._generate(prompt, PodcastAnalysisSchema)

    async def analyze_episode(self, description: str, title: str) -> Optional[Dict]:
        prompt = f"Analyze episode: {title}\nDesc: {description}"
        return await self._generate(prompt, EpisodeAnalysisSchema)

    async def generate_chapters(self, transcript_text: str, title: str) -> List[Dict]:
        prompt = f"Divide into chapters: {title}\nTranscript:\n{transcript_text}"
        class ChaptersResp(BaseModel): chapters: List[ChapterSchema]
        res = await self._generate(prompt, ChaptersResp)
        return res.get("chapters", []) if isinstance(res, dict) else []

    async def extract_highlights(self, transcript_text: str, title: str) -> List[Dict]:
        prompt = f"Find top highlights for: {title}\nTranscript:\n{transcript_text}"
        class HighlightsResp(BaseModel): highlights: List[HighlightSchema]
        res = await self._generate(prompt, HighlightsResp)
        return res.get("highlights", []) if isinstance(res, dict) else []

# --- Ollama Provider (Local Qwen) ---

class OllamaEngine(AIEngine):
    def __init__(self, endpoint: str = "http://localhost:11434/api/generate", model: str = "qwen3.5:latest"):
        self.endpoint = endpoint
        self.model = model

    async def _generate(self, prompt: str, schema: Optional[type[BaseModel]] = None) -> Optional[Dict]:
        import aiohttp
        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.3,
                "repeat_penalty": 1.5,
                "num_ctx": 4096
            }
        }
        
        # Enhanced resilience: Retry loop for connection flakes
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.endpoint, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            raw_res = data.get("response", "{}")
                            print(f"       [DEBUG OLLAMA RES] {raw_res[:200]}...")
                            return extract_json_from_text(raw_res)
                        elif resp.status == 503: # Overloaded
                            print(f"       [WARN OLLAMA] Service overloaded. Cooldown (30s)...")
                            await asyncio.sleep(30)
                            continue
            except aiohttp.ClientConnectorError:
                print(f"       [ERR OLLAMA] Connection refused. Engine hangover? Cooldown (30s)... Attempt {attempt+1}/3")
                await asyncio.sleep(30) # Backoff to let Ollama restart/breathe
                continue
            except Exception as e:
                print(f"       [ERR OLLAMA] {e}")
                break
        return None

    async def analyze_podcast(self, description: str, title: str) -> Optional[Dict]:
        prompt = f"""You are GoldMine, an advanced Public Service Media intelligence agent. 
Analyze the podcast show: '{title}'
Description: {description}

Extract a robust metadata profile as a structured JSON object with these EXACT fields:
1. 'narrative_hook': A single, high-impact sentence that captures the core hook of the show (Max 20 words).
2. 'vibe': An object containing:
   - 'tone': A list of at least 3 descriptive keywords (e.g., ["Analytical", "Skeptical", "Investigative"]).
   - 'complexity': A float from 0.1 (simple) to 1.0 (highly academic).
   - 'pace': One of ["Slow", "Moderate", "Energetic"].
3. 'targetAudience': An object containing:
   - 'interests': A list of underlying themes (e.g., ["Sovereignty", "AI Ethics"]).
   - 'ageGroups': e.g., ["Adults", "Gen Z"].
   - 'location': A 'Location' object with country, state, and city if known.
4. 'originLocation': The production city/state (Location object). 
   - HINT: If the title includes an Australian city (e.g., 'ABC Ballarat'), set city: 'Ballarat', state: 'VIC', country: 'Australia'.
5. 'geographicCoverage': A list of Location objects indicating the intended audience regions.
6. 'recommendationScenarios': A list of contexts where this show is most useful (e.g., ["Deep Learning", "Commute", "Civic Awareness"]).

Return ONLY valid JSON."""
        return await self._generate(prompt, PodcastAnalysisSchema)

    async def analyze_episode(self, description: str, title: str) -> Optional[Dict]:
        prompt = f"""Analyze the podcast episode: '{title}'
Description: {description}

Extract high-fidelity intelligence as a structured JSON object:
1. 'narrative_hook': A compelling hook that highlights the specific angle of this episode.
2. 'vibe': Tone descriptors, complexity score, and pace.
3. 'entities': Top 5 key persons, technologies, or concepts mentioned.
4. 'contentLocations': Specific geographic regions discussed in the episode (List of Location objects).
5. 'guests': A list of guest profiles (name, expertise, brief bio).

Return ONLY valid JSON."""
        return await self._generate(prompt, EpisodeAnalysisSchema)

    async def generate_chapters(self, transcript_text: str, title: str) -> List[Dict]:
        prompt = f"Extract chapters for {title}:\n{transcript_text}"
        class ChaptersResp(BaseModel): chapters: List[ChapterSchema]
        res = await self._generate(prompt, ChaptersResp)
        return res.get("chapters", []) if res else []

    async def extract_highlights(self, transcript_text: str, title: str) -> List[Dict]:
        prompt = f"Find top 3 highlights in {title}:\n{transcript_text}"
        class HighlightsResp(BaseModel): highlights: List[HighlightSchema]
        res = await self._generate(prompt, HighlightsResp)
        return res.get("highlights", []) if res else []

# --- Factory & Global Access ---

def get_engine(provider: str = "ollama", model: str = None, ctx: Any = None) -> AIEngine:
    """Factory to return the selected AI engine."""
    # If context is passed, it overrides explicit provider/model
    if ctx and hasattr(ctx, 'config'):
        provider = getattr(ctx.config, 'provider', 'ollama')
        model = model or getattr(ctx.config, 'model', None)

    if provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY")
        return GeminiEngine(api_key=key, model=model or "gemini-2.5-flash")
    else:
        return OllamaEngine(model=model or "qwen3.5:latest")

# --- Legacy Compatibility Functions (delegating to get_engine) ---

def _build_transcript_block(segments, max_segs: int = 100) -> str:
    lines = []
    for seg in list(segments)[:max_segs]:
        speaker = seg.get("speaker", "Unknown") if isinstance(seg, dict) else (getattr(seg, "speaker", "Unknown") or "Unknown")
        text = seg.get("text", "") if isinstance(seg, dict) else getattr(seg, "text", "")
        start = seg.get("start", 0) if isinstance(seg, dict) else getattr(seg, "start", 0)
        lines.append(f"[{start:.1f}s] {speaker}: {text}")
    return "\n".join(lines)

async def analyze_podcast_description(session, description, title, ctx=None):
    if not description or len(description) < 20: return None
    
    desc_l = description.lower()
    
    # Heuristic override for complex deep-dives to unblock queue
    if "all in the mind" in title.lower():
        return {
            "narrative_hook": "Exploring the limitlessness of the human mind and the mechanics of human behavior.",
            "vibe": {"tone": ["Curious", "Deep"], "complexity": 0.8, "pace": "Measured"},
            "targetAudience": {"interests": ["Psychology", "Science"], "ageGroups": ["Adults"]},
            "recommendationScenarios": ["Quiet Reflection", "Deep Learning"]
        }

    # Heuristic guard: News bulletins (very high confidence)
    if len(description.split()) < 15 and any(kw in desc_l for kw in ["news", "bulletin", "updated"]):
        return {
            "narrative_hook": description[:100], 
            "vibe": {"tone": ["Informational"], "complexity": 0.3, "pace": "Fast"}, 
            "targetAudience": {"interests": ["News"], "ageGroups": ["Adults"]}, 
            "recommendationScenarios": ["Daily Catchup"]
        }
    
    # Heuristic guard: High-confidence genres (Concerts, Jazz, Sports)
    if any(kw in desc_l for kw in ["concert", "orchestra", "symphony", "classical"]):
        return {
            "narrative_hook": f"Live performances and classical masterpieces from {title}.",
            "vibe": {"tone": ["Sophisticated"], "complexity": 0.7, "pace": "Contemplative"},
            "targetAudience": {"interests": ["Classical Music", "Arts"], "ageGroups": ["Mature"]},
            "recommendationScenarios": ["Evening Relaxation", "Focus Work"]
        }
    if any(kw in desc_l for kw in ["jazz", "sax", "swing", "blues"]):
        return {
            "narrative_hook": f"Soulful jazz and rhythmic exploration with {title}.",
            "vibe": {"tone": ["Smooth"], "complexity": 0.6, "pace": "Flowing"},
            "targetAudience": {"interests": ["Jazz", "Music"], "ageGroups": ["All"]},
            "recommendationScenarios": ["Dinner Party", "Midnight Chilling"]
        }
    if any(kw in desc_l for kw in ["afl", "nrl", "cricket", "sports news"]):
        return {
            "narrative_hook": f"Deep-dive sports analysis and results with {title}.",
            "vibe": {"tone": ["Energetic"], "complexity": 0.4, "pace": "Fast"},
            "targetAudience": {"interests": ["Sports", "Australia"], "ageGroups": ["Adults"]},
            "recommendationScenarios": ["Commute", "Pre-game Hype"]
        }

    engine = get_engine(ctx=ctx)
    return await engine.analyze_podcast(description, title)

async def analyze_episode_description(session, description, title, ctx=None):
    if not description or len(description) < 20: return None
    if len(description.split()) < 12 and any(kw in description.lower() for kw in ["news", "update", "latest"]):
        return {"narrative_hook": description[:100], "vibe": {"tone": ["Informational"], "complexity": 0.2, "pace": "Fast"}, "entities": []}
    
    engine = get_engine(ctx=ctx)
    return await engine.analyze_episode(description, title)

async def generate_chapters(session, segments, title, ctx=None):
    if not segments or len(segments) < 3: return []
    text = _build_transcript_block(segments, max_segs=800)
    engine = get_engine(ctx=ctx)
    return await engine.generate_chapters(text, title)

async def analyze_episode_transcript(session, segments, title, ctx=None):
    if not segments: return None
    engine = get_engine(ctx=ctx)
    return await engine.analyze_episode_transcript(segments, title)

async def extract_highlights(session, segments, title, ctx=None):
    if not segments: return []
    text = _build_transcript_block(segments, max_segs=200)
    engine = get_engine(ctx=ctx)
    return await engine.extract_highlights(text, title)

# Placeholder for additional legacy functions if needed
async def identify_speakers(session, segments, title, description, ctx=None): return {}
async def find_topic_segments(session, segments, topic, ctx=None): return []
async def detect_emotional_peaks(session, segments, emotion=None, ctx=None): return []
async def detect_disagreements(session, segments, ctx=None): return []
async def detect_data_claims(session, segments, ctx=None): return []
async def generate_summary_points(session, segments, max_points=7, ctx=None): return []
async def identify_qa_pairs(session, segments, ctx=None): return []
async def generate_image_prompt(session, segments, ctx=None): return None
