from typing import Tuple

def get_authority_for_podcast(title: str) -> Tuple[str, float]:
    """
    Returns (Organization, AuthorityScore) based on podcast title.
    """
    lower_title = title.lower()
    
    # Tier 1: High Authority Journalism / Newsrooms (1.0)
    high_authority_patterns = [
        "abc news", "7.30", "four corners", "rn breakfast", 
        "conversations", "the signal", "background briefing",
        "if you're listening", "abc business daily", "am", "pm", "the world today"
    ]
    for pattern in high_authority_patterns:
        if pattern in lower_title:
            return "ABC Newsroom", 1.0
            
    # Tier 2: Specialized Expertise / Niche Journalism (0.7)
    medium_authority_patterns = [
        "abc sport", "all in the mind", "life matters", "the money",
        "future tense", "science friction", "the health report",
        "law report", "religion and ethics report", "big ideas"
    ]
    for pattern in medium_authority_patterns:
        if pattern in lower_title:
            return "ABC Specialized", 0.7
            
    # Tier 3: General ABC Content (0.5)
    if "abc" in lower_title:
        return "ABC General", 0.5
        
    # Tier 4: Community / Independent / External (0.4)
    return "Community / External", 0.4
