"""Wyoming service discovery metadata."""

from __future__ import annotations

from openrecognition import __version__

try:
    from wyoming.info import AsrModel, AsrProgram, Attribution, Info
except ImportError:
    AsrModel = None  # type: ignore
    AsrProgram = None  # type: ignore
    Attribution = None  # type: ignore
    Info = None  # type: ignore


WYOMING_ASR_PROGRAM = "openrecognition"
WYOMING_ASR_MODEL = "speaker-proxy"


def build_wyoming_info(
    upstream_languages: list[str],
    *,
    supports_transcript_streaming: bool = False,
    prefers_auto_gain_enabled: bool = True,
    prefers_noise_reduction_enabled: bool = True,
) -> "Info":
    if Info is None:
        raise RuntimeError("wyoming package is not installed")
    return Info(
        asr=[
            AsrProgram(
                name=WYOMING_ASR_PROGRAM,
                description="Speaker identify (OpenRecognition) → upstream ASR",
                attribution=Attribution(
                    name="OpenRecognition",
                    url="https://github.com/openrecognition/openrecognition",
                ),
                installed=True,
                version=__version__,
                # This proxy buffers until audio-stop, so Assist must run VAD.
                requires_external_vad=True,
                # Relay upstream streaming only when that service advertises it.
                supports_transcript_streaming=supports_transcript_streaming,
                # Gain and noise reduction happen before audio reaches us.
                prefers_auto_gain_enabled=prefers_auto_gain_enabled,
                prefers_noise_reduction_enabled=prefers_noise_reduction_enabled,
                models=[
                    AsrModel(
                        name=WYOMING_ASR_MODEL,
                        description="Gate + speaker ID before STT",
                        languages=upstream_languages,
                        attribution=Attribution(
                            name="OpenRecognition",
                            url="https://github.com/openrecognition/openrecognition",
                        ),
                        installed=True,
                        version=__version__,
                    )
                ],
            )
        ]
    )
