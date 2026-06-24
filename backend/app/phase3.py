from __future__ import annotations

import os
import re
import base64
import json
import mimetypes
import shutil
import subprocess
import textwrap
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
from redis import Redis
from rq import Queue, Retry
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.main import Base, Product, SessionLocal, engine, get_db
from app.phase2 import ProductAnalysis, ProductAsset

router = APIRouter()

STORAGE_ROOT = Path(os.getenv("STORAGE_PATH", "/app/storage"))
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
FONT_FILE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_BASE_URL = os.getenv(
    "ELEVENLABS_BASE_URL",
    "https://api.elevenlabs.io",
).rstrip("/")
ELEVENLABS_MODEL_ID = os.getenv(
    "ELEVENLABS_MODEL_ID",
    "eleven_multilingual_v2",
).strip()
ELEVENLABS_OUTPUT_FORMAT = os.getenv(
    "ELEVENLABS_OUTPUT_FORMAT",
    "mp3_44100_128",
).strip()
ELEVENLABS_LANGUAGE_CODE = os.getenv(
    "ELEVENLABS_LANGUAGE_CODE",
    "id",
).strip()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta",
).rstrip("/")
GEMINI_VIDEO_MODEL = os.getenv(
    "GEMINI_VIDEO_MODEL",
    "veo-3.1-lite-generate-preview",
).strip()
GEMINI_VIDEO_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "GEMINI_VIDEO_FALLBACK_MODELS",
        (
            "veo-3.0-fast-generate-001,"
            "veo-3.0-generate-001"
        ),
    ).split(",")
    if model.strip()
]
GEMINI_IMAGE_MODEL = os.getenv(
    "GEMINI_IMAGE_MODEL",
    "gemini-2.5-flash-image",
).strip()
GEMINI_VIDEO_POLL_SECONDS = int(
    os.getenv("GEMINI_VIDEO_POLL_SECONDS", "10")
)
GEMINI_VIDEO_TIMEOUT_SECONDS = int(
    os.getenv("GEMINI_VIDEO_TIMEOUT_SECONDS", "1200")
)
RENDER_JOB_TIMEOUT_SECONDS = int(
    os.getenv("RENDER_JOB_TIMEOUT_SECONDS", "2400")
)
RAW_VEO_RETENTION_DAYS = int(
    os.getenv("RAW_VEO_RETENTION_DAYS", "30")
)


AUTOMATION_INTERNAL_TOKEN = os.getenv(
    "AUTOMATION_INTERNAL_TOKEN",
    "",
).strip()

AUTOMATION_RULE_PREFIX = (
    "product_ads:automation:rule:"
)

AUTOMATION_RULE_SET = (
    "product_ads:automation:rules"
)

AUTOMATION_DUE_SET = (
    "product_ads:automation:due"
)

AUTOMATION_LOG_KEY = (
    "product_ads:automation:logs"
)



class CreativeCampaign(Base):
    __tablename__ = "creative_campaigns"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="queued",
        index=True,
    )
    variations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    completed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    failed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class RenderJob(Base):
    __tablename__ = "render_jobs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("creative_campaigns.id", ondelete="CASCADE"),
        index=True,
    )
    variation_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="queued",
        index=True,
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    rq_job_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    output_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


Base.metadata.create_all(bind=engine)


class CampaignRequest(BaseModel):
    name: str | None = Field(
        default=None,
        max_length=300,
    )
    variations: int = Field(
        default=10,
        ge=1,
        le=50,
    )
    duration_seconds: int = Field(default=25)
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
    audience: Literal[
        "retail",
        "retail_bulk",
        "reseller",
        "custom_bulk",
    ] = "retail"
    min_order_qty: int = Field(
        default=6,
        ge=1,
        le=999,
    )
    render_mode: Literal[
        "hybrid",
        "ai_video",
        "slideshow",
    ] = "hybrid"
    ai_motion_style: Literal[
        "hand_demo",
        "desk_closeup",
        "hero_spin",
        "lifestyle",
    ] = "hand_demo"
    ai_prompt: str | None = Field(
        default=None,
        max_length=1600,
    )
    raw_master: bool = False
    product_ids: list[int] = Field(
        default_factory=list,
        max_length=12,
    )

    voiceover_enabled: bool = False
    voice_id: str | None = Field(
        default=None,
        max_length=150,
    )
    voiceover_mode: Literal["auto", "custom"] = "auto"
    voiceover_text: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator("duration_seconds")
    @classmethod
    def validate_duration(cls, value: int) -> int:
        if value not in {20, 25, 30}:
            raise ValueError(
                "Durasi harus 20, 25, atau 30 detik"
            )
        return value

    @field_validator("product_ids")
    @classmethod
    def validate_product_ids(cls, value: list[int]) -> list[int]:
        clean: list[int] = []

        for item in value:
            product_id = int(item)
            if product_id <= 0:
                continue
            if product_id not in clean:
                clean.append(product_id)

        if len(clean) > 12:
            raise ValueError("Maksimal 12 produk per campaign")

        return clean


class RawCatalogClipSelection(BaseModel):
    product_id: int = Field(
        ge=1,
    )
    clip_id: str = Field(
        min_length=1,
        max_length=120,
    )

    trim_start: float = Field(
        default=0.0,
        ge=0.0,
        le=3600.0,
    )

    trim_end: float | None = Field(
        default=None,
        ge=0.0,
        le=3600.0,
    )

    video_type: Literal[
        "hero",
        "demo",
        "detail",
        "lifestyle",
        "packaging",
        "testimonial",
    ] = "demo"

    fit_mode: Literal[
        "auto",
        "contain",
        "cover",
        "blur_fill",
    ] = "auto"




class RawVideoCatalogRequest(BaseModel):
    name: str | None = Field(
        default=None,
        max_length=300,
    )

    creative_template: Literal[
        "custom_manual",
        "retail_fast",
        "bundle_hemat",
        "reseller",
        "flash_sale",
        "product_showcase",
    ] = "bundle_hemat"
    variations: int = Field(
        default=1,
        ge=1,
        le=20,
    )
    duration_seconds: int = Field(default=25)
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"

    export_preset: Literal[
        "meta_reels",
        "tiktok",
        "instagram_feed",
        "youtube_landscape",
        "custom",
    ] = "meta_reels"
    audience: Literal[
        "retail",
        "retail_bulk",
        "reseller",
        "custom_bulk",
    ] = "retail_bulk"
    min_order_qty: int = Field(
        default=6,
        ge=1,
        le=999,
    )
    promo_enabled: bool = False
    promo_min_amount: int = Field(
        default=100000,
        ge=0,
        le=100000000,
    )
    promo_discount_percent: int = Field(
        default=10,
        ge=1,
        le=99,
    )
    promo_text: str | None = Field(
        default=None,
        max_length=240,
    )
    product_clips: list[RawCatalogClipSelection] = Field(
        min_length=5,
        max_length=6,
    )
    music_enabled: bool = False
    music_id: str | None = Field(
        default=None,
        max_length=120,
    )
    music_volume: float = Field(
        default=0.22,
        ge=0.05,
        le=1.0,
    )
    music_ducking: bool = True

    voiceover_enabled: bool = False
    voice_id: str | None = Field(
        default=None,
        max_length=150,
    )
    voiceover_mode: Literal["auto", "custom"] = "auto"
    voiceover_text: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator("duration_seconds")
    @classmethod
    def validate_duration(cls, value: int) -> int:
        if value not in {20, 25, 30}:
            raise ValueError(
                "Durasi harus 20, 25, atau 30 detik"
            )
        return value

    @field_validator("product_clips")
    @classmethod
    def validate_product_clips(
        cls,
        value: list[RawCatalogClipSelection],
    ) -> list[RawCatalogClipSelection]:
        product_ids: list[int] = []

        for item in value:
            if item.product_id in product_ids:
                raise ValueError(
                    "Setiap produk hanya boleh dipilih sekali"
                )
            product_ids.append(item.product_id)

        return value


class RawVideoAssetSettingsRequest(BaseModel):
    video_type: Literal[
        "hero",
        "demo",
        "detail",
        "lifestyle",
        "packaging",
        "testimonial",
    ] = "demo"

    fit_mode: Literal[
        "auto",
        "contain",
        "cover",
        "blur_fill",
    ] = "auto"


    is_primary: bool = False

    trim_start: float = Field(
        default=0.0,
        ge=0.0,
        le=3600.0,
    )

    trim_end: float | None = Field(
        default=None,
        ge=0.0,
        le=3600.0,
    )

    @field_validator("trim_end")
    @classmethod
    def validate_trim_end(
        cls,
        value: float | None,
    ) -> float | None:
        if value is None:
            return None

        return round(float(value), 3)


class VoicePreviewRequest(BaseModel):
    voice_id: str = Field(
        min_length=1,
        max_length=150,
    )
    text: str = Field(
        default=(
            "Produk unik dari Spacecraft. "
            "Lihat detailnya dan pesan sekarang."
        ),
        min_length=1,
        max_length=500,
    )


class ImageVariationRequest(BaseModel):
    source_kind: Literal["asset", "primary", "url"] = "primary"
    source_asset_id: int | None = None
    source_url: str | None = Field(
        default=None,
        max_length=2000,
    )
    count: int = Field(
        default=10,
        ge=1,
        le=10,
    )
    preset: Literal[
        "background_only",
        "lifestyle_desk",
        "hand_holding",
        "gift_display",
        "macro_detail",
        "marketplace_clean",
        "social_ads_hero",
    ] = "background_only"
    custom_prompt: str | None = Field(
        default=None,
        max_length=1200,
    )


def redis_connection() -> Redis:
    return Redis.from_url(REDIS_URL)


def render_queue() -> Queue:
    return Queue(
        "renders",
        connection=redis_connection(),
        default_timeout=RENDER_JOB_TIMEOUT_SECONDS,
    )


def now() -> datetime:
    return datetime.now(timezone.utc)


def raw_veo_archive_root(
    product_id: int,
) -> Path:
    return (
        STORAGE_ROOT
        / "products"
        / str(product_id)
        / "raw-veo-masters"
    )


def cleanup_expired_raw_veo_archives() -> None:
    if RAW_VEO_RETENTION_DAYS <= 0:
        return

    root = STORAGE_ROOT / "products"

    if not root.is_dir():
        return

    cutoff = now() - timedelta(
        days=RAW_VEO_RETENTION_DAYS
    )

    for archive_dir in root.glob(
        "*/raw-veo-masters/campaign-*"
    ):
        if not archive_dir.is_dir():
            continue

        manifest_path = archive_dir / "manifest.json"
        created_at: datetime | None = None

        if manifest_path.is_file():
            try:
                manifest = json.loads(
                    manifest_path.read_text(
                        encoding="utf-8",
                    )
                )
                value = manifest.get("created_at")
                if value:
                    created_at = datetime.fromisoformat(
                        str(value)
                    )
            except Exception:
                created_at = None

        if created_at is None:
            created_at = datetime.fromtimestamp(
                archive_dir.stat().st_mtime,
                tz=timezone.utc,
            )

        if created_at < cutoff:
            shutil.rmtree(
                archive_dir,
                ignore_errors=True,
            )


def archive_raw_veo_clip(
    source_path: Path,
    product_id: int | None,
    campaign_id: int | None,
    config: dict[str, Any] | None = None,
) -> Path | None:
    if (
        product_id is None
        or campaign_id is None
        or not source_path.is_file()
        or source_path.stat().st_size < 10_000
    ):
        return None

    cleanup_expired_raw_veo_archives()

    archive_dir = (
        raw_veo_archive_root(product_id)
        / f"campaign-{campaign_id}"
    )

    archive_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    archive_path = archive_dir / "raw-veo-clean.mp4"

    if (
        not archive_path.is_file()
        or archive_path.stat().st_size < 10_000
    ):
        shutil.copyfile(
            source_path,
            archive_path,
        )

    manifest_path = archive_dir / "manifest.json"
    created_at = now()

    if manifest_path.is_file():
        try:
            existing_manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8",
                )
            )
            existing_created_at = existing_manifest.get(
                "created_at"
            )
            if existing_created_at:
                created_at = datetime.fromisoformat(
                    str(existing_created_at)
                )
        except Exception:
            pass

    try:
        source_label = str(
            source_path.relative_to(STORAGE_ROOT)
        )
    except ValueError:
        source_label = str(source_path)

    manifest = {
        "type": "raw_veo_clean_master",
        "product_id": product_id,
        "campaign_id": campaign_id,
        "created_at": created_at.isoformat(),
        "retention_days": RAW_VEO_RETENTION_DAYS,
        "expires_at": (
            created_at
            + timedelta(days=RAW_VEO_RETENTION_DAYS)
        ).isoformat(),
        "source": source_label,
        "archive": str(
            archive_path.relative_to(STORAGE_ROOT)
        ),
        "model": (
            (config or {})
            .get("ai_video", {})
            .get("model")
        ),
        "motion_style": (
            (config or {})
            .get("ai_video", {})
            .get("motion_style")
        ),
        "note": (
            "Raw Veo clean clip tanpa overlay, VO, "
            "CTA, atau slideshow. Aman dipakai ulang "
            "sebagai master video."
        ),
    }

    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return archive_path


def raw_veo_clip_manifest(
    product_id: int,
    clip_id: str,
) -> dict[str, Any] | None:
    if (
        not clip_id.startswith("campaign-")
        or "/" in clip_id
        or "\\" in clip_id
        or ".." in clip_id
    ):
        return None

    manifest_path = (
        raw_veo_archive_root(product_id)
        / clip_id
        / "manifest.json"
    )

    if not manifest_path.is_file():
        return None

    try:
        manifest = json.loads(
            manifest_path.read_text(
                encoding="utf-8",
            )
        )
    except Exception:
        return None

    archive = str(
        manifest.get("archive")
        or ""
    ).strip()

    if not archive:
        return None

    archive_path = STORAGE_ROOT / archive

    try:
        archive_path.resolve().relative_to(
            STORAGE_ROOT.resolve()
        )
    except ValueError:
        return None

    if (
        not archive_path.is_file()
        or archive_path.stat().st_size < 10_000
    ):
        return None

    manifest["clip_id"] = clip_id
    manifest["archive"] = archive
    manifest["size_bytes"] = archive_path.stat().st_size
    manifest["url"] = f"/media/{archive}"

    return manifest


