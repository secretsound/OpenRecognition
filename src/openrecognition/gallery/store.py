"""Enrollment and gallery persistence."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable
from typing import Any

import numpy as np

from openrecognition.gallery import match
from openrecognition.gallery.db import Database, json_dumps, json_loads
from openrecognition.gallery.sample_meta import SampleMeta, source_display
from openrecognition.models.schemas import EnrollmentType, ModalityQuality, QualityInfo, SampleOut


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_get(row, key: str, default=None):
    """Safe sqlite3.Row access (missing columns → default)."""
    return row[key] if key in row.keys() else default


def _optional_float(value):
    return float(value) if value is not None else None


ModelVersionResolver = Callable[[str, str], str]


class GalleryStore:
    def __init__(
        self,
        db: Database,
        data_dir: Path,
        *,
        version_resolver: ModelVersionResolver | None = None,
    ):
        self.db = db
        self.data_dir = data_dir
        self.media_dir = data_dir / "media"
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self._version_resolver = version_resolver

    def set_version_resolver(self, resolver: ModelVersionResolver) -> None:
        self._version_resolver = resolver

    def create_enrollment(
        self,
        etype: EnrollmentType,
        label: str,
        species_hint: str | None = None,
        threshold: float | None = None,
        enabled: bool = True,
        model_version: str = "v1",
    ) -> dict[str, Any]:
        eid = str(uuid.uuid4())
        now = _now()
        self.db.execute(
            """INSERT INTO enrollments
               (id, type, label, species_hint, enabled, threshold, model_version, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                eid,
                etype.value,
                label,
                species_hint,
                1 if enabled else 0,
                threshold,
                model_version,
                now,
                now,
            ),
        )
        return self.get_enrollment(eid)

    def get_enrollment(self, eid: str) -> dict[str, Any] | None:
        row = self.db.fetchone("SELECT * FROM enrollments WHERE id = ?", (eid,))
        if not row:
            return None
        return self._row_to_enrollment(row)

    def list_enrollments(
        self, etype: str | None = None, q: str | None = None
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if etype:
            clauses.append("type = ?")
            params.append(etype)
        needle = (q or "").strip()
        if needle:
            clauses.append("label LIKE ? ESCAPE '\\'")
            escaped = (
                needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            params.append(f"%{escaped}%")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.fetchall(
            f"SELECT * FROM enrollments{where} ORDER BY label", tuple(params)
        )
        return [self._row_to_enrollment(r) for r in rows]

    def _row_to_enrollment(self, row) -> dict[str, Any]:
        samples = self.db.fetchone(
            "SELECT COUNT(*) as c FROM embeddings WHERE enrollment_id = ?",
            (row["id"],),
        )
        from openrecognition.gallery.db import json_loads

        external_ids: dict[str, str] = {}
        raw_ext = row["external_ids"] if "external_ids" in row.keys() else None
        if raw_ext:
            loaded = json_loads(raw_ext)
            if isinstance(loaded, dict):
                external_ids = {str(k): str(v) for k, v in loaded.items()}

        return {
            "id": row["id"],
            "type": row["type"],
            "label": row["label"],
            "species_hint": row["species_hint"],
            "enabled": bool(row["enabled"]),
            "threshold": row["threshold"],
            "learn_enabled": bool(_row_get(row, "learn_enabled", 0)),
            "learn_min_confidence": float(_row_get(row, "learn_min_confidence", 0.9) or 0.9),
            "learn_margin": float(_row_get(row, "learn_margin", 0.05) or 0.0),
            "learn_daily_cap": int(_row_get(row, "learn_daily_cap", 8) or 0),
            "learn_max_samples": int(_row_get(row, "learn_max_samples", 20) or 1),
            "wyoming_min_confidence": _optional_float(_row_get(row, "wyoming_min_confidence", None)),
            "model_version": row["model_version"],
            "external_ids": external_ids,
            "sample_count": samples["c"] if samples else 0,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def patch_enrollment(self, eid: str, **kwargs) -> dict[str, Any] | None:
        en = self.get_enrollment(eid)
        if not en:
            return None
        fields = []
        params: list[Any] = []
        if "label" in kwargs and kwargs["label"] is not None:
            fields.append("label = ?")
            params.append(kwargs["label"])
        if "threshold" in kwargs:
            if kwargs["threshold"] is None:
                fields.append("threshold = NULL")
            else:
                fields.append("threshold = ?")
                params.append(kwargs["threshold"])
        if "wyoming_min_confidence" in kwargs:
            if kwargs["wyoming_min_confidence"] is None:
                fields.append("wyoming_min_confidence = NULL")
            else:
                fields.append("wyoming_min_confidence = ?")
                params.append(kwargs["wyoming_min_confidence"])
        if "enabled" in kwargs and kwargs["enabled"] is not None:
            fields.append("enabled = ?")
            params.append(1 if kwargs["enabled"] else 0)
        if "external_ids" in kwargs and kwargs["external_ids"] is not None:
            from openrecognition.gallery.db import json_dumps

            fields.append("external_ids = ?")
            params.append(json_dumps(kwargs["external_ids"]))
        if "learn_enabled" in kwargs and kwargs["learn_enabled"] is not None:
            fields.append("learn_enabled = ?")
            params.append(1 if kwargs["learn_enabled"] else 0)
        for key in ("learn_min_confidence", "learn_margin", "learn_daily_cap", "learn_max_samples"):
            if key in kwargs and kwargs[key] is not None:
                fields.append(f"{key} = ?")
                params.append(kwargs[key])
        if not fields:
            return en
        fields.append("updated_at = ?")
        params.append(_now())
        params.append(eid)
        self.db.execute(f"UPDATE enrollments SET {', '.join(fields)} WHERE id = ?", tuple(params))
        return self.get_enrollment(eid)

    def delete_enrollment(self, eid: str, purge_media: bool = False) -> bool:
        en = self.get_enrollment(eid)
        if not en:
            return False
        media_rows = self.db.fetchall(
            "SELECT path FROM enrollment_media WHERE enrollment_id = ?", (eid,)
        )
        if purge_media:
            for m in media_rows:
                if m["path"]:
                    p = Path(m["path"])
                    if p.exists():
                        p.unlink()
        with self.db.connect() as conn:
            conn.execute("DELETE FROM embeddings WHERE enrollment_id = ?", (eid,))
            conn.execute("DELETE FROM enrollment_media WHERE enrollment_id = ?", (eid,))
            conn.execute("DELETE FROM presence WHERE enrollment_id = ?", (eid,))
            conn.execute("DELETE FROM enrollments WHERE id = ?", (eid,))
            conn.commit()
        return True

    def add_embedding(
        self,
        enrollment_id: str,
        modality: str,
        vector: np.ndarray,
        model_version: str,
        meta: SampleMeta | None = None,
    ) -> str:
        m = meta or SampleMeta()
        eid = str(uuid.uuid4())
        dim = int(vector.size)
        self.db.execute(
            """INSERT INTO embeddings
               (id, enrollment_id, modality, model_version, vector, dim, created_at,
                source, original_filename, content_type, size_bytes, duration_ms,
                phrase_index, phrase_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                eid,
                enrollment_id,
                modality,
                model_version,
                match.vector_to_bytes(vector),
                dim,
                _now(),
                m.source,
                m.original_filename,
                m.content_type,
                m.size_bytes,
                m.duration_ms,
                m.phrase_index,
                m.phrase_text,
            ),
        )
        self._refresh_centroid(enrollment_id, model_version)
        self.db.execute(
            "UPDATE enrollments SET updated_at = ? WHERE id = ?",
            (_now(), enrollment_id),
        )
        return eid

    def count_learned_today(self, enrollment_id: str) -> int:
        from openrecognition.gallery.learn import LEARN_SOURCE

        start = datetime.now(timezone.utc).date().isoformat()
        row = self.db.fetchone(
            """SELECT COUNT(*) as c FROM embeddings
               WHERE enrollment_id = ? AND source = ? AND created_at >= ?""",
            (enrollment_id, LEARN_SOURCE, start),
        )
        return int(row["c"]) if row else 0

    def trim_learned_samples(self, enrollment_id: str, max_samples: int) -> None:
        """Drop the oldest learned clips so a new one still fits. User clips stay."""
        from openrecognition.gallery.learn import LEARN_SOURCE

        keep = max(1, max_samples) - 1
        rows = self.db.fetchall(
            """SELECT id FROM embeddings
               WHERE enrollment_id = ? AND source = ?
               ORDER BY created_at ASC, rowid ASC""",
            (enrollment_id, LEARN_SOURCE),
        )
        extra = len(rows) - keep
        for row in rows[: max(0, extra)]:
            self.delete_sample(row["id"])

    def link_media_to_embedding(self, embedding_id: str, media_id: str) -> None:
        self.db.execute(
            "UPDATE enrollment_media SET embedding_id = ? WHERE id = ?",
            (embedding_id, media_id),
        )

    def _refresh_centroid(self, enrollment_id: str, model_version: str) -> None:
        rows = self.db.fetchall(
            """SELECT vector, dim FROM embeddings
               WHERE enrollment_id = ? AND model_version = ?""",
            (enrollment_id, model_version),
        )
        if not rows:
            any_left = self.db.fetchone(
                "SELECT COUNT(*) as c FROM embeddings WHERE enrollment_id = ?",
                (enrollment_id,),
            )
            if any_left and any_left["c"] == 0:
                self.db.execute(
                    "UPDATE enrollments SET centroid = NULL, updated_at = ? WHERE id = ?",
                    (_now(), enrollment_id),
                )
            return
        vectors = [match.bytes_to_vector(r["vector"], r["dim"]) for r in rows]
        centroid = match.robust_centroid(vectors)
        self.db.execute(
            "UPDATE enrollments SET centroid = ?, updated_at = ? WHERE id = ?",
            (match.vector_to_bytes(centroid), _now(), enrollment_id),
        )

    def get_embeddings_for_match(
        self,
        modality: str | None = None,
        model_version: str | None = None,
        enabled_only: bool = True,
    ) -> list[dict[str, Any]]:
        """One gallery row per enrollment, modality, and model version.

        Identity matching reads ``embeddings``, not ``enrollments.centroid``.
        That column holds a single blob and is overwritten by whichever sample
        was stored last, so a voice sample would hide a face (and the reverse).
        """
        sql = "SELECT * FROM enrollments"
        if enabled_only:
            sql += " WHERE enabled = 1"
        rows = self.db.fetchall(sql)
        results = []
        for row in rows:
            etype = row["type"]
            if modality == "audio" and etype not in ("person", "sound"):
                continue
            if modality == "image" and etype not in ("person", "pet", "object"):
                continue

            for mv, group_modality, vec in self._embedding_groups(
                row["id"], modality=modality, model_version=model_version
            ):
                results.append(
                    {
                        "id": row["id"],
                        "label": row["label"],
                        "type": etype,
                        "threshold": row["threshold"],
                        "wyoming_min_confidence": _row_get(row, "wyoming_min_confidence", None),
                        "model_version": mv,
                        "vector": vec,
                        "modality": group_modality,
                    }
                )
        return results

    def image_embeddings_for_match(
        self, face_model_version: str, visual_model_version: str
    ) -> list[dict[str, Any]]:
        """Face and pet/object centroids, kept as separate rows when versions differ."""
        items = self.get_embeddings_for_match(
            modality="image", model_version=face_model_version
        )
        if visual_model_version != face_model_version:
            items = items + self.get_embeddings_for_match(
                modality="image", model_version=visual_model_version
            )
        return items

    def _embedding_groups(
        self,
        enrollment_id: str,
        *,
        modality: str | None,
        model_version: str | None,
    ) -> list[tuple[str, str, np.ndarray]]:
        sql = """SELECT model_version, modality, vector, dim FROM embeddings
                 WHERE enrollment_id = ?"""
        params: list[Any] = [enrollment_id]
        if modality:
            sql += " AND modality = ?"
            params.append(modality)
        if model_version:
            sql += " AND model_version = ?"
            params.append(model_version)
        rows = self.db.fetchall(sql, tuple(params))
        buckets: dict[tuple[str, str], list[np.ndarray]] = {}
        for r in rows:
            key = (r["model_version"], r["modality"])
            buckets.setdefault(key, []).append(
                match.bytes_to_vector(r["vector"], r["dim"])
            )
        return [
            (mv, mod, match.robust_centroid(vectors))
            for (mv, mod), vectors in buckets.items()
        ]

    def _row_to_sample_meta(self, row) -> SampleMeta:
        source = _row_get(row, "source") or "unknown"
        return SampleMeta(
            source=source,
            original_filename=_row_get(row, "original_filename"),
            content_type=_row_get(row, "content_type"),
            size_bytes=_row_get(row, "size_bytes"),
            duration_ms=_row_get(row, "duration_ms"),
            phrase_index=_row_get(row, "phrase_index"),
            phrase_text=_row_get(row, "phrase_text"),
        )

    def _current_model_version(self, modality: str, enrollment_type: str) -> str:
        if self._version_resolver is not None:
            return self._version_resolver(modality, enrollment_type)
        from openrecognition.inference.speaker import HEURISTIC_MODEL_VERSION
        from openrecognition.inference.vision import FACE_MODEL_VERSION, VISUAL_MODEL_VERSION

        if modality == "audio":
            return HEURISTIC_MODEL_VERSION
        if enrollment_type in ("pet", "object"):
            return VISUAL_MODEL_VERSION
        return FACE_MODEL_VERSION

    def _centroid_for_model_version(
        self, enrollment_id: str, model_version: str
    ) -> np.ndarray | None:
        rows = self.db.fetchall(
            """SELECT vector, dim FROM embeddings
               WHERE enrollment_id = ? AND model_version = ?""",
            (enrollment_id, model_version),
        )
        if not rows:
            return None
        vectors = [match.bytes_to_vector(r["vector"], r["dim"]) for r in rows]
        return match.robust_centroid(vectors)

    def similarity_to_centroid(
        self,
        enrollment_id: str,
        vector: np.ndarray,
        model_version: str,
    ) -> float | None:
        centroid = self._centroid_for_model_version(enrollment_id, model_version)
        if centroid is None:
            return None
        return match.cosine_similarity(centroid, vector)

    def list_samples(self, enrollment_id: str) -> list[SampleOut]:
        en = self.get_enrollment(enrollment_id)
        if not en:
            return []
        etype = en["type"]
        rows = self.db.fetchall(
            """SELECT e.*, m.id as media_id, m.path as media_path
               FROM embeddings e
               LEFT JOIN enrollment_media m ON m.embedding_id = e.id
               WHERE e.enrollment_id = ?
               ORDER BY e.created_at DESC""",
            (enrollment_id,),
        )
        by_mv: dict[str, np.ndarray] = {}
        samples: list[SampleOut] = []
        for row in rows:
            mv = row["model_version"]
            if mv not in by_mv:
                by_mv[mv] = self._centroid_for_model_version(enrollment_id, mv)
            centroid = by_mv[mv]
            vec = match.bytes_to_vector(row["vector"], row["dim"])
            meta = self._row_to_sample_meta(row)
            sim = (
                match.cosine_similarity(centroid, vec)
                if centroid is not None
                else None
            )
            current_mv = self._current_model_version(row["modality"], etype)
            flags: list[str] = []
            if (_row_get(row, "source") or "unknown") == "unknown":
                flags.append("unknown_source")
            if mv != current_mv:
                flags.append("outdated_model")
            if sim is not None and sim < 0.5:
                flags.append("low_fit")
            if sim is not None and sim < 0.35:
                flags.append("poor_fit")
            samples.append(
                SampleOut(
                    id=row["id"],
                    enrollment_id=enrollment_id,
                    modality=row["modality"],
                    model_version=mv,
                    source=meta.source,
                    source_label=source_display(meta),
                    original_filename=meta.original_filename,
                    content_type=meta.content_type,
                    size_bytes=meta.size_bytes,
                    duration_ms=meta.duration_ms,
                    phrase_index=meta.phrase_index,
                    phrase_text=meta.phrase_text,
                    created_at=row["created_at"],
                    centroid_similarity=round(sim, 4) if sim is not None else None,
                    media_stored=bool(_row_get(row, "media_path")),
                    flags=flags,
                )
            )
        return samples

    def delete_sample(self, sample_id: str) -> bool:
        row = self.db.fetchone(
            "SELECT enrollment_id, model_version FROM embeddings WHERE id = ?",
            (sample_id,),
        )
        if not row:
            return False
        enrollment_id = row["enrollment_id"]
        media_rows = self.db.fetchall(
            "SELECT id, path FROM enrollment_media WHERE embedding_id = ?",
            (sample_id,),
        )
        for m in media_rows:
            if m["path"]:
                p = Path(m["path"])
                if p.exists():
                    p.unlink()
            self.db.execute("DELETE FROM enrollment_media WHERE id = ?", (m["id"],))
        self.db.execute("DELETE FROM embeddings WHERE id = ?", (sample_id,))
        versions = self.db.fetchall(
            "SELECT DISTINCT model_version FROM embeddings WHERE enrollment_id = ?",
            (enrollment_id,),
        )
        if versions:
            for v in versions:
                self._refresh_centroid(enrollment_id, v["model_version"])
        else:
            self.db.execute(
                "UPDATE enrollments SET centroid = NULL, updated_at = ? WHERE id = ?",
                (_now(), enrollment_id),
            )
        self.db.execute(
            "UPDATE enrollments SET updated_at = ? WHERE id = ?",
            (_now(), enrollment_id),
        )
        return True

    def find_duplicate_warning(
        self,
        vector: np.ndarray,
        model_version: str,
        exclude_id: str | None = None,
        threshold: float = 0.92,
    ) -> str | None:
        dim = vector.size
        for item in self.get_embeddings_for_match(model_version=model_version):
            if exclude_id and item["id"] == exclude_id:
                continue
            if item["vector"].size != dim:
                continue
            sim = match.cosine_similarity(vector, item["vector"])
            if sim >= threshold:
                return (
                    f"Embedding {sim:.0%} similar to existing enrollment "
                    f"'{item['label']}' ({item['type']})"
                )
        return None

    def _modality_label(self, modality: str, enrollment_type: str) -> str:
        if modality == "audio":
            return "Sound" if enrollment_type == "sound" else "Voice"
        if modality == "image":
            return "Face" if enrollment_type == "person" else "Photos"
        return modality.capitalize()

    def _expected_modalities(self, enrollment_type: str) -> list[str]:
        if enrollment_type == "person":
            return ["audio", "image"]
        if enrollment_type in ("pet", "object"):
            return ["image"]
        if enrollment_type == "sound":
            return ["audio"]
        return ["audio"]

    def _quality_target(self, enrollment_type: str, modality: str) -> int:
        """Samples needed before a consistent embedding can score near 100%."""
        if modality == "audio":
            return 8
        if enrollment_type == "pet":
            return 10
        return 6

    def _evaluate_vectors(
        self,
        vectors: list[np.ndarray],
        *,
        enrollment_type: str,
        modality: str,
    ) -> QualityInfo:
        issues: list[str] = []
        n = len(vectors)
        if n < 1:
            return QualityInfo(score=0.0, issues=["no_samples"], usable=False)
        if n < 3:
            issues.append("too_few_samples")
        centroid = match.robust_centroid(vectors)
        sims = [match.cosine_similarity(centroid, v) for v in vectors]
        avg = float(np.mean(sims))
        if avg < 0.5:
            issues.append("high_variance")
        target = self._quality_target(enrollment_type, modality)
        if n < target:
            if modality == "audio":
                issues.append("recommend_more_voice_samples")
            elif enrollment_type == "pet" and modality == "image":
                issues.append("pet_recommend_more_samples")
            elif modality == "image":
                issues.append("recommend_more_samples")
        score = min(1.0, avg * (n / float(target)))
        usable = n >= 1 and ("too_few_samples" not in issues or n >= 3)
        return QualityInfo(score=round(score, 3), issues=issues, usable=usable)

    def _evaluate_from_rows(self, enrollment_type: str, rows: list[Any]) -> QualityInfo:
        by_modality: dict[str, list[np.ndarray]] = {}
        for row in rows:
            mod = row["modality"]
            current_mv = self._current_model_version(mod, enrollment_type)
            mv = _row_get(row, "model_version")
            if mv is not None and mv != current_mv:
                continue
            by_modality.setdefault(mod, []).append(
                match.bytes_to_vector(row["vector"], row["dim"])
            )

        modality_results: list[ModalityQuality] = []
        expected = self._expected_modalities(enrollment_type)
        seen = set(expected)

        for mod in expected:
            vectors = by_modality.get(mod, [])
            q = self._evaluate_vectors(
                vectors, enrollment_type=enrollment_type, modality=mod
            )
            modality_results.append(
                ModalityQuality(
                    modality=mod,
                    label=self._modality_label(mod, enrollment_type),
                    sample_count=len(vectors),
                    score=q.score,
                    issues=q.issues,
                    usable=q.usable,
                )
            )

        for mod, vectors in by_modality.items():
            if mod in seen:
                continue
            q = self._evaluate_vectors(
                vectors, enrollment_type=enrollment_type, modality=mod
            )
            modality_results.append(
                ModalityQuality(
                    modality=mod,
                    label=self._modality_label(mod, enrollment_type),
                    sample_count=len(vectors),
                    score=q.score,
                    issues=q.issues,
                    usable=q.usable,
                )
            )

        if not rows:
            return QualityInfo(
                score=0.0,
                issues=["no_embeddings"],
                usable=False,
                modalities=modality_results,
            )

        total_samples = sum(m.sample_count for m in modality_results)
        if total_samples > 0:
            weighted = sum(m.score * m.sample_count for m in modality_results) / total_samples
            overall_score = round(weighted, 3)
        else:
            overall_score = 0.0

        overall_issues: list[str] = []
        for m in modality_results:
            for issue in m.issues:
                if issue not in overall_issues:
                    overall_issues.append(issue)

        any_usable = any(m.usable and m.sample_count > 0 for m in modality_results)

        return QualityInfo(
            score=overall_score,
            issues=overall_issues,
            usable=any_usable,
            modalities=modality_results,
        )

    def evaluate_enrollment(self, eid: str) -> QualityInfo:
        rows = self.db.fetchall(
            "SELECT vector, dim, modality, model_version FROM embeddings WHERE enrollment_id = ?",
            (eid,),
        )
        en = self.get_enrollment(eid)
        enrollment_type = en["type"] if en else "person"
        return self._evaluate_from_rows(enrollment_type, rows)

    def evaluate_many(self, enrollments: list[dict[str, Any]]) -> dict[str, QualityInfo]:
        """Score every enrollment with one embeddings query. Used by the library list."""
        if not enrollments:
            return {}
        ids = [e["id"] for e in enrollments]
        placeholders = ",".join("?" * len(ids))
        rows = self.db.fetchall(
            f"SELECT enrollment_id, vector, dim, modality, model_version "
            f"FROM embeddings WHERE enrollment_id IN ({placeholders})",
            ids,
        )
        by_id: dict[str, list[Any]] = {eid: [] for eid in ids}
        for row in rows:
            by_id.setdefault(row["enrollment_id"], []).append(row)
        return {
            en["id"]: self._evaluate_from_rows(en["type"], by_id.get(en["id"], []))
            for en in enrollments
        }

    def export_gallery(self) -> dict[str, Any]:
        enrollments = []
        for en in self.list_enrollments():
            emb_rows = self.db.fetchall(
                "SELECT modality, model_version, vector, dim FROM embeddings WHERE enrollment_id = ?",
                (en["id"],),
            )
            enrollments.append(
                {
                    **en,
                    "embeddings": [
                        {
                            "modality": r["modality"],
                            "model_version": r["model_version"],
                            "vector": [
                                float(x)
                                for x in match.bytes_to_vector(r["vector"], r["dim"])
                            ],
                        }
                        for r in emb_rows
                    ],
                }
            )
        return {
            "version": "1",
            "exported_at": _now(),
            "enrollment_count": len(enrollments),
            "enrollments": enrollments,
        }

    def import_gallery(self, data: dict[str, Any]) -> int:
        count = 0
        for en in data.get("enrollments", []):
            existing = self.db.fetchone(
                "SELECT id FROM enrollments WHERE label = ? AND type = ?",
                (en["label"], en["type"]),
            )
            if existing:
                eid = existing["id"]
            else:
                created = self.create_enrollment(
                    EnrollmentType(en["type"]),
                    en["label"],
                    en.get("species_hint"),
                    en.get("threshold"),
                    en.get("enabled", True),
                    en.get("model_version", "v1"),
                )
                eid = created["id"]
            for emb in en.get("embeddings", []):
                vec = np.array(emb["vector"], dtype=np.float32)
                self.add_embedding(
                    eid, emb["modality"], vec, emb.get("model_version", "v1")
                )
            count += 1
        return count

    def update_presence(
        self,
        enrollment_id: str,
        label: str,
        etype: str,
        modality: str,
        camera_id: str | None,
        confidence: float | None,
    ) -> None:
        now = _now()
        self.db.execute(
            """INSERT INTO presence
               (enrollment_id, label, type, last_seen_at, last_modality, last_camera_id, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(enrollment_id) DO UPDATE SET
               last_seen_at=excluded.last_seen_at,
               last_modality=excluded.last_modality,
               last_camera_id=excluded.last_camera_id,
               confidence=excluded.confidence""",
            (enrollment_id, label, etype, now, modality, camera_id, confidence),
        )

    def list_presence(self) -> list[dict[str, Any]]:
        rows = self.db.fetchall("SELECT * FROM presence ORDER BY last_seen_at DESC")
        return [dict(r) for r in rows]

    def last_seen_at(self, enrollment_id: str) -> str | None:
        row = self.db.fetchone(
            "SELECT last_seen_at FROM presence WHERE enrollment_id = ?",
            (enrollment_id,),
        )
        return row["last_seen_at"] if row else None

    def presence_map(self) -> dict[str, str]:
        return {r["enrollment_id"]: r["last_seen_at"] for r in self.list_presence()}
