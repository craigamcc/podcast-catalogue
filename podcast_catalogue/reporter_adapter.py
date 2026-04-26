import json
from datetime import datetime, timedelta
from typing import List
from .models import Podcast, Episode

def generate_editorial_report(podcasts: List[Podcast], lookback_hours: int = 48) -> str:
    """
    Synthesizes recent episode activity into a journalistic Meta-Summary.
    Mimics the 'NYT Manosphere Report' style.
    """
    threshold = datetime.now() - timedelta(hours=lookback_hours)
    recent_activity = []
    
    for p in podcasts:
        for ep in p.episodes:
            # Try to parse ISO published_at
            pub_date = None
            if ep.published_at:
                try:
                    pub_date = datetime.fromisoformat(ep.published_at.replace('Z', '+00:00'))
                except Exception:
                    pass
            
            # If recent OR if we have no date but it's part of the current crawl context
            if (pub_date and pub_date >= threshold) or not pub_date:
                recent_activity.append({
                    "show": p.title,
                    "episode": ep.title,
                    "date": ep.published_at or "Recent (Undated)",
                    "hook": ep.narrative_hook or "No hook generated.",
                    "vibe": ep.vibe.model_dump() if ep.vibe else {"tone": "Standard"},
                    "entities": ep.entities
                })

    if not recent_activity:
        return "No significant narrative activity detected in the system."

    # Construct synthesis prompt
    data_summary = json.dumps(recent_activity[:15], indent=2) # Limit to avoid context blowout
    
    report_template = f"""
# 📡 GoldMine Editorial Intelligence: Daily Meta-Summary
**Reporting Period**: {threshold.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}

## 📰 Executive Summary
[AI-generated high-level synthesis of recurring themes across the network]

## ⚡ Emerging Leads (Story Tips)
- **[Show Name]**: [Narrative Shift or Specific Tip]

## 📊 Network Vibe Shift
[Analysis of tonal distribution changes]

---
**Data Source**: GoldMine Semantic Audio Engine analysis of {len(recent_activity)} recent artifacts.
"""

    return report_template # In production, this would be fed into the LLM for the final text.
