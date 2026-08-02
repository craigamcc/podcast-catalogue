import os
import tempfile
import asyncio
import aiohttp

import certifi
import ssl

from typing import Tuple, List, Dict

# --- Lazy-loaded pyannote pipeline ---
_diarization_pipeline = None
_diarization_deps_available = False

def _monkey_patch_huggingface_hub():
    """
    Patch huggingface_hub to handle the 2026 deprecation of 'use_auth_token' in favor of 'token'.
    This allows legacy versions of pyannote.audio to work with newer huggingface_hub versions.
    """
    try:
        import huggingface_hub.file_download
        import huggingface_hub.utils._validators
        import functools
        
        orig_hf_hub_download = huggingface_hub.file_download.hf_hub_download
        
        @functools.wraps(orig_hf_hub_download)
        def patched_hf_hub_download(*args, **kwargs):
            if 'use_auth_token' in kwargs:
                kwargs['token'] = kwargs.pop('use_auth_token')
            return orig_hf_hub_download(*args, **kwargs)
            
        huggingface_hub.file_download.hf_hub_download = patched_hf_hub_download
        
        # Also patch build_hf_headers if it exists
        if hasattr(huggingface_hub.utils, "build_hf_headers"):
            orig_build_headers = huggingface_hub.utils.build_hf_headers
            @functools.wraps(orig_build_headers)
            def patched_build_headers(*args, **kwargs):
                if 'use_auth_token' in kwargs:
                    kwargs['token'] = kwargs.pop('use_auth_token')
                return orig_build_headers(*args, **kwargs)
            huggingface_hub.utils.build_hf_headers = patched_build_headers
            
    except Exception:
        pass # If we can't patch, just proceed and let the standard error handle it

def _get_diarization_pipeline():
    """Lazy-load the pyannote speaker diarization pipeline on first use."""
    global _diarization_pipeline, _diarization_deps_available
    if _diarization_pipeline is not None:
        return _diarization_pipeline

    _monkey_patch_huggingface_hub()

    try:
        import torch
        from pyannote.audio import Pipeline

        print("⏳ Loading pyannote.audio speaker diarization pipeline...")
        device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        
        # Requires HF_TOKEN in environment or active huggingface-cli login
        # using the 3.1 model as it is the most robust, widely mapped open-source version
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            print("⚠ Warning: HF_TOKEN environment variable not set. Pyannote may fail if not authenticated via CLI.")
            
        try:
            # Modern versions of pyannote.audio / huggingface_hub use 'token'
            _diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=hf_token
            )
        except TypeError:
            # Fallback for older versions if necessary
            _diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token or True
            )
        
        if _diarization_pipeline:
            _diarization_pipeline.to(device)
            _diarization_deps_available = True
            print("✅ pyannote.audio pipeline loaded successfully.")
            return _diarization_pipeline
        else:
            print("⚠ Failed to load pyannote pipeline (check token / model access agreements).")
            _diarization_deps_available = False
            return None
            
    except ImportError:
        print("⚠ pyannote.audio missing. Diarization disabled.")
        _diarization_deps_available = False
        return None
    except Exception as e:
        print(f"⚠ Pyannote pipeline initialization error: {e}")
        _diarization_deps_available = False
        return None


