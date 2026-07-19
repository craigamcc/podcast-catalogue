import os
import json
import asyncio
import re
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from .models import TranscriptSegment, ClaimStatus, AIProvenance, SourceAnchor, ContentRisk, HighlightCategory

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

def clean_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively removes 'additionalProperties' which is not supported by Gemini."""
    if not isinstance(schema, dict):
        return schema
    
    # Remove additionalProperties if it exists
    schema.pop("additionalProperties", None)
    
    # Recurse through properties, items, and definitions
    if "properties" in schema:
        for k, v in schema["properties"].items():
            schema["properties"][k] = clean_schema(v)
    if "items" in schema:
        schema["items"] = clean_schema(schema["items"])
    if "$defs" in schema:
        for k, v in schema["$defs"].items():
            schema["$defs"][k] = clean_schema(v)
    if "definitions" in schema:
        for k, v in schema["definitions"].items():
            schema["definitions"][k] = clean_schema(v)
            
    return schema

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

class PodcastAnalysisSchema(BaseModel):
    narrative_hook: str
    vibe: VibeSchema
    targetAudience: TargetAudienceSchema
    recommendationScenarios: List[str]
    originLocation: Optional[LocationSchema] = None
    geographicCoverage: List[LocationSchema] = []

class ContentRiskSchema(BaseModel):
    level: str = "low"
    categories: List[str] = []
    requiresHumanReview: bool = False

class EpisodeAnalysisSchema(BaseModel):
    narrative_hook: str
    vibe: VibeSchema
    engagement: EngagementSchema
    entities: List[str]
    contentLocations: List[LocationSchema] = []
    guests: List[GuestSchema] = []
    # Trust Layer
    genre: Optional[str] = None
    contentRisk: Optional[ContentRiskSchema] = None
    expires: Optional[str] = None
    contentReferenceTime: Optional[str] = None

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
    category: str  # QUOTE, STAT, PEAK, INSIGHT, ADVICE, ANECDOTE, GENERAL
    startTime: float
    endTime: float
    # Trust Layer
    claimStatus: Optional[str] = "unverified" # confirmed, alleged, forecast, attributed, unverified
    claimInterpreter: Optional[str] = None

class TimelineItemSchema(BaseModel):
    title: str
    type: str  # CHAPTER, EXPERT, SHOW_LINK, IMAGE
    startTime: float
    endTime: float
    link: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

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
    async def generate_deep_context_timeline(self, transcript_text: str, title: str) -> List[Dict[str, Any]]: pass
    async def generate_regional_master_pulse(self, region_id: str, episodes_data: List[Dict[str, Any]], previous_pulse: Optional[Dict] = None) -> Optional[Dict]: pass

    async def analyze_episode_transcript(self, segments: List[TranscriptSegment], title: str, transcript: Optional[str] = None) -> Optional[Dict]:
        """Deep analysis of full transcript for engagement deliverables."""
        # Bundle segments into text chunks
        if segments:
            transcript_text = "\n".join([f"[{s.speaker or '??'}] {s.text}" for s in segments])
        else:
            transcript_text = transcript or ""
        
        if not transcript_text:
            return None
        
        prompt = f"""You are GoldMine, a High-Intensity Content Scout and Editorial Trust Proxy. 
Analyze the full transcript for the episode: '{title}'

Transcript Excerpt:
{transcript_text[:12000]}

Your task is to extract the 'Engagement Layer' and 'Editorial Trust Layer'—ensuring provenance and accuracy.
Return a structured JSON object with these EXACT fields:

1. 'highlights': A list of objects containing:
   - 'title': A punchy title for the moment.
   - 'category': One of ["QUOTE", "STAT", "PEAK", "INSIGHT", "ADVICE", "ANECDOTE"].
        - 'QUOTE': Verbatim statement.
        - 'STAT': Data/numbers.
        - 'PEAK': Narrative/emotional climax.
        - 'INSIGHT': Conceptual lesson.
        - 'ADVICE': Practical guidance/actionable recommendation.
        - 'ANECDOTE': Personal story or illustrative incident.
   - 'claimStatus': Epistemic classification: 
        - 'confirmed' (fact from authority)
        - 'alleged' (attributed claim)
        - 'forecast' (future prediction)
        - 'attributed' (sourced opinion)
        - 'unverified' (default)