def list_raw_veo_clips(
    product_id: int,
) -> list[dict[str, Any]]:
    cleanup_expired_raw_veo_archives()

    root = raw_veo_archive_root(product_id)

    if not root.is_dir():
        return []

    clips: list[dict[str, Any]] = []

    for directory in sorted(
        root.glob("campaign-*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ):
        if not directory.is_dir():
            continue

        manifest = raw_veo_clip_manifest(
            product_id,
            directory.name,
        )

        if manifest:
            clips.append(manifest)

    return clips



class AutomationRuleRequest(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=200,
    )

    enabled: bool = True

    schedule_type: Literal[
        "manual",
        "once",
        "daily",
        "weekly",
    ] = "manual"

    run_at: datetime | None = None

    webhook_url: str | None = Field(
        default=None,
        max_length=2000,
    )

    campaign_payload: dict[str, Any]


class AutomationRuleToggleRequest(BaseModel):
    enabled: bool




class RenderReviewRequest(BaseModel):
    status: Literal[
        "draft",
        "review",
        "approved",
        "rejected",
    ] = "draft"

    rating: int = Field(
        default=0,
        ge=0,
        le=5,
    )

    notes: str | None = Field(
        default=None,
        max_length=2000,
    )

    winner: bool = False


def normalize_render_review(
    value: Any,
) -> dict[str, Any]:
    source = (
        value
        if isinstance(value, dict)
        else {}
    )

    status = str(
        source.get("status")
        or "draft"
    ).strip().lower()

    if status not in {
        "draft",
        "review",
        "approved",
        "rejected",
    }:
        status = "draft"

    try:
        rating = int(
            source.get("rating")
            or 0
        )
    except (TypeError, ValueError):
        rating = 0

    return {
        "status": status,
        "rating": max(0, min(rating, 5)),
        "notes": str(
            source.get("notes")
            or ""
        ).strip(),
        "winner": bool(
            source.get("winner")
        ),
        "updated_at": source.get(
            "updated_at"
        ),
    }




def automation_redis() -> Redis:
    return redis_connection()


def automation_decode(
    value: bytes | str | None,
) -> str:
    if value is None:
        return ""

    if isinstance(value, bytes):
        return value.decode(
            "utf-8",
            errors="replace",
        )

    return str(value)


def automation_rule_key(
    rule_id: str,
) -> str:
    return (
        f"{AUTOMATION_RULE_PREFIX}"
        f"{rule_id}"
    )


def automation_parse_datetime(
    value: Any,
) -> datetime | None:
    if value in {None, ""}:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(timezone.utc)


def automation_next_run(
    schedule_type: str,
    previous_run: datetime | None,
) -> datetime | None:
    if schedule_type == "manual":
        return None

    if previous_run is None:
        return None

    if schedule_type == "once":
        return None

    if schedule_type == "daily":
        return previous_run + timedelta(days=1)

    if schedule_type == "weekly":
        return previous_run + timedelta(days=7)

    return None


def automation_load_rule(
    rule_id: str,
) -> dict[str, Any] | None:
    redis_client = automation_redis()

    raw = redis_client.get(
        automation_rule_key(rule_id)
    )

    if not raw:
        return None

    try:
        value = json.loads(
            automation_decode(raw)
        )
    except json.JSONDecodeError:
        return None

    return (
        value
        if isinstance(value, dict)
        else None
    )


def automation_save_rule(
    rule: dict[str, Any],
) -> None:
    redis_client = automation_redis()
    rule_id = str(rule["id"])

    redis_client.set(
        automation_rule_key(rule_id),
        json.dumps(
            rule,
            ensure_ascii=False,
        ),
    )

    redis_client.sadd(
        AUTOMATION_RULE_SET,
        rule_id,
    )

    redis_client.zrem(
        AUTOMATION_DUE_SET,
        rule_id,
    )

    next_run_at = automation_parse_datetime(
        rule.get("next_run_at")
    )

    if (
        rule.get("enabled")
        and next_run_at is not None
    ):
        redis_client.zadd(
            AUTOMATION_DUE_SET,
            {
                rule_id:
                    next_run_at.timestamp()
            },
        )


def automation_public_rule(
    rule: dict[str, Any],
) -> dict[str, Any]:
    payload = dict(rule)

    campaign_payload = payload.get(
        "campaign_payload"
    )

    if isinstance(campaign_payload, dict):
        payload["campaign_summary"] = {
            "name": campaign_payload.get(
                "name"
            ),
            "template": campaign_payload.get(
                "creative_template"
            ),
            "variations": campaign_payload.get(
                "variations"
            ),
            "product_count": len(
                campaign_payload.get(
                    "product_clips"
                )
                or []
            ),
            "aspect_ratio": campaign_payload.get(
                "aspect_ratio"
            ),
            "export_preset": campaign_payload.get(
                "export_preset"
            ),
        }

    payload.pop(
        "campaign_payload",
        None,
    )

    return payload


def automation_write_log(
    *,
    rule_id: str,
    status: str,
    message: str,
    campaign_id: int | None = None,
) -> dict[str, Any]:
    item = {
        "id": uuid.uuid4().hex,
        "rule_id": rule_id,
        "status": status,
        "message": message,
        "campaign_id": campaign_id,
        "created_at": now().isoformat(),
    }

    redis_client = automation_redis()

    redis_client.lpush(
        AUTOMATION_LOG_KEY,
        json.dumps(
            item,
            ensure_ascii=False,
        ),
    )

    redis_client.ltrim(
        AUTOMATION_LOG_KEY,
        0,
        499,
    )

    return item


def automation_send_webhook(
    webhook_url: str | None,
    body: dict[str, Any],
) -> None:
    url = str(
        webhook_url or ""
    ).strip()

    if not url:
        return

    try:
        with httpx.Client(
            timeout=20.0,
            follow_redirects=True,
        ) as client:
            response = client.post(
                url,
                json=body,
            )

            response.raise_for_status()
    except Exception as exc:
        automation_write_log(
            rule_id=str(
                body.get("rule_id")
                or ""
            ),
            status="webhook_failed",
            message=str(exc)[:500],
            campaign_id=body.get(
                "campaign_id"
            ),
        )



def campaign_to_dict(
    campaign: CreativeCampaign,
    jobs: list[RenderJob] | None = None,
) -> dict[str, Any]:
    payload = {
        "id": campaign.id,
        "product_id": campaign.product_id,
        "name": campaign.name,
        "status": campaign.status,
        "variations": campaign.variations,
        "completed_count": campaign.completed_count,
        "failed_count": campaign.failed_count,
        "settings": campaign.settings,
        "created_at": (
            campaign.created_at.isoformat()
            if campaign.created_at
            else None
        ),
        "updated_at": (
            campaign.updated_at.isoformat()
            if campaign.updated_at
            else None
        ),
    }

    if jobs is not None:
        payload["jobs"] = [
            job_to_dict(job)
            for job in jobs
        ]

    return payload


def job_to_dict(job: RenderJob) -> dict[str, Any]:
    config = (
        job.config
        if isinstance(job.config, dict)
        else {}
    )

    thumbnail_path = str(
        config.get("thumbnail_path")
        or ""
    ).strip()

    return {
        "id": job.id,
        "variation_index": job.variation_index,
        "status": job.status,
        "config": config,
        "qa": config.get("qa"),
        "review": normalize_render_review(
            config.get("review")
        ),
        "thumbnail_url": (
            f"/media/{thumbnail_path}"
            if thumbnail_path
            else None
        ),
        "output_url": (
            f"/media/{job.output_path}"
            if job.output_path
            else None
        ),
        "error_message": job.error_message,
        "started_at": (
            job.started_at.isoformat()
            if job.started_at
            else None
        ),
        "finished_at": (
            job.finished_at.isoformat()
            if job.finished_at
            else None
        ),
    }


def image_sources(
    product: Product,
    assets: list[ProductAsset],
) -> list[dict[str, str]]:
    """
    Return image sources ordered by fidelity.

    Priority:
    1. Product primary image from the original catalog.
    2. Original/uploaded local product assets.
    3. Other catalog media.
    4. AI-generated image variations.

    This prevents raw AI video from accidentally using a generated
    variation as the authoritative product reference.
    """
    result: list[dict[str, str]] = []

    def append_unique(source: dict[str, str]) -> None:
        if source not in result:
            result.append(source)

    if product.primary_image_url:
        append_unique({
            "kind": "remote",
            "url": product.primary_image_url,
        })

    original_assets = [
        asset
        for asset in assets
        if (
            asset.asset_type == "image"
            and str(getattr(asset, "source", "") or "").lower()
            != "generated"
        )
    ]

    generated_assets = [
        asset
        for asset in assets
        if (
            asset.asset_type == "image"
            and str(getattr(asset, "source", "") or "").lower()
            == "generated"
        )
    ]

    for asset in original_assets:
        append_unique({
            "kind": "local",
            "path": asset.relative_path,
        })

    for item in (product.payload or {}).get("media", []):
        if (
            item.get("type") == "image"
            and item.get("url")
        ):
            append_unique({
                "kind": "remote",
                "url": item["url"],
            })

    for asset in generated_assets:
        append_unique({
            "kind": "local",
            "path": asset.relative_path,
        })

    return result


def product_collection_name(
    products: list[Product],
) -> str:
    if len(products) <= 1:
        return products[0].name

    names = [product.name for product in products[:3]]
    suffix = (
        ""
        if len(products) <= 3
        else f" + {len(products) - 3} produk lain"
    )

    return "Bundle " + ", ".join(names) + suffix


def format_rupiah(value: float | int) -> str:
    amount = int(round(float(value)))
    return "Rp" + f"{amount:,}".replace(",", ".")


def product_collection_price_label(
    products: list[Product],
) -> str:
    numeric = [
        float(product.price_value)
        for product in products
        if product.price_value is not None
    ]

    if numeric:
        lowest = min(numeric)
        highest = max(numeric)
        if lowest == highest:
            return f"Mulai {format_rupiah(lowest)}"
        return (
            f"{format_rupiah(lowest)} - "
            f"{format_rupiah(highest)}"
        )

    labels = [
        product.price_label
        for product in products
        if product.price_label
    ]

    return labels[0] if labels else "Cek harga di katalog"


def raw_catalog_promo_label(
    payload: RawVideoCatalogRequest,
) -> str | None:
    if not payload.promo_enabled:
        return None

    custom = (
        payload.promo_text
        or ""
    ).strip()

    if custom:
        return custom

    return (
        f"Promo: Diskon {payload.promo_discount_percent}% "
        f"untuk pembelian di atas "
        f"{format_rupiah(payload.promo_min_amount)}"
    )


def spoken_collection_price(
    products: list[Product],
) -> str:
    numeric = [
        int(round(float(product.price_value)))
        for product in products
        if product.price_value is not None
    ]

    if numeric:
        lowest = min(numeric)
        highest = max(numeric)
        if lowest == highest:
            return (
                "mulai "
                + number_to_indonesian(lowest).strip()
                + " rupiah"
            )
        return (
            number_to_indonesian(lowest).strip()
            + " sampai "
            + number_to_indonesian(highest).strip()
            + " rupiah"
        )

    return "harga dapat dilihat di katalog"


def combined_selling_point(
    products: list[Product],
    analyses: dict[int, ProductAnalysis],
) -> str:
    points: list[str] = []

    for product in products[:4]:
        point = first_selling_point(
            product,
            analyses.get(product.id),
        )
        if point and point not in points:
            points.append(point)

    if not points:
        return "pilihan produk unik dan menarik dari SpaceCraft"

    return "; ".join(points)[:260]


def enrich_sources_with_product(
    sources: list[dict[str, str]],
    product: Product,
) -> list[dict[str, str]]:
    enriched: list[dict[str, str]] = []

    for source in sources:
        item = dict(source)
        item["product_id"] = str(product.id)
        item["product_name"] = product.name
        enriched.append(item)

    return enriched


def reference_sources_for_products(
    all_sources: list[dict[str, str]],
    products: list[Product],
    max_items: int = 6,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    seen_products: set[str] = set()

    for product in products:
        product_key = str(product.id)
        source = next(
            (
                item
                for item in all_sources
                if item.get("product_id") == product_key
            ),
            None,
        )
        if source:
            selected.append(source)
            seen_products.add(product_key)

    for source in all_sources:
        if len(selected) >= max_items:
            break
        key = json.dumps(
            source,
            sort_keys=True,
        )
        if key not in {
            json.dumps(item, sort_keys=True)
            for item in selected
        }:
            selected.append(source)

    return selected[:max_items]


def creative_text(
    product: Product,
    analysis: ProductAnalysis | None,
    audience: str = "retail",
    min_order_qty: int = 6,
) -> tuple[list[str], list[str]]:
    hooks: list[str] = []
    ctas: list[str] = []

    if analysis and analysis.result:
        hooks = [
            str(item.get("text", "")).strip()
            for item in analysis.result.get("hooks", [])
            if item.get("text")
        ]

        ctas = [
            str(item).strip()
            for item in analysis.result.get(
                "cta_options",
                [],
            )
            if item
        ]

    audience_hooks: list[str] = []
    audience_ctas: list[str] = []

    if audience == "retail_bulk":
        audience_hooks = [
            "Bisa beli satuan, tapi makin seru kalau dibuat bundle.",
            "Cari hadiah kecil yang bisa dipilih satuan atau beberapa varian?",
            "Ambil satu boleh, tambah beberapa varian juga menarik.",
            "Cocok untuk koleksi pribadi, gift bundle, atau souvenir kecil.",
            f"{product.name} bisa jadi pilihan satuan atau paket kecil.",
        ]
        audience_ctas = [
            "Cek opsi satuan atau bundle",
            "Tanya harga bundle hemat",
            "Pilih satuan atau beberapa varian",
            "Pilih varian dan jumlahnya",
            "Lanjut tanya stok dan warna",
        ]
    elif audience == "reseller":
        audience_hooks = [
            "Cari produk unik untuk dijual ulang?",
            "Mulai jualan produk 3D print tanpa punya mesin.",
            f"{product.name} bisa jadi item menarik untuk katalog reseller.",
            "Produk kecil, visual unik, cocok untuk etalase marketplace.",
            "Tambah pilihan produk unik untuk toko atau dropship kamu.",
        ]
        audience_ctas = [
            "Tanya paket reseller Spacecraft",
            "Mulai jadi reseller",
            "Minta katalog reseller",
            "Cek harga reseller",
            "Diskusi peluang jualan",
        ]
    elif audience == "custom_bulk":
        audience_hooks = [
            "Butuh souvenir custom untuk komunitas atau event?",
            "Buat merchandise kecil yang beda dari souvenir biasa.",
            "Cocok untuk event, komunitas, sekolah, atau brand kecil.",
            "Dari ide custom sampai produk jadi, bisa dibantu Spacecraft.",
            "Pesanan banyak bisa dibuat lebih personal.",
        ]
        audience_ctas = [
            "Kirim brief custom",
            "Tanya estimasi pesanan bulk",
            "Diskusi kebutuhan event",
            "Minta penawaran custom",
            "Mulai konsultasi custom order",
        ]

    fallback_hooks = [
        "Produk kecil yang bikin orang langsung penasaran.",
        "Lihat detail unik produk ini dari dekat.",
        "Kelihatannya simpel, tapi hasilnya menarik.",
        f"Kenalan dengan {product.name}.",
        "Cari hadiah unik yang tidak pasaran?",
        "Satu produk, banyak alasan untuk suka.",
        "Detail kecilnya membuat produk ini berbeda.",
        "Cocok untuk koleksi atau hadiah personal.",
        "Tampil beda dengan produk kreatif ini.",
        "Lihat sampai akhir untuk detail produknya.",
    ]

    fallback_ctas = [
        "Lihat detail di Spacecraft",
        "Cek produknya sekarang",
        "Pesan melalui katalog Spacecraft",
        "Temukan pilihan lengkapnya",
        "Klik untuk melihat detail",
    ]

    hooks = audience_hooks + hooks + fallback_hooks
    ctas = audience_ctas + ctas + fallback_ctas

    return hooks, ctas



def creative_template_label(
    template: str | None,
) -> str:
    labels = {
        "custom_manual": "Custom Manual",
        "retail_fast": "Retail Cepat Closing",
        "bundle_hemat": "Bundle Hemat",
        "reseller": "Reseller",
        "flash_sale": "Flash Sale",
        "product_showcase": "Product Showcase",
    }

    return labels.get(
        str(template or ""),
        "Custom Manual",
    )


def creative_template_text(
    template: str | None,
    products: list[Product],
) -> tuple[list[str], list[str]]:
    template_value = str(
        template or "custom_manual"
    ).strip()

    product_names = ", ".join(
        product.name
        for product in products[:3]
    )

    product_count = len(products)

    if template_value == "retail_fast":
        return (
            [
                "Lucu, unik, dan siap bikin orang langsung penasaran.",
                "Lihat pilihan produk kecil yang susah dilewatkan.",
                "Produk unik seperti ini cocok jadi hadiah dadakan.",
                f"{product_count} pilihan menarik dalam satu video.",
                "Jangan tunggu kehabisan varian favorit.",
            ],
            [
                "Pesan sekarang melalui WhatsApp",
                "Pilih produk favoritmu sekarang",
                "Tanya stok sebelum kehabisan",
                "Klik dan lanjutkan pemesanan",
                "Amankan pilihanmu hari ini",
            ],
        )

    if template_value == "bundle_hemat":
        return (
            [
                "Ambil satu boleh, bundle beberapa produk lebih hemat.",
                "Bikin gift set unik dari beberapa pilihan favorit.",
                f"Gabungkan {product_names} dalam satu bundle menarik.",
                "Semakin banyak pilihan, semakin seru bundlenya.",
                "Cari hadiah kecil dengan banyak pilihan produk?",
            ],
            [
                "Tanya harga bundle hemat",
                "Pilih isi bundle favoritmu",
                "Pesan satuan atau langsung bundle",
                "Cek promo bundle hari ini",
                "Kirim pilihan produkmu sekarang",
            ],
        )

    if template_value == "reseller":
        return (
            [
                "Cari produk unik untuk menambah isi katalog jualan?",
                "Produk kecil dengan visual kuat untuk seller marketplace.",
                "Mulai jualan tanpa harus punya mesin 3D print.",
                f"{product_count} pilihan produk siap masuk katalog reseller.",
                "Tambah produk yang beda dari toko lain.",
            ],
            [
                "Minta katalog harga reseller",
                "Tanya paket reseller Spacecraft",
                "Mulai jualan produk ini",
                "Cek minimum order reseller",
                "Diskusikan peluang reseller sekarang",
            ],
        )

    if template_value == "flash_sale":
        return (
            [
                "Flash Sale! Pilih produk favorit sebelum promonya selesai.",
                "Harga spesial terbatas untuk beberapa pilihan produk.",
                "Promo singkat untuk produk unik yang paling banyak dilihat.",
                "Jangan lewatkan harga khusus hari ini.",
                "Waktunya checkout sebelum promo berakhir.",
            ],
            [
                "Ambil promo sekarang",
                "Pesan sebelum harga kembali normal",
                "Klik dan gunakan promo hari ini",
                "Amankan produk favoritmu",
                "Tanya stok promo sekarang",
            ],
        )

    if template_value == "product_showcase":
        return (
            [
                "Lihat detail setiap produk dari dekat.",
                "Beberapa desain unik dalam satu showcase.",
                f"Kenalan dengan {product_names}.",
                "Perhatikan bentuk, warna, dan detail produknya.",
                "Pilihan produk kreatif dari Spacecraft.",
            ],
            [
                "Lihat detail produk di Spacecraft",
                "Pilih desain yang paling kamu suka",
                "Cek koleksi lengkapnya",
                "Temukan produk favoritmu",
                "Tanya detail dan ketersediaan",
            ],
        )

    return [], []


def merge_unique_creative_text(
    preferred: list[str],
    fallback: list[str],
) -> list[str]:
    result: list[str] = []

    for value in [*preferred, *fallback]:
        clean = str(value or "").strip()

        if clean and clean not in result:
            result.append(clean)

    return result



def creative_text_for_collection(
    products: list[Product],
    analyses: dict[int, ProductAnalysis],
    audience: str = "retail",
    min_order_qty: int = 6,
) -> tuple[list[str], list[str]]:
    if len(products) <= 1:
        product = products[0]
        return creative_text(
            product,
            analyses.get(product.id),
            audience,
            min_order_qty,
        )

    collection_name = product_collection_name(products)
    product_names = ", ".join(
        product.name
        for product in products[:3]
    )

    hooks = [
        f"Beberapa pilihan unik SpaceCraft dalam satu video.",
        f"Lihat kombinasi {product_names} dari dekat.",
        "Cari gift kecil yang bisa dipilih satuan atau bundle?",
        "Satu etalase produk kreatif untuk koleksi atau hadiah.",
        f"{collection_name} cocok untuk pilihan bundle hemat.",
    ]

    if audience == "reseller":
        hooks = [
            "Cari beberapa produk unik untuk isi katalog reseller?",
            "Tambah varian 3D print yang mudah ditawarkan ulang.",
            f"Lihat pilihan produk SpaceCraft: {product_names}.",
            "Produk kecil, visual kuat, cocok untuk etalase marketplace.",
            "Buat toko kamu punya pilihan produk yang lebih beda.",
        ] + hooks
    elif audience == "custom_bulk":
        hooks = [
            "Butuh beberapa opsi souvenir untuk event atau komunitas?",
            "Bandingkan pilihan merchandise kecil dalam satu video.",
            "Dari ide custom sampai pilihan produk jadi, bisa dibantu.",
            "Cocok untuk kebutuhan hadiah, event, komunitas, atau brand.",
        ] + hooks
    elif audience == "retail_bulk":
        hooks = [
            "Bisa pilih satuan, bisa juga dibuat bundle hemat.",
            "Ambil satu boleh, tambah beberapa varian juga menarik.",
            "Pilih beberapa produk kecil untuk gift set yang lebih seru.",
        ] + hooks

    ctas = [
        "Pilih produk favoritmu",
        "Tanya opsi bundle hemat",
        "Cek detail di spacecraft.id",
        "Tanya stok dan varian",
        "Lanjut pilih satuan atau bundle",
    ]

    if audience == "reseller":
        ctas = [
            "Minta katalog reseller",
            "Tanya paket reseller",
            "Cek harga reseller",
        ] + ctas
    elif audience == "custom_bulk":
        ctas = [
            "Kirim brief custom",
            "Minta penawaran bulk",
            "Diskusi kebutuhan event",
        ] + ctas

    for product in products:
        product_hooks, product_ctas = creative_text(
            product,
            analyses.get(product.id),
            audience,
            min_order_qty,
        )
        hooks.extend(product_hooks[:2])
        ctas.extend(product_ctas[:2])

    return hooks, ctas


def number_to_indonesian(value: int) -> str:
    value = int(value)

    words = [
        "",
        "satu",
        "dua",
        "tiga",
        "empat",
        "lima",
        "enam",
        "tujuh",
        "delapan",
        "sembilan",
        "sepuluh",
        "sebelas",
    ]

    if value < 0:
        return "minus " + number_to_indonesian(abs(value))
    if value < 12:
        return words[value]
    if value < 20:
        return number_to_indonesian(value - 10) + " belas"
    if value < 100:
        tens, rest = divmod(value, 10)
        result = number_to_indonesian(tens) + " puluh"
        return (
            result
            if rest == 0
            else result + " " + number_to_indonesian(rest)
        )
    if value < 200:
        rest = value - 100
        return (
            "seratus"
            if rest == 0
            else "seratus " + number_to_indonesian(rest)
        )
    if value < 1000:
        hundreds, rest = divmod(value, 100)
        result = number_to_indonesian(hundreds) + " ratus"
        return (
            result
            if rest == 0
            else result + " " + number_to_indonesian(rest)
        )
    if value < 2000:
        rest = value - 1000
        return (
            "seribu"
            if rest == 0
            else "seribu " + number_to_indonesian(rest)
        )
    if value < 1_000_000:
        thousands, rest = divmod(value, 1000)
        result = number_to_indonesian(thousands) + " ribu"
        return (
            result
            if rest == 0
            else result + " " + number_to_indonesian(rest)
        )
    if value < 1_000_000_000:
        millions, rest = divmod(value, 1_000_000)
        result = number_to_indonesian(millions) + " juta"
        return (
            result
            if rest == 0
            else result + " " + number_to_indonesian(rest)
        )

    billions, rest = divmod(value, 1_000_000_000)
    result = number_to_indonesian(billions) + " miliar"
    return (
        result
        if rest == 0
        else result + " " + number_to_indonesian(rest)
    )


def spoken_price(product: Product) -> str:
    if product.price_value is not None:
        rounded = int(round(float(product.price_value)))
        return (
            number_to_indonesian(rounded).strip()
            + " rupiah"
        )

    return (
        product.price_label
        or "harga dapat dilihat di katalog"
    )


def first_selling_point(
    product: Product,
    analysis: ProductAnalysis | None,
) -> str:
    if analysis and analysis.result:
        points = analysis.result.get(
            "selling_points",
            [],
        )

        if points:
            return str(points[0]).strip()

    source = (
        product.short_description
        or product.description
        or "desain unik dan menarik"
    )

    first = source.split(".", 1)[0].strip()
    return first[:180]


def replace_placeholders(
    value: str,
    replacements: dict[str, str],
) -> str:
    result = value

    for key, replacement in replacements.items():
        result = result.replace(
            "{" + key + "}",
            replacement,
        )

    return result


def limit_words(
    value: str,
    max_words: int,
) -> str:
    words = value.split()

    if len(words) <= max_words:
        return value.strip()

    shortened = " ".join(words[:max_words]).rstrip(
        " ,;:-"
    )

    if shortened[-1:] not in ".!?":
        shortened += "."

    return shortened


def build_voiceover_script(
    product: Product,
    analysis: ProductAnalysis | None,
    hook: str,
    cta: str,
    duration_seconds: int,
    mode: str,
    custom_text: str | None,
    audience: str,
    min_order_qty: int,
    products: list[Product] | None = None,
    analyses: dict[int, ProductAnalysis] | None = None,
) -> str:
    products = products or [product]
    analyses = analyses or {}
    is_multi_product = len(products) > 1
    product_name = product_collection_name(products)
    price = (
        spoken_collection_price(products)
        if is_multi_product
        else spoken_price(product)
    )
    selling_point = limit_words(
        (
            combined_selling_point(
                products,
                analyses,
            )
            if is_multi_product
            else first_selling_point(
                product,
                analysis,
            )
        ),
        {
            10: 8,
            15: 12,
            20: 22,
            30: 24,
        }.get(duration_seconds, 12),
    )

    replacements = {
        "hook": hook,
        "product": product_name,
        "price": price,
        "cta": cta,
        "selling_point": selling_point,
    }

    if mode == "custom" and custom_text:
        script = replace_placeholders(
            custom_text.strip(),
            replacements,
        )
    elif is_multi_product and audience == "retail_bulk":
        script = (
            f"{hook} Ini pilihan produk 3D print dari Spacecraft. "
            "Bisa pilih satuan, atau kombinasikan beberapa item "
            f"jadi bundle hemat. {selling_point}. {cta}."
        )
    elif is_multi_product and audience == "reseller":
        script = (
            f"{hook} Ini beberapa produk Spacecraft untuk isi katalog. "
            "Cocok untuk reseller, marketplace, toko hadiah, "
            f"atau toko aksesori. {selling_point}. {cta}."
        )
    elif is_multi_product and audience == "custom_bulk":
        script = (
            f"{hook} Ini beberapa referensi produk 3D print "
            "untuk merchandise, souvenir event, komunitas, "
            f"atau brand kecil. {selling_point}. {cta}."
        )
    elif is_multi_product:
        script = (
            f"{hook} Ini beberapa pilihan produk 3D print "
            f"dari Spacecraft. {selling_point}. "
            f"Harga {price}. {cta}."
        )
    elif audience == "retail_bulk":
        script = (
            f"{hook} Ini {product.name}. "
            f"Bisa dibeli satuan, dan kalau ambil beberapa varian "
            f"bisa jadi bundle hemat untuk hadiah, koleksi, "
            f"atau souvenir kecil. "
            f"Harganya {price}. {cta}."
        )
    elif audience == "reseller":
        script = (
            f"{hook} Ini {product.name}. "
            f"Produk unik seperti ini cocok untuk seller marketplace, "
            f"dropshipper, toko hadiah, atau toko aksesori. "
            f"{selling_point}. {cta}."
        )
    elif audience == "custom_bulk":
        script = (
            f"{hook} Ini {product.name}. "
            f"Bisa jadi referensi untuk merchandise custom, souvenir event, "
            f"komunitas, sekolah, atau brand kecil. "
            f"{selling_point}. {cta}."
        )
    elif duration_seconds <= 10:
        script = (
            f"{hook} Ini {product.name}. "
            f"Harganya {price}. {cta}."
        )
    elif duration_seconds <= 15:
        script = (
            f"{hook} Ini {product.name}. "
            f"{selling_point}. "
            f"Harganya {price}. {cta}."
        )
    elif duration_seconds <= 20:
        material = (
            product.material
            or "material pilihan"
        )
        script = (
            f"{hook} Kenalan dengan {product.name}. "
            f"{selling_point}. "
            f"Ukurannya mungil, detailnya rapi, "
            f"dan cocok jadi aksesori koleksi atau hadiah kecil. "
            f"Dibuat menggunakan {material}. "
            f"Harganya {price}. {cta}."
        )
    else:
        material = (
            product.material
            or "material pilihan"
        )
        script = (
            f"{hook} Kenalan dengan {product.name}. "
            f"{selling_point}. "
            f"Dibuat menggunakan {material}, "
            f"dengan detail yang menarik untuk "
            f"koleksi pribadi atau hadiah. "
            f"Harganya {price}. {cta}."
        )

    max_words = {
        10: 24,
        15: 34,
        20: 62,
        30: 62,
    }.get(duration_seconds, 34)

    return limit_words(
        " ".join(script.split()),
        max_words,
    )


def build_ai_video_prompt(
    product: Product,
    analysis: ProductAnalysis | None,
    hook: str,
    cta: str,
    style: str,
    custom_prompt: str | None,
    audience: str,
    min_order_qty: int,
    products: list[Product] | None = None,
    analyses: dict[int, ProductAnalysis] | None = None,
) -> str:
    products = products or [product]
    analyses = analyses or {}

    custom_direction = str(
        custom_prompt or ""
    ).strip()

    fidelity_lock = (
        "RAW_MASTER_FIDELITY_LOCK"
        in custom_direction.upper()
    )

    clean_raw_master = (
        "RAW_MASTER_CLEAN_CONTEXTUAL"
        in custom_direction.upper()
    )

    if clean_raw_master:
        product_name = str(product.name or "product").strip()
        product_name_lower = product_name.lower()

        identity_lock = (
            "Use the supplied reference image as the absolute source of "
            "truth. Preserve the exact same product in every frame: exact "
            "silhouette, shape, geometry, proportions, thickness, number "
            "of parts, face, eyes, mouth, expression, colors, surface "
            "texture, printed details, articulation points, buttons, "
            "holes, loops, chain, keyring, decorations, seams, edges, "
            "and every visible small detail. Do not redesign, recolor, "
            "replace, simplify, duplicate, add, or remove any product "
            "component. The product must remain rigid 3D-printed plastic. "
            "No morphing, melting, stretching, squeezing, bending, "
            "inflating, softening, food texture, or transformation. "
        )

        camera_rule = (
            "Use one continuous clean image-to-video shot. Keep the "
            "product large, centered, fully visible, sharp, and well lit. "
            "Use only subtle camera movement and natural realistic motion. "
            "No scene cuts, no text, no captions, no subtitles, no price, "
            "no product description, no CTA, no logo, no watermark, no "
            "voice-over, no packaging, and no unrelated objects. "
        )

        if "clicker" in product_name_lower:
            action = (
                "Show one realistic adult hand entering slowly and pressing "
                "only the intended clicker mechanism two or three times. "
                "Each press must look mechanically plausible. The product "
                "body, face, silhouette, legs, colors, and all components "
                "must remain unchanged and rigid. Do not squash or deform "
                "the product while clicking. "
            )
        elif "fidget" in product_name_lower:
            action = (
                "Show one realistic adult hand gently demonstrating the "
                "intended fidget mechanism without covering the product "
                "and without changing its shape or components. "
            )
        else:
            action = (
                "Show a subtle realistic product demonstration while the "
                "product identity remains perfectly unchanged. "
            )

        if (
            "keychain" in product_name_lower
            or "key chain" in product_name_lower
            or "gantungan" in product_name_lower
        ):
            action += (
                "After the product demonstration, briefly show the existing "
                "keychain loop or chain naturally attached to a simple bag "
                "strap. Use only the keychain hardware already visible in "
                "the reference image. Do not invent a new loop, chain, hook, "
                "or accessory. Keep the product fully recognizable. "
            )

        prompt = (
            f"Create a clean raw image-to-video product demonstration for "
            f"{product_name}. "
            + identity_lock
            + action
            + camera_rule
            + "Temporal consistency is mandatory. The first frame, middle "
            + "frames, and final frame must all show the exact same physical "
            + "product from the reference image."
        )

        return " ".join(prompt.split())

    if fidelity_lock:
        clean_direction = re.sub(
            r"RAW_MASTER_FIDELITY_LOCK",
            "",
            custom_direction,
            flags=re.IGNORECASE,
        ).strip(" .,-")

        prompt = (
            f"Animate the supplied reference image of {product.name}. "
            "The reference image is the absolute and authoritative source "
            "of truth. This is image-to-video animation, not product "
            "redesign, not concept generation, and not a new product. "

            "IDENTITY LOCK: preserve the exact original product identity "
            "in every frame. Keep exactly the same outer silhouette, "
            "geometry, proportions, dimensions, thickness, layer count, "
            "part count, component positions, spacing, orientation, color "
            "layout, surface texture, printed details, facial features, "
            "eyes, mouth, expression, decoration, holes, keychain loop, "
            "chain, buttons, seams, grooves, edges, and all small details "
            "visible in the reference image. "

            "Do not invent any unseen side, hidden component, additional "
            "decoration, brand mark, feature, limb, face, button, hole, "
            "layer, accessory, or duplicate product. Do not remove or "
            "replace any existing component. "

            "The product must remain a rigid physical 3D-printed plastic "
            "object. It must never morph, transform, bend, stretch, squash, "
            "inflate, shrink, melt, wobble, jiggle, become soft, become "
            "food-like, become organic, or change material. "

            "MOTION RESTRICTION: the product itself stays completely still "
            "and unchanged. Animate only the camera and lighting. Use one "
            "continuous shot with an extremely subtle slow camera push-in "
            "or very small parallax movement. Maximum apparent camera angle "
            "change is five degrees. Keep the same visible side of the "
            "product throughout the entire video. Do not rotate the product. "
            "Do not reveal a new backside or unseen geometry. "

            "No hands, no fingers, no people, no interaction, no pressing, "
            "no touching, no picking up, no spinning platform, no dramatic "
            "orbit, no scene transition, no cuts, and no camera whip. "

            "Keep the product centered, fully visible, sharply focused, "
            "well lit, and approximately the same size in frame. Preserve "
            "the original background unless only a subtle studio lighting "
            "improvement is required. "

            "Generate a clean silent raw product master. No text, captions, "
            "subtitles, CTA, price, logo, watermark, fake packaging, or "
            "additional objects. Temporal consistency is mandatory: every "
            "frame must depict the exact same physical product."
        )

        if clean_direction:
            prompt += (
                " Optional safe camera or lighting direction: "
                + clean_direction
                + ". This optional direction must never override the "
                "identity lock or motion restrictions."
            )

        return " ".join(prompt.split())

    is_multi_product = len(products) > 1

    selling_point = (
        combined_selling_point(
            products,
            analyses,
        )
        if is_multi_product
        else first_selling_point(
            product,
            analysis,
        )
    )

    style_prompts = {
        "hand_demo": (
            "An adult hand carefully holds the rigid product without "
            "covering, pressing, bending, or changing any product detail. "
            "The product must remain visually identical to the reference."
        ),
        "desk_closeup": (
            "Use a single continuous tabletop close-up with subtle camera "
            "push-in. Keep the product stationary and preserve its exact "
            "reference geometry and visible details."
        ),
        "hero_spin": (
            "Use only a very small camera arc around the product. Do not "
            "rotate or redesign the product and do not reveal invented "
            "hidden geometry."
        ),
        "lifestyle": (
            "Place the unchanged rigid product in a simple realistic "
            "setting. Do not alter its shape, colors, parts, or details."
        ),
    }

    if is_multi_product:
        product_lines = "; ".join(
            item.name
            for item in products[:8]
        )

        prompt = (
            "Create a realistic short product video featuring these "
            f"products: {product_lines}. The uploaded reference image is "
            "the authoritative source for every product. Preserve each "
            "product's exact silhouette, geometry, proportions, color "
            "layout, material, part count, facial details, decoration, "
            "buttons, holes, and accessories in every frame. "
            f"{style_prompts.get(style, style_prompts['desk_closeup'])} "
            f"Collection benefit: {selling_point}. "
            f"Creative concept: {hook}. CTA concept: {cta}. "
            "Do not morph, deform, redesign, duplicate incorrectly, add "
            "parts, remove parts, change colors, or invent hidden geometry. "
            "No readable text, subtitles, watermark, or fake labels."
        )
    else:
        prompt = (
            f"Create a realistic short product video for {product.name}. "
            "Use the uploaded product image as the authoritative source of "
            "truth. Preserve the exact product silhouette, geometry, "
            "proportions, thickness, part count, layer count, colors, "
            "material, facial features, printed details, holes, buttons, "
            "keychain parts, decoration, and all visible small details in "
            "every frame. "
            f"{style_prompts.get(style, style_prompts['desk_closeup'])} "
            f"Product benefit: {selling_point}. "
            f"Creative concept: {hook}. CTA concept: {cta}. "
            "The product is rigid plastic. Do not morph, deform, bend, "
            "compress, melt, redesign, recolor, add parts, remove parts, "
            "change the face, duplicate the object, or invent unseen "
            "geometry. No readable text, subtitles, watermark, or labels."
        )

    if custom_direction:
        prompt += (
            " Extra direction: "
            + custom_direction
            + ". This direction must not override product identity."
        )

    return " ".join(prompt.split())


def build_variation_config(
    product: Product,
    analysis: ProductAnalysis | None,
    source: dict[str, str],
    sources: list[dict[str, str]],
    hook: str,
    cta: str,
    index: int,
    request: CampaignRequest,
    products: list[Product] | None = None,
    analyses: dict[int, ProductAnalysis] | None = None,
) -> dict[str, Any]:
    products = products or [product]
    analyses = analyses or {}
    collection_name = product_collection_name(products)
    price_label = (
        product_collection_price_label(products)
        if len(products) > 1
        else (product.price_label or "Cek harga di katalog")
    )
    reference_sources = reference_sources_for_products(
        sources,
        products,
    )

    motions = [
        "zoom_in",
        "zoom_out",
        "pan_left",
        "pan_right",
        "soft_zoom",
    ]

    layouts = [
        "top_focus",
        "center_focus",
        "bottom_focus",
    ]

    voiceover_script = None

    if request.voiceover_enabled:
        voiceover_script = build_voiceover_script(
            product=product,
            analysis=analysis,
            hook=hook,
            cta=cta,
            duration_seconds=request.duration_seconds,
            mode=request.voiceover_mode,
            custom_text=request.voiceover_text,
            audience=request.audience,
            min_order_qty=request.min_order_qty,
            products=products,
            analyses=analyses,
        )

    return {
        "product_name": collection_name,
        "product_names": [
            item.name
            for item in products
        ],
        "product_ids": [
            item.id
            for item in products
        ],
        "product_count": len(products),
        "price_label": price_label,
        "product_url": product.product_url,
        "hook": hook,
        "cta": cta,
        "audience": request.audience,
        "min_order_qty": request.min_order_qty,
        "source": source,
        "reference_sources": reference_sources,
        "slideshow_sources": (
            sources[index % len(sources):]
            + sources[:index % len(sources)]
        )[:8],
        "motion": motions[index % len(motions)],
        "layout": layouts[index % len(layouts)],
        "duration_seconds": request.duration_seconds,
        "aspect_ratio": request.aspect_ratio,
        "render_mode": request.render_mode,
        "raw_master": bool(request.raw_master),
        "ai_video": {
            "provider": "gemini_veo",
            "model": GEMINI_VIDEO_MODEL,
            "motion_style": request.ai_motion_style,
            "prompt": build_ai_video_prompt(
                product=product,
                analysis=analysis,
                hook=hook,
                cta=cta,
                style=request.ai_motion_style,
                custom_prompt=request.ai_prompt,
                audience=request.audience,
                min_order_qty=request.min_order_qty,
                products=products,
                analyses=analyses,
            ),
        },
        "voiceover": {
            "enabled": bool(
                request.voiceover_enabled
            ),
            "voice_id": request.voice_id,
            "script": voiceover_script,
            "model_id": ELEVENLABS_MODEL_ID,
            "language_code": (
                ELEVENLABS_LANGUAGE_CODE
            ),
        },
    }


def refresh_campaign(
    db: Session,
    campaign_id: int,
) -> None:
    campaign = db.get(
        CreativeCampaign,
        campaign_id,
    )

    if campaign is None:
        return

    rows = list(
        db.scalars(
            select(RenderJob).where(
                RenderJob.campaign_id
                == campaign_id
            )
        ).all()
    )

    completed = sum(
        row.status == "completed"
        for row in rows
    )

    failed = sum(
        row.status == "failed"
        for row in rows
    )

    active = sum(
        row.status in {"queued", "rendering"}
        for row in rows
    )

    campaign.completed_count = completed
    campaign.failed_count = failed

    if active:
        campaign.status = (
            "rendering"
            if any(
                row.status == "rendering"
                for row in rows
            )
            else "queued"
        )
    elif failed and completed:
        campaign.status = "partial"
    elif failed and not completed:
        campaign.status = "failed"
    else:
        campaign.status = "completed"

    campaign.updated_at = now()
    db.commit()


def wrap(
    value: str,
    width: int,
) -> str:
    return "\n".join(
        textwrap.wrap(
            value.strip(),
            width=width,
            break_long_words=False,
            break_on_hyphens=False,
        )
    )


def dimensions(
    aspect_ratio: str,
) -> tuple[int, int]:
    if aspect_ratio == "1:1":
        return 720, 720
    if aspect_ratio == "16:9":
        return 1280, 720
    return 720, 1280


def prepare_source(
    source: dict[str, str],
    temp_dir: Path,
) -> Path:
    if source.get("kind") == "local":
        path = STORAGE_ROOT / source["path"]

        if not path.is_file():
            raise RuntimeError(
                "Asset lokal tidak ditemukan: "
                + source["path"]
            )

        return path

    url = source.get("url")

    if not url:
        raise RuntimeError("URL gambar kosong")

    suffix = Path(
        url.split("?", 1)[0]
    ).suffix.lower()

    if suffix not in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
    }:
        suffix = ".jpg"

    destination = (
        temp_dir / f"source-{uuid.uuid4().hex}{suffix}"
    )

    with httpx.stream(
        "GET",
        url,
        follow_redirects=True,
        timeout=60,
    ) as response:
        response.raise_for_status()
        total = 0

        with destination.open("wb") as output:
            for chunk in response.iter_bytes(
                1024 * 1024
            ):
                total += len(chunk)

                if total > 40 * 1024 * 1024:
                    raise RuntimeError(
                        "Gambar sumber melebihi 40 MB"
                    )

                output.write(chunk)

    return destination


def prepare_reference_source(
    config: dict[str, Any],
    temp_dir: Path,
) -> Path:
    reference_sources = config.get("reference_sources") or []

    if len(reference_sources) <= 1:
        return prepare_source(
            reference_sources[0]
            if reference_sources
            else config["source"],
            temp_dir,
        )

    source_paths = [
        prepare_source(source, temp_dir)
        for source in reference_sources[:6]
    ]

    return compose_reference_collage(
        source_paths,
        temp_dir,
    )


def compose_reference_collage(
    source_paths: list[Path],
    temp_dir: Path,
) -> Path:
    if len(source_paths) == 1:
        return source_paths[0]

    cell = 640
    count = len(source_paths)
    cols = 2 if count <= 4 else 3
    rows = (count + cols - 1) // cols
    output_path = temp_dir / "multi-product-reference.jpg"

    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    layout: list[str] = []

    for index, path in enumerate(source_paths):
        inputs.extend(["-loop", "1", "-t", "1", "-i", str(path)])
        label = f"p{index}"
        labels.append(f"[{label}]")
        filters.append(
            f"[{index}:v]scale={cell}:{cell}:"
            "force_original_aspect_ratio=decrease,"
            f"pad={cell}:{cell}:(ow-iw)/2:(oh-ih)/2:"
            "color=white,setsar=1"
            f"[{label}]"
        )
        x = (index % cols) * cell
        y = (index // cols) * cell
        layout.append(f"{x}_{y}")

    filter_complex = (
        ";".join(filters)
        + ";"
        + "".join(labels)
        + f"xstack=inputs={count}:layout={'|'.join(layout)}:"
        + f"fill=white,scale={cols * cell}:{rows * cell}"
    )

    command = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=180,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Gagal membuat reference collage: "
            + result.stderr[-1200:]
        )

    if (
        not output_path.is_file()
        or output_path.stat().st_size < 10_000
    ):
        raise RuntimeError(
            "Reference collage multi produk tidak valid"
        )

    return output_path


def redact_api_key(message: str) -> str:
    if GEMINI_API_KEY:
        return message.replace(
            GEMINI_API_KEY,
            "[REDACTED]",
        )

    return message


def gemini_model_path(
    model_name: str | None = None,
) -> str:
    model = (
        model_name
        or GEMINI_VIDEO_MODEL
    ).strip()

    if model.startswith("models/"):
        return model

    return f"models/{model}"


def gemini_video_model_candidates(
    config: dict[str, Any],
) -> list[str]:
    configured = (
        (config.get("ai_video") or {}).get("model")
        or GEMINI_VIDEO_MODEL
    )

    candidates: list[str] = []

    for model in [
        configured,
        GEMINI_VIDEO_MODEL,
        *GEMINI_VIDEO_FALLBACK_MODELS,
    ]:
        value = str(model or "").strip()

        if value and value not in candidates:
            candidates.append(value)

    return candidates


def should_try_next_veo_model(
    error: Exception,
) -> bool:
    message = str(error).lower()

    retry_markers = [
        "429",
        "quota",
        "resource_exhausted",
        "rate limit",
        "rate-limits",
        "not found",
        "not_found",
        "not supported",
        "unsupported",
        "permission",
    ]

    return any(
        marker in message
        for marker in retry_markers
    )


def gemini_url(path: str) -> str:
    return f"{GEMINI_BASE_URL}/{path.lstrip('/')}"


def source_mime_type(path: Path) -> str:
    mime, _ = mimetypes.guess_type(
        str(path)
    )

    return mime or "image/jpeg"


def find_video_base64(
    value: Any,
) -> str | None:
    if isinstance(value, dict):
        mime = str(
            value.get("mimeType")
            or value.get("mime_type")
            or ""
        )

        for key in (
            "bytesBase64Encoded",
            "bytes_base64_encoded",
            "videoBytes",
            "bytesBase64",
            "data",
        ):
            candidate = value.get(key)

            if (
                isinstance(candidate, str)
                and len(candidate) > 1000
                and (
                    not mime
                    or "video" in mime.lower()
                )
            ):
                return candidate

        for item in value.values():
            found = find_video_base64(item)

            if found:
                return found

    if isinstance(value, list):
        for item in value:
            found = find_video_base64(item)

            if found:
                return found

    return None


def find_video_uri(
    value: Any,
) -> str | None:
    if isinstance(value, dict):
        for key in (
            "uri",
            "url",
            "fileUri",
            "downloadUri",
            "downloadUrl",
        ):
            candidate = value.get(key)

            if (
                isinstance(candidate, str)
                and candidate
            ):
                return candidate

        for item in value.values():
            found = find_video_uri(item)

            if found:
                return found

    if isinstance(value, list):
        for item in value:
            found = find_video_uri(item)

            if found:
                return found

    return None


def find_image_inline_data(
    value: Any,
) -> tuple[str, str] | None:
    if isinstance(value, dict):
        inline = (
            value.get("inlineData")
            or value.get("inline_data")
        )

        if isinstance(inline, dict):
            data = inline.get("data")
            mime = (
                inline.get("mimeType")
                or inline.get("mime_type")
                or "image/png"
            )

            if (
                isinstance(data, str)
                and len(data) > 1000
                and str(mime).startswith("image/")
            ):
                return str(data), str(mime)

        for key in (
            "bytesBase64Encoded",
            "bytes_base64_encoded",
            "imageBytes",
            "bytesBase64",
            "data",
        ):
            candidate = value.get(key)
            mime = str(
                value.get("mimeType")
                or value.get("mime_type")
                or ""
            )

            if (
                isinstance(candidate, str)
                and len(candidate) > 1000
                and (
                    not mime
                    or mime.startswith("image/")
                )
            ):
                return candidate, mime or "image/png"

        for item in value.values():
            found = find_image_inline_data(item)

            if found:
                return found

    if isinstance(value, list):
        for item in value:
            found = find_image_inline_data(item)

            if found:
                return found

    return None


def build_image_variation_prompt(
    product: Product,
    preset: str,
    index: int,
    custom_prompt: str | None,
) -> str:
    preset_prompts = {
        "background_only": (
            "Change only the background, surface, lighting, "
            "crop, and advertising composition. Keep the product "
            "front-facing and clearly visible."
        ),
        "lifestyle_desk": (
            "Place the product on a clean modern desk scene with "
            "subtle props, natural daylight, and shallow depth of field."
        ),
        "hand_holding": (
            "Show an adult hand lightly holding the product without "
            "pressing, bending, squeezing, or covering important details."
        ),
        "gift_display": (
            "Place the product in a cute gift display scene with tidy "
            "wrapping accents and warm studio lighting."
        ),
        "macro_detail": (
            "Create a close product detail composition with crisp plastic "
            "texture, button area visible, and clean studio background."
        ),
        "marketplace_clean": (
            "Create a clean marketplace product photo with a bright neutral "
            "background, soft shadow, and high product clarity."
        ),
        "social_ads_hero": (
            "Create a social ads hero image with bold background color, "
            "clean negative space, and strong product focus."
        ),
    }

    prompt = (
        f"Edit the provided source image for {product.name}. "
        "Use the source image as an exact product reference. "
        "Do not alter the product shape, silhouette, color, size, "
        "button placement, printed details, material, or proportions. "
        "The product is a rigid plastic 3D printed item, not soft, "
        "not squishy, not edible, and must not bend, melt, deform, "
        "or look like real food. "
        f"{preset_prompts.get(preset, preset_prompts['background_only'])} "
        "Only change the background, surrounding scene, lighting, "
        "surface, camera crop, and safe props around the product. "
        "Do not add text, captions, watermarks, logos, or extra labels. "
        f"Variation number {index + 1}: use a distinct but realistic "
        "background and composition from other variations."
    )

    if custom_prompt:
        prompt += " Extra art direction: " + custom_prompt.strip()

    return " ".join(prompt.split())


def generate_gemini_image_variation(
    source_path: Path,
    product: Product,
    preset: str,
    index: int,
    destination: Path,
    custom_prompt: str | None = None,
) -> tuple[Path, str]:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY belum dikonfigurasi"
        )

    image_bytes = source_path.read_bytes()

    if len(image_bytes) > 20 * 1024 * 1024:
        raise RuntimeError(
            "Source image melebihi 20 MB"
        )

    model = GEMINI_IMAGE_MODEL

    if not model.startswith("models/"):
        model = f"models/{model}"

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": build_image_variation_prompt(
                            product=product,
                            preset=preset,
                            index=index,
                            custom_prompt=custom_prompt,
                        )
                    },
                    {
                        "inlineData": {
                            "mimeType": source_mime_type(
                                source_path
                            ),
                            "data": base64.b64encode(
                                image_bytes
                            ).decode("ascii"),
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "responseModalities": [
                "IMAGE",
            ],
        },
    }

    response = httpx.post(
        gemini_url(f"{model}:generateContent"),
        params={"key": GEMINI_API_KEY},
        json=payload,
        timeout=180,
        follow_redirects=True,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Gemini image variation HTTP "
            f"{response.status_code}: "
            + redact_api_key(
                response.text[:1200]
            )
        )

    found = find_image_inline_data(
        response.json()
    )

    if not found:
        raise RuntimeError(
            "Gemini tidak mengembalikan image data"
        )

    image_base64, mime_type = found
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    destination.write_bytes(
        base64.b64decode(image_base64)
    )

    if (
        not destination.is_file()
        or destination.stat().st_size < 5_000
    ):
        raise RuntimeError(
            "Generated image tidak valid"
        )

    return destination, mime_type


