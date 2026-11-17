from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Asset, ExtractedItem, ProcessingRun, Project


def _now_utc() -> datetime:
    return datetime.now(UTC)


CATEGORY_DISPLAY = {
    "reference": "Reference assets",
    "logo": "Brand logos",
    "font": "Fonts & typography",
    "audio": "Music & audio",
    "footage": "Video footage",
    "other": "Other production resources",
}


def normalize_category(cat: str, filename: str = "", content_type: str = "") -> str:
    raw = (cat or "").lower().strip()
    fn = (filename or "").lower().strip()
    ct = (content_type or "").lower().strip()

    if any(k in raw for k in ["logo", "mark", "brand_mark", "icon"]):
        return "logo"
    if any(k in raw for k in ["font", "typeface", "typography", "otf", "ttf", "woff"]):
        return "font"
    if any(k in raw for k in ["audio", "music", "song", "track", "sfx", "sound", "voiceover", "vo"]):
        return "audio"
    if any(k in raw for k in ["footage", "video", "broll", "b-roll", "clip", "raw", "scene"]):
        return "footage"
    if any(k in raw for k in ["reference", "brief", "guideline", "moodboard", "image", "doc", "overlay"]):
        return "reference"

    # Fallback to file extension / MIME type
    if fn.endswith((".woff", ".woff2", ".ttf", ".otf")):
        return "font"
    if fn.endswith((".svg", ".ai", ".eps")) or ("logo" in fn):
        return "logo"
    if fn.endswith((".mp3", ".wav", ".aac", ".flac", ".m4a")) or ct.startswith("audio/"):
        return "audio"
    if fn.endswith((".mp4", ".mov", ".mkv", ".braw", ".avi")) or ct.startswith("video/"):
        return "footage"
    if fn.endswith((".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".md")):
        return "reference"

    return "other"


def verify_asset_on_disk(storage_key: str) -> dict[str, Any]:
    """
    Evidence-based check: never claim an asset exists on disk unless there is actual evidence.
    """
    path = Path(storage_key).resolve()

    if not path.is_file():
        return {
            "exists_on_disk": False,
            "size_verified": False,
            "actual_size_bytes": 0,
            "verification_status": "Missing",
            "evidence": "File record exists in database, but physical file was not found in storage.",
        }

    try:
        stat = path.stat()
        if stat.st_size == 0:
            return {
                "exists_on_disk": True,
                "size_verified": False,
                "actual_size_bytes": 0,
                "verification_status": "Unverified",
                "evidence": "File exists on disk but is 0 bytes (empty file).",
            }
        return {
            "exists_on_disk": True,
            "size_verified": True,
            "actual_size_bytes": stat.st_size,
            "verification_status": "Present",
            "evidence": f"Verified in secure storage ({stat.st_size:,} bytes, modified {datetime.fromtimestamp(stat.st_mtime, UTC).strftime('%Y-%m-%d %H:%M UTC')}).",
        }
    except Exception as exc:
        return {
            "exists_on_disk": False,
            "size_verified": False,
            "actual_size_bytes": 0,
            "verification_status": "Unverified",
            "evidence": f"Storage inspection error: {exc}",
        }


def get_project_asset_intelligence(db: Session, project: Project, workspace_id: int) -> dict[str, Any]:
    """
    Builds comprehensive evidence-based asset tracking for a project.
    Distinguishes:
    - Present: verified on disk with matching file upload
    - Missing: explicitly required or marked missing
    - Unknown: extracted requirement without matching evidence
    - Unverified: file uploaded or referenced but physical/format evidence unconfirmed
    """
    # 1. Fetch all uploaded assets for this project
    asset_rows = db.scalars(
        select(Asset).where(Asset.project_id == project.id, Asset.workspace_id == workspace_id).order_by(Asset.created_at.desc())
    ).all()

    uploaded_list = []
    category_buckets: dict[str, list[dict]] = {
        "reference": [],
        "logo": [],
        "font": [],
        "audio": [],
        "footage": [],
        "other": [],
    }

    present_count = 0
    unverified_count = 0
    missing_count = 0
    unknown_count = 0

    for a in asset_rows:
        disk_check = verify_asset_on_disk(a.storage_key)
        cat_key = normalize_category(a.category, a.filename, a.content_type)
        status = disk_check["verification_status"]

        if status == "Present":
            present_count += 1
        elif status == "Unverified":
            unverified_count += 1
        else:
            missing_count += 1

        item = {
            "id": a.id,
            "filename": a.filename,
            "category": cat_key,
            "category_label": CATEGORY_DISPLAY.get(cat_key, "Other resources"),
            "original_category": a.category,
            "content_type": a.content_type,
            "size_bytes": a.size_bytes,
            "status": status,
            "evidence": disk_check["evidence"],
            "exists_on_disk": disk_check["exists_on_disk"],
            "download_url": f"/api/assets/{a.id}/download",
            "created_at": a.created_at.isoformat(),
        }
        uploaded_list.append(item)
        category_buckets[cat_key].append(item)

    # 2. Extract asset requirements from project's processing runs and extracted items
    runs = db.scalars(
        select(ProcessingRun).where(ProcessingRun.project_id == project.id, ProcessingRun.workspace_id == workspace_id)
    ).all()
    run_ids = [r.id for r in runs]

    requirements = []
    if run_ids:
        extractions = db.scalars(
            select(ExtractedItem).where(ExtractedItem.run_id.in_(run_ids))
        ).all()

        for ext in extractions:
            desc_lower = ext.description.lower()
            cat_lower = ext.category.lower()

            # Check if this extracted item is an asset requirement
            is_asset = any(k in cat_lower for k in ["asset", "logo", "font", "music", "audio", "footage", "video", "broll", "reference"]) or \
                       any(k in desc_lower for k in ["logo", "font", "soundtrack", "audio track", "b-roll", "footage", "aspect ratio", "brand guidelines", "vector"])

            if is_asset:
                req_cat = normalize_category(ext.category, ext.description)
                # Match against uploaded assets
                matching_asset = next(
                    (u for u in uploaded_list if u["category"] == req_cat or req_cat in u["filename"].lower() or any(w in u["filename"].lower() for w in ext.description.lower().split() if len(w) > 4)),
                    None
                )

                if matching_asset:
                    req_status = matching_asset["status"]
                    evidence_text = f"Matched uploaded asset '{matching_asset['filename']}' ({matching_asset['evidence']})"
                else:
                    if "missing" in desc_lower or "need" in desc_lower or "provide" in desc_lower or "send" in desc_lower:
                        req_status = "Missing"
                        evidence_text = f"Transcript quote: \"{ext.source_quote or ext.description}\" identifies this as needed."
                        missing_count += 1
                    else:
                        req_status = "Unknown"
                        evidence_text = "Referenced in transcript feedback but no matching file has been uploaded."
                        unknown_count += 1

                requirements.append({
                    "id": f"ext-{ext.id}",
                    "name": ext.description,
                    "category": req_cat,
                    "category_label": CATEGORY_DISPLAY.get(req_cat, "Other resources"),
                    "status": req_status,
                    "source_quote": ext.source_quote,
                    "confidence": ext.confidence,
                    "evidence": evidence_text,
                    "matched_asset_id": matching_asset["id"] if matching_asset else None,
                    "matched_filename": matching_asset["filename"] if matching_asset else None,
                    "requires_confirmation": ext.requires_confirmation,
                })

    total_requirements = len(requirements)
    total_uploaded = len(uploaded_list)
    total_tracked = total_requirements + total_uploaded

    # Calculate evidence-based readiness
    readiness_pct = round((present_count / total_tracked * 100), 1) if total_tracked > 0 else 0.0

    return {
        "project_id": project.id,
        "project_name": project.name,
        "summary": {
            "total_uploaded": total_uploaded,
            "total_requirements": total_requirements,
            "present_count": present_count,
            "missing_count": missing_count,
            "unknown_count": unknown_count,
            "unverified_count": unverified_count,
            "readiness_percentage": readiness_pct,
            "status_description": f"{present_count} verified present out of {total_tracked} tracked items ({readiness_pct}% coverage)",
        },
        "category_breakdown": [
            {
                "key": cat_key,
                "label": CATEGORY_DISPLAY[cat_key],
                "uploaded_count": len(category_buckets[cat_key]),
                "present_count": sum(1 for item in category_buckets[cat_key] if item["status"] == "Present"),
                "assets": category_buckets[cat_key],
            }
            for cat_key in ["reference", "logo", "font", "audio", "footage", "other"]
        ],
        "uploaded_assets": uploaded_list,
        "extracted_requirements": requirements,
    }