2. 'timeline': A list of 'Deep Context' markers:
   - 'title': Descriptive title (e.g., 'Expert Mention: Mark Hammond').
   - 'type': One of ["EXPERT", "SHOW_LINK", "IMAGE", "FACT_CHECK"].
   - 'startTime' / 'endTime': Precise timestamps.
   - 'link': Optional URL for deep linking.
   - 'metadata': dict with 'bio', 'context', or 'source'.

3. 'engagement': An object containing:
   - 'takeaway': The #1 counter-intuitive or essential lesson (Max 25 words).
   - 'keyStatistics': notable data points.
   - 'bestQuotes': verbatim, speaker-attributed excerpts.
   - 'whyListen': compelling 'Industrial-Noir' style value proposition.
   - 'socialPost': provocative social media draft.
   - 'audiogramCaptions': list of {{"text": str, "start": float, "end": float}} for the TOP highlight.

4. 'guests': list of formal interviewees (name, expertise, bio).

5. 'trust': An object containing:
   - 'genre': schema.org genre (e.g., 'news_bulletin', 'interview', 'panel_discussion', 'investigative').
   - 'contentRisk': {{"level": "low/medium/high", "categories": ["court", "crime", "health", "named_individual", "emergency"], "requiresHumanReview": bool}}.
   - 'expires': ISO datetime when this information becomes stale (e.g., road closures expire in hours, policy in weeks).
   - 'contentReferenceTime': ISO datetime for the specific events discussed.

Return ONLY valid JSON.
"""
        
        class DeepEngagementResp(BaseModel):
            highlights: List[HighlightSchema]
            timeline: List[TimelineItemSchema] = Field(default_factory=list)
            engagement: EngagementSchema
            guests: List[GuestSchema] = Field(default_factory=list)
            trust: Optional[Dict[str, Any]] = None # {genre, contentRisk, expires, contentReferenceTime}
            
        res = await self._generate(prompt, DeepEngagementResp)
        
        # --- Post-Processor: Trust Wiring & Source Anchoring ---
        if isinstance(res, dict):
            # 1. AI Provenance
            from datetime import datetime, timezone
            res["ai_provenance"] = {
                "modelName": self.model,
                "generatedAt": datetime.now(timezone.utc).isoformat()
            }
            
            # 2. Verbatim Source Anchors
            if segments and res.get("highlights"):
                for hl in res["highlights"]:
                    start, end = hl.get("startTime", 0), hl.get("endTime", 0)
                    # Find all segments that overlap with this highlight
                    matching_text = []
                    for s in segments:
                        s_start = getattr(s, "start", 0) if not isinstance(s, dict) else s.get("start", 0)
                        s_end = getattr(s, "end", 0) if not isinstance(s, dict) else s.get("end", 0)
                        s_text = getattr(s, "text", "") if not isinstance(s, dict) else s.get("text", "")
                        
                        if (s_start >= start and s_start < end) or (s_end > start and s_end <= end) or (s_start <= start and s_end >= end):
                            matching_text.append(s_text)
                    
                    if matching_text:
                        hl["sourceAnchor"] = {
                            "transcriptText": " ".join(matching_text).strip(),
                            "timestampStart": start,
                            "timestampEnd": end
                        }
                    
                    # Set claimInterpreter
                    hl["claimInterpreter"] = self.model
            
        return res

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
            # Enforce strict schema by stripping additionalProperties (Gemini constraint)
            raw_schema = schema.model_json_schema()
            cleaned_schema = clean_schema(raw_schema)
            
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=cleaned_schema,
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

    async def generate_deep_context_timeline(self, transcript_text: str, title: str) -> List[Dict]:
        prompt = f"Extract rich Deep Context markers (experts, shows, images) for {title}:\n{transcript_text}"
        class TimelineResp(BaseModel): timeline: List[TimelineItemSchema]
        res = await self._generate(prompt, TimelineResp)
        return res.get("timeline", []) if isinstance(res, dict) else []

    async def generate_regional_master_pulse(self, region_id: str, episodes_data: List[Dict[str, Any]], previous_pulse: Optional[Dict] = None) -> Optional[Dict]:
        context_blocks = []
        for ep in episodes_data:
            experts_str = ", ".join(ep.get("experts", []))
            block = (
                f"SHOW: {ep.get('podcast_title')}\n"
                f"EPISODE: {ep.get('title')}\n"
                f"AUTHORITY: {ep.get('source_organization')} (Score: {ep.get('authority_score')})\n"
                f"HOOK: {ep.get('narrative_hook')}\n"
                f"EXPERTS MENTIONED: {experts_str}\n"
                f"TAKEAWAY: {ep.get('engagement', {}).get('takeaway')}\n"
            )
            context_blocks.append(block)
        all_context = "\n---\n".join(context_blocks)
        
        prev_context = ""
        if previous_pulse:
            prev_shifts = [f"- {s.get('title')}: {s.get('shift')}" for s in previous_pulse.get("narrativeShifts", [])]
            prev_context = "\nPREVIOUS PULSE CONTEXT (For Narrative Continuity):\n" + "\n".join(prev_shifts)

        prompt = f"""You are GoldMine Regional Intelligence. 