def download_gemini_video_uri(
    uri: str,
    destination: Path,
) -> None:
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
    }

    if uri.startswith("http://") or uri.startswith("https://"):
        urls = [uri]
    else:
        clean = uri.lstrip("/")
        urls = [
            gemini_url(f"{clean}:download"),
            gemini_url(clean),
        ]

    last_error = ""

    for url in urls:
        try:
            response = httpx.get(
                url,
                headers=headers,
                params={
                    "key": GEMINI_API_KEY,
                    "alt": "media",
                },
                timeout=300,
                follow_redirects=True,
            )

            if response.status_code == 200:
                destination.write_bytes(
                    response.content
                )
                return

            last_error = (
                f"HTTP {response.status_code}: "
                f"{response.text[:800]}"
            )
        except Exception as error:
            last_error = str(error)

    raise RuntimeError(
        "Gagal download video Gemini/Veo: "
        + redact_api_key(last_error)
    )


def generate_gemini_product_video_with_model(
    config: dict[str, Any],
    source_path: Path,
    destination: Path,
    model_name: str,
) -> Path:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY belum dikonfigurasi"
        )

    image_bytes = source_path.read_bytes()

    if len(image_bytes) > 20 * 1024 * 1024:
        raise RuntimeError(
            "Gambar untuk AI video melebihi 20 MB"
        )

    ai_config = config.get("ai_video") or {}

    instance = {
        "prompt": str(
            ai_config.get("prompt")
            or config.get("hook")
            or ""
        ),
        "image": {
            "bytesBase64Encoded": base64.b64encode(
                image_bytes
            ).decode("ascii"),
            "mimeType": source_mime_type(
                source_path
            ),
        },
    }

    payload = {
        "instances": [instance],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": config.get(
                "aspect_ratio",
                "9:16",
            ),
            "personGeneration": "allow_adult",
        },
    }

    start_url = gemini_url(
        f"{gemini_model_path(model_name)}:predictLongRunning"
    )

    try:
        response = httpx.post(
            start_url,
            params={"key": GEMINI_API_KEY},
            json=payload,
            timeout=120,
            follow_redirects=True,
        )
    except Exception as error:
        raise RuntimeError(
            "Gagal menghubungi Gemini/Veo: "
            + str(error)
        ) from error

    if response.status_code != 200:
        raise RuntimeError(
            "Gemini/Veo start render HTTP "
            f"{response.status_code}: "
            f"model={model_name} "
            + redact_api_key(
                response.text[:1200]
            )
        )

    operation = response.json()
    operation_name = operation.get("name")

    if not operation_name:
        raise RuntimeError(
            "Gemini/Veo tidak mengembalikan operation name"
        )

    deadline = (
        time.monotonic()
        + GEMINI_VIDEO_TIMEOUT_SECONDS
    )

    while not operation.get("done"):
        if time.monotonic() >= deadline:
            raise RuntimeError(
                "Timeout menunggu video Gemini/Veo selesai"
            )

        time.sleep(
            max(2, GEMINI_VIDEO_POLL_SECONDS)
        )

        operation_url = (
            operation_name
            if operation_name.startswith("http")
            else gemini_url(operation_name)
        )

        poll = httpx.get(
            operation_url,
            params={"key": GEMINI_API_KEY},
            timeout=60,
            follow_redirects=True,
        )

        if poll.status_code != 200:
            raise RuntimeError(
                "Gemini/Veo poll HTTP "
                f"{poll.status_code}: "
                f"model={model_name} "
                + redact_api_key(
                    poll.text[:1200]
                )
            )

        operation = poll.json()

        if operation.get("error"):
            raise RuntimeError(
                "Gemini/Veo render gagal: "
                f"model={model_name} "
                + redact_api_key(
                    str(operation["error"])[:1200]
                )
            )

    video_base64 = find_video_base64(
        operation
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if video_base64:
        destination.write_bytes(
            base64.b64decode(video_base64)
        )
    else:
        uri = find_video_uri(operation)

        if not uri:
            raise RuntimeError(
                "Gemini/Veo selesai, tetapi file video "
                "tidak ditemukan dalam response"
            )

        download_gemini_video_uri(
            uri,
            destination,
        )

    if (
        not destination.is_file()
        or destination.stat().st_size < 10_000
    ):
        raise RuntimeError(
            "Video Gemini/Veo tidak valid"
        )

    return destination


def generate_gemini_product_video(
    config: dict[str, Any],
    source_path: Path,
    destination: Path,
) -> Path:
    errors: list[str] = []
    candidates = gemini_video_model_candidates(
        config
    )

    for index, model_name in enumerate(candidates):
        try:
            return generate_gemini_product_video_with_model(
                config=config,
                source_path=source_path,
                destination=destination,
                model_name=model_name,
            )
        except Exception as error:
            errors.append(str(error))

            if (
                index == len(candidates) - 1
                or not should_try_next_veo_model(error)
            ):
                break

    raise RuntimeError(
        "Semua model Gemini/Veo gagal. "
        + " | ".join(errors)[-3000:]
    )


def motion_expression(
    motion: str,
    frames: int = 450,
) -> tuple[str, str, str]:
    frame_count = max(1, frames)

    if motion == "zoom_out":
        return (
            "if(eq(on,0),1.090,max(1.0,zoom-0.00045))",
            "iw/2-(iw/zoom/2)",
            "ih/2-(ih/zoom/2)",
        )

    if motion == "pan_left":
        return (
            "min(zoom+0.00032,1.075)",
            (
                "(iw-iw/zoom)*"
                f"(0.62-0.24*on/{frame_count})"
            ),
            "ih/2-(ih/zoom/2)",
        )

    if motion == "pan_right":
        return (
            "min(zoom+0.00032,1.075)",
            (
                "(iw-iw/zoom)*"
                f"(0.38+0.24*on/{frame_count})"
            ),
            "ih/2-(ih/zoom/2)",
        )

    if motion == "soft_zoom":
        return (
            "min(zoom+0.00030,1.070)",
            "iw/2-(iw/zoom/2)",
            "ih/2-(ih/zoom/2)",
        )

    return (
        "min(zoom+0.00042,1.090)",
        "iw/2-(iw/zoom/2)",
        "ih/2-(ih/zoom/2)",
    )


def elevenlabs_headers() -> dict[str, str]:
    return {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }


def fetch_elevenlabs_voices() -> list[dict[str, Any]]:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError(
            "ELEVENLABS_API_KEY belum dikonfigurasi"
        )

    response = httpx.get(
        f"{ELEVENLABS_BASE_URL}/v2/voices",
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Accept": "application/json",
        },
        params={
            "page_size": 100,
            "sort": "name",
            "sort_direction": "asc",
            "include_total_count": "false",
        },
        timeout=60,
        follow_redirects=True,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs HTTP {response.status_code}: "
            f"{response.text[:800]}"
        )

    data = response.json()
    result = []

    for voice in data.get("voices", []):
        result.append({
            "voice_id": voice.get("voice_id"),
            "name": voice.get("name") or "Unnamed Voice",
            "category": voice.get("category"),
            "description": voice.get("description"),
            "preview_url": voice.get("preview_url"),
            "labels": voice.get("labels") or {},
        })

    return [
        voice
        for voice in result
        if voice.get("voice_id")
    ]


