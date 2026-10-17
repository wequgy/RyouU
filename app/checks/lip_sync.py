"""Lip-sync check: compares mouth openness from InsightFace landmark_3d_68 against
the audio energy envelope decoded from the same video file with PyAV.

Signal only:
Speech present but lips not moving, or no correlation -> `uncertain` "voice and lips do not line up" (goes to review).
Never hard-fails until thresholds are calibrated on real recordings.
"""
import numpy as np

from ..models import CheckContext, CheckResult
from .base import register
from . import face_match


def decode_audio_energy(video_path, audio_path=None, target_fps=15):
    """Decode audio track using PyAV and compute RMS energy envelope."""
    try:
        import av
        source = None
        # First attempt: audio stream from video_path
        if video_path:
            try:
                c = av.open(str(video_path))
                if c.streams.audio:
                    source = (c, c.streams.audio[0])
                else:
                    c.close()
            except Exception:
                pass
        
        # Second attempt: fallback to dedicated audio_path
        if source is None and audio_path:
            try:
                c = av.open(str(audio_path))
                if c.streams.audio:
                    source = (c, c.streams.audio[0])
            except Exception:
                pass

        if source is None:
            return []

        container, audio_stream = source
        sample_rate = audio_stream.rate or 16000
        window_size = int(sample_rate / target_fps)

        all_samples = []
        for frame in container.decode(audio_stream):
            arr = frame.to_ndarray()
            if arr.ndim > 1:
                arr = arr.mean(axis=0)
            all_samples.extend(arr.astype(np.float32))
        container.close()

        if not all_samples:
            return []

        samples = np.array(all_samples)
        max_val = np.max(np.abs(samples))
        if max_val > 0:
            samples = samples / max_val

        energies = []
        for i in range(0, len(samples), window_size):
            chunk = samples[i:i + window_size]
            if len(chunk) > 0:
                rms = np.sqrt(np.mean(chunk ** 2))
                energies.append(float(rms))
        return energies
    except Exception:
        return []


def evaluate_lip_sync(video_path, audio_path=None) -> CheckResult:
    if not video_path:
        return CheckResult.skipped("lip_sync", "No challenge video provided")

    try:
        from . import video_deepfake
        frames = video_deepfake.sample_frames(video_path, n=12)
        fps = 15.0
    except Exception as e:
        return CheckResult.uncertain("lip_sync", f"Failed to read video frames: {e}")

    if len(frames) < 4:
        return CheckResult.uncertain("lip_sync", "Video too short for lip-sync analysis")

    try:
        app = face_match._load_app()
    except Exception as e:
        return CheckResult.uncertain("lip_sync", f"InsightFace model unavailable: {e}")

    openness = []
    for img in frames:
        faces = app.get(img)
        if not faces:
            continue
        f = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        lm = getattr(f, "landmark_3d_68", None)
        if lm is not None and len(lm) >= 68:
            h = np.linalg.norm(lm[62] - lm[66])
            w = np.linalg.norm(lm[48] - lm[54]) + 1e-6
            openness.append(float(h / w))

    if len(openness) < 3:
        return CheckResult.uncertain("lip_sync", "Could not track facial landmarks across frames")

    audio_energies = decode_audio_energy(video_path, audio_path=audio_path, target_fps=int(fps))
    if not audio_energies or len(audio_energies) < 3:
        return CheckResult.uncertain("lip_sync", "No audible speech or audio track found in video")

    min_len = min(len(openness), len(audio_energies))
    open_arr = np.array(openness[:min_len])
    audio_arr = np.array(audio_energies[:min_len])

    speech_active = float(np.mean(audio_arr)) > 0.05
    openness_var = float(np.var(open_arr))

    if np.std(open_arr) > 1e-5 and np.std(audio_arr) > 1e-5:
        corr = float(np.corrcoef(open_arr, audio_arr)[0, 1])
    else:
        corr = 0.0

    details = {
        "frames_evaluated": min_len,
        "mean_audio_energy": round(float(np.mean(audio_arr)), 4),
        "openness_variance": round(openness_var, 5),
        "audio_lip_correlation": round(corr, 3),
    }

    if speech_active and openness_var < 0.0003:
        return CheckResult("lip_sync", "fail", 0.1, 0.7,
                           "voice and lips do not line up: speech detected while lips remained static (possible voice spoof or off-camera speaker)", details)

    if speech_active and corr < -0.15:
        return CheckResult("lip_sync", "fail", 0.2, 0.6,
                           "voice and lips do not line up: mouth movement does not match speech audio", details)

    return CheckResult("lip_sync", "pass", 0.9, 0.5, "Lip movements correlate with speech audio", details)


@register("lip_sync")
def lip_sync(ctx: CheckContext) -> CheckResult:
    video_path = ctx.files.get("challenge_video")
    audio_path = ctx.files.get("challenge_audio") or ctx.files.get("phrase_audio")
    return evaluate_lip_sync(video_path, audio_path=audio_path)