Synthesize a 'Master Regional Pulse' for: '{region_id}'

REGIONAL SIGNALS:
{all_context}
{prev_context}

Your task:
1. **Authority Weighting**: Each signal has an 'AUTHORITY Score'. Give significantly more weight to 'ABC Newsroom' (1.0) and 'ABC Specialized' (0.7) reports.
2. **Master Summary**: A 50-word high-intensity summary of the regional landscape.
3. **Narrative Shifts**: Identify 3-5 key updates.
4. **Canonical Events**: Cluster the signals into 1-3 'Canonical Events'. An event is a specific, actionable news story or topic that spans multiple episodes or persists over time. 
   - 'eventId': A URL-friendly slug (e.g. 'seqld-flood-recovery-2026').
   - 'title': Human-readable event name.
   - 'description': What happened.
   - 'tags': Keywords.
   - 'storylineUpdates': A list of objects representing the coverage. Each object must have 'updateId' (a unique slug), 'episodeTitle' (the episode title), 'date' (ISO date of the episode), and 'summary' (how this episode advances the event).
5. **Featured Episodes**: IDs of the most relevant episodes.

Return ONLY valid JSON.
"""
        class RegionalPulseResp(BaseModel):
            masterSummary: str
            narrativeShifts: List[Dict[str, Any]]
            featuredEpisodes: List[str]
            canonicalEvents: List[Dict[str, Any]] = Field(default_factory=list)
            
        return await self._generate(prompt, RegionalPulseResp)

# --- Ollama Provider (Local Qwen) ---

class OllamaEngine(AIEngine):
    def __init__(self, endpoint: str = None, model: str = None):
        from .config import OLLAMA_GENERATE_URL, OLLAMA_MODEL
        self.endpoint = endpoint or OLLAMA_GENERATE_URL
        self.model = model or OLLAMA_MODEL

    async def generate_regional_master_pulse(self, region_id: str, episodes_data: List[Dict[str, Any]], previous_pulse: Optional[Dict] = None) -> Optional[Dict]:
        context_blocks = []
        for ep in episodes_data:
            experts_str = ", ".join(ep.get("experts", []))
            block = (
                f"SHOW: {ep.get('podcast_title')}\n"
                f"EPISODE: {ep.get('title')}\n"
                f"AUTHORITY: {ep.get('source_organization')} (Score: {ep.get('authority_score')})\n"
                f"HOOK: {ep.get('narrative_hook')}\n"
                f"EXPERTS MENTIONED: {experts_str}\n"
                f"TAKEAWAY: {ep.get('engagement', {}).get('takeaway')}\n"
            )
            context_blocks.append(block)
        all_context = "\n---\n".join(context_blocks)
        
        prev_context = ""
        if previous_pulse:
            prev_shifts = [f"- {s.get('title')}: {s.get('shift')}" for s in previous_pulse.get("narrativeShifts", [])]
            prev_context = "\nPREVIOUS PULSE CONTEXT (For Narrative Continuity):\n" + "\n".join(prev_shifts)

        prompt = f"""You are GoldMine Regional Intelligence. 