def generate_elevenlabs_audio(
    voice_id: str,
    text: str,
    destination: Path,
) -> Path:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError(
            "ELEVENLABS_API_KEY belum dikonfigurasi"
        )

    if not voice_id:
        raise RuntimeError(
            "Voice ElevenLabs belum dipilih"
        )

    payload: dict[str, Any] = {
        "text": text,
        "model_id": ELEVENLABS_MODEL_ID,
    }

    if ELEVENLABS_LANGUAGE_CODE:
        payload["language_code"] = (
            ELEVENLABS_LANGUAGE_CODE
        )

    endpoint = (
        f"{ELEVENLABS_BASE_URL}"
        f"/v1/text-to-speech/{voice_id}"
    )

    response = httpx.post(
        endpoint,
        headers=elevenlabs_headers(),
        params={
            "output_format": (
                ELEVENLABS_OUTPUT_FORMAT
            ),
        },
        json=payload,
        timeout=180,
        follow_redirects=True,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs TTS HTTP "
            f"{response.status_code}: "
            f"{response.text[:1000]}"
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination.write_bytes(
        response.content
    )

    if (
        not destination.is_file()
        or destination.stat().st_size < 1000
    ):
        raise RuntimeError(
            "Audio ElevenLabs tidak valid"
        )

    return destination


def prepare_voiceover(
    config: dict[str, Any],
    temp_dir: Path,
) -> Path | None:
    voiceover = (
        config.get("voiceover")
        or {}
    )

    if not voiceover.get("enabled"):
        return None

    text = str(
        voiceover.get("script")
        or ""
    ).strip()

    if not text:
        raise RuntimeError(
            "Naskah voice-over kosong"
        )

    return generate_elevenlabs_audio(
        voice_id=str(
            voiceover.get("voice_id")
            or ""
        ),
        text=text,
        destination=(
            temp_dir / "voiceover.mp3"
        ),
    )


def media_duration_seconds(
    path: Path,
) -> float | None:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        return None

    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def atempo_chain(
    speed: float,
) -> list[str]:
    speed = max(0.5, min(speed, 4.0))
    filters: list[str] = []

    while speed > 2.0:
        filters.append("atempo=2.000")
        speed /= 2.0

    while speed < 0.5:
        filters.append("atempo=0.500")
        speed /= 0.5

    filters.append(f"atempo={speed:.3f}")
    return filters


def voiceover_filter_chain(
    voiceover_path: Path,
    duration: int,
) -> str:
    fade_start = max(
        duration - 0.45,
        0,
    )

    filters = [
        "aresample=44100",
        (
            "aformat=sample_fmts=fltp:"
            "channel_layouts=stereo"
        ),
        "highpass=f=80",
        "lowpass=f=14500",
        "loudnorm=I=-15:LRA=9:TP=-1.5",
    ]

    actual_duration = media_duration_seconds(
        voiceover_path
    )

    target_duration = max(
        1.0,
        duration - 0.75,
    )

    if (
        actual_duration
        and actual_duration > target_duration
    ):
        filters.extend(
            atempo_chain(
                actual_duration / target_duration
            )
        )
    elif (
        actual_duration
        and actual_duration < target_duration * 0.94
    ):
        filters.extend(
            atempo_chain(
                actual_duration / target_duration
            )
        )

    filters.extend([
        f"apad=pad_dur={duration}",
        f"atrim=0:{duration}",
        "afade=t=in:st=0:d=0.12",
        f"afade=t=out:st={fade_start}:d=0.4",
    ])

    return (
        "[1:a]"
        + ",".join(filters)
        + "[a]"
    )


def render_slideshow_video(
    config: dict[str, Any],
    output_path: Path,
    temp_dir: Path,
    voiceover_path: Path | None = None,
) -> None:
    slideshow_sources = [
        item
        for item in (config.get("slideshow_sources") or [])
        if isinstance(item, dict)
    ]

    if len(slideshow_sources) > 1:
        render_multi_product_slideshow_video(
            config=config,
            sources=slideshow_sources,
            output_path=output_path,
            temp_dir=temp_dir,
            voiceover_path=voiceover_path,
        )
        return

    source_path = prepare_source(
        config["source"],
        temp_dir,
    )

    width, height = dimensions(
        config["aspect_ratio"]
    )

    duration = int(
        config["duration_seconds"]
    )

    frames = duration * 30
    hook_size = 32 if width <= 720 else 42
    title_size = 25 if width <= 720 else 32
    price_size = 36 if width <= 720 else 48
    cta_size = 22 if width <= 720 else 30
    brand_size = 17 if width <= 720 else 22

    files = {
        "hook": temp_dir / "hook.txt",
        "name": temp_dir / "name.txt",
        "price": temp_dir / "price.txt",
        "cta": temp_dir / "cta.txt",
        "brand": temp_dir / "brand.txt",
    }

    files["hook"].write_text(
        wrap(config["hook"], 25),
        encoding="utf-8",
    )

    files["name"].write_text(
        wrap(config["product_name"], 24),
        encoding="utf-8",
    )

    files["price"].write_text(
        str(config["price_label"]),
        encoding="utf-8",
    )

    files["cta"].write_text(
        wrap(config["cta"], 40),
        encoding="utf-8",
    )

    files["brand"].write_text(
        "spacecraft.id",
        encoding="utf-8",
    )

    zoom, x_expr, y_expr = motion_expression(
        config["motion"]
    )

    if config["layout"] == "center_focus":
        hook_y = "h*0.14"
        name_y = "h*0.55"
        price_y = "h*0.72"
        cta_y = "h*0.84"
    elif config["layout"] == "bottom_focus":
        hook_y = "h*0.08"
        name_y = "h*0.63"
        price_y = "h*0.77"
        cta_y = "h*0.88"
    else:
        hook_y = "h*0.07"
        name_y = "h*0.58"
        price_y = "h*0.74"
        cta_y = "h*0.86"

    video_filter = (
        f"scale={width}:{height}:"
        "force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"zoompan=z='{zoom}':"
        f"x='{x_expr}':"
        f"y='{y_expr}':"
        f"d={frames}:"
        f"s={width}x{height}:"
        "fps=30,"
        "format=yuv420p,"
        "drawbox=x=0:y=0:"
        "w=iw:h=ih*0.24:"
        "color=black@0.28:t=fill,"
        "drawbox=x=0:y=ih*0.52:"
        "w=iw:h=ih*0.48:"
        "color=black@0.42:t=fill,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['hook']}':"
        "fontcolor=white:"
        f"fontsize={hook_size}:"
        "line_spacing=10:"
        "x=(w-text_w)/2:"
        f"y={hook_y}:"
        "box=1:"
        "boxcolor=black@0.34:"
        "boxborderw=16,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['name']}':"
        "fontcolor=white:"
        f"fontsize={title_size}:"
        "line_spacing=8:"
        "x=(w-text_w)/2:"
        f"y={name_y}:"
        "box=1:"
        "boxcolor=black@0.48:"
        "boxborderw=14,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['price']}':"
        "fontcolor=0x9EF0BD:"
        f"fontsize={price_size}:"
        "x=(w-text_w)/2:"
        f"y={price_y}:"
        "box=1:"
        "boxcolor=black@0.48:"
        "boxborderw=14,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['cta']}':"
        "fontcolor=white:"
        f"fontsize={cta_size}:"
        "line_spacing=8:"
        "x=(w-text_w)/2:"
        f"y={cta_y}:"
        "box=1:"
        "boxcolor=0x665DFF@0.90:"
        "boxborderw=16,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['brand']}':"
        "fontcolor=white@0.80:"
        f"fontsize={brand_size}:"
        "x=(w-text_w)/2:"
        "y=h-text_h-20"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-framerate",
        "30",
        "-i",
        str(source_path),
    ]

    if voiceover_path:
        filter_complex = (
            f"[0:v]{video_filter}[v];"
            + voiceover_filter_chain(
                voiceover_path,
                duration,
            )
        )

        command.extend([
            "-i",
            str(voiceover_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
        ])
    else:
        command.extend([
            "-vf",
            video_filter,
            "-an",
        ])

    command.extend([
        "-t",
        str(duration),
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
    ])

    if voiceover_path:
        command.extend([
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "44100",
        ])

    command.extend([
        "-movflags",
        "+faststart",
        str(output_path),
    ])

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=1200,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr[-3000:]
        )

    if (
        not output_path.is_file()
        or output_path.stat().st_size < 10_000
    ):
        raise RuntimeError(
            "Output render tidak valid"
        )


def render_multi_product_slideshow_video(
    config: dict[str, Any],
    sources: list[dict[str, str]],
    output_path: Path,
    temp_dir: Path,
    voiceover_path: Path | None = None,
) -> None:
    duration = int(
        config["duration_seconds"]
    )

    slide_count = min(
        len(sources),
        max(
            2,
            min(
                6,
                round(duration / 3),
            ),
        ),
    )

    selected_sources = sources[:slide_count]
    base_duration = duration / slide_count
    motions = [
        "zoom_in",
        "pan_right",
        "zoom_out",
        "pan_left",
        "soft_zoom",
        "pan_down",
    ]

    segments: list[Path] = []

    for index, source in enumerate(selected_sources):
        segment = (
            temp_dir
            / f"multi-slideshow-{index + 1:03d}.mp4"
        )
        segment_duration = base_duration

        if index == slide_count - 1:
            segment_duration = (
                duration
                - base_duration * (slide_count - 1)
            )

        render_photo_segment(
            source=source,
            output_path=segment,
            temp_dir=temp_dir,
            aspect_ratio=config["aspect_ratio"],
            duration=max(1.2, segment_duration),
            motion=motions[index % len(motions)],
            fit_mode="contain",
        )
        segments.append(segment)

    base_video = temp_dir / "multi-slideshow-base.mp4"
    concat_video_segments(
        segments=segments,
        output_path=base_video,
        temp_dir=temp_dir,
    )

    overlay_config = dict(config)
    overlay_config["product_name"] = (
        ""
    )
    overlay_config["hook"] = (
        config.get("hook")
        or "Pilihan produk SpaceCraft"
    )
    overlay_config["cta"] = (
        config.get("cta")
        or "Lihat katalog lengkap di spacecraft.id"
    )

    overlay_existing_video(
        input_path=base_video,
        config=overlay_config,
        output_path=output_path,
        temp_dir=temp_dir,
        voiceover_path=voiceover_path,
    )

    if (
        not output_path.is_file()
        or output_path.stat().st_size < 10_000
    ):
        raise RuntimeError(
            "Output multi-product slideshow tidak valid"
        )


def render_ai_product_video(
    config: dict[str, Any],
    output_path: Path,
    temp_dir: Path,
    voiceover_path: Path | None = None,
    campaign_id: int | None = None,
    product_id: int | None = None,
) -> None:
    source_path = prepare_reference_source(
        config,
        temp_dir,
    )

    ai_clip_path = get_or_generate_shared_ai_clip(
        config=config,
        source_path=source_path,
        temp_dir=temp_dir,
        campaign_id=campaign_id,
        product_id=product_id,
    )

    width, height = dimensions(
        config["aspect_ratio"]
    )

    duration = int(
        config["duration_seconds"]
    )

    hook_size = 36 if width <= 720 else 46
    title_size = 30 if width <= 720 else 40
    price_size = 42 if width <= 720 else 54
    cta_size = 27 if width <= 720 else 34
    brand_size = 19 if width <= 720 else 24

    files = {
        "hook": temp_dir / "ai-hook.txt",
        "name": temp_dir / "ai-name.txt",
        "price": temp_dir / "ai-price.txt",
        "cta": temp_dir / "ai-cta.txt",
        "brand": temp_dir / "ai-brand.txt",
    }

    files["hook"].write_text(
        wrap(config["hook"], 24),
        encoding="utf-8",
    )

    files["name"].write_text(
        wrap(config["product_name"], 28),
        encoding="utf-8",
    )

    files["price"].write_text(
        str(config["price_label"]),
        encoding="utf-8",
    )

    files["cta"].write_text(
        wrap(config["cta"], 26),
        encoding="utf-8",
    )

    files["brand"].write_text(
        "spacecraft.id",
        encoding="utf-8",
    )

    video_filter = (
        f"scale={width}:{height}:"
        "force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        "setsar=1,"
        "fps=30,"
        "format=yuv420p,"
        "drawbox=x=0:y=0:"
        "w=iw:h=ih*0.18:"
        "color=black@0.26:t=fill,"
        "drawbox=x=0:y=0:"
        "w=iw:h=ih*0.07:"
        "color=black@0.22:t=fill,"
        "drawbox=x=0:y=ih*0.58:"
        "w=iw:h=ih*0.27:"
        "color=black@0.24:t=fill,"
        "drawbox=x=iw*0.10:y=ih*0.61:"
        "w=iw*0.80:h=ih*0.18:"
        "color=black@0.58:t=fill,"
        "drawbox=x=iw*0.10:y=ih*0.61:"
        "w=6:h=ih*0.18:"
        "color=0x9EF0BD@0.96:t=fill,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['hook']}':"
        "fontcolor=white:"
        f"fontsize={hook_size}:"
        "line_spacing=7:"
        "x=w*0.10:"
        "y=h*0.055:"
        "shadowcolor=black@0.55:"
        "shadowx=2:"
        "shadowy=2,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['name']}':"
        "fontcolor=white:"
        f"fontsize={title_size}:"
        "line_spacing=6:"
        "x=w*0.15:"
        "y=h*0.635:"
        "shadowcolor=black@0.50:"
        "shadowx=1:"
        "shadowy=1,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['price']}':"
        "fontcolor=0x9EF0BD:"
        f"fontsize={price_size}:"
        "x=w*0.15:"
        "y=h*0.695:"
        "shadowcolor=black@0.50:"
        "shadowx=1:"
        "shadowy=1,"
        "drawbox=x=(iw-iw*0.76)/2:y=ih*0.825:"
        "w=iw*0.76:h=ih*0.060:"
        "color=0x275EFE@0.92:t=fill,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['cta']}':"
        "fontcolor=white:"
        f"fontsize={cta_size}:"
        "line_spacing=6:"
        "x=(w-text_w)/2:"
        "y=h*0.836:"
        "shadowcolor=black@0.35:"
        "shadowx=1:"
        "shadowy=1,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['brand']}':"
        "fontcolor=white@0.66:"
        f"fontsize={brand_size}:"
        "x=(w-text_w)/2:"
        "y=h*0.925"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(ai_clip_path),
    ]

    if voiceover_path:
        filter_complex = (
            f"[0:v]{video_filter}[v];"
            + voiceover_filter_chain(
                voiceover_path,
                duration,
            )
        )

        command.extend([
            "-i",
            str(voiceover_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
        ])
    else:
        command.extend([
            "-vf",
            video_filter,
            "-an",
        ])

    command.extend([
        "-t",
        str(duration),
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
    ])

    if voiceover_path:
        command.extend([
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "44100",
        ])

    command.extend([
        "-movflags",
        "+faststart",
        str(output_path),
    ])

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=1200,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr[-3000:]
        )

    if (
        not output_path.is_file()
        or output_path.stat().st_size < 10_000
    ):
        raise RuntimeError(
            "Output AI product video tidak valid"
        )


def get_or_generate_shared_ai_clip(
    config: dict[str, Any],
    source_path: Path,
    temp_dir: Path,
    campaign_id: int | None = None,
    product_id: int | None = None,
) -> Path:
    if campaign_id is None:
        generated_path = generate_gemini_product_video(
            config=config,
            source_path=source_path,
            destination=(
                temp_dir / "ai-product-video.mp4"
            ),
        )
        archive_raw_veo_clip(
            generated_path,
            product_id,
            campaign_id,
            config,
        )
        return generated_path

    shared_dir = (
        STORAGE_ROOT
        / "renders"
        / str(campaign_id)
    )

    shared_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    shared_path = (
        shared_dir
        / "shared-ai-product-video.mp4"
    )

    if (
        shared_path.is_file()
        and shared_path.stat().st_size > 10_000
    ):
        archive_raw_veo_clip(
            shared_path,
            product_id,
            campaign_id,
            config,
        )
        return shared_path

    lock_path = shared_path.with_suffix(
        ".lock"
    )

    lock_handle = None

    try:
        lock_handle = os.open(
            lock_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )
    except FileExistsError:
        deadline = time.monotonic() + 1800

        while time.monotonic() < deadline:
            if (
                shared_path.is_file()
                and shared_path.stat().st_size > 10_000
            ):
                archive_raw_veo_clip(
                    shared_path,
                    product_id,
                    campaign_id,
                    config,
                )
                return shared_path

            time.sleep(5)

        raise RuntimeError(
            "Timeout menunggu shared AI clip campaign"
        )

    try:
        temp_output = (
            temp_dir
            / f"shared-ai-product-video-{uuid.uuid4().hex}.mp4"
        )

        generate_gemini_product_video(
            config=config,
            source_path=source_path,
            destination=temp_output,
        )

        shutil.copyfile(
            temp_output,
            shared_path,
        )

        archive_raw_veo_clip(
            shared_path,
            product_id,
            campaign_id,
            config,
        )

        return shared_path

    finally:
        if lock_handle is not None:
            os.close(lock_handle)

        lock_path.unlink(
            missing_ok=True,
        )


def overlay_existing_video(
    input_path: Path,
    config: dict[str, Any],
    output_path: Path,
    temp_dir: Path,
    voiceover_path: Path | None = None,
) -> None:
    width, height = dimensions(
        config["aspect_ratio"]
    )

    duration = int(
        config["duration_seconds"]
    )

    hook_size = 35 if width <= 720 else 46
    title_size = 27 if width <= 720 else 35
    price_size = 42 if width <= 720 else 54
    cta_size = 25 if width <= 720 else 32
    brand_size = 18 if width <= 720 else 23

    files = {
        "hook": temp_dir / "hybrid-hook.txt",
        "name": temp_dir / "hybrid-name.txt",
        "price": temp_dir / "hybrid-price.txt",
        "cta": temp_dir / "hybrid-cta.txt",
        "brand": temp_dir / "hybrid-brand.txt",
    }

    files["hook"].write_text(
        wrap(config["hook"], 25),
        encoding="utf-8",
    )

    files["name"].write_text(
        wrap(config["product_name"], 24),
        encoding="utf-8",
    )

    files["price"].write_text(
        str(config["price_label"]),
        encoding="utf-8",
    )

    files["cta"].write_text(
        wrap(config["cta"], 40),
        encoding="utf-8",
    )

    files["brand"].write_text(
        "spacecraft.id",
        encoding="utf-8",
    )

    video_filter = (
        f"scale={width}:{height}:"
        "force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        "setsar=1,"
        "fps=30,"
        "format=yuv420p,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['hook']}':"
        "fontcolor=white:"
        "bordercolor=black@0.76:"
        "borderw=3:"
        f"fontsize={hook_size}:"
        "line_spacing=8:"
        "x=w*0.070:"
        "y=h*0.060:"
        "shadowcolor=black@0.72:"
        "shadowx=2:"
        "shadowy=3,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['name']}':"
        "fontcolor=white:"
        "bordercolor=black@0.72:"
        "borderw=3:"
        f"fontsize={title_size}:"
        "line_spacing=7:"
        "x=(w-text_w)/2:"
        "y=h*0.665:"
        "shadowcolor=black@0.62:"
        "shadowx=2:"
        "shadowy=2,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['price']}':"
        "fontcolor=0x9EF0BD:"
        "bordercolor=black@0.82:"
        "borderw=3:"
        f"fontsize={price_size}:"
        "x=(w-text_w)/2:"
        "y=h*0.745:"
        "shadowcolor=black@0.72:"
        "shadowx=2:"
        "shadowy=3,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['cta']}':"
        "fontcolor=0x7DB2FF:"
        "bordercolor=black@0.82:"
        "borderw=3:"
        f"fontsize={cta_size}:"
        "line_spacing=6:"
        "x=(w-text_w)/2:"
        "y=h*0.862:"
        "shadowcolor=black@0.72:"
        "shadowx=2:"
        "shadowy=2,"
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['brand']}':"
        "fontcolor=white@0.78:"
        "bordercolor=black@0.62:"
        "borderw=2:"
        f"fontsize={brand_size}:"
        "x=(w-text_w)/2:"
        "y=h*0.930"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
    ]

    if voiceover_path:
        filter_complex = (
            f"[0:v]{video_filter}[v];"
            + voiceover_filter_chain(
                voiceover_path,
                duration,
            )
        )

        command.extend([
            "-i",
            str(voiceover_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
        ])
    else:
        command.extend([
            "-vf",
            video_filter,
            "-an",
        ])

    command.extend([
        "-t",
        str(duration),
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
    ])

    if voiceover_path:
        command.extend([
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "44100",
        ])

    command.extend([
        "-movflags",
        "+faststart",
        str(output_path),
    ])

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=1200,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr[-3000:]
        )

    if (
        not output_path.is_file()
        or output_path.stat().st_size < 10_000
    ):
        raise RuntimeError(
            "Output hybrid video tidak valid"
        )



