"""Sound events that the audio gate can actually distinguish.

Doorbell, bark, and glass-break are not inferred from loudness. A loud
non-speech clip used to be labeled bark; that guess is gone until a real
classifier exists.
"""

from openrecognition.inference.audio_gate import heuristic_gate, load_wav_pcm
from openrecognition.models.schemas import EntityResult


def classify_sound_events(audio_bytes: bytes) -> list[EntityResult]:
    audio, sr = load_wav_pcm(audio_bytes)
    gate = heuristic_gate(audio, sr)
    entities: list[EntityResult] = []
    if gate.scores.get("speech", 0) > 0.5:
        entities.append(
            EntityResult(
                label="speech",
                type="sound",
                recognition_type="sound_event",
                confidence=gate.scores["speech"],
                modality="audio",
            )
        )
    if gate.scores.get("music", 0) > 0.45:
        entities.append(
            EntityResult(
                label="music",
                type="sound",
                recognition_type="sound_event",
                confidence=gate.scores["music"],
                modality="audio",
            )
        )
    return entities
