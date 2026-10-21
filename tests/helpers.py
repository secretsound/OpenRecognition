import io
import wave

import numpy as np


def wav_bytes(duration=0.5, sr=16000, freq=440.0) -> bytes:
    t = np.linspace(0, duration, int(sr * duration), dtype=np.float32)
    audio = (0.3 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()