async def download_file(url: str, dest_path: str):
    """
    Robust downloader: use direct HTTP GET for explicit audio file URLs (.mp3/.m4a/.wav),
    otherwise fall back to yt-dlp to extract the best audio stream and write it to dest_path.
    """
    # simple heuristic: if url looks like a direct audio file, stream it
    audio_exts = ('.mp3', '.m4a', '.wav', '.aac', '.flac', '.ogg')
    if any(url.lower().endswith(ext) for ext in audio_exts):
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url) as response:
                with open(dest_path, 'wb') as f:
                    while True:
                        chunk = await response.content.read(1024*1024) # 1MB chunks
                        if not chunk:
                            break
                        f.write(chunk)
        return

    # Otherwise use yt-dlp to extract best audio -> write to dest_path
    # Use ffmpeg remux via yt-dlp and prefer ffmpeg for HLS
    print(f"Using yt-dlp to extract audio from page: {url}")
    import sys as _sys
    # prefer calling 'python -m yt_dlp' using the current interpreter to ensure we invoke the venv-installed package
    ytdlp_cmd = [
        _sys.executable,
        '-m', 'yt_dlp',
        '--no-warnings',
        '--no-mtime',
        '--quiet',
        '--format', 'bestaudio/best',
        '--downloader', 'ffmpeg',
        '--downloader-args', 'ffmpeg:-probesize 5000000 -analyzeduration 5000000',
        '--hls-prefer-ffmpeg',
        '--output', dest_path,
        url
    ]
    proc = await asyncio.create_subprocess_exec(*ytdlp_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed (rc={proc.returncode}): {stderr.decode(errors='ignore')}")
    return

def transcribe_audio(audio_path: str, model: str = "large-v3-turbo") -> dict:
    """
    Transcribes audio using MLX Whisper.
    Returns the FULL Whisper result dict (contains 'text' and 'segments').
    
    Models (MLX-optimized):
      - 'base'            → 39M params, fast, ~13% WER (legacy default)
      - 'large-v3-turbo'  → 809M params (4 decoder layers), ~5% WER
    """
    import mlx_whisper

    print(f"Transcribing {audio_path} using model='{model}'...")

    # Handle repo naming convention differences in mlx-community
    repo_id = f"mlx-community/whisper-{model}"
    if model != "large-v3-turbo":
        repo_id += "-mlx"
        
    result = mlx_whisper.transcribe(audio_path, path_or_hf_repo=repo_id)
    return result

def cluster_speakers(audio_path: str, segments: List[Dict]) -> List[Dict]:
    """
    Performs true neural speaker diarization using pyannote.audio.
    Maps continuous speaker intervals to the discrete Whisper text segments via maximum overlap (IoU/duration).
    """
    pipeline = _get_diarization_pipeline()
    if pipeline is None or not segments:
        return segments

    print(f"Diarizing audio using pyannote (this runs inference over the full audio)...")
    try:
        # returns pyannote.core.Annotation
        diarization = pipeline(audio_path)
        
        # Map pyannote intervals to the Whisper segments
        for seg in segments:
            start = seg["start"]
            end = seg["end"]
            
            best_speaker = None
            max_overlap = 0.0
            
            # itertracks yields (segment_range, track, label)
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                overlap_start = max(start, turn.start)
                overlap_end = min(end, turn.end)
                overlap_duration = max(0.0, overlap_end - overlap_start)
                
                if overlap_duration > max_overlap:
                    max_overlap = overlap_duration
                    best_speaker = speaker
            
            if best_speaker:
                seg["speaker"] = best_speaker

        print(f"✅ Diarization complete. Speakers assigned to segments.")
        return segments
    except Exception as e:
        print(f"⚠ Pyannote diarization failed: {e}")
        return segments

async def process_episode_transcription(audio_url: str, duration_limit: int = 0) -> Tuple[str, List[Dict]]:
    """
    Downloads and transcribes an episode.
    If duration_limit > 0, only processes the first N seconds.
    Returns a tuple of (plain_text_transcript, segments_list).
    Each segment is: {"text": "...", "start": 0.0, "end": 2.5, "speaker": None}
    """
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
        
    trimmed_path = tmp_path.replace(".mp3", "_trimmed.mp3")
    wav_path = tmp_path.replace(".mp3", ".wav")
    
    # Track all temp files for cleanup
    temp_files = [tmp_path, trimmed_path, wav_path]
    
    try:
        print(f"Downloading {audio_url}...")
        await download_file(audio_url, tmp_path)

        target_path = tmp_path
        
        # Trim audio if limit requested (for testing/verification)
        if duration_limit > 0:
            print(f"Trimming audio to {duration_limit} seconds...")
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-probesize", "5000000", "-analyzeduration", "5000000", "-i", tmp_path, "-t", str(duration_limit), "-f", "wav", "-acodec", "pcm_s16le", "-ar", "16000", trimmed_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.communicate()
            if proc.returncode == 0:
                target_path = trimmed_path
        else:
            # Convert to WAV for torchaudio reliability across environments
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-probesize", "5000000", "-analyzeduration", "5000000", "-i", tmp_path, "-acodec", "pcm_s16le", "-ar", "16000", wav_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.communicate()
            if proc.returncode == 0:
                target_path = wav_path

        # Run transcription in a separate thread (it's CPU intensive/blocking)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, transcribe_audio, target_path)
        
        plain_text = result.get("text", "")
        
        # Extract timestamped segments from Whisper output
        raw_segments = result.get("segments", [])
        segments = [
            {
                "text": seg.get("text", "").strip(),
                "start": round(seg.get("start", 0.0), 2),
                "end": round(seg.get("end", 0.0), 2),
                "speaker": None
            }
            for seg in raw_segments
            if seg.get("text", "").strip()
        ]
        
        # Run pyannote diarization (lazy-loads pipeline on first call)
        pipeline = _get_diarization_pipeline()
        if pipeline is not None:
            segments = await loop.run_in_executor(None, cluster_speakers, target_path, segments)
        
        return plain_text, segments

    except Exception as e:
        print(f"Error transcribing: {e}")
        return "", []
    finally:
        for path in temp_files:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
