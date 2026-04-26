import asyncio
import os
from podcast_catalogue.transcriber import transcribe_audio, cluster_speakers, download_file

async def verify():
    audio_url = "https://mediacore-live-production.akamaized.net/audio/02/gk/Z/tr.mp3"
    audio_path = "verify_audio.mp3"
    
    if not os.path.exists(audio_path):
        print("Downloading test audio...")
        await download_file(audio_url, audio_path)
    
    # 1. Transcribe (fast mode)
    print("Transcribing first 30s...")
    # Manually trim for speed
    trimmed_path = "verify_audio_trimmed.mp3"
    os.system(f"ffmpeg -y -i {audio_path} -t 30 -c copy {trimmed_path}")
    
    result = transcribe_audio(trimmed_path, model="base")
    segments = result.get("segments", [])
    
    # 2. Diarize
    print("Diarizing...")
    diarized_segments = cluster_speakers(trimmed_path, segments)
    
    for i, seg in enumerate(diarized_segments[:5]):
        speaker = seg.get("speaker", "UNKNOWN")
        text = seg.get("text", "")
        print(f"[{speaker}] {text.strip()}")

if __name__ == "__main__":
    asyncio.run(verify())