def resolve_raw_catalog_fit_mode(
    requested_mode: str | None,
    video_type: str | None,
    source_orientation: str | None,
    aspect_ratio: str,
) -> str:
    requested = str(
        requested_mode or "auto"
    ).strip().lower()

    if requested in {
        "contain",
        "cover",
        "blur_fill",
    }:
        return requested

    video_type_value = str(
        video_type or "demo"
    ).strip().lower()

    orientation = str(
        source_orientation or ""
    ).strip().lower()

    target_orientation = {
        "9:16": "portrait",
        "16:9": "landscape",
        "1:1": "square",
    }.get(
        aspect_ratio,
        "portrait",
    )

    if (
        orientation
        and orientation != target_orientation
        and target_orientation != "square"
    ):
        return "blur_fill"

    if video_type_value in {
        "hero",
        "lifestyle",
        "packaging",
    }:
        return "cover"

    if video_type_value in {
        "demo",
        "detail",
    }:
        return "blur_fill"

    return "contain"



def render_raw_catalog_segment(
    input_path: Path,
    output_path: Path,
    aspect_ratio: str,
    duration: float,
    trim_start: float = 0.0,
    trim_end: float | None = None,
    fit_mode: str = "contain",
) -> None:
    width, height = dimensions(
        aspect_ratio
    )

    duration = max(
        0.25,
        float(duration),
    )

    trim_start = max(
        0.0,
        float(trim_start or 0.0),
    )

    normalized_trim_end = (
        float(trim_end)
        if trim_end is not None
        else None
    )

    if (
        normalized_trim_end is not None
        and normalized_trim_end <= trim_start
    ):
        raise RuntimeError(
            "Trim selesai harus lebih besar "
            "daripada trim mulai"
        )

    fit_mode = str(
        fit_mode or "contain"
    ).strip().lower()

    if fit_mode not in {
        "contain",
        "cover",
        "blur_fill",
    }:
        fit_mode = "contain"

    trim_filter = (
        f"trim=start={trim_start:.3f}"
    )

    if normalized_trim_end is not None:
        trim_filter += (
            f":end={normalized_trim_end:.3f}"
        )

    trim_filter += ",setpts=PTS-STARTPTS"

    ending_filter = (
        "setsar=1,"
        f"tpad=stop_mode=clone:"
        f"stop_duration={duration:.3f},"
        f"trim=duration={duration:.3f},"
        "setpts=PTS-STARTPTS,"
        "fps=30,"
        "format=yuv420p"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
    ]

    if fit_mode == "blur_fill":
        filter_complex = (
            f"[0:v]{trim_filter},"
            "split=2[background][foreground];"
            "[background]"
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            "boxblur=luma_radius=min(h\,w)/28:"
            "luma_power=2,"
            "eq=brightness=-0.08:"
            "saturation=0.78"
            "[blurred];"
            "[foreground]"
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=decrease"
            "[main];"
            "[blurred][main]"
            "overlay="
            "(main_w-overlay_w)/2:"
            "(main_h-overlay_h)/2,"
            f"{ending_filter}"
            "[v]"
        )

        command.extend([
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
        ])

    else:
        if fit_mode == "cover":
            fit_filter = (
                f"scale={width}:{height}:"
                "force_original_aspect_ratio=increase,"
                f"crop={width}:{height}"
            )
        else:
            fit_filter = (
                f"scale={width}:{height}:"
                "force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:"
                "(ow-iw)/2:(oh-ih)/2:"
                "color=black"
            )

        video_filter = (
            f"{trim_filter},"
            f"{fit_filter},"
            f"{ending_filter}"
        )

        command.extend([
            "-vf",
            video_filter,
        ])

    command.extend([
        "-an",
        "-t",
        f"{duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ])

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=1200,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr[-4000:]
        )

    if (
        not output_path.is_file()
        or output_path.stat().st_size < 10_000
    ):
        raise RuntimeError(
            "Segment raw catalog tidak valid"
        )



def raw_catalog_safe_area(
    aspect_ratio: str,
) -> dict[str, float]:
    """
    Normalized safe-area positions.

    Untuk output 9:16, elemen penting dijauhkan dari:
    - tombol UI TikTok/Reels di sisi kanan;
    - caption/account area di bagian bawah;
    - header platform di bagian atas.
    """
    ratio = str(
        aspect_ratio or "9:16"
    ).strip()

    if ratio == "9:16":
        return {
            "top": 0.070,
            "hook_y": 0.085,
            "product_box_y": 0.680,
            "product_text_y": 0.705,
            "closing_box_y": 0.625,
            "closing_start_y": 0.650,
            "cta_y": 0.815,
            "brand_y": 0.855,
            "bottom_limit": 0.875,
            "horizontal_margin": 0.075,
        }

    if ratio == "1:1":
        return {
            "top": 0.055,
            "hook_y": 0.070,
            "product_box_y": 0.700,
            "product_text_y": 0.725,
            "closing_box_y": 0.650,
            "closing_start_y": 0.680,
            "cta_y": 0.860,
            "brand_y": 0.920,
            "bottom_limit": 0.940,
            "horizontal_margin": 0.060,
        }

    return {
        "top": 0.050,
        "hook_y": 0.065,
        "product_box_y": 0.700,
        "product_text_y": 0.725,
        "closing_box_y": 0.650,
        "closing_start_y": 0.680,
        "cta_y": 0.865,
        "brand_y": 0.920,
        "bottom_limit": 0.945,
        "horizontal_margin": 0.055,
    }


def build_raw_catalog_layout_snapshot(
    raw_clips: list[dict[str, Any]],
    aspect_ratio: str,
) -> dict[str, Any]:
    safe_area = raw_catalog_safe_area(
        aspect_ratio
    )

    warnings: list[str] = []
    clips: list[dict[str, Any]] = []

    for index, clip in enumerate(raw_clips):
        width = clip.get("source_width")
        height = clip.get("source_height")
        orientation = str(
            clip.get("source_orientation")
            or "unknown"
        )
        fit_mode = str(
            clip.get("fit_mode")
            or "contain"
        )
        requested_fit_mode = str(
            clip.get("requested_fit_mode")
            or "auto"
        )
        video_type = str(
            clip.get("video_type")
            or "demo"
        )

        if (
            aspect_ratio == "9:16"
            and orientation == "landscape"
            and fit_mode == "contain"
        ):
            warnings.append(
                f"Clip {index + 1}: landscape dengan "
                "Contain dapat menyisakan area kosong."
            )

        try:
            numeric_width = int(width)
            numeric_height = int(height)

            if (
                numeric_width < 720
                or numeric_height < 720
            ):
                warnings.append(
                    f"Clip {index + 1}: resolusi source "
                    f"{numeric_width}x{numeric_height} rendah."
                )
        except (TypeError, ValueError):
            pass

        clips.append({
            "order": index + 1,
            "asset_id": clip.get("asset_id"),
            "clip_id": clip.get("clip_id"),
            "product_id": clip.get("product_id"),
            "product_name": clip.get("product_name"),
            "video_type": video_type,
            "requested_fit_mode": requested_fit_mode,
            "resolved_fit_mode": fit_mode,
            "source_orientation": orientation,
            "source_width": width,
            "source_height": height,
            "trim_start": clip.get("trim_start"),
            "trim_end": clip.get("trim_end"),
        })

    return {
        "version": "b6",
        "aspect_ratio": aspect_ratio,
        "safe_area": safe_area,
        "clips": clips,
        "warnings": warnings,
        "created_at": now().isoformat(),
    }



def overlay_raw_catalog_video(
    input_path: Path,
    config: dict[str, Any],
    output_path: Path,
    temp_dir: Path,
    voiceover_path: Path | None = None,
) -> None:
    width, height = dimensions(
        config["aspect_ratio"]
    )

    duration = int(
        config["duration_seconds"]
    )

    hook_size = 33 if width <= 720 else 44
    catalog_size = 21 if width <= 720 else 28
    promo_size = 22 if width <= 720 else 30
    cta_size = 24 if width <= 720 else 32
    brand_size = 17 if width <= 720 else 22
    top_box_x = int(width * 0.045)
    top_box_y = int(height * safe_area["top"])
    top_box_w = int(width * 0.91)
    top_box_h = int(height * 0.175)
    product_box_x = int(width * 0.055)
    product_box_y = int(height * safe_area["product_box_y"])
    product_box_w = int(width * 0.89)
    product_box_h = int(height * 0.105)
    catalog_box_x = int(width * 0.055)
    catalog_box_y = int(height * safe_area["closing_box_y"])
    catalog_box_w = int(width * 0.89)
    catalog_box_h = int(height * 0.245)
    hook_end = min(
        float(duration),
        max(2.8, duration * 0.34),
    )

    raw_clips = config.get("raw_clips") or []
    product_items: list[dict[str, str]] = []

    for index, clip in enumerate(raw_clips):
        name = str(
            clip.get("product_name")
            or f"Produk {index + 1}"
        )
        price = str(
            clip.get("product_price_label")
            or ""
        ).strip()
        product_items.append({
            "name": name,
            "price": price,
            "label": (
                f"{name} - {price}"
                if price
                else name
            ),
        })

    product_names = [
        item["label"]
        for item in product_items
    ]

    if not product_names:
        product_names = [
            str(name)
            for name in (
                config.get("product_names")
                or [config.get("product_name") or "Produk"]
            )
        ]
        product_items = [
            {
                "name": name,
                "price": "",
                "label": name,
            }
            for name in product_names
        ]

    closing_duration = min(
        4.0,
        max(3.0, duration * 0.16),
    )

    final_start = max(
        0.0,
        float(duration) - closing_duration,
    )

    segment_duration = (
        final_start / max(1, len(product_names))
    )

    files = {
        "hook": temp_dir / "catalog-hook.txt",
        "catalog": temp_dir / "catalog-lines.txt",
        "promo": temp_dir / "catalog-promo.txt",
        "cta": temp_dir / "catalog-cta.txt",
        "brand": temp_dir / "catalog-brand.txt",
    }

    files["hook"].write_text(
        wrap(config["hook"], 25),
        encoding="utf-8",
    )

    product_files: list[Path] = []

    for index, name in enumerate(product_names):
        product_file = (
            temp_dir
            / f"catalog-product-{index + 1:02d}.txt"
        )
        product_file.write_text(
            wrap(f"{index + 1}. {name}", 28),
            encoding="utf-8",
        )
        product_files.append(product_file)

    catalog_lines = [
        f"{index + 1}. {name}"
        for index, name in enumerate(product_names)
    ]

    promo = (
        (config.get("promo") or {})
        if isinstance(config.get("promo"), dict)
        else {}
    )
    promo_enabled = bool(promo.get("enabled"))
    promo_label = str(
        promo.get("label")
        or ""
    ).strip()

    catalog_text_lines = [
        "Pilih produk favoritmu:",
    ]

    if promo_enabled and promo_label:
        catalog_text_lines.append(
            promo_label.upper()
        )

    catalog_text_lines.extend(catalog_lines)

    files["catalog"].write_text(
        "\n".join(
            wrap(line, 32)
            for line in catalog_text_lines
        ),
        encoding="utf-8",
    )

    closing_lines: list[dict[str, Any]] = []
    closing_y = safe_area["closing_start_y"]

    def add_closing_line(
        text: str,
        color: str,
        size: int,
        width_chars: int = 30,
    ) -> None:
        nonlocal closing_y

        line_path = (
            temp_dir
            / f"closing-line-{len(closing_lines) + 1:02d}.txt"
        )
        wrapped = wrap(
            text,
            width_chars,
        )
        line_path.write_text(
            wrapped,
            encoding="utf-8",
        )
        lines = max(
            1,
            wrapped.count("\n") + 1,
        )
        closing_lines.append({
            "path": line_path,
            "color": color,
            "size": size,
            "y": closing_y,
        })
        closing_y += (
            0.033 * lines
            + 0.014
        )

    add_closing_line(
        "Pilih produk favoritmu:",
        "0x9EF0BD",
        catalog_size + 2,
        30,
    )

    if promo_enabled and promo_label:
        add_closing_line(
            promo_label.upper(),
            "0xFFD36A",
            promo_size,
            30,
        )

    add_closing_line(
        (
            f"{len(product_names)} pilihan produk "
            "tersedia"
        ),
        "white",
        max(18, catalog_size),
        30,
    )

    if promo_enabled and promo_label:
        files["promo"].write_text(
            wrap(promo_label, 34),
            encoding="utf-8",
        )

    files["cta"].write_text(
        wrap(config["cta"], 34),
        encoding="utf-8",
    )

    files["brand"].write_text(
        "spacecraft.id",
        encoding="utf-8",
    )

    filter_parts = [
        (
            f"tpad=stop_mode=clone:"
            f"stop_duration={closing_duration:.3f},"
            f"trim=duration={float(duration):.3f},"
            "setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            "setsar=1,fps=30,format=yuv420p"
        ),
        f"drawbox=x={top_box_x}:y={top_box_y}:"
        f"w={top_box_w}:h={top_box_h}:"
        "color=black@0.45:t=fill:"
        f"enable='between(t\\,0\\,{hook_end:.3f})'",
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['hook']}':"
        "fontcolor=white:"
        "bordercolor=black@0.72:"
        "borderw=3:"
        f"fontsize={hook_size}:"
        "line_spacing=8:"
        "x=w*0.070:"
        f"y=h*{safe_area['hook_y']:.3f}:"
        "shadowcolor=black@0.72:"
        "shadowx=2:"
        "shadowy=3:"
        f"enable='between(t\\,0\\,{hook_end:.3f})'",
    ]

    for index, product_file in enumerate(product_files):
        start = index * segment_duration
        end = min(
            (index + 1) * segment_duration,
            final_start,
        )

        if end <= start:
            continue

        enabled = f"between(t\\,{start:.3f}\\,{end:.3f})"
        filter_parts.extend([
            f"drawbox=x={product_box_x}:y={product_box_y}:"
            f"w={product_box_w}:h={product_box_h}:"
            "color=black@0.52:t=fill:"
            f"enable='{enabled}'",
            f"drawtext=fontfile='{FONT_FILE}':"
            f"textfile='{product_file}':"
            "fontcolor=white:"
            "bordercolor=black@0.72:"
            "borderw=3:"
            f"fontsize={catalog_size + 2}:"
            "line_spacing=6:"
            "x=w*0.085:"
            f"y=h*{safe_area['product_text_y']:.3f}:"
            "shadowcolor=black@0.70:"
            "shadowx=2:"
            "shadowy=2:"
            f"enable='{enabled}'",
        ])

    final_enabled = f"gte(t\\,{final_start:.3f})"
    filter_parts.extend([
        f"drawbox=x={catalog_box_x}:y={catalog_box_y}:"
        f"w={catalog_box_w}:h={catalog_box_h}:"
        "color=black@0.58:t=fill:"
        f"enable='{final_enabled}'",
    ])

    for line in closing_lines:
        filter_parts.append(
            f"drawtext=fontfile='{FONT_FILE}':"
            f"textfile='{line['path']}':"
            "expansion=none:"
            f"fontcolor={line['color']}:"
            "bordercolor=black@0.78:"
            "borderw=2:"
            f"fontsize={line['size']}:"
            "line_spacing=6:"
            "x=w*0.085:"
            f"y=h*{line['y']:.3f}:"
            "shadowcolor=black@0.72:"
            "shadowx=2:"
            "shadowy=2:"
            f"enable='{final_enabled}'"
        )

    if closing_y < safe_area["cta_y"] - 0.025:
        filter_parts.append(
            f"drawtext=fontfile='{FONT_FILE}':"
            f"textfile='{files['cta']}':"
            "expansion=none:"
            "fontcolor=0x9EF0BD:"
            "bordercolor=black@0.82:"
            "borderw=3:"
            f"fontsize={cta_size}:"
            "line_spacing=6:"
            "x=(w-text_w)/2:"
            f"y=h*{safe_area['cta_y']:.3f}:"
            "shadowcolor=black@0.72:"
            "shadowx=2:"
            "shadowy=2:"
            f"enable='{final_enabled}'"
        )

    filter_parts.extend([
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['brand']}':"
        "fontcolor=white@0.74:"
        "bordercolor=black@0.60:"
        "borderw=2:"
        f"fontsize={brand_size}:"
        "x=(w-text_w)/2:"
        f"y=h*{safe_area['brand_y']:.3f}",
    ])

    video_filter = ",".join(filter_parts)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    music_config = (
        config.get("music")
        if isinstance(
            config.get("music"),
            dict,
        )
        else {}
    )

    music_path: Path | None = None

    if music_config.get("enabled"):
        archive = str(
            music_config.get("archive")
            or ""
        ).strip()

        candidate = STORAGE_ROOT / archive

        try:
            candidate.resolve().relative_to(
                STORAGE_ROOT.resolve()
            )
        except ValueError:
            candidate = Path(
                "/music-path-invalid"
            )

        if (
            candidate.is_file()
            and candidate.stat().st_size > 100
        ):
            music_path = candidate

    music_volume = max(
        0.05,
        min(
            float(
                music_config.get("volume")
                or 0.22
            ),
            1.0,
        ),
    )

    music_ducking = bool(
        music_config.get("ducking", True)
    )

    fade_out_start = max(
        float(duration) - 0.65,
        0.0,
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
    ]

    if voiceover_path:
        command.extend([
            "-i",
            str(voiceover_path),
        ])

    if music_path:
        command.extend([
            "-stream_loop",
            "-1",
            "-i",
            str(music_path),
        ])

    video_chain = (
        f"[0:v]{video_filter}[v]"
    )

    if voiceover_path and music_path:
        music_input_index = 2

        voice_chain = voiceover_filter_chain(
            voiceover_path,
            duration,
        ).replace(
            "[a]",
            "[vo_base]",
        )

        music_chain = (
            f"[{music_input_index}:a]"
            "aresample=44100,"
            "aformat=sample_fmts=fltp:"
            "channel_layouts=stereo,"
            "asetpts=PTS-STARTPTS,"
            f"volume={music_volume:.3f},"
            f"atrim=0:{duration},"
            "afade=t=in:st=0:d=0.40,"
            f"afade=t=out:st={fade_out_start:.3f}:"
            "d=0.60"
            "[music_base]"
        )

        if music_ducking:
            mix_chain = (
                "[vo_base]"
                "asplit=2"
                "[vo_side][vo_mix];"
                "[music_base][vo_side]"
                "sidechaincompress="
                "threshold=0.025:"
                "ratio=10:"
                "attack=18:"
                "release=450:"
                "makeup=1"
                "[music_ducked];"
                "[music_ducked][vo_mix]"
                "amix="
                "inputs=2:"
                "duration=longest:"
                "dropout_transition=0:"
                "normalize=0,"
                f"atrim=0:{duration}"
                "[a]"
            )
        else:
            mix_chain = (
                "[music_base][vo_base]"
                "amix="
                "inputs=2:"
                "duration=longest:"
                "dropout_transition=0:"
                "normalize=0,"
                f"atrim=0:{duration}"
                "[a]"
            )

        filter_complex = (
            video_chain
            + ";"
            + voice_chain
            + ";"
            + music_chain
            + ";"
            + mix_chain
        )

        command.extend([
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
        ])

    elif voiceover_path:
        filter_complex = (
            video_chain
            + ";"
            + voiceover_filter_chain(
                voiceover_path,
                duration,
            )
        )

        command.extend([
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
        ])

    elif music_path:
        music_chain = (
            "[1:a]"
            "aresample=44100,"
            "aformat=sample_fmts=fltp:"
            "channel_layouts=stereo,"
            "asetpts=PTS-STARTPTS,"
            f"volume={music_volume:.3f},"
            f"atrim=0:{duration},"
            "afade=t=in:st=0:d=0.40,"
            f"afade=t=out:st={fade_out_start:.3f}:"
            "d=0.60"
            "[a]"
        )

        filter_complex = (
            video_chain
            + ";"
            + music_chain
        )

        command.extend([
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
        ])

    else:
        silent_fade_start = max(
            float(duration) - 0.40,
            0.0,
        )

        command.extend([
            "-f",
            "lavfi",
            "-t",
            str(duration),
            "-i",
            (
                "anullsrc="
                "channel_layout=stereo:"
                "sample_rate=44100"
            ),
        ])

        silent_chain = (
            "[1:a]"
            "aresample=44100,"
            "aformat=sample_fmts=fltp:"
            "channel_layouts=stereo,"
            f"atrim=0:{duration},"
            "asetpts=PTS-STARTPTS,"
            "afade=t=in:st=0:d=0.10,"
            f"afade=t=out:st={silent_fade_start:.3f}:"
            "d=0.35"
            "[a]"
        )

        filter_complex = (
            video_chain
            + ";"
            + silent_chain
        )

        command.extend([
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
        ])

    command.extend([
        "-t",
        str(duration),
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
    ])

    command.extend([
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-ar",
        "44100",
    ])

    command.extend([
        "-movflags",
        "+faststart",
        str(output_path),
    ])

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=1200,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr[-3000:]
        )

    if (
        not output_path.is_file()
        or output_path.stat().st_size < 10_000
    ):
        raise RuntimeError(
            "Output raw catalog video tidak valid"
        )


