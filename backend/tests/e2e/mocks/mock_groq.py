"""Deterministic Offline Mock for Groq Whisper and Feedback Extraction.

Provides deterministic responses for feedback extraction and audio transcription,
conforming strictly to ExtractionResult and ServiceUnavailable schemas.
"""

from __future__ import annotations

from pathlib import Path

from app.schemas import (
    AssetRequirement,
    ExtractionItem,
    ExtractionResult,
)
from app.services.groq import ServiceUnavailable


class MockGroqService:
    """Offline mock for Groq Whisper transcription and feedback extraction."""

    def __init__(self) -> None:
        self.should_fail_extraction: bool = False
        self.should_fail_transcription: bool = False
        self.failure_status_code: int = 503
        self.failure_message: str = "Mock Groq service simulated outage."
        self.recorded_extractions: list[str] = []
        self.recorded_transcriptions: list[tuple[str, str, str]] = []

    def reset(self) -> None:
        """Reset service state and failure triggers."""
        self.should_fail_extraction = False
        self.should_fail_transcription = False
        self.failure_status_code = 503
        self.failure_message = "Mock Groq service simulated outage."
        self.recorded_extractions.clear()
        self.recorded_transcriptions.clear()

    async def extract_feedback(self, transcript: str) -> ExtractionResult:
        """Extract structured feedback items from transcript text."""
        self.recorded_extractions.append(transcript)
        if self.should_fail_extraction:
            raise ServiceUnavailable(self.failure_message)

        text = transcript.strip()
        if not text:
            return ExtractionResult(summary="", requests=[], required_assets=[])

        # Heuristic deterministic extraction based on content
        raw_lines = [
            line.strip("- *0123456789. ")
            for line in text.split("\n")
            if len(line.strip()) > 3
        ]
        if not raw_lines:
            raw_lines = [text]

        items: list[ExtractionItem] = []
        ambiguities: list[str] = []
        required_assets: list[AssetRequirement] = []

        for idx, line in enumerate(raw_lines[:12]):
            lower = line.lower()

            # 1. Category detection
            cat = "creative"
            if any(w in lower for w in ["color", "grade", "dark", "bright", "lut", "saturation", "tint", "contrast", "warm", "cool"]):
                cat = "grading"
            elif any(w in lower for w in ["audio", "music", "sound", "track", "voice", "mix", "volume", "dialogue", "sfx", "bass", "stem"]):
                cat = "audio"
            elif any(w in lower for w in ["pace", "slow", "fast", "speed", "timing", "cut", "trim", "transition", "scene"]):
                cat = "pacing"
            elif any(w in lower for w in ["graphic", "title", "font", "lower third", "text", "logo", "caption"]):
                cat = "graphics"

            # 2. Inferred / Ambiguity detection
            is_ambiguous = any(
                w in lower for w in ["maybe", "perhaps", "feel", "pop", "vibe", "punchy", "something like", "better", "not sure"]
            )

            # 3. Memory classification
            mem_class = "project_specific"
            if any(w in lower for w in ["always", "never", "every project", "brand guideline", "standard"]):
                mem_class = "reusable_preference"
            elif any(w in lower for w in ["temporary", "just for this", "only this version"]):
                mem_class = "temporary_revision"

            if is_ambiguous:
                ambiguities.append(f"Ambiguity in note #{idx + 1}: '{line}' requires confirmation.")

            items.append(
                ExtractionItem(
                    description=line,
                    category=cat,
                    source_quote=line,
                    classification="inferred" if is_ambiguous else "explicit",
                    confidence=0.68 if is_ambiguous else 0.94,
                    requires_confirmation=is_ambiguous,
                    kind="revision" if any(w in lower for w in ["change", "fix", "trim", "adjust", "remove"]) else "request",
                    memory_class=mem_class,
                )
            )

            # 4. Asset requirement detection
            if any(w in lower for w in ["logo", "mark", "brand asset"]):
                required_assets.append(AssetRequirement(name="Brand Logo Vector", category="logo"))
            if any(w in lower for w in ["music track", "soundtrack", "audio stem", "voiceover"]):
                required_assets.append(AssetRequirement(name="Audio Master Track", category="audio"))
            if any(w in lower for w in ["raw footage", "b-roll", "clip"]):
                required_assets.append(AssetRequirement(name="B-Roll Footage", category="footage"))

        summary = f"Extracted {len(items)} actionable creative requirements for review."
        return ExtractionResult(
            summary=summary,
            requests=items,
            ambiguities=ambiguities,
            questions=[],
            missing_information=[],
            production_risks=[],
            required_assets=required_assets,
        )

    async def transcribe_audio(self, path: str, filename: str, content_type: str) -> tuple[str, str]:
        """Transcribe an audio file path deterministically."""
        self.recorded_transcriptions.append((path, filename, content_type))
        if self.should_fail_transcription:
            raise ServiceUnavailable(self.failure_message)

        p = Path(path)
        if not p.is_file():
            raise ServiceUnavailable(f"Audio file not found at path {path}")

        size = p.stat().st_size
        if size == 0:
            raise ValueError("Empty transcription")

        fn_lower = filename.lower()
        if "color" in fn_lower:
            text = "Please enhance contrast and apply warm organic color balance to all interior shots."
        elif "pacing" in fn_lower or "trim" in fn_lower:
            text = "The intro pacing feels too slow, please trim 2 seconds from the opening sequence."
        elif "audio" in fn_lower or "music" in fn_lower:
            text = "Make the music transition punchier and align the cut to the beat at 14 seconds."
        else:
            text = "Please ensure the opening sequence has slow cinematic pacing and the color grade uses warm natural saturation."

        return text, "whisper-large-v3-turbo"
