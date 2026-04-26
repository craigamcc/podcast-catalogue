"""
Audio Clip Extraction.

Extracts audio clips from podcast episodes using ffmpeg.
Uses HTTP seek to stream only the needed bytes from the CDN.
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Optional


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = re.sub(r'[^a-z0-9]+', '_', text.lower().strip())
    return slug[:60].strip('_')


def _clip_filename(podcast_title: str, episode_title: str, start: float, end: float) -> str:
    """Generate a deterministic filename for a clip."""
    p_slug = _slugify(podcast_title)
    e_slug = _slugify(episode_title)
    return f"{p_slug}__{e_slug}__{int(start)}-{int(end)}.mp3"


def _format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mmm format for ffmpeg."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


async def extract_clip(
    audio_url: str,
    start_seconds: float,
    end_seconds: float,
    output_dir: str = "data/clips",
    podcast_title: str = "clip",
    episode_title: str = "episode",
) -> str:
    """
    Extract an audio clip from a podcast episode.

    Uses ffmpeg's HTTP input with -ss/-to to stream only the relevant portion
    from the CDN, avoiding full episode download.

    Args:
        audio_url: Direct URL to the full MP3 file.
        start_seconds: Start time in seconds.
        end_seconds: End time in seconds.
        output_dir: Directory to save clips.
        podcast_title: Used for filename generation.
        episode_title: Used for filename generation.

    Returns:
        Absolute path to the generated MP3 file.

    Raises:
        ValueError: If timestamps are invalid.
        RuntimeError: If ffmpeg fails.
    """
    if start_seconds < 0:
        raise ValueError("start_seconds must be >= 0")
    if end_seconds <= start_seconds:
        raise ValueError("end_seconds must be > start_seconds")
    if not audio_url:
        raise ValueError("audio_url is required")

    os.makedirs(output_dir, exist_ok=True)

    filename = _clip_filename(podcast_title, episode_title, start_seconds, end_seconds)
    output_path = os.path.join(output_dir, filename)

    # Cache: if clip already exists, return it immediately
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return os.path.abspath(output_path)

    ss = _format_timestamp(start_seconds)
    to = _format_timestamp(end_seconds)

    # Use ffmpeg with HTTP seek — streams only the needed bytes
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-ss", ss,
        "-to", to,
        "-i", audio_url,
        "-acodec", "libmp3lame",
        "-q:a", "2",  # High quality VBR
        output_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode(errors="replace")[-500:] if stderr else "Unknown error"
        # Clean up failed output
        if os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError(f"ffmpeg failed (exit {proc.returncode}): {error_msg}")

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("ffmpeg produced no output")

    abs_path = os.path.abspath(output_path)
    duration = end_seconds - start_seconds
    size_kb = os.path.getsize(output_path) / 1024
    print(f"  🎵 Clip saved: {abs_path} ({duration:.1f}s, {size_kb:.0f}KB)")

    return abs_path


async def stitch_clips(
    audio_url: str,
    time_ranges: list,
    output_dir: str = "data/clips",
    label: str = "stitched",
) -> str:
    """
    Extract multiple time ranges and concatenate them into one MP3.

    Uses ffmpeg's concat demuxer: extracts each range as a temp file,
    then merges them into a single output.

    Args:
        audio_url: Direct URL to the full MP3 file.
        time_ranges: List of (start_seconds, end_seconds) tuples.
        output_dir: Directory to save the output.
        label: Label for the output filename.

    Returns:
        Absolute path to the stitched MP3 file.
    """
    import tempfile

    if not time_ranges:
        raise ValueError("time_ranges must not be empty")
    if not audio_url:
        raise ValueError("audio_url is required")

    os.makedirs(output_dir, exist_ok=True)

    # Deterministic filename from ranges
    range_hash = "_".join(f"{int(s)}-{int(e)}" for s, e in time_ranges[:5])
    slug = _slugify(label)
    filename = f"{slug}__{range_hash}.mp3"
    output_path = os.path.join(output_dir, filename)

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return os.path.abspath(output_path)

    temp_files = []
    concat_list_path = None

    try:
        # Step 1: Extract each range as a temporary file
        for i, (start, end) in enumerate(time_ranges):
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            temp_files.append(tmp.name)

            ss = _format_timestamp(start)
            to = _format_timestamp(end)

            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y",
                "-ss", ss, "-to", to,
                "-i", audio_url,
                "-acodec", "libmp3lame", "-q:a", "2",
                tmp.name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()

        # Step 2: Create concat list file
        concat_list = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        )
        concat_list_path = concat_list.name
        for tf in temp_files:
            concat_list.write(f"file '{tf}'\n")
        concat_list.close()

        # Step 3: Concatenate
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list_path,
            "-acodec", "libmp3lame", "-q:a", "2",
            output_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode(errors="replace")[-500:] if stderr else "Unknown"
            raise RuntimeError(f"ffmpeg concat failed: {error_msg}")

        abs_path = os.path.abspath(output_path)
        size_kb = os.path.getsize(output_path) / 1024
        total_dur = sum(e - s for s, e in time_ranges)
        print(f"  🎵 Stitched {len(time_ranges)} clips: {abs_path} ({total_dur:.1f}s, {size_kb:.0f}KB)")
        return abs_path

    finally:
        for tf in temp_files:
            if os.path.exists(tf):
                try:
                    os.remove(tf)
                except OSError:
                    pass
        if concat_list_path and os.path.exists(concat_list_path):
            try:
                os.remove(concat_list_path)
            except OSError:
                pass


async def generate_audiogram(
    audio_url: str,
    start_seconds: float,
    end_seconds: float,
    captions: list = None,
    title: str = "",
    image_path: str = None,
    output_dir: str = "data/clips",
    width: int = 1080,
    height: int = 1080,
) -> str:
    """
    Create an audiogram video (MP4) with waveform visualization and optional captions.
    Supports a background image with a cinematic Ken Burns (zoompan) effect.

    Args:
        audio_url: Direct URL to the full MP3.
        start_seconds: Start time.
        end_seconds: End time.
        captions: Optional list of {text, start, end, speaker} dicts for burned-in subtitles.
        title: Title overlay text.
        image_path: Optional path to a background image.
        output_dir: Directory to save output.
        width/height: Video dimensions (square for social media).

    Returns:
        Absolute path to the MP4 file.
    """
    import tempfile

    if not audio_url:
        raise ValueError("audio_url is required")
    if end_seconds <= start_seconds:
        raise ValueError("end_seconds must be > start_seconds")

    os.makedirs(output_dir, exist_ok=True)

    slug = _slugify(title or "audiogram")
    image_suffix = "_ai" if image_path else ""
    filename = f"{slug}__{int(start_seconds)}-{int(end_seconds)}{image_suffix}.mp4"
    output_path = os.path.join(output_dir, filename)

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return os.path.abspath(output_path)

    ss = _format_timestamp(start_seconds)
    to = _format_timestamp(end_seconds)
    duration = end_seconds - start_seconds

    # Build ffmpeg filter graph
    filter_parts = []
    
    # 1. Background (Solid color or Image with Ken Burns Zoom)
    if image_path and os.path.exists(image_path):
        # Scale image 20% larger than output, then zoompan slowly
        upscale = int(width * 1.2)
        frames = int(duration * 25)
        filter_parts.append(
            f"[1:v]scale={upscale}:{upscale},"
            f"zoompan=z='min(zoom+0.0005,1.2)':d={frames}:s={width}x{height}:fps=25"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'[bg]"
        )
    else:
        filter_parts.append(f"color=c=0x1a1a2e:s={width}x{height}:d={duration}[bg]")

    # 2. Audio Visualizer overlay
    vis_h = height // 4
    filter_parts.extend([
        f"[0:a]showwaves=s={width}x{vis_h}:mode=cline:colors=0x4FC3F7[waves]",
        f"[bg][waves]overlay=0:{height - vis_h}[v]"
    ])

    # 3. Title overlay
    if title:
        safe_title = title.replace("'", "").replace(":", " -")[:60]
        # try to use a nice font if it exists, otherwise fallback to arial
        filter_parts.append(
            f"[v]drawtext=text='{safe_title}':fontsize=36:fontcolor=white:"
            f"x=(w-text_w)/2:y=60:font='Impact'[v]"
        )

    # 4. Caption overlay (subtitle-style at bottom)
    if captions:
        srt_path = tempfile.NamedTemporaryFile(suffix=".srt", mode="w", delete=False)
        offset = start_seconds
        for i, cap in enumerate(captions, 1):
            cap_start = max(0, (cap.get("start", 0) if isinstance(cap, dict) else getattr(cap, "start", 0)) - offset)
            cap_end = max(cap_start + 0.1, (cap.get("end", 0) if isinstance(cap, dict) else getattr(cap, "end", 0)) - offset)
            text = cap.get("text", "") if isinstance(cap, dict) else getattr(cap, "text", "")
            speaker = cap.get("speaker", "") if isinstance(cap, dict) else getattr(cap, "speaker", "")
            label = f"{speaker}: " if speaker else ""
            srt_path.write(f"{i}\n")
            srt_path.write(f"{_srt_timestamp(cap_start)} --> {_srt_timestamp(cap_end)}\n")
            srt_path.write(f"{label}{text}\n\n")
        srt_path.close()

        safe_srt = srt_path.name.replace("'", "'\\''").replace(":", "\\\\:")
        filter_parts.append(
            f"[v]subtitles=filename='{safe_srt}':force_style='FontSize=26,PrimaryColour=&Hffffff&,Alignment=2,MarginV=120'[v]"
        )

    filter_graph = ";".join(filter_parts)

    async def _run_ffmpeg(graph: str, use_image: bool = False):
        cmd = [
            "ffmpeg", "-y",
            "-ss", ss, "-to", to,
            "-i", audio_url
        ]
        if use_image:
            cmd.extend(["-i", image_path])
            
        cmd.extend([
            "-filter_complex", graph,
            "-map", "[v]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            output_path
        ])
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        return proc.returncode, stderr.decode(errors="replace") if stderr else ""

    returncode, err_msg = await _run_ffmpeg(filter_graph, use_image=bool(image_path))

    # Fallback cascade:
    # Level 1: If text filters (drawtext/subtitles) are missing, retry Premium without text
    if returncode != 0 and ("No such filter: 'drawtext'" in err_msg or "No such filter: 'subtitles'" in err_msg):
        print("  ⚠️ FFMPEG missing text filters. Retrying premium visuals without text.")
        fallback_v1_graph = ";".join(filter_parts[:3])  # Background, visualizer, and overlay
        returncode, err_msg = await _run_ffmpeg(fallback_v1_graph, use_image=bool(image_path))

    # Level 2: If it still fails, drop to basic static background + showwaves
    if returncode != 0:
        print(f"  ⚠️ Premium FFMPEG failed, trying basic fallback... ({returncode})")
        
        fallback_parts = []
        if image_path and os.path.exists(image_path):
             fallback_parts.append(f"[1:v]scale={width}:{height}[bg]")
        else:
             fallback_parts.append(f"color=c=0x1a1a2e:s={width}x{height}:d={duration}[bg]")
             
        fallback_parts.extend([
            f"[0:a]showwaves=s={width}x{height//4}:mode=cline:colors=0x4FC3F7[waves]",
            "[bg][waves]overlay=0:h-h/3[v]"
        ])
        
        fallback_graph = ";".join(fallback_parts)
        returncode, err_msg = await _run_ffmpeg(fallback_graph, use_image=bool(image_path))

    # Clean up temp srt
    if captions:
        try:
            os.remove(srt_path.name)
        except OSError:
            pass

    if returncode != 0:
        error_snippet = err_msg[-500:] if err_msg else "Unknown"
        if os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError(f"ffmpeg audiogram failed: {error_snippet}")

    abs_path = os.path.abspath(output_path)
    size_kb = os.path.getsize(output_path) / 1024
    print(f"  🎬 Audiogram saved: {abs_path} ({duration:.1f}s, {size_kb:.0f}KB)")
    return abs_path


def _srt_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    ms = int((s - int(s)) * 1000)
    return f"{h:02d}:{m:02d}:{int(s):02d},{ms:03d}"