def render_raw_catalog_video(
    config: dict[str, Any],
    output_path: Path,
    temp_dir: Path,
    voiceover_path: Path | None = None,
) -> None:
    raw_clips = config.get("raw_clips") or []

    if not 5 <= len(raw_clips) <= 6:
        raise RuntimeError(
            "Raw video catalog membutuhkan 5 sampai 6 clip"
        )

    duration = int(
        config["duration_seconds"]
    )

    closing_duration = min(
        4.0,
        max(3.0, duration * 0.16),
    )

    product_duration = max(
        1.0,
        float(duration) - closing_duration,
    )

    transition_duration = min(
        0.30,
        max(
            0.24,
            product_duration * 0.012,
        ),
    )

    transition_total = (
        transition_duration
        * max(0, len(raw_clips) - 1)
    )

    segment_duration = max(
        0.75,
        (
            product_duration
            + transition_total
        )
        / len(raw_clips),
    )

    segments: list[Path] = []

    for index, clip in enumerate(raw_clips):
        archive = str(
            clip.get("archive")
            or ""
        ).strip()

        input_path = STORAGE_ROOT / archive

        try:
            input_path.resolve().relative_to(
                STORAGE_ROOT.resolve()
            )
        except ValueError:
            raise RuntimeError(
                "Raw clip berada di luar storage"
            )

        if (
            not input_path.is_file()
            or input_path.stat().st_size < 10_000
        ):
            raise RuntimeError(
                "Raw clip tidak ditemukan: " + archive
            )

        segment = (
            temp_dir
            / f"raw-catalog-{index + 1:03d}.mp4"
        )

        render_raw_catalog_segment(
            input_path=input_path,
            output_path=segment,
            aspect_ratio=config["aspect_ratio"],
            duration=segment_duration,
            trim_start=float(
                clip.get("trim_start")
                or 0.0
            ),
            trim_end=(
                float(clip["trim_end"])
                if clip.get("trim_end")
                is not None
                else None
            ),
            fit_mode=str(
                clip.get("fit_mode")
                or "contain"
            ),
        )

        segments.append(segment)

    base_video = temp_dir / "raw-catalog-base.mp4"

    crossfade_video_segments(
        segments=segments,
        output_path=base_video,
        segment_duration=segment_duration,
        transition_duration=transition_duration,
    )

    overlay_raw_catalog_video(
        input_path=base_video,
        config=config,
        output_path=output_path,
        temp_dir=temp_dir,
        voiceover_path=voiceover_path,
    )


def render_video_segment(
    input_path: Path,
    output_path: Path,
    aspect_ratio: str,
    duration: float,
) -> None:
    width, height = dimensions(
        aspect_ratio
    )

    command = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(input_path),
        "-t",
        f"{duration:.3f}",
        "-vf",
        (
            "crop=iw*0.76:ih:(iw-iw*0.76)/2:0,"
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            "setsar=1,fps=30,format=yuv420p"
        ),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=1200,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr[-3000:]
        )


def render_photo_segment(
    source: dict[str, str],
    output_path: Path,
    temp_dir: Path,
    aspect_ratio: str,
    duration: float,
    motion: str,
    fit_mode: str = "cover",
) -> None:
    source_path = prepare_source(
        source,
        temp_dir,
    )

    width, height = dimensions(
        aspect_ratio
    )

    frames = max(1, int(duration * 30))
    zoom, x_expr, y_expr = motion_expression(
        motion,
        frames,
    )

    if fit_mode == "contain":
        video_filter = (
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:"
            "(ow-iw)/2:(oh-ih)/2:"
            "color=0xF3F5FA,"
            "setsar=1,"
            f"zoompan=z='{zoom}':"
            f"x='{x_expr}':"
            f"y='{y_expr}':"
            f"d={frames}:"
            f"s={width}x{height}:"
            "fps=30,format=yuv420p"
        )
    else:
        video_filter = (
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"zoompan=z='{zoom}':"
            f"x='{x_expr}':"
            f"y='{y_expr}':"
            f"d={frames}:"
            f"s={width}x{height}:"
            "fps=30,format=yuv420p"
        )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vf",
        video_filter,
        "-frames:v",
        str(frames),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=1200,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr[-3000:]
        )



def crossfade_video_segments(
    segments: list[Path],
    output_path: Path,
    segment_duration: float,
    transition_duration: float = 0.28,
) -> None:
    if not segments:
        raise RuntimeError(
            "Tidak ada segment untuk digabungkan"
        )

    if len(segments) == 1:
        shutil.copy2(
            segments[0],
            output_path,
        )
        return

    segment_duration = max(
        0.5,
        float(segment_duration),
    )

    transition_duration = max(
        0.05,
        min(
            float(transition_duration),
            segment_duration * 0.30,
            0.50,
        ),
    )

    command = [
        "ffmpeg",
        "-y",
    ]

    for segment in segments:
        command.extend([
            "-i",
            str(segment),
        ])

    filter_parts: list[str] = []

    for index in range(len(segments)):
        filter_parts.append(
            f"[{index}:v]"
            "settb=AVTB,"
            "setpts=PTS-STARTPTS,"
            "format=yuv420p"
            f"[v{index}]"
        )

    current_label = "[v0]"

    for index in range(1, len(segments)):
        output_label = f"[xf{index}]"

        offset = (
            index
            * (
                segment_duration
                - transition_duration
            )
        )

        filter_parts.append(
            f"{current_label}[v{index}]"
            "xfade="
            "transition=fade:"
            f"duration={transition_duration:.3f}:"
            f"offset={offset:.3f}"
            f"{output_label}"
        )

        current_label = output_label

    command.extend([
        "-filter_complex",
        ";".join(filter_parts),
        "-map",
        current_label,
        "-an",
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ])

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=1200,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr[-4000:]
        )

    if (
        not output_path.is_file()
        or output_path.stat().st_size < 10_000
    ):
        raise RuntimeError(
            "Output crossfade raw catalog tidak valid"
        )



def concat_video_segments(
    segments: list[Path],
    output_path: Path,
    temp_dir: Path,
) -> None:
    concat_file = temp_dir / "hybrid-concat.txt"

    concat_file.write_text(
        "\n".join(
            f"file '{segment.as_posix()}'"
            for segment in segments
        )
        + "\n",
        encoding="utf-8",
    )

    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        str(output_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=1200,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr[-3000:]
        )


def render_hybrid_video(
    config: dict[str, Any],
    output_path: Path,
    temp_dir: Path,
    voiceover_path: Path | None = None,
    campaign_id: int | None = None,
    product_id: int | None = None,
) -> None:
    source_path = prepare_reference_source(
        config,
        temp_dir,
    )

    ai_clip_path = get_or_generate_shared_ai_clip(
        config=config,
        source_path=source_path,
        temp_dir=temp_dir,
        campaign_id=campaign_id,
        product_id=product_id,
    )

    total_duration = int(
        config["duration_seconds"]
    )

    ai_duration = min(
        8.0,
        max(5.0, total_duration * 0.45),
    )

    if total_duration <= 10:
        ai_duration = min(7.0, total_duration)

    remaining = max(
        0.0,
        float(total_duration) - ai_duration,
    )

    slideshow_sources = (
        config.get("slideshow_sources")
        or [config["source"]]
    )

    slide_count = 0

    if remaining > 0:
        slide_count = min(
            len(slideshow_sources),
            3,
            max(1, int((remaining + 3.9) // 4)),
        )

    segments: list[Path] = []

    ai_segment = temp_dir / "segment-000-ai.mp4"
    render_video_segment(
        input_path=ai_clip_path,
        output_path=ai_segment,
        aspect_ratio=config["aspect_ratio"],
        duration=ai_duration,
    )
    segments.append(ai_segment)

    if slide_count:
        base_slide_duration = remaining / slide_count

        motions = [
            "zoom_in",
            "pan_right",
            "zoom_out",
        ]

        for index, source in enumerate(
            slideshow_sources[:slide_count]
        ):
            segment = (
                temp_dir
                / f"segment-{index + 1:03d}-photo.mp4"
            )

            render_photo_segment(
                source=source,
                output_path=segment,
                temp_dir=temp_dir,
                aspect_ratio=config["aspect_ratio"],
                duration=base_slide_duration,
                motion=motions[index % len(motions)],
            )

            segments.append(segment)

    base_video = temp_dir / "hybrid-base.mp4"
    concat_video_segments(
        segments=segments,
        output_path=base_video,
        temp_dir=temp_dir,
    )

    overlay_existing_video(
        input_path=base_video,
        config=config,
        output_path=output_path,
        temp_dir=temp_dir,
        voiceover_path=voiceover_path,
    )


def render_clean_raw_ai_master(
    config: dict[str, Any],
    output_path: Path,
    temp_dir: Path,
    campaign_id: int | None = None,
    product_id: int | None = None,
) -> None:
    """
    Generate a clean image-to-video master.

    No hook, title, description, price, CTA, branding, slideshow,
    subtitle, watermark, or voice-over is added.
    """
    source_path = prepare_reference_source(
        config,
        temp_dir,
    )

    ai_clip_path = get_or_generate_shared_ai_clip(
        config=config,
        source_path=source_path,
        temp_dir=temp_dir,
        campaign_id=campaign_id,
        product_id=product_id,
    )

    width, height = dimensions(
        config.get("aspect_ratio", "9:16")
    )

    duration = int(
        config.get("duration_seconds", 10)
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(ai_clip_path),
        "-t",
        str(duration),
        "-vf",
        (
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:"
            "(ow-iw)/2:(oh-ih)/2:"
            "color=black,"
            "setsar=1,"
            "fps=30,"
            "format=yuv420p"
        ),
        "-an",
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "21",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=1200,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Clean raw AI render gagal: "
            + result.stderr[-3000:]
        )

    if (
        not output_path.is_file()
        or output_path.stat().st_size < 10_000
    ):
        raise RuntimeError(
            "Output clean raw AI video tidak valid"
        )


def render_video(
    config: dict[str, Any],
    output_path: Path,
    temp_dir: Path,
    voiceover_path: Path | None = None,
    campaign_id: int | None = None,
    product_id: int | None = None,
) -> None:
    if (
        config.get("render_mode") == "ai_video"
        and bool(config.get("raw_master"))
    ):
        render_clean_raw_ai_master(
            config=config,
            output_path=output_path,
            temp_dir=temp_dir,
            campaign_id=campaign_id,
            product_id=product_id,
        )
        return

    if config.get("render_mode") == "raw_catalog":
        render_raw_catalog_video(
            config,
            output_path,
            temp_dir,
            voiceover_path,
        )
        return

    if config.get("render_mode") == "hybrid":
        render_hybrid_video(
            config,
            output_path,
            temp_dir,
            voiceover_path,
            campaign_id,
            product_id,
        )
        return

    if config.get("render_mode") == "ai_video":
        render_ai_product_video(
            config,
            output_path,
            temp_dir,
            voiceover_path,
            campaign_id,
            product_id,
        )
        return

    render_slideshow_video(
        config,
        output_path,
        temp_dir,
        voiceover_path,
    )



def parse_ffprobe_rate(
    value: Any,
) -> float | None:
    clean = str(value or "").strip()

    if not clean:
        return None

    try:
        if "/" in clean:
            numerator, denominator = clean.split(
                "/",
                1,
            )

            denominator_value = float(
                denominator or 0
            )

            if denominator_value == 0:
                return None

            return round(
                float(numerator)
                / denominator_value,
                3,
            )

        return round(float(clean), 3)

    except (TypeError, ValueError, ZeroDivisionError):
        return None


def inspect_render_output(
    output_path: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    expected_duration = float(
        config.get("duration_seconds")
        or 0
    )

    expected_aspect = str(
        config.get("aspect_ratio")
        or "9:16"
    )

    expected_width, expected_height = dimensions(
        expected_aspect
    )

    errors: list[str] = []
    warnings: list[str] = []

    metadata: dict[str, Any] = {
        "status": "failed",
        "label": "QA Failed",
        "errors": errors,
        "warnings": warnings,
        "expected_duration_seconds": (
            expected_duration
        ),
        "expected_aspect_ratio": expected_aspect,
        "expected_width": expected_width,
        "expected_height": expected_height,
        "duration_seconds": None,
        "duration_delta_seconds": None,
        "width": None,
        "height": None,
        "fps": None,
        "video_codec": None,
        "pixel_format": None,
        "audio_codec": None,
        "audio_sample_rate": None,
        "audio_channels": None,
        "has_audio": False,
        "size_bytes": 0,
        "size_mb": 0.0,
        "checked_at": now().isoformat(),
    }

    if not output_path.is_file():
        errors.append(
            "File output tidak ditemukan"
        )
        return metadata

    size_bytes = output_path.stat().st_size

    metadata["size_bytes"] = size_bytes
    metadata["size_mb"] = round(
        size_bytes / 1024 / 1024,
        2,
    )

    if size_bytes < 50_000:
        errors.append(
            "Ukuran output terlalu kecil"
        )
    elif size_bytes < 150_000:
        warnings.append(
            "Ukuran output lebih kecil dari normal"
        )
    elif size_bytes > 150 * 1024 * 1024:
        warnings.append(
            "Ukuran output melebihi 150 MB"
        )

    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(output_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=45,
    )

    if result.returncode != 0:
        errors.append(
            "FFprobe tidak dapat membaca output: "
            + result.stderr[-500:]
        )
        return metadata

    try:
        payload = json.loads(
            result.stdout or "{}"
        )
    except json.JSONDecodeError:
        errors.append(
            "Metadata FFprobe tidak valid"
        )
        return metadata

    streams = payload.get("streams") or []
    format_info = payload.get("format") or {}

    video_stream = next(
        (
            stream
            for stream in streams
            if stream.get("codec_type") == "video"
        ),
        None,
    )

    audio_stream = next(
        (
            stream
            for stream in streams
            if stream.get("codec_type") == "audio"
        ),
        None,
    )

    if video_stream is None:
        errors.append(
            "Video stream tidak ditemukan"
        )
    else:
        width = video_stream.get("width")
        height = video_stream.get("height")

        metadata["width"] = width
        metadata["height"] = height
        metadata["video_codec"] = (
            video_stream.get("codec_name")
        )
        metadata["pixel_format"] = (
            video_stream.get("pix_fmt")
        )
        metadata["fps"] = parse_ffprobe_rate(
            video_stream.get("avg_frame_rate")
            or video_stream.get("r_frame_rate")
        )

        if (
            width != expected_width
            or height != expected_height
        ):
            errors.append(
                "Resolusi output tidak sesuai preset: "
                f"{width}x{height}, target "
                f"{expected_width}x{expected_height}"
            )

        if metadata["video_codec"] != "h264":
            warnings.append(
                "Codec video bukan H.264"
            )

        if metadata["pixel_format"] != "yuv420p":
            warnings.append(
                "Pixel format bukan yuv420p"
            )

        fps = metadata["fps"]

        if fps is None:
            warnings.append(
                "FPS tidak dapat dibaca"
            )
        elif not 29.0 <= float(fps) <= 31.0:
            warnings.append(
                f"FPS output {fps}, target 30"
            )

    metadata["has_audio"] = audio_stream is not None

    if audio_stream is None:
        if config.get("render_mode") == "raw_catalog":
            errors.append(
                "Audio track tidak ditemukan"
            )
        else:
            warnings.append(
                "Output tidak memiliki audio"
            )
    else:
        metadata["audio_codec"] = (
            audio_stream.get("codec_name")
        )

        sample_rate = audio_stream.get(
            "sample_rate"
        )

        try:
            metadata["audio_sample_rate"] = int(
                sample_rate
            )
        except (TypeError, ValueError):
            metadata["audio_sample_rate"] = None

        metadata["audio_channels"] = (
            audio_stream.get("channels")
        )

        if metadata["audio_codec"] != "aac":
            warnings.append(
                "Codec audio bukan AAC"
            )

        if metadata["audio_sample_rate"] not in {
            44100,
            48000,
        }:
            warnings.append(
                "Sample rate audio tidak standar"
            )

    duration_value = (
        format_info.get("duration")
        or (
            video_stream.get("duration")
            if video_stream
            else None
        )
    )

    try:
        actual_duration = round(
            float(duration_value),
            3,
        )
    except (TypeError, ValueError):
        actual_duration = None

    metadata["duration_seconds"] = actual_duration

    if actual_duration is None:
        errors.append(
            "Durasi output tidak dapat dibaca"
        )
    elif expected_duration > 0:
        duration_delta = round(
            actual_duration - expected_duration,
            3,
        )

        metadata[
            "duration_delta_seconds"
        ] = duration_delta

        absolute_delta = abs(duration_delta)

        if absolute_delta > 1.50:
            errors.append(
                "Durasi output berbeda terlalu jauh: "
                f"{actual_duration:.2f} detik, "
                f"target {expected_duration:.2f} detik"
            )
        elif absolute_delta > 0.60:
            warnings.append(
                "Durasi output sedikit berbeda: "
                f"{actual_duration:.2f} detik, "
                f"target {expected_duration:.2f} detik"
            )

    if errors:
        metadata["status"] = "failed"
        metadata["label"] = "QA Failed"
    elif warnings:
        metadata["status"] = "warning"
        metadata["label"] = "QA Warning"
    else:
        metadata["status"] = "passed"
        metadata["label"] = "QA Passed"

    return metadata


def generate_render_thumbnail(
    output_path: Path,
    thumbnail_path: Path,
    duration_seconds: float | int | None,
) -> bool:
    duration = max(
        1.0,
        float(duration_seconds or 1.0),
    )

    capture_time = min(
        max(duration * 0.20, 1.0),
        max(duration - 0.40, 0.10),
    )

    thumbnail_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{capture_time:.3f}",
        "-i",
        str(output_path),
        "-frames:v",
        "1",
        "-vf",
        (
            "scale="
            "'min(720,iw)':-2:"
            "flags=lanczos"
        ),
        "-q:v",
        "3",
        str(thumbnail_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=90,
    )

    return bool(
        result.returncode == 0
        and thumbnail_path.is_file()
        and thumbnail_path.stat().st_size > 5_000
    )



def render_job(
    job_id: int,
) -> dict[str, Any]:
    db = SessionLocal()

    temp_dir = (
        STORAGE_ROOT
        / "tmp"
        / f"render-{job_id}-{uuid.uuid4().hex}"
    )

    temp_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        job = db.get(
            RenderJob,
            job_id,
        )

        if job is None:
            raise RuntimeError(
                "Render job tidak ditemukan"
            )

        campaign = db.get(
            CreativeCampaign,
            job.campaign_id,
        )

        if campaign is None:
            raise RuntimeError(
                "Campaign tidak ditemukan"
            )

        job.status = "rendering"
        job.started_at = now()
        job.error_message = None

        campaign.status = "rendering"
        campaign.updated_at = now()

        db.commit()

        relative_output = (
            f"renders/{campaign.id}/"
            f"creative-{job.variation_index:03d}.mp4"
        )

        output_path = (
            STORAGE_ROOT
            / relative_output
        )

        voiceover_path = prepare_voiceover(
            job.config,
            temp_dir,
        )

        render_video(
            job.config,
            output_path,
            temp_dir,
            voiceover_path,
            campaign.id,
            campaign.product_id,
        )

        render_qa = inspect_render_output(
            output_path,
            job.config,
        )

        if render_qa.get("status") == "failed":
            raise RuntimeError(
                "Render QA gagal: "
                + "; ".join(
                    render_qa.get("errors")
                    or ["Output tidak valid"]
                )
            )

        relative_thumbnail = (
            f"renders/{campaign.id}/"
            f"creative-{job.variation_index:03d}.jpg"
        )

        thumbnail_path = (
            STORAGE_ROOT
            / relative_thumbnail
        )

        thumbnail_created = generate_render_thumbnail(
            output_path,
            thumbnail_path,
            render_qa.get("duration_seconds")
            or job.config.get("duration_seconds"),
        )

        if not thumbnail_created:
            relative_thumbnail = None

            render_qa.setdefault(
                "warnings",
                [],
            ).append(
                "Thumbnail gagal dibuat"
            )

            if render_qa.get("status") == "passed":
                render_qa["status"] = "warning"
                render_qa["label"] = "QA Warning"

        db.expire_all()
        job = db.get(
            RenderJob,
            job_id,
        )

        if job is None:
            return {
                "ok": False,
                "job_id": job_id,
                "skipped": True,
                "reason": "render_job_deleted",
            }

        campaign = db.get(
            CreativeCampaign,
            job.campaign_id,
        )

        if campaign is None:
            return {
                "ok": False,
                "job_id": job_id,
                "skipped": True,
                "reason": "campaign_deleted",
            }

        updated_config = dict(
            job.config or {}
        )

        updated_config["qa"] = render_qa
        updated_config["thumbnail_path"] = (
            relative_thumbnail
        )
        updated_config["thumbnail_created"] = bool(
            relative_thumbnail
        )

        job.config = updated_config
        job.output_path = relative_output
        job.status = "completed"
        job.finished_at = now()

        db.commit()
        refresh_campaign(
            db,
            campaign.id,
        )

        return {
            "ok": True,
            "job_id": job.id,
            "output_path": relative_output,
            "thumbnail_path": relative_thumbnail,
            "qa": render_qa,
        }

    except Exception as error:
        db.rollback()
        job = db.get(
            RenderJob,
            job_id,
        )

        if job is None:
            return {
                "ok": False,
                "job_id": job_id,
                "skipped": True,
                "reason": "render_job_deleted",
            }

        campaign = db.get(
            CreativeCampaign,
            job.campaign_id,
        )

        if campaign is None:
            return {
                "ok": False,
                "job_id": job_id,
                "skipped": True,
                "reason": "campaign_deleted",
            }

        if job is not None:
            job.status = "failed"
            job.error_message = str(error)[-4000:]
            job.finished_at = now()

            db.commit()
            refresh_campaign(
                db,
                job.campaign_id,
            )

        raise

    finally:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )

        db.close()


@router.get("/api/voiceover/status")
def voiceover_status():
    return {
        "ok": True,
        "configured": bool(
            ELEVENLABS_API_KEY
        ),
        "provider": "elevenlabs",
        "model_id": ELEVENLABS_MODEL_ID,
        "output_format": (
            ELEVENLABS_OUTPUT_FORMAT
        ),
        "language_code": (
            ELEVENLABS_LANGUAGE_CODE
        ),
    }


@router.get("/api/voiceover/voices")
def voiceover_voices():
    try:
        voices = fetch_elevenlabs_voices()
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error

    return {
        "ok": True,
        "voices": voices,
    }


@router.post("/api/voiceover/preview")
def voiceover_preview(
    payload: VoicePreviewRequest,
):
    preview_dir = (
        STORAGE_ROOT
        / "voice-previews"
    )

    filename = (
        f"preview-{uuid.uuid4().hex}.mp3"
    )

    destination = (
        preview_dir
        / filename
    )

    try:
        generate_elevenlabs_audio(
            voice_id=payload.voice_id,
            text=payload.text,
            destination=destination,
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error

    return {
        "ok": True,
        "audio_url": (
            f"/media/voice-previews/{filename}"
        ),
    }


@router.get("/api/studio/stats")
def studio_stats(
    db: Session = Depends(get_db),
):
    return {
        "ok": True,
        "campaigns": (
            db.scalar(
                select(
                    func.count(
                        CreativeCampaign.id
                    )
                )
            )
            or 0
        ),
        "renders": (
            db.scalar(
                select(
                    func.count(RenderJob.id)
                ).where(
                    RenderJob.status
                    == "completed"
                )
            )
            or 0
        ),
        "queued": (
            db.scalar(
                select(
                    func.count(RenderJob.id)
                ).where(
                    RenderJob.status.in_(
                        ["queued", "rendering"]
                    )
                )
            )
            or 0
        ),
        "voiceover_configured": bool(
            ELEVENLABS_API_KEY
        ),
        "ai_video_configured": bool(
            GEMINI_API_KEY
        ),
        "ai_video_model": GEMINI_VIDEO_MODEL,
    }


@router.get("/api/ai-video/status")
def ai_video_status():
    return {
        "ok": True,
        "configured": bool(GEMINI_API_KEY),
        "provider": "gemini_veo",
        "model": GEMINI_VIDEO_MODEL,
        "image_model": GEMINI_IMAGE_MODEL,
        "base_url": GEMINI_BASE_URL,
        "timeout_seconds": (
            GEMINI_VIDEO_TIMEOUT_SECONDS
        ),
    }



def probe_uploaded_raw_video(
    absolute_path: Path,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "duration_seconds": None,
        "width": None,
        "height": None,
        "fps": None,
        "orientation": None,
        "has_audio": False,
    }

    if not absolute_path.is_file():
        return metadata

    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(absolute_path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return metadata

        payload = json.loads(
            result.stdout or "{}"
        )

    except Exception:
        return metadata

    streams = payload.get("streams") or []

    video_stream = next(
        (
            item
            for item in streams
            if item.get("codec_type") == "video"
        ),
        None,
    )

    audio_stream = next(
        (
            item
            for item in streams
            if item.get("codec_type") == "audio"
        ),
        None,
    )

    metadata["has_audio"] = audio_stream is not None

    if video_stream:
        width = video_stream.get("width")
        height = video_stream.get("height")

        metadata["width"] = width
        metadata["height"] = height

        if width and height:
            if height > width:
                metadata["orientation"] = "portrait"
            elif width > height:
                metadata["orientation"] = "landscape"
            else:
                metadata["orientation"] = "square"

        fps_value = (
            video_stream.get("avg_frame_rate")
            or video_stream.get("r_frame_rate")
            or ""
        )

        try:
            if "/" in str(fps_value):
                numerator, denominator = str(
                    fps_value
                ).split("/", 1)

                denominator_value = float(
                    denominator or 1
                )

                if denominator_value:
                    metadata["fps"] = round(
                        float(numerator)
                        / denominator_value,
                        2,
                    )
            elif fps_value:
                metadata["fps"] = round(
                    float(fps_value),
                    2,
                )
        except Exception:
            metadata["fps"] = None

        duration_value = (
            video_stream.get("duration")
            or (payload.get("format") or {}).get(
                "duration"
            )
        )

        try:
            if duration_value is not None:
                metadata["duration_seconds"] = round(
                    float(duration_value),
                    2,
                )
        except Exception:
            metadata["duration_seconds"] = None

    return metadata


def raw_video_settings_path(
    product_id: int,
) -> Path:
    folder = (
        STORAGE_ROOT
        / "products"
        / str(product_id)
    )

    folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    return folder / "raw-video-settings.json"


def load_raw_video_settings(
    product_id: int,
) -> dict[str, dict[str, Any]]:
    settings_path = raw_video_settings_path(
        product_id
    )

    if not settings_path.is_file():
        return {}

    try:
        payload = json.loads(
            settings_path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(payload, dict):
            return {}

        return {
            str(key): value
            for key, value in payload.items()
            if isinstance(value, dict)
        }

    except Exception:
        return {}


def save_raw_video_settings(
    product_id: int,
    settings: dict[str, dict[str, Any]],
) -> None:
    settings_path = raw_video_settings_path(
        product_id
    )

    temporary_path = settings_path.with_suffix(
        ".json.tmp"
    )

    temporary_path.write_text(
        json.dumps(
            settings,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(settings_path)



def music_library_root() -> Path:
    folder = STORAGE_ROOT / "music-library"
    folder.mkdir(
        parents=True,
        exist_ok=True,
    )
    return folder


def music_library_manifest_path() -> Path:
    return (
        music_library_root()
        / "manifest.json"
    )


def load_music_library_manifest() -> dict[str, dict[str, Any]]:
    manifest_path = music_library_manifest_path()

    if not manifest_path.is_file():
        return {}

    try:
        payload = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(payload, dict):
            return {}

        return {
            str(key): value
            for key, value in payload.items()
            if isinstance(value, dict)
        }

    except Exception:
        return {}


def save_music_library_manifest(
    manifest: dict[str, dict[str, Any]],
) -> None:
    path = music_library_manifest_path()
    temporary = path.with_suffix(".json.tmp")

    temporary.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary.replace(path)


def music_item_to_dict(
    music_id: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    archive = str(
        item.get("archive") or ""
    )

    return {
        "music_id": music_id,
        "title": item.get("title") or music_id,
        "original_name": (
            item.get("original_name")
            or item.get("title")
            or music_id
        ),
        "archive": archive,
        "url": (
            f"/media/{archive}"
            if archive
            else None
        ),
        "mime_type": item.get("mime_type"),
        "size_bytes": item.get("size_bytes"),
        "duration_seconds": item.get(
            "duration_seconds"
        ),
        "created_at": item.get("created_at"),
    }


def resolve_music_library_item(
    music_id: str | None,
) -> tuple[dict[str, Any], Path] | None:
    clean_id = str(
        music_id or ""
    ).strip()

    if not clean_id:
        return None

    manifest = load_music_library_manifest()
    item = manifest.get(clean_id)

    if not item:
        return None

    archive = str(
        item.get("archive") or ""
    ).strip()

    if not archive:
        return None

    absolute_path = STORAGE_ROOT / archive

    try:
        absolute_path.resolve().relative_to(
            STORAGE_ROOT.resolve()
        )
    except ValueError:
        return None

    if (
        not absolute_path.is_file()
        or absolute_path.stat().st_size < 100
    ):
        return None

    return item, absolute_path


@router.get("/api/music-library")
def list_music_library():
    manifest = load_music_library_manifest()

    items = [
        music_item_to_dict(
            music_id,
            item,
        )
        for music_id, item in manifest.items()
    ]

    items.sort(
        key=lambda item:
            item.get("created_at") or "",
        reverse=True,
    )

    return {
        "ok": True,
        "music": items,
    }


@router.post("/api/music-library")
async def upload_music_library(
    files: list[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Tidak ada file musik dipilih",
        )

    if len(files) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maksimal 10 file musik per upload",
        )

    allowed_extensions = {
        ".mp3",
        ".wav",
        ".m4a",
        ".aac",
        ".ogg",
    }

    max_bytes = 50 * 1024 * 1024
    root = music_library_root()
    manifest = load_music_library_manifest()

    created_paths: list[Path] = []
    created_ids: list[str] = []

    try:
        for upload in files:
            original_name = Path(
                upload.filename or "music"
            ).name

            extension = Path(
                original_name
            ).suffix.lower()

            if extension not in allowed_extensions:
                raise HTTPException(
                    status_code=415,
                    detail=(
                        "Format musik tidak didukung: "
                        f"{original_name}"
                    ),
                )

            music_id = uuid.uuid4().hex
            stored_name = (
                f"{music_id}{extension}"
            )
            absolute_path = root / stored_name

            created_paths.append(absolute_path)
            created_ids.append(music_id)

            total = 0

            with absolute_path.open("wb") as output:
                while True:
                    chunk = await upload.read(
                        1024 * 1024
                    )

                    if not chunk:
                        break

                    total += len(chunk)

                    if total > max_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=(
                                f"{original_name} "
                                "melebihi 50 MB"
                            ),
                        )

                    output.write(chunk)

            await upload.close()

            duration = media_duration_seconds(
                absolute_path
            )

            if (
                duration is None
                or duration <= 0
            ):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "File audio tidak valid: "
                        f"{original_name}"
                    ),
                )

            archive = (
                absolute_path
                .relative_to(STORAGE_ROOT)
                .as_posix()
            )

            manifest[music_id] = {
                "title": Path(
                    original_name
                ).stem,
                "original_name": original_name,
                "archive": archive,
                "mime_type": (
                    upload.content_type
                    or "audio/mpeg"
                ),
                "size_bytes": total,
                "duration_seconds": round(
                    float(duration),
                    2,
                ),
                "created_at": now().isoformat(),
            }

        save_music_library_manifest(manifest)

    except Exception:
        for music_id in created_ids:
            manifest.pop(music_id, None)

        for created_path in created_paths:
            created_path.unlink(
                missing_ok=True
            )

        save_music_library_manifest(manifest)
        raise

    return {
        "ok": True,
        "message": (
            f"{len(created_ids)} musik "
            "berhasil diunggah"
        ),
        "music": [
            music_item_to_dict(
                music_id,
                manifest[music_id],
            )
            for music_id in created_ids
        ],
    }


@router.delete("/api/music-library/{music_id}")
def delete_music_library_item(
    music_id: str,
):
    manifest = load_music_library_manifest()
    item = manifest.get(music_id)

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Musik tidak ditemukan",
        )

    resolved = resolve_music_library_item(
        music_id
    )

    if resolved:
        _, absolute_path = resolved
        absolute_path.unlink(
            missing_ok=True
        )

    manifest.pop(music_id, None)
    save_music_library_manifest(manifest)

    return {
        "ok": True,
        "message": "Musik berhasil dihapus",
    }


@router.get("/api/products/{product_id}/raw-videos")
def product_raw_videos(
    product_id: int,
    db: Session = Depends(get_db),
):
    product = db.get(
        Product,
        product_id,
    )

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Produk tidak ditemukan",
        )

    video_assets = list(
        db.scalars(
            select(ProductAsset)
            .where(
                ProductAsset.product_id == product_id,
                ProductAsset.asset_type == "video",
            )
            .order_by(
                ProductAsset.created_at.desc(),
                ProductAsset.id.desc(),
            )
        ).all()
    )

    video_settings = load_raw_video_settings(
        product_id
    )

    raw_videos = []

    for asset in video_assets:
        absolute_path = (
            STORAGE_ROOT
            / asset.relative_path
        )

        metadata = probe_uploaded_raw_video(
            absolute_path
        )

        asset_settings = video_settings.get(
            str(asset.id),
            {}
        )

        raw_videos.append(
            {
                "clip_id": f"asset-{asset.id}",
                "asset_id": asset.id,
                "product_id": asset.product_id,
                "label": asset.original_name,
                "title": asset.original_name,
                "archive": asset.relative_path,
                "url": f"/media/{asset.relative_path}",
                "mime_type": asset.mime_type,
                "size_bytes": asset.size_bytes,
                "source": "uploaded",
                "video_type": asset_settings.get(
                    "video_type",
                    "demo",
                ),
                "fit_mode": asset_settings.get(
                    "fit_mode",
                    "auto",
                ),
                "is_primary": bool(
                    asset_settings.get(
                        "is_primary",
                        False,
                    )
                ),
                "trim_start": float(
                    asset_settings.get(
                        "trim_start",
                        0.0,
                    )
                    or 0.0
                ),
                "trim_end": (
                    float(
                        asset_settings["trim_end"]
                    )
                    if asset_settings.get(
                        "trim_end"
                    ) is not None
                    else None
                ),
                "duration_seconds": metadata.get(
                    "duration_seconds"
                ),
                "width": metadata.get("width"),
                "height": metadata.get("height"),
                "fps": metadata.get("fps"),
                "orientation": metadata.get(
                    "orientation"
                ),
                "has_audio": metadata.get(
                    "has_audio",
                    False,
                ),
                "created_at": (
                    asset.created_at.isoformat()
                    if asset.created_at
                    else None
                ),
            }
        )

    raw_videos.sort(
        key=lambda item: (
            not bool(
                item.get("is_primary")
            ),
            item.get("created_at") or "",
        )
    )

    return {
        "ok": True,
        "product": {
            "id": product.id,
            "name": product.name,
        },
        "raw_videos": raw_videos,
    }




@router.put(
    "/api/products/{product_id}/raw-videos/"
    "{asset_id}/settings"
)
def update_raw_video_asset_settings(
    product_id: int,
    asset_id: int,
    payload: RawVideoAssetSettingsRequest,
    db: Session = Depends(get_db),
):
    product = db.get(
        Product,
        product_id,
    )

    if not product:
        raise HTTPException(
            status_code=404,
            detail="Produk tidak ditemukan",
        )

    asset = db.get(
        ProductAsset,
        asset_id,
    )

    if (
        not asset
        or asset.product_id != product_id
        or asset.asset_type != "video"
    ):
        raise HTTPException(
            status_code=404,
            detail="Raw video tidak ditemukan",
        )

    trim_start = round(
        float(payload.trim_start or 0.0),
        3,
    )

    trim_end = (
        round(
            float(payload.trim_end),
            3,
        )
        if payload.trim_end is not None
        else None
    )

    if (
        trim_end is not None
        and trim_end <= trim_start
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Trim selesai harus lebih besar "
                "daripada trim mulai"
            ),
        )

    settings = load_raw_video_settings(
        product_id
    )

    if payload.is_primary:
        for key, item in settings.items():
            if isinstance(item, dict):
                item["is_primary"] = False

    settings[str(asset_id)] = {
        "video_type": payload.video_type,
        "fit_mode": payload.fit_mode,
        "is_primary": bool(
            payload.is_primary
        ),
        "trim_start": trim_start,
        "trim_end": trim_end,
    }

    save_raw_video_settings(
        product_id,
        settings,
    )

    return {
        "ok": True,
        "message": "Pengaturan raw video disimpan",
        "asset_id": asset_id,
        "settings": settings[str(asset_id)],
    }

@router.post(
    "/api/products/{product_id}/image-variations"
)
def generate_image_variations(
    product_id: int,
    payload: ImageVariationRequest,
    db: Session = Depends(get_db),
):
    product = db.get(
        Product,
        product_id,
    )

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Produk tidak ditemukan",
        )

    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=400,
            detail=(
                "GEMINI_API_KEY belum dikonfigurasi "
                "untuk image variation"
            ),
        )

    source: dict[str, str]

    if payload.source_kind == "asset":
        if not payload.source_asset_id:
            raise HTTPException(
                status_code=400,
                detail="Pilih source image asset",
            )

        asset = db.get(
            ProductAsset,
            payload.source_asset_id,
        )

        if (
            asset is None
            or asset.product_id != product_id
            or asset.asset_type != "image"
        ):
            raise HTTPException(
                status_code=404,
                detail="Source image asset tidak ditemukan",
            )

        source = {
            "kind": "local",
            "path": asset.relative_path,
        }

    elif payload.source_kind == "url":
        if not payload.source_url:
            raise HTTPException(
                status_code=400,
                detail="Source URL belum diisi",
            )

        source = {
            "kind": "remote",
            "url": payload.source_url,
        }

    else:
        if not product.primary_image_url:
            raise HTTPException(
                status_code=400,
                detail="Produk belum memiliki primary image",
            )

        source = {
            "kind": "remote",
            "url": product.primary_image_url,
        }

    destination_dir = (
        STORAGE_ROOT
        / "products"
        / str(product_id)
        / "assets"
    )

    temp_dir = (
        STORAGE_ROOT
        / "tmp"
        / f"image-variations-{uuid.uuid4().hex}"
    )

    temp_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    saved_records: list[ProductAsset] = []
    created_files: list[Path] = []

    try:
        source_path = prepare_source(
            source,
            temp_dir,
        )

        for index in range(payload.count):
            stored_name = (
                f"{uuid.uuid4().hex}.png"
            )

            absolute_path = (
                destination_dir
                / stored_name
            )

            generated_path, mime_type = (
                generate_gemini_image_variation(
                    source_path=source_path,
                    product=product,
                    preset=payload.preset,
                    index=index,
                    destination=absolute_path,
                    custom_prompt=payload.custom_prompt,
                )
            )

            created_files.append(
                generated_path
            )

            relative_path = (
                generated_path
                .relative_to(STORAGE_ROOT)
                .as_posix()
            )

            record = ProductAsset(
                product_id=product_id,
                asset_type="image",
                original_name=(
                    "generated-"
                    f"{payload.preset}-"
                    f"{index + 1:02d}.png"
                ),
                stored_name=stored_name,
                mime_type=mime_type,
                size_bytes=generated_path.stat().st_size,
                relative_path=relative_path,
                source="generated",
            )

            db.add(record)
            saved_records.append(record)

        db.commit()

        for record in saved_records:
            db.refresh(record)

    except Exception as error:
        db.rollback()

        for created_file in created_files:
            created_file.unlink(
                missing_ok=True,
            )

        raise HTTPException(
            status_code=500,
            detail=str(error)[-1200:],
        ) from error

    finally:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )

    return {
        "ok": True,
        "message": (
            f"{len(saved_records)} image variation "
            "berhasil dibuat"
        ),
        "assets": [
            {
                "id": asset.id,
                "product_id": asset.product_id,
                "asset_type": asset.asset_type,
                "original_name": asset.original_name,
                "mime_type": asset.mime_type,
                "size_bytes": asset.size_bytes,
                "size_label": (
                    f"{asset.size_bytes / 1024:.1f} KB"
                    if asset.size_bytes < 1024 * 1024
                    else (
                        f"{asset.size_bytes / 1024 / 1024:.1f} MB"
                    )
                ),
                "url": f"/media/{asset.relative_path}",
                "source": asset.source,
                "created_at": (
                    asset.created_at.isoformat()
                    if asset.created_at
                    else None
                ),
            }
            for asset in saved_records
        ],
    }