Synthesize a 'Master Regional Pulse' for: '{region_id}'

REGIONAL SIGNALS:
{all_context}
{prev_context}

Your task:
1. **Authority Weighting**: Each signal has an 'AUTHORITY Score'. Give significantly more weight to 'ABC Newsroom' (1.0) and 'ABC Specialized' (0.7) reports.
2. **Master Summary**: A 50-word high-intensity summary of the regional landscape.
3. **Narrative Shifts**: Identify 3-5 key updates.
... (Rest of format) ...
"""
        return await self._generate(prompt)


    async def _generate(self, prompt: str, schema: Optional[type[BaseModel]] = None) -> Optional[Dict]:
        import aiohttp
        payload = {
            "model": self.model,
            "prompt": prompt,
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
                            if not raw_res or raw_res == "{}":
                                print(f"       [DEBUG OLLAMA] Empty response for prompt: {prompt[:100]}...")
                            else:
                                print(f"       [DEBUG OLLAMA] Raw Res: {raw_res[:200]}...")
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

    async def generate_deep_context_timeline(self, transcript_text: str, title: str) -> List[Dict]:
        prompt = f"Identify expert mentions and show links with timestamps for {title}:\n{transcript_text}"
        class TimelineResp(BaseModel): timeline: List[TimelineItemSchema]
        res = await self._generate(prompt, TimelineResp)
        return res.get("timeline", []) if res else []

    async def generate_regional_master_pulse(self, region_id: str, episodes_data: List[Dict[str, Any]], previous_pulse: Optional[Dict] = None) -> Optional[Dict]:
        context_blocks = []
        for ep in episodes_data:
            block = f"SHOW: {ep.get('podcast_title')}\nEPISODE: {ep.get('title')}\nHOOK: {ep.get('narrative_hook')}\nTAKEAWAY: {ep.get('engagement', {}).get('takeaway')}\n"
            context_blocks.append(block)
        all_context = "\n---\n".join(context_blocks)
        
        prompt = f"""You are GoldMine Regional Intelligence. 
Analyze the following regional news signals for the region: '{region_id}'

REGIONAL SIGNALS:
{all_context}

Your task is to synthesize a single 'Master Regional Pulse' for all listeners in this region. 
1. **Deduplicate**: Identify overlapping story arcs and merge them.
2. **Synthesize Narrative Shifts**: Identify 3-5 key narrative shifts or updates for the region.
3. **Master Summary**: Create a high-intensity 50-word master summary of the regional landscape.

Return a structured JSON object with 'masterSummary', 'narrativeShifts', and 'featuredEpisodes'.
Return ONLY valid JSON.
"""
        return await self._generate(prompt)

# --- Factory & Global Access ---

def get_engine(provider: str = "ollama", model: str = None, ctx: Any = None) -> AIEngine:
    """Factory to return the selected AI engine."""
    # If context is passed, it overrides explicit provider/model
    if ctx and hasattr(ctx, 'config'):
        provider = getattr(ctx.config, 'provider', 'ollama')
        model = model or getattr(ctx.config, 'model', None)

    from .config import GEMINI_MODEL, OLLAMA_MODEL
    if provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY")
        return GeminiEngine(api_key=key, model=model or GEMINI_MODEL)
    else:
        return OllamaEngine(model=model or OLLAMA_MODEL)

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

async def analyze_episode_transcript(session, segments, title, transcript=None, ctx=None):
    if not segments and not transcript: return None
    engine = get_engine(ctx=ctx)
    return await engine.analyze_episode_transcript(segments, title, transcript=transcript)

async def extract_highlights(session, segments, title, ctx=None):
    if not segments: return []
    text = _build_transcript_block(segments, max_segs=200)
    engine = get_engine(ctx=ctx)
    return await engine.extract_highlights(text, title)

async def generate_deep_context_timeline(session, segments, title, ctx=None):
    if not segments: return []
    text = _build_transcript_block(segments, max_segs=800)
    engine = get_engine(ctx=ctx)
    return await engine.generate_deep_context_timeline(text, title)

