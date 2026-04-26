from huggingface_hub import hf_hub_download
import os

try:
    hf_hub_download(repo_id="pyannote/speaker-diarization-3.1", filename="config.yaml", use_auth_token=True)
    print("Success with use_auth_token")
except TypeError as e:
    print(f"Failed with use_auth_token: {e}")

try:
    hf_hub_download(repo_id="pyannote/speaker-diarization-3.1", filename="config.yaml", token=True)
    print("Success with token")
except TypeError as e:
    print(f"Failed with token: {e}")