@router.post(
    "/api/products/{product_id}/campaigns"
)
def create_campaign(
    product_id: int,
    payload: CampaignRequest,
    db: Session = Depends(get_db),
):
    product = db.get(
        Product,
        product_id,
    )

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Produk tidak ditemukan",
        )

    selected_product_ids: list[int] = []
    for item in [product_id, *payload.product_ids]:
        if item not in selected_product_ids:
            selected_product_ids.append(item)

    products = list(
        db.scalars(
            select(Product).where(
                Product.id.in_(selected_product_ids)
            )
        ).all()
    )
    products_by_id = {
        item.id: item
        for item in products
    }
    missing_ids = [
        item
        for item in selected_product_ids
        if item not in products_by_id
    ]

    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=(
                "Produk tambahan tidak ditemukan: "
                + ", ".join(str(item) for item in missing_ids)
            ),
        )

    products = [
        products_by_id[item]
        for item in selected_product_ids
    ]

    if (
        payload.render_mode == "ai_video"
        and not GEMINI_API_KEY
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "GEMINI_API_KEY belum dikonfigurasi "
                "untuk AI Product Video"
            ),
        )

    if payload.voiceover_enabled:
        if not ELEVENLABS_API_KEY:
            raise HTTPException(
                status_code=400,
                detail=(
                    "ElevenLabs belum dikonfigurasi"
                ),
            )

        if not payload.voice_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Pilih voice ElevenLabs"
                ),
            )

        if (
            payload.voiceover_mode == "custom"
            and not (
                payload.voiceover_text
                or ""
            ).strip()
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Naskah custom voice-over "
                    "belum diisi"
                ),
            )

    assets = list(
        db.scalars(
            select(ProductAsset).where(
                ProductAsset.product_id.in_(
                    selected_product_ids
                )
            )
        ).all()
    )

    analyses_list = list(
        db.scalars(
            select(ProductAnalysis).where(
                ProductAnalysis.product_id.in_(
                    selected_product_ids
                )
            )
        ).all()
    )
    analyses = {
        item.product_id: item
        for item in analyses_list
    }
    analysis = analyses.get(product_id)

    assets_by_product: dict[int, list[ProductAsset]] = {
        item: []
        for item in selected_product_ids
    }
    for asset in assets:
        assets_by_product.setdefault(
            asset.product_id,
            [],
        ).append(asset)

    sources: list[dict[str, str]] = []
    for item in products:
        sources.extend(
            enrich_sources_with_product(
                image_sources(
                    item,
                    assets_by_product.get(
                        item.id,
                        [],
                    ),
                ),
                item,
            )
        )

    if not sources:
        raise HTTPException(
            status_code=400,
            detail=(
                "Produk terpilih belum memiliki gambar "
                "untuk dirender"
            ),
        )

    hooks, ctas = creative_text_for_collection(
        products,
        analyses,
        payload.audience,
        payload.min_order_qty,
    )

    layout_snapshot = (
        build_raw_catalog_layout_snapshot(
            raw_clips,
            payload.aspect_ratio,
        )
    )

    campaign = CreativeCampaign(
        product_id=product_id,
        name=(
            payload.name
            or (
                f"{product_collection_name(products)} - "
                f"{payload.variations} Variations"
            )
        ),
        status="queued",
        variations=payload.variations,
        settings={
            **payload.model_dump(),
            "product_ids": selected_product_ids,
            "product_names": [
                item.name
                for item in products
            ],
            "product_count": len(products),
        },
        created_at=now(),
        updated_at=now(),
    )

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    jobs: list[RenderJob] = []

    for index in range(
        payload.variations
    ):
        config = build_variation_config(
            product=product,
            analysis=analysis,
            source=(
                sources[
                    index % len(sources)
                ]
            ),
            sources=sources,
            hook=(
                hooks[
                    index % len(hooks)
                ]
            ),
            cta=(
                ctas[
                    index % len(ctas)
                ]
            ),
            index=index,
            request=payload,
            products=products,
            analyses=analyses,
        )

        job = RenderJob(
            campaign_id=campaign.id,
            variation_index=index + 1,
            status="queued",
            config=config,
        )

        db.add(job)
        jobs.append(job)

    db.commit()

    queue = render_queue()

    for job in jobs:
        db.refresh(job)

        queued = queue.enqueue(
            render_job,
            job.id,
            retry=Retry(
                max=1,
                interval=[10],
            ),
            job_timeout=RENDER_JOB_TIMEOUT_SECONDS,
            result_ttl=86400,
            failure_ttl=604800,
        )

        job.rq_job_id = queued.id

    db.commit()

    return {
        "ok": True,
        "message": (
            f"{payload.variations} variasi "
            "masuk antrean render"
        ),
        "campaign": campaign_to_dict(
            campaign
        ),
    }


@router.get(
    "/api/products/{product_id}/campaigns"
)
def list_campaigns(
    product_id: int,
    db: Session = Depends(get_db),
):
    campaigns = list(
        db.scalars(
            select(CreativeCampaign)
            .where(
                CreativeCampaign.product_id
                == product_id
            )
            .order_by(
                CreativeCampaign.created_at.desc()
            )
        ).all()
    )

    return {
        "ok": True,
        "campaigns": [
            campaign_to_dict(campaign)
            for campaign in campaigns
        ],
    }


@router.post("/api/campaigns/multi-product")
def create_multi_product_campaign(
    payload: CampaignRequest,
    db: Session = Depends(get_db),
):
    raise HTTPException(
        status_code=410,
        detail=(
            "Multi produk slideshow sudah dihentikan. "
            "Gunakan Raw Video Catalog Ads."
        ),
    )


