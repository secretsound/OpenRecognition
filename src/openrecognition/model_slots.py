"""Built-in model slot used for each job category."""

CATEGORY_SLOT: dict[str, str] = {
    "speech_check": "silero_vad",
    "voice_match": "speaker_embedding",
    "skip_reasons": "audio_gate_classifier",
    "find_face": "face_detector",
    "match_face": "face_embedding",
    "find_pet": "animal_detector",
    "match_pet": "visual_reid",
}

SLOT_CATEGORY: dict[str, str] = {slot: category for category, slot in CATEGORY_SLOT.items()}
