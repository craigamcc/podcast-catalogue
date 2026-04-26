import aiohttp
import re
from typing import Optional, Tuple, List

ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"

# Regex to extract ID from URL like https://podcasts.apple.com/au/podcast/conversations/id80934561
ID_REGEX = re.compile(r"id(\d+)")

async def search_itunes_podcast(session: aiohttp.ClientSession, title: str) -> Tuple[Optional[int], Optional[float], Optional[int]]:
    """
    Searches iTunes for a podcast by title.
    Returns (itunes_id, average_rating, rating_count).
    """
    # Clean title: remove " - ABC listen" and other common suffixes for better search results
    clean_title = title.replace(" - ABC listen", "").replace(" - ABC Radio", "").strip()
    
    # print(f"    Searching iTunes for: '{clean_title}'")
    try:
        async with session.get(ITUNES_SEARCH_URL, params={"term": clean_title, "media": "podcast", "country": "AU", "limit": 1}) as response:
             if response.status != 200:
                 return None, None, None
             
             data = await response.json(content_type=None)
             if data["resultCount"] > 0:
                 result = data["results"][0]
                 # print(f"    Found: {result.get('collectionName')} ({result.get('collectionId')})")
                 # print(f"    Keys: {list(result.keys())}")
                 return (
                     result.get("collectionId"),
                     result.get("averageUserRating"),
                     result.get("userRatingCount")
                 )
             else:
                 print(f"    No results found in iTunes for '{clean_title}'")
    except Exception as e:
        print(f"  Warning: iTunes search failed for {title}: {e}")
    
async def _fetch_reviews_rss(session: aiohttp.ClientSession, itunes_id: int) -> Tuple[Optional[float], int, List[dict]]:
    """
    Fetches latest reviews from RSS feed to calculate average rating and count.
    Also returns a list of top descriptive reviews.
    Fallback when the main API doesn't provide them.
    """
    rss_url = f"https://itunes.apple.com/au/rss/customerreviews/id={itunes_id}/json"
    try:
        async with session.get(rss_url) as response:
            if response.status != 200:
                print(f"  Warning: RSS returned {response.status}")
                return None, 0, []
            
            data = await response.json(content_type=None)
            entries = data.get("feed", {}).get("entry", [])
            
            if not entries:
                return None, 0, []
            
            # If there's only one review and it's a dict
            if isinstance(entries, dict):
                entries = [entries]
                
            ratings = []
            reviews = []
            for entry in entries:
                # Skip the first entry if it contains metadata about the feed/app
                if "im:rating" in entry:
                    try:
                        r = float(entry["im:rating"]["label"])
                        ratings.append(r)
                        
                        # Extract review data
                        content = entry.get("content", {}).get("label", "")
                        author = entry.get("author", {}).get("name", {}).get("label", "Anonymous")
                        
                        # Filter for quality: length > 10 chars
                        if len(content) > 10:
                            reviews.append({
                                "author": author,
                                "rating": r,
                                "content": content,
                                "date": None # RSS JSON format for date is tricky, skipping for now or parsing if easy
                            })
                            
                    except (ValueError, KeyError) as e:
                        # print(f"Error parsing entry: {e}")
                        continue
            
            if not ratings:
                return None, 0, []
            
            avg = sum(ratings) / len(ratings)
            
            # Sort reviews by length (descending) to get the most descriptive ones, take top 5
            reviews.sort(key=lambda x: len(x["content"]), reverse=True)
            top_reviews = reviews[:5]
            
            return round(avg, 1), len(ratings), top_reviews

    except Exception as e:
        print(f"  Warning: Failed to fetch RSS reviews: {e}")
        return None, 0, []


async def enrich_podcast_data(session: aiohttp.ClientSession, apple_url: Optional[str] = None, itunes_id: Optional[int] = None) -> Tuple[Optional[int], Optional[float], Optional[int], Optional[str], Optional[list], List[dict]]:
    """
    Enriches podcast data using iTunes API. 
    Returns (itunes_id, average_rating, rating_count, primary_genre, genres, reviews).
    """
    if not itunes_id and apple_url:
        match = ID_REGEX.search(apple_url)
        if match:
             itunes_id = int(match.group(1))

    if not itunes_id:
        return None, None, None, None, None, []

    try:
        async with session.get(ITUNES_LOOKUP_URL, params={"id": itunes_id, "country": "AU"}) as response:
            if response.status != 200:
                print(f"  Warning: iTunes API returned {response.status} for {itunes_id}")
                return itunes_id, None, None, None, None, []
            
            data = await response.json(content_type=None)
            if data["resultCount"] > 0:
                result = data["results"][0]
                
                rating = result.get("averageUserRating")
                count = result.get("userRatingCount")
                reviews_list = []
                
                # Fetch RSS reviews if rating missing OR to just get the review text (we want text regardless!)
                # NOTE: We always fetch RSS now to get the review TEXT, even if we have the rating stats.
                rss_rating, rss_count, top_reviews = await _fetch_reviews_rss(session, itunes_id)
                reviews_list = top_reviews
                
                # Fallback stats if missing in main API
                if not rating and rss_rating:
                     rating = rss_rating
                     count = rss_count

                return (
                    itunes_id,
                    rating,
                    count,
                    result.get("primaryGenreName"),
                    result.get("genres"),
                    reviews_list
                )
            
    except Exception as e:
        print(f"  Warning: Failed to enrich from iTunes: {e}")
        
    return itunes_id, None, None, None, None, []
