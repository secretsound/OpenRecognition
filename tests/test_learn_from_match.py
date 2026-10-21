"""Sure voice matches can become samples, with the guards the settings describe."""

import numpy as np

from openrecognition.gallery.db import Database
from openrecognition.gallery.learn import LEARN_SOURCE, learn_allowed
from openrecognition.gallery.store import GalleryStore
from openrecognition.models.schemas import EnrollmentType


def _store(tmp_path):
    data_dir = tmp_path / "data"
    return GalleryStore(Database(data_dir / "openrecognition.db"), data_dir)


def _vec() -> np.ndarray:
    vec = np.ones(8, dtype=np.float32)
    return vec / np.linalg.norm(vec)


def _person(store: GalleryStore, label: str = "Luke"):
    en = store.create_enrollment(EnrollmentType.person, label)
    store.patch_enrollment(
        en["id"],
        learn_enabled=True,
        learn_min_confidence=0.9,
        learn_margin=0.05,
        learn_daily_cap=2,
        learn_max_samples=2,
    )
    return store.get_enrollment(en["id"])


def _candidates(enrollment_id: str, score: float, other: float | None = 0.8):
    rows = [{"entity_id": enrollment_id, "confidence": score, "label": "Luke"}]
    if other is not None:
        rows.append({"entity_id": "other", "confidence": other, "label": "Other"})
    return rows


def test_learn_allowed_requires_gap_gate_and_cap():
    assert learn_allowed(
        enabled=True,
        enrollment_type="person",
        confidence=0.95,
        min_confidence=0.9,
        margin=0.05,
        candidates=[{"entity_id": "a", "confidence": 0.95}, {"entity_id": "b", "confidence": 0.8}],
        enrollment_id="a",
        gate_accepted=True,
        dry_run=False,
        learned_today=0,
        daily_cap=2,
    )
    assert not learn_allowed(
        enabled=True,
        enrollment_type="person",
        confidence=0.95,
        min_confidence=0.9,
        margin=0.05,
        candidates=[{"entity_id": "a", "confidence": 0.95}, {"entity_id": "b", "confidence": 0.93}],
        enrollment_id="a",
        gate_accepted=True,
        dry_run=False,
        learned_today=0,
        daily_cap=2,
    )
    assert not learn_allowed(
        enabled=True,
        enrollment_type="person",
        confidence=0.95,
        min_confidence=0.9,
        margin=0.05,
        candidates=[],
        enrollment_id="a",
        gate_accepted=False,
        dry_run=False,
        learned_today=0,
        daily_cap=2,
    )
    assert not learn_allowed(
        enabled=True,
        enrollment_type="person",
        confidence=0.95,
        min_confidence=0.9,
        margin=0.05,
        candidates=[],
        enrollment_id="a",
        gate_accepted=True,
        dry_run=True,
        learned_today=0,
        daily_cap=2,
    )
    assert not learn_allowed(
        enabled=True,
        enrollment_type="pet",
        confidence=0.95,
        min_confidence=0.9,
        margin=0.05,
        candidates=[],
        enrollment_id="a",
        gate_accepted=True,
        dry_run=False,
        learned_today=0,
        daily_cap=2,
    )


def test_maybe_learn_voice_stores_and_lists_the_sample(tmp_path):
    from openrecognition.gallery.learn import maybe_learn_voice

    store = _store(tmp_path)
    en = _person(store)
    store.add_embedding(en["id"], "audio", _vec(), "wespeaker-v1")
    sample_id = maybe_learn_voice(
        store,
        en["id"],
        _vec(),
        "wespeaker-v1",
        confidence=0.95,
        candidates=_candidates(en["id"], 0.95, 0.8),
        gate_accepted=True,
        dry_run=False,
    )
    assert sample_id
    learned = [s for s in store.list_samples(en["id"]) if s.source == LEARN_SOURCE]
    assert len(learned) == 1
    assert learned[0].source_label == "95% match"
    assert learned[0].modality == "audio"


def test_maybe_learn_voice_skips_close_calls_and_practice(tmp_path):
    from openrecognition.gallery.learn import maybe_learn_voice

    store = _store(tmp_path)
    en = _person(store)
    assert (
        maybe_learn_voice(
            store,
            en["id"],
            _vec(),
            "wespeaker-v1",
            confidence=0.95,
            candidates=_candidates(en["id"], 0.95, 0.93),
            gate_accepted=True,
            dry_run=False,
        )
        is None
    )
    assert (
        maybe_learn_voice(
            store,
            en["id"],
            _vec(),
            "wespeaker-v1",
            confidence=0.95,
            candidates=_candidates(en["id"], 0.95, 0.8),
            gate_accepted=True,
            dry_run=True,
        )
        is None
    )
    assert store.list_samples(en["id"]) == []


def test_learned_samples_drop_oldest_and_keep_user_clips(tmp_path):
    from openrecognition.gallery.learn import maybe_learn_voice
    from openrecognition.gallery.sample_meta import SampleMeta

    store = _store(tmp_path)
    en = _person(store)
    store.patch_enrollment(en["id"], learn_daily_cap=10)
    store.add_embedding(
        en["id"],
        "audio",
        _vec(),
        "wespeaker-v1",
        meta=SampleMeta(source="voice_wizard", phrase_text="hello"),
    )
    first = maybe_learn_voice(
        store,
        en["id"],
        _vec(),
        "wespeaker-v1",
        confidence=0.95,
        candidates=_candidates(en["id"], 0.95, None),
        gate_accepted=True,
        dry_run=False,
    )
    second = maybe_learn_voice(
        store,
        en["id"],
        _vec(),
        "wespeaker-v1",
        confidence=0.96,
        candidates=_candidates(en["id"], 0.96, None),
        gate_accepted=True,
        dry_run=False,
    )
    third = maybe_learn_voice(
        store,
        en["id"],
        _vec(),
        "wespeaker-v1",
        confidence=0.97,
        candidates=_candidates(en["id"], 0.97, None),
        gate_accepted=True,
        dry_run=False,
    )
    samples = store.list_samples(en["id"])
    learned_ids = [s.id for s in samples if s.source == LEARN_SOURCE]
    user_ids = [s.id for s in samples if s.source == "voice_wizard"]
    assert user_ids
    assert first not in learned_ids
    assert second in learned_ids
    assert third in learned_ids
    assert len(learned_ids) == 2


def test_daily_cap_stops_further_learning(tmp_path):
    from openrecognition.gallery.learn import maybe_learn_voice

    store = _store(tmp_path)
    en = _person(store)
    store.patch_enrollment(en["id"], learn_max_samples=10, learn_daily_cap=1)
    assert maybe_learn_voice(
        store,
        en["id"],
        _vec(),
        "wespeaker-v1",
        confidence=0.95,
        candidates=_candidates(en["id"], 0.95, None),
        gate_accepted=True,
        dry_run=False,
    )
    assert (
        maybe_learn_voice(
            store,
            en["id"],
            _vec(),
            "wespeaker-v1",
            confidence=0.96,
            candidates=_candidates(en["id"], 0.96, None),
            gate_accepted=True,
            dry_run=False,
        )
        is None
    )
    assert store.count_learned_today(en["id"]) == 1