@router.post("/api/campaigns/raw-video-catalog")
def create_raw_video_catalog_campaign(
    payload: RawVideoCatalogRequest,
    db: Session = Depends(get_db),
):
    selected_music: dict[str, Any] | None = None

    if payload.music_enabled:
        resolved_music = resolve_music_library_item(
            payload.music_id
        )

        if resolved_music is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Musik latar tidak ditemukan "
                    "atau file sudah tidak tersedia"
                ),
            )

        selected_music_item, selected_music_path = (
            resolved_music
        )

        selected_music = {
            "enabled": True,
            "music_id": payload.music_id,
            "title": (
                selected_music_item.get("title")
                or selected_music_item.get(
                    "original_name"
                )
                or "Background Music"
            ),
            "archive": (
                selected_music_path
                .relative_to(STORAGE_ROOT)
                .as_posix()
            ),
            "duration_seconds": (
                selected_music_item.get(
                    "duration_seconds"
                )
            ),
            "volume": round(
                float(payload.music_volume),
                3,
            ),
            "ducking": bool(
                payload.music_ducking
            ),
        }

    if payload.voiceover_enabled:
        if not ELEVENLABS_API_KEY:
            raise HTTPException(
                status_code=400,
                detail="ElevenLabs belum dikonfigurasi",
            )

        if not payload.voice_id:
            raise HTTPException(
                status_code=400,
                detail="Pilih voice ElevenLabs",
            )

        if (
            payload.voiceover_mode == "custom"
            and not (
                payload.voiceover_text
                or ""
            ).strip()
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Naskah custom voice-over belum diisi"
                ),
            )

    selected_product_ids = [
        item.product_id
        for item in payload.product_clips
    ]


    if not 5 <= len(selected_product_ids) <= 6:
        raise HTTPException(
            status_code=400,
            detail=(
                "Raw Video Catalog membutuhkan "
                "5 sampai 6 produk."
            ),
        )

    if len(set(selected_product_ids)) != len(
        selected_product_ids
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Produk yang sama tidak boleh dipilih "
                "lebih dari satu kali."
            ),
        )

    if not 20 <= payload.duration_seconds <= 30:
        raise HTTPException(
            status_code=400,
            detail=(
                "Durasi video katalog harus antara "
                "20 sampai 30 detik."
            ),
        )

    products = list(
        db.scalars(
            select(Product).where(
                Product.id.in_(selected_product_ids)
            )
        ).all()
    )

    products_by_id = {
        item.id: item
        for item in products
    }

    missing_ids = [
        item
        for item in selected_product_ids
        if item not in products_by_id
    ]

    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=(
                "Produk tidak ditemukan: "
                + ", ".join(str(item) for item in missing_ids)
            ),
        )

    ordered_products = [
        products_by_id[item]
        for item in selected_product_ids
    ]

    raw_clips: list[dict[str, Any]] = []

    for selection in payload.product_clips:
        clip = None

        clip_id = str(
            selection.clip_id or ""
        ).strip()

        if clip_id.startswith("asset-"):
            try:
                asset_id = int(
                    clip_id.removeprefix("asset-")
                )
            except ValueError:
                asset_id = 0

            asset = (
                db.get(ProductAsset, asset_id)
                if asset_id
                else None
            )

            if (
                asset is not None
                and asset.product_id
                    == selection.product_id
                and asset.asset_type == "video"
            ):
                absolute_video_path = (
                    STORAGE_ROOT
                    / asset.relative_path
                )

                if absolute_video_path.is_file():
                    source_metadata = (
                        probe_uploaded_raw_video(
                            absolute_video_path
                        )
                    )

                    source_duration = (
                        source_metadata.get(
                            "duration_seconds"
                        )
                    )

                    source_orientation = (
                        source_metadata.get(
                            "orientation"
                        )
                    )

                    resolved_fit_mode = (
                        resolve_raw_catalog_fit_mode(
                            selection.fit_mode,
                            selection.video_type,
                            source_orientation,
                            payload.aspect_ratio,
                        )
                    )

                    clip = {
                        "clip_id": clip_id,
                        "asset_id": asset.id,
                        "archive": asset.relative_path,
                        "label": asset.original_name,
                        "source": "uploaded",
                        "mime_type": asset.mime_type,
                        "trim_start": float(
                            selection.trim_start
                            or 0.0
                        ),
                        "trim_end": (
                            float(selection.trim_end)
                            if selection.trim_end
                            is not None
                            else None
                        ),
                        "video_type": (
                            selection.video_type
                            or "demo"
                        ),
                        "fit_mode": resolved_fit_mode,
                        "requested_fit_mode": (
                            selection.fit_mode
                            or "auto"
                        ),
                        "source_orientation": (
                            source_orientation
                        ),
                        "source_width": (
                            source_metadata.get("width")
                        ),
                        "source_height": (
                            source_metadata.get("height")
                        ),
                        "source_duration_seconds": (
                            float(source_duration)
                            if source_duration
                            is not None
                            else None
                        ),
                    }

        if clip is None:
            product = products_by_id[
                selection.product_id
            ]
            raise HTTPException(
                status_code=400,
                detail=(
                    "Raw video tidak ditemukan untuk "
                    f"{product.name}"
                ),
            )

        trim_start = float(
            clip.get("trim_start")
            or 0.0
        )

        trim_end = clip.get("trim_end")

        if (
            trim_end is not None
            and float(trim_end) <= trim_start
        ):
            product = products_by_id[
                selection.product_id
            ]

            raise HTTPException(
                status_code=422,
                detail=(
                    "Trim selesai harus lebih besar "
                    "daripada trim mulai untuk "
                    f"{product.name}"
                ),
            )

        source_duration = clip.get(
            "source_duration_seconds"
        )

        if source_duration is not None:
            source_duration = float(
                source_duration
            )

            if trim_start >= source_duration:
                product = products_by_id[
                    selection.product_id
                ]

                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Trim mulai berada di luar "
                        "durasi video untuk "
                        f"{product.name}"
                    ),
                )

            if (
                trim_end is not None
                and float(trim_end)
                    > source_duration + 0.05
            ):
                product = products_by_id[
                    selection.product_id
                ]

                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Trim selesai melebihi "
                        "durasi video untuk "
                        f"{product.name}"
                    ),
                )

        effective_end = (
            float(trim_end)
            if trim_end is not None
            else source_duration
        )

        effective_duration = (
            max(
                0.0,
                effective_end - trim_start,
            )
            if effective_end is not None
            else None
        )

        if (
            effective_duration is not None
            and effective_duration < 0.50
        ):
            product = products_by_id[
                selection.product_id
            ]

            raise HTTPException(
                status_code=422,
                detail=(
                    "Bagian video setelah trim "
                    "terlalu pendek untuk "
                    f"{product.name}"
                ),
            )

        clip["effective_duration_seconds"] = (
            round(effective_duration, 3)
            if effective_duration is not None
            else None
        )

        product = products_by_id[
            selection.product_id
        ]
        clip["product_name"] = product.name
        if product.price_value is not None:
            clip["product_price_label"] = format_rupiah(
                product.price_value
            )
        else:
            clip["product_price_label"] = (
                product.price_label
                or "Cek harga"
            )
        clip["product_id"] = product.id
        raw_clips.append(clip)

    analyses_list = list(
        db.scalars(
            select(ProductAnalysis).where(
                ProductAnalysis.product_id.in_(
                    selected_product_ids
                )
            )
        ).all()
    )
    analyses = {
        item.product_id: item
        for item in analyses_list
    }

    anchor = ordered_products[0]
    analysis = analyses.get(anchor.id)

    hooks, ctas = creative_text_for_collection(
        ordered_products,
        analyses,
        payload.audience,
        payload.min_order_qty,
    )

    template_hooks, template_ctas = (
        creative_template_text(
            payload.creative_template,
            ordered_products,
        )
    )

    hooks = merge_unique_creative_text(
        template_hooks,
        hooks,
    )

    ctas = merge_unique_creative_text(
        template_ctas,
        ctas,
    )

    template_label = creative_template_label(
        payload.creative_template
    )

    promo_label = raw_catalog_promo_label(payload)

    campaign = CreativeCampaign(
        product_id=anchor.id,
        name=(
            payload.name
            or (
                f"{product_collection_name(ordered_products)} "
                "Raw Video Catalog"
            )
        ),
        status="queued",
        variations=payload.variations,
        settings={
            **payload.model_dump(),
            "render_mode": "raw_catalog",
            "creative_template": payload.creative_template,
            "creative_template_label": template_label,
            "product_ids": selected_product_ids,
            "product_names": [
                item.name
                for item in ordered_products
            ],
            "product_count": len(ordered_products),
            "smart_visual_layout": True,
            "layout_snapshot": layout_snapshot,
        },
        created_at=now(),
        updated_at=now(),
    )

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    jobs: list[RenderJob] = []

    for index in range(payload.variations):
        hook = hooks[index % len(hooks)]
        cta = ctas[index % len(ctas)]
        voiceover_script = None

        if payload.voiceover_enabled:
            voiceover_script = build_voiceover_script(
                product=anchor,
                analysis=analysis,
                hook=hook,
                cta=cta,
                duration_seconds=payload.duration_seconds,
                mode=payload.voiceover_mode,
                custom_text=payload.voiceover_text,
                audience=payload.audience,
                min_order_qty=payload.min_order_qty,
                products=ordered_products,
                analyses=analyses,
            )

            if (
                promo_label
                and payload.voiceover_mode == "auto"
            ):
                voiceover_script = (
                    f"{voiceover_script} {promo_label}."
                )

        config = {
            "render_mode": "raw_catalog",
            "creative_template": payload.creative_template,
            "creative_template_label": template_label,
            "product_name": product_collection_name(
                ordered_products
            ),
            "product_names": [
                item.name
                for item in ordered_products
            ],
            "product_ids": selected_product_ids,
            "product_count": len(ordered_products),
            "price_label": product_collection_price_label(
                ordered_products
            ),
            "hook": hook,
            "cta": cta,
            "audience": payload.audience,
            "min_order_qty": payload.min_order_qty,
            "duration_seconds": payload.duration_seconds,
            "aspect_ratio": payload.aspect_ratio,
            "raw_clips": raw_clips,
            "smart_visual_layout": True,
            "layout_snapshot": layout_snapshot,
            "safe_area": layout_snapshot["safe_area"],
            "promo": {
                "enabled": bool(
                    payload.promo_enabled
                    and promo_label
                ),
                "min_amount": payload.promo_min_amount,
                "discount_percent": (
                    payload.promo_discount_percent
                ),
                "label": promo_label,
            },
            "music": (
                selected_music
                or {
                    "enabled": False,
                    "music_id": None,
                    "title": None,
                    "archive": None,
                    "duration_seconds": None,
                    "volume": round(
                        float(payload.music_volume),
                        3,
                    ),
                    "ducking": bool(
                        payload.music_ducking
                    ),
                }
            ),
            "voiceover": {
                "enabled": bool(payload.voiceover_enabled),
                "voice_id": payload.voice_id,
                "script": voiceover_script,
                "model_id": ELEVENLABS_MODEL_ID,
                "language_code": ELEVENLABS_LANGUAGE_CODE,
            },
        }

        job = RenderJob(
            campaign_id=campaign.id,
            variation_index=index + 1,
            status="queued",
            config=config,
        )

        db.add(job)
        jobs.append(job)

    db.commit()

    queue = render_queue()

    for job in jobs:
        db.refresh(job)

        queued = queue.enqueue(
            render_job,
            job.id,
            retry=Retry(
                max=1,
                interval=[10],
            ),
            job_timeout=RENDER_JOB_TIMEOUT_SECONDS,
            result_ttl=86400,
            failure_ttl=604800,
        )

        job.rq_job_id = queued.id

    db.commit()

    return {
        "ok": True,
        "message": (
            f"{payload.variations} raw video catalog "
            "masuk antrean render"
        ),
        "campaign": campaign_to_dict(campaign),
    }




@router.get("/api/automation/rules")
def list_automation_rules():
    redis_client = automation_redis()

    rule_ids = [
        automation_decode(item)
        for item in redis_client.smembers(
            AUTOMATION_RULE_SET
        )
    ]

    rules: list[dict[str, Any]] = []

    for rule_id in rule_ids:
        rule = automation_load_rule(
            rule_id
        )

        if rule is not None:
            rules.append(
                automation_public_rule(rule)
            )

    rules.sort(
        key=lambda item: str(
            item.get("created_at")
            or ""
        ),
        reverse=True,
    )

    return {
        "ok": True,
        "rules": rules,
    }


@router.post("/api/automation/rules")
def create_automation_rule(
    payload: AutomationRuleRequest,
):
    try:
        campaign_payload = (
            RawVideoCatalogRequest(
                **payload.campaign_payload
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "Payload campaign automation "
                f"tidak valid: {exc}"
            ),
        ) from exc

    run_at = automation_parse_datetime(
        payload.run_at
    )

    if (
        payload.schedule_type != "manual"
        and run_at is None
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Tanggal dan waktu jadwal "
                "wajib diisi"
            ),
        )

    rule_id = uuid.uuid4().hex

    rule = {
        "id": rule_id,
        "name": payload.name.strip(),
        "enabled": bool(
            payload.enabled
        ),
        "schedule_type":
            payload.schedule_type,
        "next_run_at": (
            run_at.isoformat()
            if run_at
            else None
        ),
        "webhook_url": (
            payload.webhook_url or ""
        ).strip() or None,
        "campaign_payload":
            campaign_payload.model_dump(
                mode="json"
            ),
        "last_run_at": None,
        "last_status": "never",
        "last_message": None,
        "last_campaign_id": None,
        "created_at": now().isoformat(),
        "updated_at": now().isoformat(),
    }

    automation_save_rule(rule)

    automation_write_log(
        rule_id=rule_id,
        status="created",
        message=(
            "Automation rule dibuat"
        ),
    )

    return {
        "ok": True,
        "message": (
            "Automation berhasil disimpan"
        ),
        "rule": automation_public_rule(
            rule
        ),
    }


@router.put(
    "/api/automation/rules/{rule_id}/toggle"
)
def toggle_automation_rule(
    rule_id: str,
    payload: AutomationRuleToggleRequest,
):
    rule = automation_load_rule(
        rule_id
    )

    if rule is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Automation rule tidak ditemukan"
            ),
        )

    rule["enabled"] = bool(
        payload.enabled
    )
    rule["updated_at"] = now().isoformat()

    automation_save_rule(rule)

    return {
        "ok": True,
        "message": (
            "Automation diaktifkan"
            if payload.enabled
            else "Automation dinonaktifkan"
        ),
        "rule": automation_public_rule(
            rule
        ),
    }


@router.delete(
    "/api/automation/rules/{rule_id}"
)
def delete_automation_rule(
    rule_id: str,
):
    redis_client = automation_redis()

    if automation_load_rule(rule_id) is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Automation rule tidak ditemukan"
            ),
        )

    redis_client.delete(
        automation_rule_key(rule_id)
    )

    redis_client.srem(
        AUTOMATION_RULE_SET,
        rule_id,
    )

    redis_client.zrem(
        AUTOMATION_DUE_SET,
        rule_id,
    )

    automation_write_log(
        rule_id=rule_id,
        status="deleted",
        message=(
            "Automation rule dihapus"
        ),
    )

    return {
        "ok": True,
        "message": (
            "Automation berhasil dihapus"
        ),
    }


@router.get("/api/automation/logs")
def list_automation_logs(
    limit: int = 50,
):
    limit = max(
        1,
        min(int(limit), 200),
    )

    redis_client = automation_redis()

    raw_items = redis_client.lrange(
        AUTOMATION_LOG_KEY,
        0,
        limit - 1,
    )

    items: list[dict[str, Any]] = []

    for raw in raw_items:
        try:
            item = json.loads(
                automation_decode(raw)
            )

            if isinstance(item, dict):
                items.append(item)
        except json.JSONDecodeError:
            continue

    return {
        "ok": True,
        "logs": items,
    }


@router.post(
    "/api/automation/rules/{rule_id}/run"
)
def run_automation_rule(
    rule_id: str,
    internal_token: str | None = None,
    db: Session = Depends(get_db),
):
    if (
        internal_token is not None
        and AUTOMATION_INTERNAL_TOKEN
        and internal_token
            != AUTOMATION_INTERNAL_TOKEN
    ):
        raise HTTPException(
            status_code=403,
            detail="Internal token tidak valid",
        )

    rule = automation_load_rule(
        rule_id
    )

    if rule is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Automation rule tidak ditemukan"
            ),
        )

    started_at = now()

    try:
        campaign_payload = (
            RawVideoCatalogRequest(
                **rule.get(
                    "campaign_payload",
                    {}
                )
            )
        )

        result = (
            create_raw_video_catalog_campaign(
                campaign_payload,
                db,
            )
        )

        campaign = result.get(
            "campaign"
        ) or {}

        campaign_id = campaign.get("id")

        rule["last_run_at"] = (
            started_at.isoformat()
        )
        rule["last_status"] = "success"
        rule["last_message"] = (
            result.get("message")
        )
        rule["last_campaign_id"] = (
            campaign_id
        )

        previous_due = (
            automation_parse_datetime(
                rule.get("next_run_at")
            )
            or started_at
        )

        next_run = automation_next_run(
            str(
                rule.get("schedule_type")
                or "manual"
            ),
            previous_due,
        )

        rule["next_run_at"] = (
            next_run.isoformat()
            if next_run
            else None
        )

        if (
            rule.get("schedule_type")
            == "once"
        ):
            rule["enabled"] = False

        rule["updated_at"] = now().isoformat()

        automation_save_rule(rule)

        automation_write_log(
            rule_id=rule_id,
            status="success",
            message=(
                result.get("message")
                or "Campaign berhasil dibuat"
            ),
            campaign_id=campaign_id,
        )

        automation_send_webhook(
            rule.get("webhook_url"),
            {
                "event":
                    "campaign.generated",
                "rule_id": rule_id,
                "rule_name":
                    rule.get("name"),
                "campaign_id":
                    campaign_id,
                "campaign": campaign,
                "message":
                    result.get("message"),
                "created_at":
                    now().isoformat(),
            },
        )

        return {
            "ok": True,
            "message": (
                result.get("message")
                or "Automation berhasil dijalankan"
            ),
            "campaign": campaign,
            "rule": automation_public_rule(
                rule
            ),
        }

    except HTTPException as exc:
        rule["last_run_at"] = (
            started_at.isoformat()
        )
        rule["last_status"] = "failed"
        rule["last_message"] = str(
            exc.detail
        )[:1000]
        rule["updated_at"] = now().isoformat()

        automation_save_rule(rule)

        automation_write_log(
            rule_id=rule_id,
            status="failed",
            message=str(
                exc.detail
            )[:1000],
        )

        raise

    except Exception as exc:
        rule["last_run_at"] = (
            started_at.isoformat()
        )
        rule["last_status"] = "failed"
        rule["last_message"] = str(exc)[:1000]
        rule["updated_at"] = now().isoformat()

        automation_save_rule(rule)

        automation_write_log(
            rule_id=rule_id,
            status="failed",
            message=str(exc)[:1000],
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Automation gagal: "
                f"{str(exc)[:500]}"
            ),
        ) from exc


@router.get("/api/campaigns/multi-product")
def list_multi_product_campaigns(
    db: Session = Depends(get_db),
):
    campaigns = list(
        db.scalars(
            select(CreativeCampaign)
            .order_by(CreativeCampaign.created_at.desc())
            .limit(100)
        ).all()
    )

    return {
        "ok": True,
        "campaigns": [
            campaign_to_dict(campaign)
            for campaign in campaigns
            if int(
                (campaign.settings or {}).get(
                    "product_count",
                    1,
                )
            ) > 1
        ],
    }


@router.get("/api/campaigns/{campaign_id}")
def campaign_detail(
    campaign_id: int,
    db: Session = Depends(get_db),
):
    campaign = db.get(
        CreativeCampaign,
        campaign_id,
    )

    if campaign is None:
        raise HTTPException(
            status_code=404,
            detail="Campaign tidak ditemukan",
        )

    jobs = list(
        db.scalars(
            select(RenderJob)
            .where(
                RenderJob.campaign_id
                == campaign_id
            )
            .order_by(
                RenderJob.variation_index
            )
        ).all()
    )

    return {
        "ok": True,
        "campaign": campaign_to_dict(
            campaign,
            jobs,
        ),
    }




@router.put(
    "/api/campaigns/{campaign_id}/jobs/{job_id}/review"
)
def update_render_review(
    campaign_id: int,
    job_id: int,
    payload: RenderReviewRequest,
    db: Session = Depends(get_db),
):
    campaign = db.get(
        CreativeCampaign,
        campaign_id,
    )

    if campaign is None:
        raise HTTPException(
            status_code=404,
            detail="Campaign tidak ditemukan",
        )

    job = db.get(
        RenderJob,
        job_id,
    )

    if (
        job is None
        or job.campaign_id != campaign_id
    ):
        raise HTTPException(
            status_code=404,
            detail="Render job tidak ditemukan",
        )

    if (
        payload.status == "approved"
        or payload.winner
    ) and job.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=(
                "Hanya render completed yang "
                "dapat di-approve atau dijadikan winner"
            ),
        )

    status = payload.status

    if payload.winner:
        status = "approved"

        other_jobs = list(
            db.scalars(
                select(RenderJob).where(
                    RenderJob.campaign_id
                    == campaign_id
                )
            ).all()
        )

        for other_job in other_jobs:
            if other_job.id == job.id:
                continue

            other_config = dict(
                other_job.config or {}
            )

            other_review = (
                normalize_render_review(
                    other_config.get("review")
                )
            )

            if other_review["winner"]:
                other_review["winner"] = False
                other_review["updated_at"] = (
                    now().isoformat()
                )
                other_config["review"] = (
                    other_review
                )
                other_job.config = other_config

    config = dict(job.config or {})

    config["review"] = {
        "status": status,
        "rating": payload.rating,
        "notes": (
            payload.notes or ""
        ).strip(),
        "winner": bool(payload.winner),
        "updated_at": now().isoformat(),
    }

    job.config = config
    campaign.updated_at = now()

    db.commit()
    db.refresh(job)

    return {
        "ok": True,
        "message": "Review berhasil disimpan",
        "job": job_to_dict(job),
    }


@router.post(
    "/api/campaigns/{campaign_id}/retry-failed"
)
def retry_failed(
    campaign_id: int,
    db: Session = Depends(get_db),
):
    campaign = db.get(
        CreativeCampaign,
        campaign_id,
    )

    if campaign is None:
        raise HTTPException(
            status_code=404,
            detail="Campaign tidak ditemukan",
        )

    jobs = list(
        db.scalars(
            select(RenderJob).where(
                RenderJob.campaign_id
                == campaign_id,
                RenderJob.status
                == "failed",
            )
        ).all()
    )

    queue = render_queue()

    for job in jobs:
        job.status = "queued"
        job.error_message = None
        job.started_at = None
        job.finished_at = None

        queued = queue.enqueue(
            render_job,
            job.id,
            retry=Retry(
                max=1,
                interval=[10],
            ),
            job_timeout=RENDER_JOB_TIMEOUT_SECONDS,
        )

        job.rq_job_id = queued.id

    campaign.status = "queued"
    campaign.updated_at = now()
    db.commit()

    return {
        "ok": True,
        "message": (
            f"{len(jobs)} render gagal "
            "dimasukkan kembali ke antrean"
        ),
    }


@router.delete("/api/campaigns/{campaign_id}")
def delete_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
):
    campaign = db.get(
        CreativeCampaign,
        campaign_id,
    )

    if campaign is None:
        raise HTTPException(
            status_code=404,
            detail="Campaign tidak ditemukan",
        )

    jobs = list(
        db.scalars(
            select(RenderJob).where(
                RenderJob.campaign_id
                == campaign_id
            )
        ).all()
    )

    for job in jobs:
        db.delete(job)

    archive_raw_veo_clip(
        (
            STORAGE_ROOT
            / "renders"
            / str(campaign_id)
            / "shared-ai-product-video.mp4"
        ),
        campaign.product_id,
        campaign_id,
        campaign.settings,
    )

    db.delete(campaign)
    db.commit()

    shutil.rmtree(
        STORAGE_ROOT
        / "renders"
        / str(campaign_id),
        ignore_errors=True,
    )

    return {
        "ok": True,
        "message": (
            "Campaign dan hasil render dihapus"
        ),
    }
