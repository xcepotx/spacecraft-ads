from __future__ import annotations

import os
import hashlib
import re
import base64
import json
import mimetypes
import random
import shutil
import subprocess
import textwrap
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
from redis import Redis
from rq import Queue, Retry
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, delete, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.main import Base, Product, SessionLocal, engine, get_db
from app.phase2 import ProductAnalysis, ProductAsset

router = APIRouter()

# B18K_PUBLISHED_PRODUCT_GUARD
ADS_PUBLISHED_STATUS = "published"


def ads_published_product_condition():
    return (
        func.lower(
            func.trim(
                func.coalesce(
                    Product.status,
                    "",
                )
            )
        )
        == ADS_PUBLISHED_STATUS
    )


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

# B18C_OPENAI_CONSTANTS_START
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    "https://api.openai.com/v1",
).strip().rstrip("/")
OPENAI_COPY_MODEL = os.getenv(
    "OPENAI_COPY_MODEL",
    "gpt-5.4-mini",
).strip()
# B18C_OPENAI_CONSTANTS_END

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


PERFORMANCE_KEY_PREFIX = (
    "product_ads:performance:"
)

PERFORMANCE_CAMPAIGN_SET_PREFIX = (
    "product_ads:performance:campaign:"
)


WABOT_BASE_URL = os.getenv(
    "WABOT_BASE_URL",
    "",
).strip().rstrip("/")

WABOT_API_KEY = os.getenv(
    "WABOT_API_KEY",
    "",
).strip()

WABOT_CAMPAIGN_PREFIX = (
    "product_ads:wabot:campaign:"
)

WABOT_EVENT_PREFIX = (
    "product_ads:wabot:events:"
)

WABOT_EVENT_LIMIT = 500


# B15 SPACECRAFT CATALOG SELECTOR
SPACECRAFT_BASE_URL = os.getenv(
    "SPACECRAFT_BASE_URL",
    "https://spacecraft.id",
).strip().rstrip("/")

SPACECRAFT_WABOT_KEY = os.getenv(
    "SPACECRAFT_WABOT_KEY",
    "",
).strip()




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


# B19A_CATALOG_CACHE_MODELS
class SpacecraftCatalogCache(Base):
    __tablename__ = "spacecraft_catalog_cache"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    catalog_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )

    slug: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )

    headline: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    catalog_type: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        index=True,
    )

    flow_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    source_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    campaign_name: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )

    audience_label: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )

    go_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="published",
        index=True,
    )

    products_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    catalog_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    source_synced_at: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )


class SpacecraftCatalogProductCache(Base):
    __tablename__ = (
        "spacecraft_catalog_product_cache"
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    catalog_id: Mapped[int] = mapped_column(
        ForeignKey(
            "spacecraft_catalog_cache.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    external_product_id: Mapped[str] = (
        mapped_column(
            String(100),
            nullable=False,
            index=True,
        )
    )

    local_product_id: Mapped[int | None] = (
        mapped_column(
            ForeignKey(
                "products.id",
                ondelete="SET NULL",
            ),
            nullable=True,
            index=True,
        )
    )

    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    slug: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="published",
        index=True,
    )

    commerce_position: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
        )
    )

    bundle_quantity: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
            default=1,
        )
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    catalog_label: Mapped[str | None] = (
        mapped_column(
            String(300),
            nullable=True,
        )
    )

    payload: Mapped[dict[str, Any]] = (
        mapped_column(
            JSON,
            nullable=False,
            default=dict,
        )
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(
                timezone.utc
            ),
        )
    )

    updated_at: Mapped[datetime] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(
                timezone.utc
            ),
        )
    )


# B19C_LINKED_CREATIVE_SET_MODEL
class CreativeSet(Base):
    __tablename__ = "creative_sets"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    creative_set_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    catalog_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    catalog_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    catalog_name: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )

    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "creative_campaigns.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="draft",
        index=True,
    )

    commerce_ready: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    product_ids: Mapped[list[int]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    commerce_product_ids: Mapped[list[int]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    creative_product_ids: Mapped[list[int]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    raw_asset_ids: Mapped[list[int]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    go_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # B19D_CATALOG_DRIFT_MODEL
    drift_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="current",
        index=True,
    )

    current_catalog_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    drift_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    drift_detected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    drift_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
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




class RawCatalogVariantRecipe(BaseModel):
    label: str = Field(
        min_length=1,
        max_length=160,
    )

    hook: str | None = Field(
        default=None,
        max_length=500,
    )

    cta: str | None = Field(
        default=None,
        max_length=500,
    )

    promo_text: str | None = Field(
        default=None,
        max_length=240,
    )

    voiceover_text: str | None = Field(
        default=None,
        max_length=2000,
    )

    product_order: list[int] | None = Field(
        default=None,
        min_length=5,
        max_length=6,
    )

    hook_code: str | None = Field(
        default=None,
        max_length=40,
    )

    cta_code: str | None = Field(
        default=None,
        max_length=40,
    )

    promo_code: str | None = Field(
        default=None,
        max_length=40,
    )

    order_code: str | None = Field(
        default=None,
        max_length=40,
    )

    voice_code: str | None = Field(
        default=None,
        max_length=40,
    )

    enabled: bool = True





class CreativeSetPrepareRequest(BaseModel):
    source_type: Literal[
        "spacecraft",
        "custom",
    ]

    catalog_code: str | None = Field(
        default=None,
        max_length=50,
    )

    catalog_hash: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )

    name: str | None = Field(
        default=None,
        max_length=300,
    )

    product_ids: list[int] = Field(
        default_factory=list,
        min_length=1,
        max_length=20,
    )


class RawVideoCatalogRequest(BaseModel):
    # B19A_LINKED_CATALOG_REQUEST
    catalog_source: Literal[
        "spacecraft",
        "custom",
    ] = "custom"

    catalog_code: str | None = Field(
        default=None,
        max_length=50,
    )

    catalog_hash: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )

    pricing_source: Literal[
        "meta",
        "instagram",
        "tiktok",
        "direct",
    ] = "meta"

    # B19C_CREATIVE_SET_REQUEST_FIELDS
    creative_set_code: str | None = Field(
        default=None,
        max_length=50,
    )

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
    # B18C_RAW_COPY_FIELDS_START
    hook: str | None = Field(
        default=None,
        max_length=180,
    )
    cta: str | None = Field(
        default=None,
        max_length=140,
    )
    # B18C_RAW_COPY_FIELDS_END
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

    approved_voice_asset_id: str | None = Field(
        default=None,
        min_length=32,
        max_length=32,
    )
    approved_voice_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    approved_voice_duration_seconds: float | None = Field(
        default=None,
        gt=0,
        le=3600,
    )

    variant_recipes: list[
        RawCatalogVariantRecipe
    ] = Field(
        default_factory=list,
        max_length=24,
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


class SingleProductVideoRequest(BaseModel):
    product_id: int = Field(
        ge=1,
    )

    name: str | None = Field(
        default=None,
        max_length=300,
    )

    raw_clip_id: str | None = Field(
        default=None,
        max_length=120,
    )

    duration_seconds: int = Field(default=20)
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"

    hook: str | None = Field(
        default=None,
        max_length=180,
    )

    cta: str | None = Field(
        default=None,
        max_length=140,
    )

    image_count: int = Field(
        default=4,
        ge=0,
        le=6,
    )

    voiceover_enabled: bool = False
    voice_id: str | None = Field(
        default=None,
        max_length=160,
    )
    voiceover_mode: Literal["auto", "custom"] = "auto"
    voiceover_text: str | None = Field(
        default=None,
        max_length=700,
    )

    @field_validator("duration_seconds")
    @classmethod
    def validate_duration(cls, value: int) -> int:
        if value not in {15, 20, 25, 30}:
            raise ValueError(
                "Durasi harus 15, 20, 25, atau 30 detik"
            )
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


# B18D_DURATION_AWARE_VOICEOVER
B18D_CLOSING_RESERVED_SECONDS = 5.0
B18D_TIMELINE_BUFFER_SECONDS = 0.5


def voiceover_max_seconds(
    duration_seconds: int | float,
    closing_reserved_seconds: float = B18D_CLOSING_RESERVED_SECONDS,
) -> float:
    return round(
        max(
            1.0,
            float(duration_seconds)
            - max(0.0, float(closing_reserved_seconds))
            - B18D_TIMELINE_BUFFER_SECONDS,
        ),
        3,
    )


def compact_voice_product_alias(name: str) -> str:
    value = str(name or '').strip()
    if value.lower().startswith('sack of '):
        value = value[8:].strip()
    removable = {'articulated', 'fidget', 'keychain', 'new'}
    words = [word for word in value.split() if word.lower() not in removable]
    compact = ' '.join(words).strip()
    return compact or str(name or '').strip()


# B18G_APPROVED_VOICE_ASSET_REUSE
B18G_APPROVED_VOICE_DIR = "voice-approved"
B18G_PREVIEW_VOICE_DIR = "voice-previews"
B18G_VOICE_SPEED = 1.0

# B18H_SMART_VOICE_TIMELINE_FIT
B18H_MAX_OVER_SECONDS = 1.20
B18H_MAX_SPEED_MULTIPLIER = 1.06
B18H_TARGET_MARGIN_SECONDS = 0.08
B18H_SILENCE_THRESHOLD_DB = -48


def voice_asset_fingerprint(
    voice_id: str,
    text: str,
    model_id: str = ELEVENLABS_MODEL_ID,
    language_code: str = ELEVENLABS_LANGUAGE_CODE,
    output_format: str = ELEVENLABS_OUTPUT_FORMAT,
    speed: float = B18G_VOICE_SPEED,
) -> str:
    payload = {
        "voice_id": str(voice_id or "").strip(),
        "text": str(text or "").strip(),
        "model_id": str(model_id or "").strip(),
        "language_code": str(language_code or "").strip(),
        "output_format": str(output_format or "").strip(),
        "speed": round(float(speed), 3),
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_voice_asset_id(asset_id: str) -> str:
    value = str(asset_id or "").strip().lower()
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise RuntimeError("Voice asset ID tidak valid")
    return value


def voice_preview_audio_path(asset_id: str) -> Path:
    value = validate_voice_asset_id(asset_id)
    return STORAGE_ROOT / B18G_PREVIEW_VOICE_DIR / f"preview-{value}.mp3"


def voice_preview_metadata_path(asset_id: str) -> Path:
    value = validate_voice_asset_id(asset_id)
    return STORAGE_ROOT / B18G_PREVIEW_VOICE_DIR / f"preview-{value}.json"


def approved_voice_audio_path(asset_id: str) -> Path:
    value = validate_voice_asset_id(asset_id)
    return STORAGE_ROOT / B18G_APPROVED_VOICE_DIR / f"approved-{value}.mp3"


def approved_voice_metadata_path(asset_id: str) -> Path:
    value = validate_voice_asset_id(asset_id)
    return STORAGE_ROOT / B18G_APPROVED_VOICE_DIR / f"approved-{value}.json"


def write_voice_metadata(destination: Path, payload: dict[str, Any]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(destination)


def read_voice_metadata(source: Path) -> dict[str, Any]:
    if not source.is_file():
        raise RuntimeError("Metadata voice asset tidak ditemukan")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception as error:
        raise RuntimeError("Metadata voice asset tidak valid") from error
    if not isinstance(payload, dict):
        raise RuntimeError("Metadata voice asset harus berupa object")
    return payload



def _run_voice_fit_ffmpeg(
    source: Path,
    destination: Path,
    audio_filter: str,
) -> None:
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vn",
        "-af",
        audio_filter,
        "-ar",
        "44100",
        "-ac",
        "2",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "128k",
        str(destination),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            (result.stderr or "FFmpeg voice fit gagal")[-1800:]
        )

    if (
        not destination.is_file()
        or destination.stat().st_size < 1000
    ):
        raise RuntimeError(
            "Output Smart Voice Fit tidak valid"
        )


def fit_voice_preview_asset(
    asset_id: str,
    voice_id: str,
    text: str,
    protected_terms: list[str],
    target_duration_seconds: int,
    closing_reserved_seconds: int,
) -> dict[str, Any]:
    source_id = validate_voice_asset_id(asset_id)
    source_audio = voice_preview_audio_path(source_id)
    source_metadata_path = voice_preview_metadata_path(source_id)

    if (
        not source_audio.is_file()
        or source_audio.stat().st_size < 1000
    ):
        raise RuntimeError(
            "Preview voice tidak ditemukan. Preview ulang."
        )

    source_metadata = read_voice_metadata(source_metadata_path)
    normalized_text = normalize_tts_text_indonesian(
        text,
        protected_terms,
    )
    expected_fingerprint = voice_asset_fingerprint(
        voice_id=voice_id,
        text=normalized_text,
    )

    if str(source_metadata.get("fingerprint") or "") != expected_fingerprint:
        raise RuntimeError(
            "Fingerprint preview berubah. Preview ulang."
        )
    if str(source_metadata.get("voice_id") or "") != str(voice_id):
        raise RuntimeError(
            "Voice ID preview berubah. Preview ulang."
        )
    if str(source_metadata.get("normalized_text") or "") != normalized_text:
        raise RuntimeError(
            "Teks preview berubah. Preview ulang."
        )

    source_duration = media_duration_seconds(source_audio)
    if source_duration is None:
        raise RuntimeError(
            "Durasi preview tidak dapat dibaca"
        )

    max_seconds = voiceover_max_seconds(
        target_duration_seconds,
        closing_reserved_seconds,
    )
    source_duration = float(source_duration)
    over_by = max(0.0, source_duration - max_seconds)

    if source_duration <= max_seconds:
        return {
            "preview_asset_id": source_id,
            "fingerprint": expected_fingerprint,
            "audio_url": (
                f"/media/{B18G_PREVIEW_VOICE_DIR}/"
                f"preview-{source_id}.mp3"
            ),
            "normalized_text": normalized_text,
            "source_duration_seconds": round(source_duration, 3),
            "trimmed_duration_seconds": round(source_duration, 3),
            "actual_duration_seconds": round(source_duration, 3),
            "max_voiceover_seconds": max_seconds,
            "trimmed_seconds": 0.0,
            "speed_multiplier": 1.0,
            "fit_applied": False,
            "fits_timeline": True,
        }

    if over_by > B18H_MAX_OVER_SECONDS:
        raise RuntimeError(
            "Voice-over terlalu panjang untuk Auto Fit. "
            "Gunakan Ringkas Otomatis atau Perpanjang Durasi."
        )

    work_id = uuid.uuid4().hex
    preview_dir = STORAGE_ROOT / B18G_PREVIEW_VOICE_DIR
    preview_dir.mkdir(parents=True, exist_ok=True)
    trimmed_path = preview_dir / f".fit-trim-{work_id}.mp3"
    fitted_id = uuid.uuid4().hex
    fitted_audio = voice_preview_audio_path(fitted_id)
    fitted_metadata_path = voice_preview_metadata_path(fitted_id)

    trim_filter = (
        "silenceremove="
        "start_periods=1:"
        "start_duration=0.04:"
        f"start_threshold={B18H_SILENCE_THRESHOLD_DB}dB,"
        "areverse,"
        "silenceremove="
        "start_periods=1:"
        "start_duration=0.04:"
        f"start_threshold={B18H_SILENCE_THRESHOLD_DB}dB,"
        "areverse"
    )

    try:
        _run_voice_fit_ffmpeg(
            source_audio,
            trimmed_path,
            trim_filter,
        )

        trimmed_duration = media_duration_seconds(trimmed_path)
        if trimmed_duration is None:
            raise RuntimeError(
                "Durasi audio setelah trim tidak dapat dibaca"
            )
        trimmed_duration = float(trimmed_duration)
        trimmed_seconds = max(0.0, source_duration - trimmed_duration)

        speed_multiplier = 1.0
        if trimmed_duration <= max_seconds:
            shutil.copy2(trimmed_path, fitted_audio)
        else:
            target_seconds = max(
                0.5,
                max_seconds - B18H_TARGET_MARGIN_SECONDS,
            )
            speed_multiplier = trimmed_duration / target_seconds

            if speed_multiplier > B18H_MAX_SPEED_MULTIPLIER:
                raise RuntimeError(
                    "Auto Fit membutuhkan kecepatan "
                    f"{speed_multiplier:.3f}x, melebihi batas aman "
                    f"{B18H_MAX_SPEED_MULTIPLIER:.2f}x. "
                    "Gunakan Ringkas Otomatis atau Perpanjang Durasi."
                )

            _run_voice_fit_ffmpeg(
                trimmed_path,
                fitted_audio,
                f"atempo={speed_multiplier:.6f}",
            )

        fitted_duration = media_duration_seconds(fitted_audio)
        if fitted_duration is None:
            raise RuntimeError(
                "Durasi hasil Auto Fit tidak dapat dibaca"
            )
        fitted_duration = float(fitted_duration)

        if fitted_duration > max_seconds + 0.04:
            correction = fitted_duration / max(
                0.5,
                max_seconds - 0.04,
            )
            corrected_speed = speed_multiplier * correction

            if corrected_speed > B18H_MAX_SPEED_MULTIPLIER:
                raise RuntimeError(
                    "Hasil Auto Fit masih melebihi timeline dan "
                    "koreksi melampaui batas aman."
                )

            fitted_audio.unlink(missing_ok=True)
            speed_multiplier = corrected_speed
            _run_voice_fit_ffmpeg(
                trimmed_path,
                fitted_audio,
                f"atempo={speed_multiplier:.6f}",
            )
            fitted_duration = media_duration_seconds(fitted_audio)
            if fitted_duration is None:
                raise RuntimeError(
                    "Durasi hasil koreksi tidak dapat dibaca"
                )
            fitted_duration = float(fitted_duration)

        if fitted_duration > max_seconds + 0.04:
            raise RuntimeError(
                "Hasil Auto Fit masih melebihi slot maksimum"
            )

        metadata = {
            **source_metadata,
            "asset_id": fitted_id,
            "fingerprint": expected_fingerprint,
            "approved": False,
            "parent_preview_asset_id": source_id,
            "fit_applied": True,
            "fit_method": "trim_silence_and_atempo",
            "source_duration_seconds": round(source_duration, 3),
            "trimmed_duration_seconds": round(trimmed_duration, 3),
            "trimmed_seconds": round(trimmed_seconds, 3),
            "speed_multiplier": round(speed_multiplier, 6),
            "duration_seconds": round(fitted_duration, 3),
            "max_voiceover_seconds": max_seconds,
            "created_at": now().isoformat(),
        }
        write_voice_metadata(fitted_metadata_path, metadata)

        return {
            "preview_asset_id": fitted_id,
            "fingerprint": expected_fingerprint,
            "audio_url": (
                f"/media/{B18G_PREVIEW_VOICE_DIR}/"
                f"preview-{fitted_id}.mp3"
            ),
            "normalized_text": normalized_text,
            "source_duration_seconds": round(source_duration, 3),
            "trimmed_duration_seconds": round(trimmed_duration, 3),
            "actual_duration_seconds": round(fitted_duration, 3),
            "max_voiceover_seconds": max_seconds,
            "trimmed_seconds": round(trimmed_seconds, 3),
            "speed_multiplier": round(speed_multiplier, 6),
            "fit_applied": True,
            "fits_timeline": fitted_duration <= max_seconds + 0.04,
        }
    except Exception:
        fitted_audio.unlink(missing_ok=True)
        fitted_metadata_path.unlink(missing_ok=True)
        raise
    finally:
        trimmed_path.unlink(missing_ok=True)

def resolve_approved_voice_asset(
    asset_id: str,
    expected_fingerprint: str | None = None,
    expected_voice_id: str | None = None,
    expected_text: str | None = None,
) -> dict[str, Any]:
    value = validate_voice_asset_id(asset_id)
    audio_path = approved_voice_audio_path(value)
    metadata_path = approved_voice_metadata_path(value)
    if not audio_path.is_file() or audio_path.stat().st_size < 1000:
        raise RuntimeError("Approved voice audio tidak ditemukan")
    metadata = read_voice_metadata(metadata_path)
    if metadata.get("approved") is not True:
        raise RuntimeError("Voice asset belum di-approve")
    if str(metadata.get("asset_id") or "") != value:
        raise RuntimeError("Voice asset ID metadata tidak cocok")
    fingerprint = str(metadata.get("fingerprint") or "").strip()
    if not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        raise RuntimeError("Fingerprint approved voice tidak valid")
    if expected_fingerprint and fingerprint != str(expected_fingerprint).strip():
        raise RuntimeError("Fingerprint approved voice berubah")
    if expected_voice_id and str(metadata.get("voice_id") or "").strip() != str(expected_voice_id).strip():
        raise RuntimeError("Voice ID approved audio tidak cocok")
    normalized_text = str(metadata.get("normalized_text") or "").strip()
    if expected_text is not None and normalized_text != str(expected_text).strip():
        raise RuntimeError("Teks approved audio tidak cocok")
    actual_duration = media_duration_seconds(audio_path)
    if actual_duration is None:
        raise RuntimeError("Durasi approved voice tidak dapat dibaca")
    stored_duration = float(metadata.get("duration_seconds") or 0)
    if stored_duration > 0 and abs(stored_duration - float(actual_duration)) > 0.25:
        raise RuntimeError("Durasi approved voice tidak konsisten")
    return {
        **metadata,
        "asset_id": value,
        "fingerprint": fingerprint,
        "duration_seconds": round(float(actual_duration), 3),
        "audio_path": audio_path,
        "metadata_path": metadata_path,
    }


# VOICE_DRAFT_APPROVAL_V1
# B18C_AI_COPY_MODEL_START
class AICopyGenerateRequest(BaseModel):
    product_ids: list[int] = Field(
        min_length=1,
        max_length=6,
    )
    mode: Literal["hook", "cta", "both"] = "both"
    audience: Literal[
        "retail",
        "retail_bulk",
        "reseller",
        "custom_bulk",
    ] = "retail_bulk"
    duration_seconds: int = Field(default=25, ge=10, le=60)
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
    creative_template: str = Field(
        default="bundle_hemat",
        max_length=80,
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
    promo_text: str | None = Field(default=None, max_length=240)
    current_hook: str | None = Field(default=None, max_length=180)
    current_cta: str | None = Field(default=None, max_length=140)
# B18C_AI_COPY_MODEL_END


class VoiceDraftRequest(BaseModel):
    product_ids: list[int] = Field(
        min_length=1,
        max_length=12,
    )
    audience: Literal[
        "retail",
        "retail_bulk",
        "reseller",
        "custom_bulk",
    ] = "retail"
    duration_seconds: int = Field(
        default=25,
        ge=10,
        le=60,
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
        max_length=500,
    )
    draft_style: Literal[
        'standard',
        'compact',
    ] = 'standard'


class VoiceNormalizeRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=2000,
    )
    protected_terms: list[str] = Field(
        default_factory=list,
        max_length=24,
    )


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
        max_length=2000,
    )
    protected_terms: list[str] = Field(
        default_factory=list,
        max_length=24,
    )
    target_duration_seconds: int = Field(
        default=25,
        ge=10,
        le=60,
    )
    closing_reserved_seconds: float = Field(
        default=B18D_CLOSING_RESERVED_SECONDS,
        ge=2.0,
        le=10.0,
    )


class VoiceApproveRequest(BaseModel):
    preview_asset_id: str = Field(min_length=32, max_length=32)
    fingerprint: str = Field(min_length=64, max_length=64)
    voice_id: str = Field(min_length=1, max_length=150)
    text: str = Field(min_length=1, max_length=2000)
    protected_terms: list[str] = Field(default_factory=list, max_length=24)


class VoiceFitRequest(BaseModel):
    preview_asset_id: str = Field(
        min_length=32,
        max_length=32,
    )
    voice_id: str = Field(
        min_length=1,
        max_length=150,
    )
    text: str = Field(
        min_length=1,
        max_length=2000,
    )
    protected_terms: list[str] = Field(
        default_factory=list,
        max_length=24,
    )
    target_duration_seconds: int = Field(
        default=25,
        ge=10,
        le=180,
    )
    closing_reserved_seconds: int = Field(
        default=5,
        ge=1,
        le=20,
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



# B18I_RAW_CATALOG_IDEMPOTENCY
RAW_CATALOG_IDEMPOTENCY_TTL_SECONDS = 15
RAW_CATALOG_IDEMPOTENCY_WAIT_SECONDS = 5.0


def raw_catalog_request_fingerprint(
    payload: RawVideoCatalogRequest,
) -> str:
    serialized = json.dumps(
        payload.model_dump(
            mode="json",
            exclude_none=False,
        ),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def raw_catalog_idempotency_key(
    fingerprint: str,
) -> str:
    return (
        "product_ads:raw_catalog:"
        "idempotency:"
        f"{fingerprint}"
    )


def raw_catalog_existing_response(
    db: Session,
    campaign_id: int,
) -> dict[str, Any] | None:
    campaign = db.get(
        CreativeCampaign,
        int(campaign_id),
    )

    if campaign is None:
        return None

    return {
        "ok": True,
        "deduplicated": True,
        "message": (
            "Permintaan identik sudah diproses. "
            "Campaign sebelumnya digunakan kembali."
        ),
        "campaign": campaign_to_dict(
            campaign
        ),
    }


def acquire_raw_catalog_submission(
    payload: RawVideoCatalogRequest,
    db: Session,
) -> tuple[str, str, Redis, dict[str, Any] | None]:
    fingerprint = (
        raw_catalog_request_fingerprint(
            payload
        )
    )

    key = raw_catalog_idempotency_key(
        fingerprint
    )

    token = uuid.uuid4().hex
    client = redis_connection()

    acquired = client.set(
        key,
        f"processing:{token}",
        nx=True,
        ex=RAW_CATALOG_IDEMPOTENCY_TTL_SECONDS,
    )

    if acquired:
        return (
            fingerprint,
            key,
            client,
            None,
        )

    deadline = (
        time.monotonic()
        + RAW_CATALOG_IDEMPOTENCY_WAIT_SECONDS
    )

    while time.monotonic() < deadline:
        current = automation_decode(
            client.get(key)
        )

        if current.startswith("campaign:"):
            raw_id = current.split(
                ":",
                1,
            )[1]

            if raw_id.isdigit():
                response = (
                    raw_catalog_existing_response(
                        db,
                        int(raw_id),
                    )
                )

                if response is not None:
                    return (
                        fingerprint,
                        key,
                        client,
                        response,
                    )

        time.sleep(0.10)

    raise HTTPException(
        status_code=409,
        detail=(
            "Permintaan campaign identik sedang "
            "diproses. Tunggu beberapa detik."
        ),
    )

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



class PerformanceEntryRequest(BaseModel):
    impressions: int = Field(
        default=0,
        ge=0,
    )

    clicks: int = Field(
        default=0,
        ge=0,
    )

    spend: float = Field(
        default=0,
        ge=0,
    )

    leads: int = Field(
        default=0,
        ge=0,
    )

    closings: int = Field(
        default=0,
        ge=0,
    )

    revenue: float = Field(
        default=0,
        ge=0,
    )

    notes: str | None = Field(
        default=None,
        max_length=2000,
    )

    source: str | None = Field(
        default="manual",
        max_length=100,
    )




class WABotCampaignRequest(BaseModel):
    catalog_code: str | None = Field(
        default=None,
        max_length=100,
    )

    source_code: str | None = Field(
        default="spacecraft_ads",
        max_length=100,
    )

    external_campaign_code: str | None = Field(
        default=None,
        max_length=150,
    )

    whatsapp_number: str | None = Field(
        default=None,
        max_length=40,
    )

    opening_message: str | None = Field(
        default=None,
        max_length=2000,
    )

    webhook_enabled: bool = False

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )



# B19A_CATALOG_CACHE_API
def b19a_catalog_headers() -> dict[str, str]:
    return {
        "X-SpaceCraft-Wabot-Key":
            SPACECRAFT_WABOT_KEY,
        "Accept": "application/json",
    }


def b19a_spacecraft_json(
    path: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if (
        not SPACECRAFT_BASE_URL
        or not SPACECRAFT_WABOT_KEY
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "SpaceCraft Catalog API "
                "belum dikonfigurasi"
            ),
        )

    try:
        response = httpx.get(
            f"{SPACECRAFT_BASE_URL}{path}",
            headers=b19a_catalog_headers(),
            params=params or None,
            timeout=20,
            follow_redirects=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "SpaceCraft Catalog API "
                "tidak dapat dijangkau: "
                f"{type(exc).__name__}"
            ),
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=(
                "SpaceCraft Catalog API "
                f"mengembalikan HTTP "
                f"{response.status_code} "
                f"untuk {path}"
            ),
        )

    try:
        payload = response.json()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Response SpaceCraft Catalog "
                "bukan JSON valid"
            ),
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=502,
            detail=(
                "Struktur response SpaceCraft "
                "Catalog tidak valid"
            ),
        )

    return payload


def b19a_clean_external_product_id(
    item: dict[str, Any],
) -> str:
    value = str(
        item.get("external_id")
        or item.get("product_id")
        or item.get("id")
        or ""
    ).strip()

    if value.startswith(
        "spacecraft-product-"
    ):
        value = value.removeprefix(
            "spacecraft-product-"
        )

    return value


def b19a_pricing_source_code(
    pricing_source: str | None,
) -> str:
    value = str(
        pricing_source
        or "meta"
    ).strip().lower()

    if value == "instagram":
        return "IG"

    if value == "tiktok":
        return "TT"

    if value == "direct":
        return "WEB"

    return "META"


def b19a_go_url_for_pricing_source(
    catalog_code: str,
    pricing_source: str | None,
) -> str:
    value = str(
        pricing_source
        or "meta"
    ).strip().lower()

    source_path = {
        "instagram": "instagram",
        "tiktok": "tiktok",
        "direct": "web",
    }.get(value, "meta")

    return (
        f"{SPACECRAFT_BASE_URL}"
        f"/go/{source_path}/{catalog_code}"
    )


def b19a_live_price_overrides(
    catalog_code: str,
    pricing_source: str | None,
    rows: list[SpacecraftCatalogProductCache],
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    source_code = b19a_pricing_source_code(
        pricing_source
    )

    detail = b19a_spacecraft_json(
        f"/api/wabot/catalogs/{catalog_code}",
        params={"source": source_code},
    )

    catalog = (
        detail.get("catalog")
        if isinstance(detail.get("catalog"), dict)
        else {}
    )

    products = (
        catalog.get("products")
        if isinstance(catalog.get("products"), list)
        else (
            detail.get("products")
            if isinstance(detail.get("products"), list)
            else []
        )
    )

    external_to_local = {
        str(row.external_product_id): int(row.local_product_id)
        for row in rows
        if row.local_product_id
    }

    overrides: dict[int, dict[str, Any]] = {}

    for item in products:
        if not isinstance(item, dict):
            continue

        external_id = b19a_clean_external_product_id(
            item
        )

        local_id = external_to_local.get(
            external_id
        )

        if not local_id:
            continue

        overrides[local_id] = {
            "price": item.get("price"),
            "price_label": (
                item.get("price_label")
                or item.get("formatted_price")
            ),
            "direct_price": item.get("direct_price"),
            "direct_price_label": item.get(
                "direct_price_label"
            ),
            "pricing_layer": item.get(
                "pricing_layer"
            ),
        }

    return overrides, {
        "source_code": source_code,
        "pricing_layer": (
            catalog.get("pricing", {})
            if isinstance(
                catalog.get("pricing"),
                dict,
            )
            else {}
        ),
    }


def b19a_catalog_hash(
    catalog: dict[str, Any],
    products: list[dict[str, Any]],
) -> str:
    canonical = {
        "catalog_code": wabot_normalize_code(
            catalog.get("catalog_id")
            or catalog.get("catalog_code")
            or catalog.get("code")
        ),
        "name": b11_clean_text(
            catalog.get("name")
            or catalog.get("headline")
            or ""
        ),
        "catalog_type":
            catalog.get("catalog_type"),
        "flow_type":
            catalog.get("flow_type"),
        "products": [
            {
                "external_product_id":
                    b19a_clean_external_product_id(
                        item
                    ),
                "status": str(
                    item.get("status")
                    or ""
                ).strip().lower(),
                "position": index,
                "quantity": int(
                    item.get(
                        "catalog_bundle_quantity"
                    )
                    or 1
                ),
                "is_primary": bool(
                    item.get(
                        "catalog_is_primary"
                    )
                ),
            }
            for index, item in enumerate(
                products,
                start=1,
            )
        ],
    }

    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(
        encoded
    ).hexdigest()


def b19a_sync_catalog_cache(
    db: Session,
) -> dict[str, Any]:
    list_payload = b19a_spacecraft_json(
        "/api/wabot/catalogs"
    )

    raw_catalogs = (
        list_payload.get("catalogs")
        or []
    )

    if not raw_catalogs:
        raise HTTPException(
            status_code=502,
            detail=(
                "SpaceCraft tidak "
                "mengembalikan Mini Catalog"
            ),
        )

    seen_codes: set[str] = set()
    synced: list[dict[str, Any]] = []

    for summary in raw_catalogs:
        if not isinstance(summary, dict):
            continue

        code = wabot_normalize_code(
            summary.get("catalog_id")
            or summary.get("catalog_code")
            or summary.get("code")
        )

        if not code:
            continue

        detail_payload = (
            b19a_spacecraft_json(
                f"/api/wabot/catalogs/{code}"
            )
        )

        catalog_payload = (
            detail_payload.get("catalog")
            or {}
        )

        if not isinstance(
            catalog_payload,
            dict,
        ):
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Detail catalog {code} "
                    "tidak valid"
                ),
            )

        products = (
            catalog_payload.get("products")
            or []
        )

        if not isinstance(products, list):
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Detail catalog {code} "
                    "memiliki products yang "
                    "bukan list"
                ),
            )

        # B19_SYNC_EMPTY_MEMBERSHIP_GUARD
        existing_catalog = db.scalar(
            select(
                SpacecraftCatalogCache
            ).where(
                SpacecraftCatalogCache
                .catalog_code
                == code
            )
        )

        existing_member_count = 0

        if existing_catalog is not None:
            existing_member_count = int(
                db.scalar(
                    select(
                        func.count(
                            SpacecraftCatalogProductCache.id
                        )
                    ).where(
                        SpacecraftCatalogProductCache
                        .catalog_id
                        == existing_catalog.id
                    )
                )
                or 0
            )

        declared_count = int(
            catalog_payload.get(
                "products_count"
            )
            or summary.get(
                "products_count"
            )
            or 0
        )

        if (
            not products
            and (
                existing_member_count > 0
                or declared_count > 0
            )
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Sync {code} dibatalkan: "
                    "SpaceCraft mengembalikan "
                    "membership kosong/tidak "
                    "konsisten. Cache lama "
                    "dipertahankan."
                ),
            )

        if (
            declared_count > 0
            and len(products)
            != declared_count
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Sync {code} dibatalkan: "
                    f"products_count={declared_count} "
                    f"tetapi products={len(products)}. "
                    "Cache lama dipertahankan."
                ),
            )

        seen_codes.add(code)

        external_ids = [
            b19a_clean_external_product_id(
                item
            )
            for item in products
            if isinstance(item, dict)
        ]

        external_ids = [
            item
            for item in external_ids
            if item
        ]

        local_products = list(
            db.scalars(
                select(Product).where(
                    Product.external_id.in_(
                        external_ids
                    )
                )
            ).all()
        ) if external_ids else []

        local_by_external = {
            str(item.external_id): item
            for item in local_products
        }

        catalog = db.scalar(
            select(
                SpacecraftCatalogCache
            ).where(
                SpacecraftCatalogCache
                .catalog_code
                == code
            )
        )

        if catalog is None:
            catalog = (
                SpacecraftCatalogCache(
                    catalog_code=code,
                    name=code,
                    catalog_hash=(
                        "0" * 64
                    ),
                )
            )
            db.add(catalog)
            db.flush()

        catalog.name = b11_clean_text(
            catalog_payload.get("name")
            or catalog_payload.get(
                "headline"
            )
            or summary.get("name")
            or code
        )

        catalog.slug = (
            catalog_payload.get("slug")
            or summary.get("slug")
        )

        catalog.headline = (
            catalog_payload.get("headline")
            or summary.get("headline")
        )

        catalog.catalog_type = (
            catalog_payload.get(
                "catalog_type"
            )
            or summary.get("catalog_type")
        )

        catalog.flow_type = (
            catalog_payload.get("flow_type")
            or summary.get("flow_type")
        )

        catalog.source_code = (
            catalog_payload.get("source_code")
            or summary.get("source_code")
        )

        catalog.campaign_name = (
            catalog_payload.get(
                "campaign_name"
            )
            or summary.get("campaign_name")
        )

        catalog.audience_label = (
            catalog_payload.get(
                "audience_label"
            )
            or summary.get("audience_label")
        )

        catalog.go_url = (
            summary.get("go_url")
            or (
                f"{SPACECRAFT_BASE_URL}"
                f"/go/{code}"
            )
        )

        catalog.status = "published"
        catalog.products_count = len(
            products
        )

        catalog.catalog_hash = (
            b19a_catalog_hash(
                catalog_payload,
                [
                    item
                    for item in products
                    if isinstance(item, dict)
                ],
            )
        )

        catalog.source_synced_at = str(
            detail_payload.get("synced_at")
            or list_payload.get("synced_at")
            or ""
        ) or None

        catalog.payload = {
            "summary": summary,
            "detail": catalog_payload,
            "shop_id":
                detail_payload.get("shop_id"),
            "shop_name":
                detail_payload.get("shop_name"),
        }

        catalog.last_synced_at = now()
        catalog.updated_at = now()

        db.execute(
            delete(
                SpacecraftCatalogProductCache
            ).where(
                SpacecraftCatalogProductCache
                .catalog_id
                == catalog.id
            )
        )

        mapped_count = 0

        for position, item in enumerate(
            products,
            start=1,
        ):
            if not isinstance(item, dict):
                continue

            external_id = (
                b19a_clean_external_product_id(
                    item
                )
            )

            local_product = (
                local_by_external.get(
                    external_id
                )
            )

            if (
                local_product is not None
                and str(
                    local_product.status
                    or ""
                ).strip().lower()
                == ADS_PUBLISHED_STATUS
            ):
                local_product_id = (
                    local_product.id
                )
                mapped_count += 1
            else:
                local_product_id = None

            db.add(
                SpacecraftCatalogProductCache(
                    catalog_id=catalog.id,
                    external_product_id=(
                        external_id
                    ),
                    local_product_id=(
                        local_product_id
                    ),
                    name=b11_clean_text(
                        item.get("name")
                        or external_id
                        or (
                            f"Produk "
                            f"{position}"
                        )
                    ),
                    slug=item.get("slug"),
                    status=str(
                        item.get("status")
                        or "published"
                    ).strip().lower(),
                    commerce_position=(
                        position
                    ),
                    bundle_quantity=max(
                        1,
                        int(
                            item.get(
                                "catalog_bundle_quantity"
                            )
                            or 1
                        ),
                    ),
                    is_primary=bool(
                        item.get(
                            "catalog_is_primary"
                        )
                    ),
                    catalog_label=(
                        item.get(
                            "catalog_label"
                        )
                    ),
                    payload=item,
                    created_at=now(),
                    updated_at=now(),
                )
            )

        synced.append({
            "catalog_code": code,
            "products_count":
                len(products),
            "mapped_products_count":
                mapped_count,
            "catalog_hash":
                catalog.catalog_hash,
        })

    hidden_codes: list[str] = []

    for catalog in db.scalars(
        select(
            SpacecraftCatalogCache
        )
    ).all():
        if (
            catalog.catalog_code
            not in seen_codes
        ):
            catalog.status = (
                "source_hidden"
            )
            catalog.updated_at = now()
            hidden_codes.append(
                catalog.catalog_code
            )

    # B19D_DRIFT_RECONCILE_AFTER_SYNC
    drift = b19d_reconcile_catalog_drift(db)

    db.commit()

    return {
        "ok": True,
        "source": "spacecraft",
        "drift": drift,
        "count": len(synced),
        "catalogs": synced,
        "hidden_catalog_codes":
            hidden_codes,
        "source_synced_at":
            list_payload.get(
                "synced_at"
            ),
        "synced_at": now().isoformat(),
    }


def b19a_catalog_rows(
    db: Session,
    catalog_id: int,
) -> list[
    SpacecraftCatalogProductCache
]:
    return list(
        db.scalars(
            select(
                SpacecraftCatalogProductCache
            )
            .where(
                SpacecraftCatalogProductCache
                .catalog_id
                == catalog_id
            )
            .order_by(
                SpacecraftCatalogProductCache
                .commerce_position
            )
        ).all()
    )


def b19a_raw_video_counts(
    db: Session,
    local_product_ids: list[int],
) -> dict[int, int]:
    if not local_product_ids:
        return {}

    rows = db.execute(
        select(
            ProductAsset.product_id,
            func.count(ProductAsset.id),
        )
        .where(
            ProductAsset.product_id.in_(
                local_product_ids
            ),
            ProductAsset.asset_type
            == "video",
        )
        .group_by(
            ProductAsset.product_id
        )
    ).all()

    return {
        int(product_id): int(count)
        for product_id, count in rows
    }


def b19a_catalog_to_dict(
    catalog: SpacecraftCatalogCache,
    products: list[
        SpacecraftCatalogProductCache
    ],
    db: Session,
    *,
    include_products: bool,
) -> dict[str, Any]:
    local_ids = [
        int(item.local_product_id)
        for item in products
        if item.local_product_id
    ]

    raw_counts = (
        b19a_raw_video_counts(
            db,
            local_ids,
        )
    )

    mapped_count = sum(
        1
        for item in products
        if item.local_product_id
    )

    published_count = sum(
        1
        for item in products
        if str(
            item.status or ""
        ).strip().lower()
        == ADS_PUBLISHED_STATUS
    )

    ready_count = sum(
        1
        for item in products
        if (
            item.local_product_id
            and raw_counts.get(
                int(
                    item.local_product_id
                ),
                0,
            ) > 0
        )
    )

    product_count = len(products)
    reasons: list[str] = []

    if product_count < 5:
        reasons.append(
            "Catalog memiliki kurang "
            "dari 5 produk"
        )

    if product_count > 6:
        reasons.append(
            "Render engine saat ini "
            "maksimal 6 produk"
        )

    if mapped_count != product_count:
        reasons.append(
            "Ada produk catalog yang "
            "belum terpetakan ke Ads"
        )

    if published_count != product_count:
        reasons.append(
            "Ada anggota catalog yang "
            "bukan published"
        )

    compatible = (
        catalog.status == "published"
        and 5 <= product_count <= 6
        and mapped_count == product_count
        and published_count == product_count
    )

    result: dict[str, Any] = {
        "catalog_code":
            catalog.catalog_code,
        "catalog_id":
            catalog.catalog_code,
        "name": catalog.name,
        "slug": catalog.slug,
        "headline": catalog.headline,
        "catalog_type":
            catalog.catalog_type,
        "flow_type":
            catalog.flow_type,
        "source_code":
            catalog.source_code,
        "campaign_name":
            catalog.campaign_name,
        "audience_label":
            catalog.audience_label,
        "go_url": catalog.go_url,
        "status": catalog.status,
        "products_count":
            product_count,
        "mapped_products_count":
            mapped_count,
        "published_products_count":
            published_count,
        "raw_video_ready_count":
            ready_count,
        "catalog_hash":
            catalog.catalog_hash,
        "render_compatible":
            compatible,
        "compatibility_reasons":
            reasons,
        "source_synced_at":
            catalog.source_synced_at,
        "last_synced_at": (
            catalog.last_synced_at
            .isoformat()
            if catalog.last_synced_at
            else None
        ),
    }

    if include_products:
        result["products"] = [
            {
                "external_product_id":
                    item.external_product_id,
                "local_product_id":
                    item.local_product_id,
                "name": item.name,
                "slug": item.slug,
                "status": item.status,
                "commerce_position":
                    item.commerce_position,
                "bundle_quantity":
                    item.bundle_quantity,
                "is_primary":
                    item.is_primary,
                "catalog_label":
                    item.catalog_label,
                "raw_video_count": (
                    raw_counts.get(
                        int(
                            item.local_product_id
                        ),
                        0,
                    )
                    if item.local_product_id
                    else 0
                ),
                "has_raw_video": bool(
                    item.local_product_id
                    and raw_counts.get(
                        int(
                            item.local_product_id
                        ),
                        0,
                    ) > 0
                ),
            }
            for item in products
        ]

    return result


@router.post(
    "/api/spacecraft/catalogs/sync"
)
def sync_spacecraft_catalog_cache(
    db: Session = Depends(get_db),
):
    return b19a_sync_catalog_cache(
        db
    )


@router.get(
    "/api/spacecraft/catalogs"
)
def list_spacecraft_catalog_cache(
    db: Session = Depends(get_db),
):
    catalogs = list(
        db.scalars(
            select(
                SpacecraftCatalogCache
            )
            .where(
                SpacecraftCatalogCache
                .status
                == "published"
            )
            .order_by(
                SpacecraftCatalogCache
                .catalog_code
            )
        ).all()
    )

    items = [
        b19a_catalog_to_dict(
            catalog,
            b19a_catalog_rows(
                db,
                catalog.id,
            ),
            db,
            include_products=False,
        )
        for catalog in catalogs
    ]

    return {
        "ok": True,
        "source": "cache",
        "count": len(items),
        "catalogs": items,
    }


@router.get(
    "/api/spacecraft/catalogs/{catalog_code}"
)
def get_spacecraft_catalog_cache(
    catalog_code: str,
    db: Session = Depends(get_db),
):
    code = wabot_normalize_code(
        catalog_code
    )

    catalog = db.scalar(
        select(
            SpacecraftCatalogCache
        ).where(
            SpacecraftCatalogCache
            .catalog_code
            == code
        )
    )

    if catalog is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Mini Catalog SpaceCraft "
                "tidak ditemukan"
            ),
        )

    return {
        "ok": True,
        "catalog": (
            b19a_catalog_to_dict(
                catalog,
                b19a_catalog_rows(
                    db,
                    catalog.id,
                ),
                db,
                include_products=True,
            )
        ),
    }


def b19a_validate_linked_catalog(
    payload: RawVideoCatalogRequest,
    selected_product_ids: list[int],
    db: Session,
) -> dict[str, Any] | None:
    if (
        payload.catalog_source
        != "spacecraft"
    ):
        return None

    code = wabot_normalize_code(
        payload.catalog_code
    )

    if not code:
        raise HTTPException(
            status_code=422,
            detail=(
                "Pilih Mini Catalog "
                "SpaceCraft sebelum render"
            ),
        )

    if not payload.catalog_hash:
        raise HTTPException(
            status_code=422,
            detail=(
                "Catalog hash belum tersedia. "
                "Refresh dan Apply Catalog ulang."
            ),
        )

    catalog = db.scalar(
        select(
            SpacecraftCatalogCache
        ).where(
            SpacecraftCatalogCache
            .catalog_code
            == code,
            SpacecraftCatalogCache
            .status
            == "published",
        )
    )

    if catalog is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Mini Catalog {code} "
                "tidak tersedia atau "
                "tidak published"
            ),
        )

    rows = b19a_catalog_rows(
        db,
        catalog.id,
    )

    context = b19a_catalog_to_dict(
        catalog,
        rows,
        db,
        include_products=True,
    )

    if not context[
        "render_compatible"
    ]:
        reason = (
            context[
                "compatibility_reasons"
            ][0]
            if context[
                "compatibility_reasons"
            ]
            else (
                "Catalog belum kompatibel "
                "untuk render"
            )
        )

        raise HTTPException(
            status_code=422,
            detail=f"{code}: {reason}",
        )

    if (
        payload.catalog_hash
        != catalog.catalog_hash
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"{code} berubah sejak "
                "dipilih. Refresh dan "
                "Apply Catalog ulang."
            ),
        )

    commerce_product_ids = [
        int(item.local_product_id)
        for item in rows
        if item.local_product_id
    ]

    if (
        len(commerce_product_ids)
        != len(selected_product_ids)
        or set(commerce_product_ids)
        != set(selected_product_ids)
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Anggota Creative Set harus "
                "sama persis dengan anggota "
                f"Mini Catalog {code}"
            ),
        )

    price_overrides, pricing_context = (
        b19a_live_price_overrides(
            code,
            payload.pricing_source,
            rows,
        )
    )

    source_code = pricing_context[
        "source_code"
    ]

    return {
        "catalog_code": code,
        "catalog_hash":
            catalog.catalog_hash,
        "catalog_name": catalog.name,
        "catalog_type":
            catalog.catalog_type,
        "flow_type":
            catalog.flow_type,
        "source_code":
            source_code,
        "pricing_source":
            payload.pricing_source,
        "pricing_source_code":
            source_code,
        "pricing_layer":
            pricing_context.get(
                "pricing_layer"
            ),
        "price_overrides":
            price_overrides,
        "go_url": b19a_go_url_for_pricing_source(
            code,
            payload.pricing_source,
        ),
        "commerce_product_ids":
            commerce_product_ids,
        "snapshot": context,
    }




# B19B_CREATIVE_READINESS_API
def b19b_product_readiness(
    product_id: int,
    db: Session,
) -> dict[str, Any]:
    result = product_raw_videos(
        product_id,
        db,
    )

    raw_videos = (
        result.get("raw_videos")
        or []
    )

    primary_count = sum(
        1
        for item in raw_videos
        if item.get("is_primary")
    )

    return {
        "product_id": product_id,
        "raw_video_count": len(raw_videos),
        "primary_raw_video_count":
            primary_count,
        "has_raw_video": bool(raw_videos),
        "has_primary_raw_video":
            primary_count > 0,
        "creative_ready": bool(raw_videos),
        "status": (
            "ready"
            if raw_videos
            else "missing_assets"
        ),
        "raw_videos": raw_videos,
    }


def b19b_catalog_readiness(
    catalog_code: str,
    db: Session,
) -> dict[str, Any]:
    code = wabot_normalize_code(
        catalog_code
    )

    catalog = db.scalar(
        select(
            SpacecraftCatalogCache
        ).where(
            SpacecraftCatalogCache
            .catalog_code
            == code
        )
    )

    if catalog is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Mini Catalog SpaceCraft "
                "tidak ditemukan"
            ),
        )

    rows = b19a_catalog_rows(
        db,
        catalog.id,
    )

    products: list[dict[str, Any]] = []

    for row in rows:
        if not row.local_product_id:
            products.append({
                "external_product_id":
                    row.external_product_id,
                "local_product_id": None,
                "name": row.name,
                "commerce_position":
                    row.commerce_position,
                "raw_video_count": 0,
                "primary_raw_video_count": 0,
                "has_raw_video": False,
                "has_primary_raw_video": False,
                "creative_ready": False,
                "status": "unmapped",
                "raw_videos": [],
            })
            continue

        item = b19b_product_readiness(
            int(row.local_product_id),
            db,
        )

        item.update({
            "external_product_id":
                row.external_product_id,
            "local_product_id":
                int(row.local_product_id),
            "name": row.name,
            "commerce_position":
                row.commerce_position,
        })

        products.append(item)

    total = len(products)

    ready = sum(
        1
        for item in products
        if item["creative_ready"]
    )

    primary_ready = sum(
        1
        for item in products
        if item["has_primary_raw_video"]
    )

    missing = [
        item
        for item in products
        if not item["creative_ready"]
    ]

    unmapped = [
        item
        for item in products
        if item["status"] == "unmapped"
    ]

    ready_to_render = (
        total > 0
        and ready == total
        and not unmapped
    )

    if ready_to_render:
        status = "ready"
    elif ready == 0:
        status = "not_ready"
    else:
        status = "missing_assets"

    return {
        "catalog_code": code,
        "catalog_name": catalog.name,
        "catalog_hash":
            catalog.catalog_hash,
        "products_total": total,
        "products_ready": ready,
        "products_missing":
            len(missing),
        "products_with_primary":
            primary_ready,
        "ready_percentage": (
            round(
                (ready / total) * 100,
                1,
            )
            if total
            else 0.0
        ),
        "ready_to_render":
            ready_to_render,
        "status": status,
        "products": products,
        "checked_at": now().isoformat(),
    }


@router.get(
    "/api/spacecraft/catalogs/"
    "{catalog_code}/readiness"
)
def get_spacecraft_catalog_readiness(
    catalog_code: str,
    db: Session = Depends(get_db),
):
    return {
        "ok": True,
        "readiness":
            b19b_catalog_readiness(
                catalog_code,
                db,
            ),
    }


def b19b_validate_catalog_readiness(
    payload: RawVideoCatalogRequest,
    db: Session,
) -> dict[str, Any] | None:
    if (
        payload.catalog_source
        != "spacecraft"
    ):
        return None

    readiness = b19b_catalog_readiness(
        payload.catalog_code or "",
        db,
    )

    if not readiness[
        "ready_to_render"
    ]:
        missing_names = [
            item["name"]
            for item in readiness[
                "products"
            ]
            if not item[
                "creative_ready"
            ]
        ]

        detail = (
            ", ".join(
                missing_names[:4]
            )
            or (
                "anggota catalog belum "
                "siap"
            )
        )

        if len(missing_names) > 4:
            detail += (
                f" dan "
                f"{len(missing_names) - 4} "
                "produk lain"
            )

        raise HTTPException(
            status_code=422,
            detail=(
                "Creative Readiness belum "
                f"lengkap untuk "
                f"{readiness['catalog_code']}: "
                f"{readiness['products_ready']}/"
                f"{readiness['products_total']} "
                f"produk siap. "
                f"Belum siap: {detail}"
            ),
        )

    return readiness




# B19C_LINKED_CREATIVE_SET_API
def b19c_new_code() -> str:
    return (
        "CS"
        + datetime.now(
            timezone.utc
        ).strftime("%y%m%d")
        + uuid.uuid4().hex[:6].upper()
    )


def b19c_asset_ids(
    payload: RawVideoCatalogRequest,
) -> list[int]:
    result: list[int] = []

    for item in payload.product_clips:
        value = str(
            item.clip_id
            or ""
        ).strip()

        if value.startswith("asset-"):
            raw = value.removeprefix(
                "asset-"
            )

            if raw.isdigit():
                result.append(int(raw))

    return result


def b19c_to_dict(
    item: CreativeSet,
) -> dict[str, Any]:
    return {
        "id": item.id,
        "creative_set_code":
            item.creative_set_code,
        "source_type":
            item.source_type,
        "catalog_code":
            item.catalog_code,
        "catalog_hash":
            item.catalog_hash,
        "catalog_name":
            item.catalog_name,
        "campaign_id":
            item.campaign_id,
        "status":
            item.status,
        "commerce_ready":
            bool(item.commerce_ready),
        "product_ids":
            item.product_ids or [],
        "commerce_product_ids":
            item.commerce_product_ids or [],
        "creative_product_ids":
            item.creative_product_ids or [],
        "raw_asset_ids":
            item.raw_asset_ids or [],
        "go_url":
            item.go_url,
        "snapshot":
            item.snapshot or {},
        # B19D_DRIFT_SERIALIZATION
        "drift_status":
            item.drift_status or "current",
        "current_catalog_hash":
            item.current_catalog_hash,
        "drift_reason":
            item.drift_reason,
        "drift_detected_at": (
            item.drift_detected_at.isoformat()
            if item.drift_detected_at
            else None
        ),
        "drift_checked_at": (
            item.drift_checked_at.isoformat()
            if item.drift_checked_at
            else None
        ),
        "is_stale": (
            item.drift_status == "stale"
        ),
        "created_at": (
            item.created_at.isoformat()
            if item.created_at
            else None
        ),
        "updated_at": (
            item.updated_at.isoformat()
            if item.updated_at
            else None
        ),
    }


def b19c_prepare(
    request: CreativeSetPrepareRequest,
    db: Session,
) -> CreativeSet:
    product_ids = list(
        dict.fromkeys(
            int(item)
            for item in request.product_ids
            if int(item) > 0
        )
    )

    if request.source_type == "custom":
        item = CreativeSet(
            creative_set_code=
                b19c_new_code(),
            source_type="custom",
            catalog_code=None,
            catalog_hash=None,
            catalog_name=(
                b11_clean_text(
                    request.name
                    or "Custom Creative Set"
                )
            ),
            status="internal_draft",
            commerce_ready=False,
            product_ids=product_ids,
            commerce_product_ids=[],
            creative_product_ids=
                product_ids,
            raw_asset_ids=[],
            go_url=None,
            snapshot={
                "source_type": "custom",
                "product_ids":
                    product_ids,
                "created_at":
                    now().isoformat(),
            },
            drift_status="not_applicable",
            current_catalog_hash=None,
            drift_reason=None,
            drift_detected_at=None,
            drift_checked_at=now(),
            created_at=now(),
            updated_at=now(),
        )

        db.add(item)
        db.commit()
        db.refresh(item)

        return item

    code = wabot_normalize_code(
        request.catalog_code
    )

    if not code:
        raise HTTPException(
            status_code=422,
            detail=(
                "catalog_code wajib untuk "
                "Linked Creative Set"
            ),
        )

    catalog = (
        get_spacecraft_catalog_cache(
            code,
            db=db,
        )["catalog"]
    )

    readiness = b19b_catalog_readiness(
        code,
        db,
    )

    if (
        request.catalog_hash
        != catalog["catalog_hash"]
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"{code} berubah. "
                "Refresh dan Apply ulang."
            ),
        )

    commerce_ids = [
        int(item["local_product_id"])
        for item in catalog["products"]
        if item["local_product_id"]
    ]

    if (
        len(commerce_ids)
        != len(product_ids)
        or set(commerce_ids)
        != set(product_ids)
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Anggota Creative Set harus "
                "sama dengan anggota "
                f"{code}"
            ),
        )

    status = (
        "ready"
        if readiness[
            "ready_to_render"
        ]
        else "missing_assets"
    )

    item = CreativeSet(
        creative_set_code=
            b19c_new_code(),
        source_type="spacecraft",
        catalog_code=code,
        catalog_hash=
            catalog["catalog_hash"],
        catalog_name=
            catalog["name"],
        status=status,
        commerce_ready=bool(
            readiness[
                "ready_to_render"
            ]
        ),
        product_ids=commerce_ids,
        commerce_product_ids=
            commerce_ids,
        creative_product_ids=
            product_ids,
        raw_asset_ids=[],
        go_url=catalog["go_url"],
        snapshot={
            "catalog": catalog,
            "readiness": readiness,
            "prepared_at":
                now().isoformat(),
        },
        drift_status="current",
        current_catalog_hash=
            catalog["catalog_hash"],
        drift_reason=None,
        drift_detected_at=None,
        drift_checked_at=now(),
        created_at=now(),
        updated_at=now(),
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


def b19c_validate_for_render(
    payload: RawVideoCatalogRequest,
    selected_product_ids: list[int],
    db: Session,
) -> CreativeSet:
    code = wabot_normalize_code(
        payload.creative_set_code
    )

    if not code:
        raise HTTPException(
            status_code=422,
            detail=(
                "Creative Set belum dibuat. "
                "Apply Mini Catalog ulang."
            ),
        )

    item = db.scalar(
        select(
            CreativeSet
        ).where(
            CreativeSet
            .creative_set_code
            == code
        )
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Creative Set {code} "
                "tidak ditemukan"
            ),
        )

    if (
        item.source_type
        != payload.catalog_source
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Source Creative Set tidak "
                "sesuai dengan request"
            ),
        )

    if item.source_type == "custom":
        if item.commerce_ready:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Custom Creative Set "
                    "memiliki status invalid"
                ),
            )

        if (
            set(
                item.creative_product_ids
                or []
            )
            != set(selected_product_ids)
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Produk Custom Creative "
                    "Set telah berubah. Buat "
                    "Creative Set ulang."
                ),
            )

        item.status = "internal_render"
        item.updated_at = now()
        db.flush()

        return item

    # B19D_STALE_RENDER_GUARD
    b19d_reconcile_catalog_drift(
        db,
        [item.catalog_code]
        if item.catalog_code
        else None,
    )

    db.refresh(item)

    if item.drift_status == "stale":
        raise HTTPException(
            status_code=409,
            detail=(
                item.drift_reason
                or (
                    "Creative Set stale. "
                    "Apply Catalog ulang."
                )
            ),
        )

    if (
        not item.commerce_ready
        or item.status
        not in {
            "ready",
            "rendering",
            "rendered",
            "approved",
        }
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Creative Set {code} "
                "belum commerce-ready"
            ),
        )

    if (
        item.catalog_code
        != wabot_normalize_code(
            payload.catalog_code
        )
        or item.catalog_hash
        != payload.catalog_hash
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Creative Set tidak lagi "
                "sesuai dengan Mini Catalog. "
                "Refresh dan Apply ulang."
            ),
        )

    if (
        set(
            item.commerce_product_ids
            or []
        )
        != set(selected_product_ids)
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Anggota Creative Set tidak "
                "sama dengan Mini Catalog"
            ),
        )

    item.creative_product_ids = (
        selected_product_ids
    )

    item.raw_asset_ids = (
        b19c_asset_ids(payload)
    )

    item.status = "rendering"
    item.updated_at = now()
    db.flush()

    return item


def b19c_campaign_guard(
    campaign: CreativeCampaign,
) -> dict[str, Any]:
    settings = (
        campaign.settings
        or {}
    )

    source = settings.get(
        "catalog_source"
    )

    code = settings.get(
        "creative_set_code"
    )

    commerce_ready = bool(
        settings.get(
            "creative_set_commerce_ready"
        )
    )

    if (
        source != "spacecraft"
        or not code
        or not commerce_ready
        or not settings.get(
            "catalog_code"
        )
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Campaign belum terhubung "
                "ke Linked Creative Set "
                "commerce-ready. WABot, "
                "/go/CATxxx, dan attribution "
                "dikunci."
            ),
        )

    return settings


@router.post(
    "/api/creative-sets/prepare"
)
def prepare_creative_set(
    request: CreativeSetPrepareRequest,
    db: Session = Depends(get_db),
):
    item = b19c_prepare(
        request,
        db,
    )

    return {
        "ok": True,
        "creative_set":
            b19c_to_dict(item),
    }


@router.get(
    "/api/creative-sets"
)
def list_creative_sets(
    db: Session = Depends(get_db),
):
    items = list(
        db.scalars(
            select(
                CreativeSet
            ).order_by(
                CreativeSet.id.desc()
            )
        ).all()
    )

    return {
        "ok": True,
        "count": len(items),
        "creative_sets": [
            b19c_to_dict(item)
            for item in items
        ],
    }


@router.get(
    "/api/creative-sets/{creative_set_code}"
)
def get_creative_set(
    creative_set_code: str,
    db: Session = Depends(get_db),
):
    code = wabot_normalize_code(
        creative_set_code
    )

    item = db.scalar(
        select(
            CreativeSet
        ).where(
            CreativeSet
            .creative_set_code
            == code
        )
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Creative Set tidak ditemukan"
            ),
        )

    return {
        "ok": True,
        "creative_set":
            b19c_to_dict(item),
    }




# B19D_CATALOG_DRIFT_API
def b19d_catalog_diff_reason(
    item: CreativeSet,
    catalog: SpacecraftCatalogCache | None,
    current_product_ids: list[int],
) -> str:
    if catalog is None:
        return (
            f"Mini Catalog {item.catalog_code or '-'} "
            "tidak lagi tersedia di cache."
        )

    old_ids = [
        int(value)
        for value in (
            item.commerce_product_ids or []
        )
    ]

    additions = sorted(
        set(current_product_ids) - set(old_ids)
    )

    removals = sorted(
        set(old_ids) - set(current_product_ids)
    )

    reasons: list[str] = []

    if item.catalog_hash != catalog.catalog_hash:
        reasons.append("snapshot hash berbeda")

    if additions:
        reasons.append(
            "produk ditambahkan: "
            + ", ".join(
                str(value)
                for value in additions[:10]
            )
        )

    if removals:
        reasons.append(
            "produk dihapus: "
            + ", ".join(
                str(value)
                for value in removals[:10]
            )
        )

    if catalog.status != "published":
        reasons.append(
            f"status catalog menjadi {catalog.status}"
        )

    if not reasons:
        reasons.append(
            "metadata atau urutan commerce berubah"
        )

    return (
        f"{item.catalog_code}: "
        + "; ".join(reasons)
        + ". Apply Catalog ulang untuk "
        "membuat snapshot terbaru."
    )


def b19d_reconcile_catalog_drift(
    db: Session,
    catalog_codes: list[str] | None = None,
) -> dict[str, Any]:
    query = select(CreativeSet).where(
        CreativeSet.source_type == "spacecraft"
    )

    if catalog_codes:
        normalized = [
            wabot_normalize_code(value)
            for value in catalog_codes
            if wabot_normalize_code(value)
        ]

        query = query.where(
            CreativeSet.catalog_code.in_(normalized)
        )

    items = list(db.scalars(query).all())
    stale: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    for item in items:
        catalog = db.scalar(
            select(SpacecraftCatalogCache).where(
                SpacecraftCatalogCache.catalog_code
                == item.catalog_code
            )
        )

        rows = (
            b19a_catalog_rows(db, catalog.id)
            if catalog is not None
            else []
        )

        current_ids = [
            int(row.local_product_id)
            for row in rows
            if row.local_product_id
        ]

        item.drift_checked_at = now()
        item.current_catalog_hash = (
            catalog.catalog_hash
            if catalog is not None
            else None
        )

        hash_match = bool(
            catalog is not None
            and item.catalog_hash == catalog.catalog_hash
            and catalog.status == "published"
        )

        membership_match = (
            set(item.commerce_product_ids or [])
            == set(current_ids)
        )

        if hash_match and membership_match:
            if item.drift_status != "stale":
                item.drift_status = "current"
                item.drift_reason = None
                item.drift_detected_at = None

            current.append({
                "creative_set_code":
                    item.creative_set_code,
                "catalog_code":
                    item.catalog_code,
                "catalog_hash":
                    item.catalog_hash,
            })
            continue

        item.drift_status = "stale"
        item.status = "stale"
        item.commerce_ready = False

        if item.drift_detected_at is None:
            item.drift_detected_at = now()

        item.drift_reason = b19d_catalog_diff_reason(
            item,
            catalog,
            current_ids,
        )

        stale.append({
            "creative_set_code":
                item.creative_set_code,
            "catalog_code":
                item.catalog_code,
            "snapshot_hash":
                item.catalog_hash,
            "current_catalog_hash":
                item.current_catalog_hash,
            "reason":
                item.drift_reason,
        })

    db.flush()

    return {
        "checked": len(items),
        "stale_count": len(stale),
        "current_count": len(current),
        "stale": stale,
        "current": current,
        "checked_at": now().isoformat(),
    }


@router.post("/api/creative-sets/drift/check")
def check_all_creative_set_drift(
    db: Session = Depends(get_db),
):
    result = b19d_reconcile_catalog_drift(db)
    db.commit()

    return {
        "ok": True,
        "drift": result,
    }


@router.get(
    "/api/creative-sets/"
    "{creative_set_code}/drift"
)
def get_creative_set_drift(
    creative_set_code: str,
    db: Session = Depends(get_db),
):
    code = wabot_normalize_code(
        creative_set_code
    )

    item = db.scalar(
        select(CreativeSet).where(
            CreativeSet.creative_set_code == code
        )
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Creative Set tidak ditemukan",
        )

    result = b19d_reconcile_catalog_drift(
        db,
        [item.catalog_code]
        if item.catalog_code
        else None,
    )

    db.commit()
    db.refresh(item)

    return {
        "ok": True,
        "creative_set": b19c_to_dict(item),
        "drift": result,
    }



# B16 ADS ATTRIBUTION BRIDGE
class B16WhatsAppClickRequest(BaseModel):
    campaign_code: str | None = Field(
        default=None,
        max_length=150,
    )

    catalog_code: str | None = Field(
        default=None,
        max_length=100,
    )

    source_code: str | None = Field(
        default="spacecraft_ads",
        max_length=100,
    )

    creative_code: str | None = Field(
        default=None,
        max_length=180,
    )

    phone: str | None = Field(
        default=None,
        max_length=50,
    )

    opening_message: str | None = Field(
        default=None,
        max_length=3000,
    )

    destination_url: str | None = Field(
        default=None,
        max_length=4000,
    )


class WABotEventRequest(BaseModel):
    event_type: Literal[
        "lead",
        "conversation",
        "product_selected",
        "shipping_checked",
        "checkout",
        "paid",
        "closing",
        "cancelled",
    ]

    phone: str | None = Field(
        default=None,
        max_length=50,
    )

    order_id: str | None = Field(
        default=None,
        max_length=150,
    )

    catalog_code: str | None = Field(
        default=None,
        max_length=100,
    )

    source_code: str | None = Field(
        default=None,
        max_length=100,
    )

    value: float = Field(
        default=0,
        ge=0,
    )

    payload: dict[str, Any] = Field(
        default_factory=dict,
    )




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





def wabot_campaign_key(
    campaign_id: int,
) -> str:
    return (
        f"{WABOT_CAMPAIGN_PREFIX}"
        f"{campaign_id}"
    )


def wabot_event_key(
    campaign_id: int,
) -> str:
    return (
        f"{WABOT_EVENT_PREFIX}"
        f"{campaign_id}"
    )


def wabot_normalize_code(
    value: Any,
    fallback: str = "",
) -> str:
    text = re.sub(
        r"[^A-Za-z0-9_-]+",
        "-",
        str(value or "").strip(),
    ).strip("-")

    return text[:150] or fallback


def wabot_normalize_phone(
    value: Any,
) -> str:
    phone = re.sub(
        r"[^0-9]+",
        "",
        str(value or ""),
    )

    if phone.startswith("0"):
        phone = "62" + phone[1:]

    return phone[:30]


def wabot_load_config(
    campaign_id: int,
) -> dict[str, Any]:
    raw = redis_connection().get(
        wabot_campaign_key(campaign_id)
    )

    if not raw:
        return {}

    try:
        parsed = json.loads(
            automation_decode(raw)
        )
    except json.JSONDecodeError:
        return {}

    return (
        parsed
        if isinstance(parsed, dict)
        else {}
    )


def wabot_save_config(
    campaign_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    config = {
        **payload,
        "updated_at": now().isoformat(),
    }

    redis_connection().set(
        wabot_campaign_key(campaign_id),
        json.dumps(
            config,
            ensure_ascii=False,
        ),
    )

    return config


def wabot_campaign_payload(
    campaign: CreativeCampaign,
    jobs: list[RenderJob],
    saved_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = (
        saved_config
        if isinstance(saved_config, dict)
        else {}
    )

    settings = (
        campaign.settings
        if isinstance(campaign.settings, dict)
        else {}
    )

    ad_copy = b11_campaign_copy(
        campaign,
        jobs,
    )

    campaign_code = (
        wabot_normalize_code(
            config.get(
                "external_campaign_code"
            )
        )
        or b11_campaign_code(campaign)
    )

    catalog_code = wabot_normalize_code(
        config.get("catalog_code")
        or settings.get("catalog_code")
        or settings.get("catalog_bundle_code")
        or "",
    )

    source_code = wabot_normalize_code(
        config.get("source_code")
        or settings.get("source_code")
        or "spacecraft_ads",
        "spacecraft_ads",
    )

    product_ids = [
        int(item)
        for item in (
            settings.get("product_ids")
            or []
        )
        if str(item).isdigit()
    ]

    product_names = [
        b11_clean_text(item)
        for item in (
            settings.get("product_names")
            or ad_copy.get("products")
            or []
        )
        if b11_clean_text(item)
    ]

    opening_message = b11_clean_text(
        config.get("opening_message")
        or ad_copy.get("whatsapp_opening")
    )

    attribution = {
        "source_code": source_code,
        "campaign_code": campaign_code,
        "catalog_code": (
            catalog_code or None
        ),
        "creative_campaign_id":
            campaign.id,
        "creative_code": (
            f"{campaign_code}-MASTER"
        ),
        "platform": "spacecraft_ads",
    }

    return {
        "version": "b16",
        "event": "campaign_lead",
        "campaign": {
            "id": campaign.id,
            "code": campaign_code,
            "name": campaign.name,
            "status": campaign.status,
            "catalog_code":
                catalog_code or None,
            "source_code": source_code,
        },
        "products": {
            "ids": product_ids,
            "names": product_names,
            "count": len(product_names),
        },
        "offer": {
            "promo":
                ad_copy.get("promo"),
            "cta":
                ad_copy.get(
                    "cta_recommendation"
                ),
            "opening_message":
                opening_message,
        },
        "attribution": attribution,
        "wabot": {
            "phone":
                wabot_normalize_phone(
                    config.get(
                        "whatsapp_number"
                    )
                )
                or None,
            "webhook_enabled": bool(
                config.get(
                    "webhook_enabled"
                )
            ),
            "configured": bool(
                WABOT_BASE_URL
            ),
        },
        "metadata": (
            config.get("metadata")
            if isinstance(
                config.get("metadata"),
                dict,
            )
            else {}
        ),
        "generated_at": now().isoformat(),
    }


def wabot_write_event(
    campaign_id: int,
    event: dict[str, Any],
) -> dict[str, Any]:
    record = {
        **event,
        "id": uuid.uuid4().hex,
        "campaign_id": campaign_id,
        "created_at": now().isoformat(),
    }

    client = redis_connection()

    client.lpush(
        wabot_event_key(campaign_id),
        json.dumps(
            record,
            ensure_ascii=False,
        ),
    )

    client.ltrim(
        wabot_event_key(campaign_id),
        0,
        WABOT_EVENT_LIMIT - 1,
    )

    return record


def wabot_read_events(
    campaign_id: int,
    limit: int = 100,
) -> list[dict[str, Any]]:
    raw_items = redis_connection().lrange(
        wabot_event_key(campaign_id),
        0,
        max(0, min(limit, 500) - 1),
    )

    result: list[dict[str, Any]] = []

    for raw in raw_items:
        try:
            parsed = json.loads(
                automation_decode(raw)
            )
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            result.append(parsed)

    return result


def wabot_event_summary(
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    total_value = 0.0

    for event in events:
        event_type = str(
            event.get("event_type")
            or "unknown"
        )

        counts[event_type] = (
            counts.get(event_type, 0)
            + 1
        )

        try:
            total_value += float(
                event.get("value")
                or 0
            )
        except (TypeError, ValueError):
            pass

    return {
        "total_events": len(events),
        "counts": counts,
        "total_value": round(
            total_value,
            2,
        ),
    }



def b11_slugify(
    value: Any,
    fallback: str = "campaign",
) -> str:
    text = str(value or "").strip().lower()

    text = re.sub(
        r"[^a-z0-9]+",
        "-",
        text,
    ).strip("-")

    return text[:80] or fallback


# B18J_DESCRIPTIVE_EXPORT_FILENAMES
def b18j_campaign_asset_filename(
    campaign: CreativeCampaign,
    variation_index: int,
    extension: str,
    *,
    kind: str = "video",
    approved: bool = True,
    winner: bool = False,
) -> str:
    suffix = str(extension or "").strip().lower()

    if not suffix.startswith("."):
        suffix = f".{suffix}"

    if not re.fullmatch(r"\.[a-z0-9]{2,6}", suffix):
        suffix = ".mp4" if kind == "video" else ".jpg"

    parts = [
        "spacecraft",
        b11_campaign_code(campaign),
        b11_slugify(campaign.name, "campaign")[:40],
        f"v{int(variation_index):02d}",
    ]

    if approved:
        parts.append("approved")

    if winner:
        parts.append("winner")

    if kind == "thumbnail":
        parts.append("thumbnail")

    return "-".join(parts) + suffix


def b11_clean_text(
    value: Any,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip(),
    )


def b11_campaign_code(
    campaign: CreativeCampaign,
) -> str:
    return f"CMP{campaign.id:06d}"


def b11_campaign_copy(
    campaign: CreativeCampaign,
    jobs: list[RenderJob],
) -> dict[str, Any]:
    settings = (
        campaign.settings
        if isinstance(campaign.settings, dict)
        else {}
    )

    product_names = [
        b11_clean_text(item)
        for item in (
            settings.get("product_names")
            or []
        )
        if b11_clean_text(item)
    ]

    if not product_names:
        product_names = [
            b11_clean_text(
                settings.get("product_name")
                or campaign.name
            )
        ]

    product_label = ", ".join(
        product_names[:6]
    )

    template_label = b11_clean_text(
        settings.get(
            "creative_template_label"
        )
        or settings.get(
            "creative_template"
        )
        or "Product Showcase"
    )

    audience = b11_clean_text(
        settings.get("audience")
        or "retail"
    )

    promo_text = b11_clean_text(
        settings.get("promo_text")
    )

    promo_min_amount = settings.get(
        "promo_min_amount"
    )

    promo_discount = settings.get(
        "promo_discount_percent"
    )

    promo_parts: list[str] = []

    if promo_text:
        promo_parts.append(promo_text)

    if promo_discount:
        promo_parts.append(
            f"Diskon {promo_discount}%"
        )

    if promo_min_amount:
        try:
            amount = int(
                float(promo_min_amount)
            )

            promo_parts.append(
                "minimal belanja "
                f"Rp{amount:,.0f}"
                .replace(",", ".")
            )
        except (TypeError, ValueError):
            pass

    promo_label = ", ".join(
        promo_parts
    )

    completed_jobs = [
        job
        for job in jobs
        if job.status == "completed"
    ]

    hook_candidates: list[str] = []
    cta_candidates: list[str] = []

    for job in completed_jobs:
        config = (
            job.config
            if isinstance(job.config, dict)
            else {}
        )

        hook = b11_clean_text(
            config.get("hook")
        )

        cta = b11_clean_text(
            config.get("cta")
        )

        if (
            hook
            and hook not in hook_candidates
        ):
            hook_candidates.append(hook)

        if (
            cta
            and cta not in cta_candidates
        ):
            cta_candidates.append(cta)

    default_hook = (
        hook_candidates[0]
        if hook_candidates
        else (
            f"Lagi cari pilihan {product_label} "
            "yang unik dan menarik?"
        )
    )

    default_cta = (
        cta_candidates[0]
        if cta_candidates
        else "Pesan sekarang melalui WhatsApp."
    )

    promo_sentence = (
        f" Nikmati {promo_label}."
        if promo_label
        else ""
    )

    primary_texts = [
        (
            f"{default_hook} "
            f"Temukan {product_label} dalam satu "
            f"pilihan {template_label.lower()}."
            f"{promo_sentence} {default_cta}"
        ),
        (
            f"Bikin pilihan produk jadi lebih praktis. "
            f"{product_label} siap untuk kebutuhanmu."
            f"{promo_sentence} Klik dan pesan sekarang "
            "sebelum kehabisan."
        ),
        (
            f"Pilihan menarik untuk kamu yang mencari "
            f"{product_label}. Cocok untuk audience "
            f"{audience.replace('_', ' ')}."
            f"{promo_sentence} Hubungi kami melalui "
            "WhatsApp untuk detail dan pemesanan."
        ),
    ]

    headlines = [
        f"{product_names[0]} Pilihan SpaceCraft",
        f"Promo {template_label}",
        "Pesan Mudah via WhatsApp",
        "Pilihan Produk Unik Hari Ini",
        (
            f"Diskon {promo_discount}% Sekarang"
            if promo_discount
            else "Lihat Koleksi Terbaru"
        ),
    ]

    descriptions = [
        (
            f"Temukan {product_label} dan pesan "
            "langsung melalui WhatsApp."
        ),
        (
            f"{template_label} dengan pilihan produk "
            "yang menarik dan siap dipesan."
        ),
        (
            (
                f"{promo_label.capitalize()}. "
                if promo_label
                else ""
            )
            + "Stok terbatas, cek detail sekarang."
        ),
    ]

    whatsapp_opening = (
        "Halo SpaceCraft, saya tertarik dengan "
        f"campaign {b11_campaign_code(campaign)} "
        f"untuk produk {product_label}. "
        "Boleh minta informasi harga, stok, "
        "dan cara pemesanannya?"
    )

    return {
        "campaign_code":
            b11_campaign_code(campaign),
        "campaign_name": campaign.name,
        "template": template_label,
        "audience": audience,
        "products": product_names,
        "promo": promo_label or None,
        "primary_texts": [
            b11_clean_text(item)
            for item in primary_texts
        ],
        "headlines": [
            b11_clean_text(item)
            for item in headlines
        ],
        "descriptions": [
            b11_clean_text(item)
            for item in descriptions
        ],
        "cta_recommendation":
            "Kirim Pesan WhatsApp",
        "whatsapp_opening":
            whatsapp_opening,
        "generated_at": now().isoformat(),
    }


def b11_campaign_export_manifest(
    campaign: CreativeCampaign,
    jobs: list[RenderJob],
    ad_copy: dict[str, Any],
) -> dict[str, Any]:
    approved_jobs: list[
        dict[str, Any]
    ] = []

    for job in jobs:
        config = (
            job.config
            if isinstance(job.config, dict)
            else {}
        )

        review = normalize_render_review(
            config.get("review")
        )

        if (
            job.status != "completed"
            or review.get("status")
                != "approved"
        ):
            continue

        approved_jobs.append({
            "job_id": job.id,
            "variation_index":
                job.variation_index,
            "winner": bool(
                review.get("winner")
            ),
            "rating": review.get("rating"),
            "review_notes":
                review.get("notes"),
            "output_path": job.output_path,
            "thumbnail_path":
                config.get("thumbnail_path"),
            "qa": config.get("qa"),
            "hook": config.get("hook"),
            "cta": config.get("cta"),
            "export_preset":
                config.get("export_preset"),
            "aspect_ratio":
                config.get("aspect_ratio"),
        })

    return {
        "version": "b11",
        "campaign": campaign_to_dict(
            campaign
        ),
        "ad_copy": ad_copy,
        "approved_assets": approved_jobs,
        "approved_count":
            len(approved_jobs),
        "created_at": now().isoformat(),
    }


def b11_build_export_package(
    campaign: CreativeCampaign,
    jobs: list[RenderJob],
) -> dict[str, Any]:
    ad_copy = b11_campaign_copy(
        campaign,
        jobs,
    )

    manifest = (
        b11_campaign_export_manifest(
            campaign,
            jobs,
            ad_copy,
        )
    )

    approved_assets = manifest[
        "approved_assets"
    ]

    if not approved_assets:
        raise HTTPException(
            status_code=400,
            detail=(
                "Belum ada video Approved. "
                "Set status minimal satu video "
                "menjadi Approved sebelum export."
            ),
        )

    campaign_code = ad_copy[
        "campaign_code"
    ]

    folder_slug = b11_slugify(
        campaign.name
    )

    export_dir = (
        STORAGE_ROOT
        / "campaign-exports"
        / f"campaign-{campaign.id}"
    )

    export_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    package_name = (
        "spacecraft-"
        f"{campaign_code}-"
        f"{folder_slug}-"
        "approved-"
        f"{now().strftime('%Y%m%d-%H%M%S')}"
        ".zip"
    )

    package_path = export_dir / package_name

    qa_report = {
        "campaign_code": campaign_code,
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "approved_count":
            len(approved_assets),
        "jobs": [
            {
                "job_id": item["job_id"],
                "variation_index":
                    item["variation_index"],
                "winner": item["winner"],
                "rating": item["rating"],
                "qa": item["qa"],
            }
            for item in approved_assets
        ],
        "generated_at": now().isoformat(),
    }

    copy_lines = [
        f"CAMPAIGN CODE: {campaign_code}",
        f"CAMPAIGN: {campaign.name}",
        "",
        "PRIMARY TEXT",
    ]

    for index, text in enumerate(
        ad_copy["primary_texts"],
        start=1,
    ):
        copy_lines.extend([
            f"{index}. {text}",
            "",
        ])

    copy_lines.append("HEADLINES")

    for index, text in enumerate(
        ad_copy["headlines"],
        start=1,
    ):
        copy_lines.append(
            f"{index}. {text}"
        )

    copy_lines.extend([
        "",
        "DESCRIPTIONS",
    ])

    for index, text in enumerate(
        ad_copy["descriptions"],
        start=1,
    ):
        copy_lines.append(
            f"{index}. {text}"
        )

    copy_lines.extend([
        "",
        "CTA RECOMMENDATION",
        ad_copy["cta_recommendation"],
        "",
        "WHATSAPP OPENING",
        ad_copy["whatsapp_opening"],
        "",
    ])

    with zipfile.ZipFile(
        package_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        root_name = (
            "spacecraft-"
            f"{campaign_code}-"
            f"{folder_slug}"
        )

        archive.writestr(
            f"{root_name}/ad-copy.txt",
            "\n".join(copy_lines),
        )

        archive.writestr(
            f"{root_name}/campaign-manifest.json",
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
            ),
        )

        archive.writestr(
            f"{root_name}/qa-report.json",
            json.dumps(
                qa_report,
                ensure_ascii=False,
                indent=2,
            ),
        )

        for item in approved_assets:
            variation = int(
                item["variation_index"]
            )

            winner_suffix = (
                "-winner"
                if item["winner"]
                else ""
            )

            video_relative = str(
                item.get("output_path")
                or ""
            ).strip()

            if video_relative:
                video_path = (
                    STORAGE_ROOT
                    / video_relative
                )

                try:
                    video_path.resolve().relative_to(
                        STORAGE_ROOT.resolve()
                    )
                except ValueError:
                    video_path = Path(
                        "/invalid"
                    )

                if video_path.is_file():
                    extension = (
                        video_path.suffix
                        or ".mp4"
                    )

                    archive.write(
                        video_path,
                        (
                            f"{root_name}/videos/"
                            + b18j_campaign_asset_filename(
                                campaign,
                                variation,
                                extension,
                                kind="video",
                                approved=True,
                                winner=bool(item["winner"]),
                            )
                        ),
                    )

            thumbnail_relative = str(
                item.get("thumbnail_path")
                or ""
            ).strip()

            if thumbnail_relative:
                thumbnail_path = (
                    STORAGE_ROOT
                    / thumbnail_relative
                )

                try:
                    thumbnail_path.resolve().relative_to(
                        STORAGE_ROOT.resolve()
                    )
                except ValueError:
                    thumbnail_path = Path(
                        "/invalid"
                    )

                if thumbnail_path.is_file():
                    extension = (
                        thumbnail_path.suffix
                        or ".jpg"
                    )

                    archive.write(
                        thumbnail_path,
                        (
                            f"{root_name}/thumbnails/"
                            + b18j_campaign_asset_filename(
                                campaign,
                                variation,
                                extension,
                                kind="thumbnail",
                                approved=True,
                                winner=bool(item["winner"]),
                            )
                        ),
                    )

    relative_path = (
        package_path
        .relative_to(STORAGE_ROOT)
        .as_posix()
    )

    return {
        "campaign_code": campaign_code,
        "package_name": package_name,
        "package_path": relative_path,
        "package_url":
            f"/media/{relative_path}",
        "approved_count":
            len(approved_assets),
        "size_bytes":
            package_path.stat().st_size,
        "manifest": manifest,
        "ad_copy": ad_copy,
    }




def performance_key(
    campaign_id: int,
    job_id: int,
) -> str:
    return (
        f"{PERFORMANCE_KEY_PREFIX}"
        f"{campaign_id}:{job_id}"
    )


def performance_campaign_set_key(
    campaign_id: int,
) -> str:
    return (
        f"{PERFORMANCE_CAMPAIGN_SET_PREFIX}"
        f"{campaign_id}"
    )


def performance_number(
    value: Any,
    default: float = 0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def performance_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(
            float(value)
        )
    except (TypeError, ValueError):
        return default


def performance_calculate(
    raw: dict[str, Any] | None,
) -> dict[str, Any]:
    source = (
        raw
        if isinstance(raw, dict)
        else {}
    )

    impressions = max(
        0,
        performance_int(
            source.get("impressions")
        ),
    )

    clicks = max(
        0,
        performance_int(
            source.get("clicks")
        ),
    )

    spend = max(
        0.0,
        performance_number(
            source.get("spend")
        ),
    )

    leads = max(
        0,
        performance_int(
            source.get("leads")
        ),
    )

    closings = max(
        0,
        performance_int(
            source.get("closings")
        ),
    )

    revenue = max(
        0.0,
        performance_number(
            source.get("revenue")
        ),
    )

    ctr = (
        clicks / impressions * 100
        if impressions
        else 0
    )

    cpm = (
        spend / impressions * 1000
        if impressions
        else 0
    )

    cpc = (
        spend / clicks
        if clicks
        else 0
    )

    cpl = (
        spend / leads
        if leads
        else 0
    )

    lead_conversion = (
        leads / clicks * 100
        if clicks
        else 0
    )

    closing_conversion = (
        closings / leads * 100
        if leads
        else 0
    )

    roas = (
        revenue / spend
        if spend
        else 0
    )

    profit = revenue - spend

    score = (
        min(ctr, 10) * 8
        + min(roas, 10) * 15
        + min(
            closing_conversion,
            100,
        ) * 0.45
        + min(closings, 20) * 4
    )

    if impressions < 500:
        recommendation = "keep_testing"
        recommendation_label = (
            "Keep Testing"
        )
        recommendation_reason = (
            "Data belum cukup. Tambahkan "
            "impressions sebelum mengambil keputusan."
        )

    elif (
        roas >= 3
        and closings >= 2
    ):
        recommendation = "scale"
        recommendation_label = "Scale"
        recommendation_reason = (
            "ROAS dan closing kuat. "
            "Layak menaikkan budget bertahap."
        )

    elif (
        ctr >= 1.5
        and leads > 0
        and closings == 0
    ):
        recommendation = "revise"
        recommendation_label = "Revise"
        recommendation_reason = (
            "Creative menarik klik, tetapi belum "
            "menghasilkan closing. Periksa offer, "
            "landing flow, atau follow-up WhatsApp."
        )

    elif (
        impressions >= 1500
        and (
            ctr < 0.7
            or (
                spend > 0
                and roas < 1
            )
        )
    ):
        recommendation = "stop"
        recommendation_label = "Stop"
        recommendation_reason = (
            "Performa lemah setelah data cukup. "
            "Hentikan atau ganti hook dan creative."
        )

    else:
        recommendation = "keep_testing"
        recommendation_label = (
            "Keep Testing"
        )
        recommendation_reason = (
            "Performa belum cukup kuat untuk scale "
            "atau stop. Lanjutkan pengujian."
        )

    return {
        "impressions": impressions,
        "clicks": clicks,
        "spend": round(spend, 2),
        "leads": leads,
        "closings": closings,
        "revenue": round(revenue, 2),
        "ctr": round(ctr, 4),
        "cpm": round(cpm, 2),
        "cpc": round(cpc, 2),
        "cpl": round(cpl, 2),
        "lead_conversion": round(
            lead_conversion,
            4,
        ),
        "closing_conversion": round(
            closing_conversion,
            4,
        ),
        "roas": round(roas, 4),
        "profit": round(profit, 2),
        "score": round(score, 4),
        "recommendation":
            recommendation,
        "recommendation_label":
            recommendation_label,
        "recommendation_reason":
            recommendation_reason,
        "notes": str(
            source.get("notes")
            or ""
        ).strip(),
        "source": str(
            source.get("source")
            or "manual"
        ).strip(),
        "updated_at":
            source.get("updated_at"),
    }


def performance_load(
    campaign_id: int,
    job_id: int,
) -> dict[str, Any]:
    redis_client = redis_connection()

    raw = redis_client.get(
        performance_key(
            campaign_id,
            job_id,
        )
    )

    if not raw:
        return performance_calculate({})

    try:
        parsed = json.loads(
            automation_decode(raw)
        )
    except json.JSONDecodeError:
        parsed = {}

    return performance_calculate(
        parsed
        if isinstance(parsed, dict)
        else {}
    )


def performance_save(
    campaign_id: int,
    job_id: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    redis_client = redis_connection()

    calculated = performance_calculate(
        {
            **data,
            "updated_at":
                now().isoformat(),
        }
    )

    redis_client.set(
        performance_key(
            campaign_id,
            job_id,
        ),
        json.dumps(
            calculated,
            ensure_ascii=False,
        ),
    )

    redis_client.sadd(
        performance_campaign_set_key(
            campaign_id
        ),
        str(job_id),
    )

    return calculated


def performance_job_metadata(
    job: RenderJob,
) -> dict[str, Any]:
    config = (
        job.config
        if isinstance(job.config, dict)
        else {}
    )

    review = normalize_render_review(
        config.get("review")
    )

    return {
        "job_id": job.id,
        "campaign_id":
            job.campaign_id,
        "variation_index":
            job.variation_index,
        "status": job.status,
        "hook": str(
            config.get("hook")
            or ""
        ).strip(),
        "cta": str(
            config.get("cta")
            or ""
        ).strip(),
        "template": str(
            config.get(
                "creative_template_label"
            )
            or config.get(
                "creative_template"
            )
            or "Custom"
        ).strip(),
        "export_preset":
            config.get("export_preset"),
        "review_status":
            review.get("status"),
        "review_rating":
            review.get("rating"),
        "review_winner":
            review.get("winner"),
        "thumbnail_url": (
            f"/media/{config.get('thumbnail_path')}"
            if config.get(
                "thumbnail_path"
            )
            else None
        ),
        "output_url": (
            f"/media/{job.output_path}"
            if job.output_path
            else None
        ),
    }


def performance_campaign_dashboard(
    campaign: CreativeCampaign,
    jobs: list[RenderJob],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    for job in jobs:
        metrics = performance_load(
            campaign.id,
            job.id,
        )

        items.append({
            **performance_job_metadata(job),
            "metrics": metrics,
        })

    ranked = sorted(
        items,
        key=lambda item: (
            item["metrics"]["score"],
            item["metrics"]["roas"],
            item["metrics"]["closings"],
            item["metrics"]["ctr"],
        ),
        reverse=True,
    )

    for index, item in enumerate(
        ranked,
        start=1,
    ):
        item["rank"] = index

    totals = {
        "impressions": sum(
            item["metrics"]["impressions"]
            for item in items
        ),
        "clicks": sum(
            item["metrics"]["clicks"]
            for item in items
        ),
        "spend": round(
            sum(
                item["metrics"]["spend"]
                for item in items
            ),
            2,
        ),
        "leads": sum(
            item["metrics"]["leads"]
            for item in items
        ),
        "closings": sum(
            item["metrics"]["closings"]
            for item in items
        ),
        "revenue": round(
            sum(
                item["metrics"]["revenue"]
                for item in items
            ),
            2,
        ),
    }

    totals_calculated = (
        performance_calculate(totals)
    )

    for key in (
        "ctr",
        "cpm",
        "cpc",
        "cpl",
        "lead_conversion",
        "closing_conversion",
        "roas",
        "profit",
    ):
        totals[key] = (
            totals_calculated[key]
        )

    hook_stats: dict[
        str,
        list[float],
    ] = {}

    template_stats: dict[
        str,
        list[float],
    ] = {}

    cta_stats: dict[
        str,
        list[float],
    ] = {}

    for item in items:
        score = item[
            "metrics"
        ]["score"]

        hook = item.get("hook") or "-"
        template = (
            item.get("template") or "-"
        )
        cta = item.get("cta") or "-"

        hook_stats.setdefault(
            hook,
            [],
        ).append(score)

        template_stats.setdefault(
            template,
            [],
        ).append(score)

        cta_stats.setdefault(
            cta,
            [],
        ).append(score)

    def aggregate_dimension(
        source: dict[
            str,
            list[float],
        ],
    ) -> list[dict[str, Any]]:
        values = [
            {
                "label": label,
                "sample_count":
                    len(scores),
                "average_score": round(
                    sum(scores)
                    / len(scores),
                    4,
                ),
            }
            for label, scores
            in source.items()
        ]

        values.sort(
            key=lambda item:
                item["average_score"],
            reverse=True,
        )

        return values[:10]

    performance_winner = (
        ranked[0]
        if ranked
        and ranked[0][
            "metrics"
        ]["impressions"] > 0
        else None
    )

    return {
        "campaign": {
            "id": campaign.id,
            "name": campaign.name,
            "status": campaign.status,
            "campaign_code":
                b11_campaign_code(
                    campaign
                ),
        },
        "totals": totals,
        "items": ranked,
        "performance_winner":
            performance_winner,
        "dimensions": {
            "hooks":
                aggregate_dimension(
                    hook_stats
                ),
            "templates":
                aggregate_dimension(
                    template_stats
                ),
            "ctas":
                aggregate_dimension(
                    cta_stats
                ),
        },
        "generated_at": now().isoformat(),
    }


def performance_campaign_csv(
    dashboard: dict[str, Any],
) -> str:
    headers = [
        "rank",
        "campaign_id",
        "job_id",
        "variation",
        "hook",
        "template",
        "cta",
        "impressions",
        "clicks",
        "ctr_percent",
        "spend",
        "cpm",
        "cpc",
        "leads",
        "cpl",
        "closings",
        "closing_conversion_percent",
        "revenue",
        "roas",
        "profit",
        "score",
        "recommendation",
        "notes",
        "updated_at",
    ]

    def csv_cell(value: Any) -> str:
        text = str(
            value
            if value is not None
            else ""
        )

        return (
            '"'
            + text.replace('"', '""')
            + '"'
        )

    rows = [
        ",".join(headers)
    ]

    for item in dashboard["items"]:
        metrics = item["metrics"]

        values = [
            item.get("rank"),
            item.get("campaign_id"),
            item.get("job_id"),
            item.get(
                "variation_index"
            ),
            item.get("hook"),
            item.get("template"),
            item.get("cta"),
            metrics.get("impressions"),
            metrics.get("clicks"),
            metrics.get("ctr"),
            metrics.get("spend"),
            metrics.get("cpm"),
            metrics.get("cpc"),
            metrics.get("leads"),
            metrics.get("cpl"),
            metrics.get("closings"),
            metrics.get(
                "closing_conversion"
            ),
            metrics.get("revenue"),
            metrics.get("roas"),
            metrics.get("profit"),
            metrics.get("score"),
            metrics.get(
                "recommendation_label"
            ),
            metrics.get("notes"),
            metrics.get("updated_at"),
        ]

        rows.append(
            ",".join(
                csv_cell(value)
                for value in values
            )
        )

    return "\n".join(rows)



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


# VOICE_DRAFT_HELPERS_V1
_ID_NUMBER_WORDS = (
    "nol",
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
)


def indonesian_number_words(value: int) -> str:
    number = int(value)

    if number < 0:
        return "minus " + indonesian_number_words(
            abs(number)
        )

    if number < 12:
        return _ID_NUMBER_WORDS[number]

    if number < 20:
        return (
            indonesian_number_words(number - 10)
            + " belas"
        )

    if number < 100:
        tens, remainder = divmod(number, 10)
        result = (
            indonesian_number_words(tens)
            + " puluh"
        )
        if remainder:
            result += " " + indonesian_number_words(
                remainder
            )
        return result

    if number < 200:
        remainder = number - 100
        return (
            "seratus"
            + (
                " " + indonesian_number_words(remainder)
                if remainder
                else ""
            )
        )

    if number < 1000:
        hundreds, remainder = divmod(number, 100)
        result = (
            indonesian_number_words(hundreds)
            + " ratus"
        )
        if remainder:
            result += " " + indonesian_number_words(
                remainder
            )
        return result

    if number < 2000:
        remainder = number - 1000
        return (
            "seribu"
            + (
                " " + indonesian_number_words(remainder)
                if remainder
                else ""
            )
        )

    units = (
        (1_000_000_000_000, "triliun"),
        (1_000_000_000, "miliar"),
        (1_000_000, "juta"),
        (1_000, "ribu"),
    )

    for divisor, label in units:
        if number >= divisor:
            quotient, remainder = divmod(
                number,
                divisor,
            )
            result = (
                indonesian_number_words(quotient)
                + " "
                + label
            )
            if remainder:
                result += (
                    " "
                    + indonesian_number_words(remainder)
                )
            return result

    return str(number)


def _parse_spoken_integer(value: str) -> int:
    digits = re.sub(r"[^0-9]", "", value or "")
    return int(digits or "0")


def normalize_tts_text_indonesian(
    value: str,
    protected_terms: list[str] | None = None,
) -> str:
    result = str(value or "").strip()
    protected_terms = protected_terms or []
    replacements: dict[str, str] = {}

    clean_terms = sorted(
        {
            str(item).strip()
            for item in protected_terms
            if str(item).strip()
        },
        key=len,
        reverse=True,
    )

    for index, term in enumerate(clean_terms):
        token = chr(0xE000 + index)
        replacements[token] = term
        result = result.replace(term, token)

    def replace_rupiah(match: re.Match[str]) -> str:
        amount = _parse_spoken_integer(
            match.group(1)
        )
        return (
            indonesian_number_words(amount)
            + " rupiah"
        )

    def replace_percent(match: re.Match[str]) -> str:
        amount = int(match.group(1))
        return (
            indonesian_number_words(amount)
            + " persen"
        )

    def replace_piece(match: re.Match[str]) -> str:
        amount = int(match.group(1))
        return (
            indonesian_number_words(amount)
            + " buah"
        )

    result = re.sub(
        r"(?i)\bRp\.?\s*([0-9][0-9.,]*)",
        replace_rupiah,
        result,
    )
    result = re.sub(
        r"\b([0-9]+)\s*%",
        replace_percent,
        result,
    )
    result = re.sub(
        r"(?i)\b([0-9]+)\s*(?:pcs?|pieces?)\b",
        replace_piece,
        result,
    )
    result = re.sub(
        r"(?i)\bWA\b",
        "WhatsApp",
        result,
    )
    result = result.replace("&", " dan ")

    result = re.sub(
        r"(?<![\w])([0-9]+)(?![\w])",
        lambda match: indonesian_number_words(
            int(match.group(1))
        ),
        result,
    )

    result = re.sub(r"\s+", " ", result)
    result = re.sub(r"\s+([,.;!?])", r"\1", result)

    for token, term in replacements.items():
        result = result.replace(token, term)

    return result.strip()


def join_exact_product_names(names: list[str]) -> str:
    clean = [
        str(item).strip()
        for item in names
        if str(item).strip()
    ]

    if not clean:
        return "produk pilihan Spacecraft"

    if len(clean) == 1:
        return clean[0]

    if len(clean) == 2:
        return f"{clean[0]} dan {clean[1]}"

    return (
        ", ".join(clean[:-1])
        + ", dan "
        + clean[-1]
    )


def build_catalog_voiceover_draft(
    products: list[Product],
    audience: str,
    duration_seconds: int,
    promo_enabled: bool,
    promo_min_amount: int,
    promo_discount_percent: int,
    promo_text: str | None,
    compact: bool = False,
) -> str:
    exact_names = [item.name for item in products]
    aliases = [compact_voice_product_alias(item.name) for item in products]

    if compact:
        product_sentence = join_exact_product_names(aliases)
        script_parts = [
            'Enam fidget unik bisa kamu pilih atau kombinasikan dalam satu pesanan.',
            f'Ada {product_sentence}.',
        ]
    else:
        product_sentence = join_exact_product_names(exact_names)
        intro_by_audience = {
            'reseller': 'Sedang mencari koleksi unik untuk menambah pilihan produk di tokomu?',
            'custom_bulk': 'Butuh pilihan produk unik untuk merchandise atau pesanan dalam jumlah banyak?',
            'retail_bulk': 'Lagi cari fidget unik yang seru dan bisa dikombinasikan dalam satu pesanan?',
            'retail': 'Lagi cari fidget unik yang seru dan bikin rileks?',
        }
        script_parts = [
            intro_by_audience.get(audience, intro_by_audience['retail']),
            f'Kenalan dengan {product_sentence}.',
        ]
        if audience == 'reseller':
            script_parts.append('Pilih koleksi yang paling cocok untuk katalog dan pelangganmu.')
        elif audience == 'custom_bulk':
            script_parts.append('Pilih beberapa item sesuai kebutuhan acara, komunitas, atau brand kamu.')
        else:
            script_parts.append('Pilih satu produk favoritmu, atau gabungkan beberapa item sekaligus.')

    if promo_enabled:
        custom_promo = (promo_text or '').strip()
        if custom_promo:
            normalized_custom_promo = normalize_tts_text_indonesian(
                custom_promo,
                exact_names + aliases,
            ).strip()
            if normalized_custom_promo and normalized_custom_promo[-1] not in '.!?':
                normalized_custom_promo += '.'
            script_parts.append(normalized_custom_promo)

        if promo_min_amount > 0:
            offer_sentence = (
                'Belanja minimal '
                + indonesian_number_words(promo_min_amount)
                + ' rupiah dan dapatkan diskon '
                + indonesian_number_words(promo_discount_percent)
                + ' persen.'
            )
        else:
            offer_sentence = (
                'Dapatkan diskon '
                + indonesian_number_words(promo_discount_percent)
                + ' persen.'
            )
        script_parts.append(offer_sentence)

    script_parts.append('Pesan sekarang melalui WhatsApp.')
    draft = ' '.join(item.strip() for item in script_parts if item.strip())
    return normalize_tts_text_indonesian(draft, exact_names + aliases)

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
    voiceover = config.get("voiceover") or {}
    if not voiceover.get("enabled"):
        return None
    text = str(voiceover.get("script") or "").strip()
    if not text:
        raise RuntimeError("Naskah voice-over kosong")
    asset_id = str(voiceover.get("approved_asset_id") or "").strip()
    fingerprint = str(voiceover.get("approved_fingerprint") or "").strip()
    if asset_id or fingerprint:
        if not asset_id or not fingerprint:
            raise RuntimeError("Approved voice asset tidak lengkap")
        approved = resolve_approved_voice_asset(
            asset_id=asset_id,
            expected_fingerprint=fingerprint,
            expected_voice_id=str(voiceover.get("voice_id") or ""),
            expected_text=text,
        )
        destination = temp_dir / "voiceover.mp3"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(approved["audio_path"], destination)
        return destination
    return generate_elevenlabs_audio(
        voice_id=str(voiceover.get("voice_id") or ""),
        text=text,
        destination=temp_dir / "voiceover.mp3",
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
    preserve_natural_duration: bool = False,
) -> str:
    actual_duration = media_duration_seconds(voiceover_path)
    if preserve_natural_duration and actual_duration:
        fade_start = max(min(float(actual_duration), float(duration)) - 0.35, 0.0)
    else:
        fade_start = max(duration - 0.45, 0)

    filters = [
        'aresample=44100',
        'aformat=sample_fmts=fltp:channel_layouts=stereo',
        'highpass=f=80',
        'lowpass=f=14500',
        'loudnorm=I=-15:LRA=9:TP=-1.5',
    ]
    target_duration = max(1.0, duration - 0.75)
    if not preserve_natural_duration:
        if actual_duration and actual_duration > target_duration:
            filters.extend(atempo_chain(actual_duration / target_duration))
        elif actual_duration and actual_duration < target_duration * 0.94:
            filters.extend(atempo_chain(actual_duration / target_duration))

    filters.extend([
        f'apad=pad_dur={duration}',
        f'atrim=0:{duration}',
        'afade=t=in:st=0:d=0.12',
        f'afade=t=out:st={fade_start:.3f}:d=0.35',
    ])
    return '[1:a]' + ','.join(filters) + '[a]'

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


def render_raw_catalog_image_segment(
    input_path: Path,
    output_path: Path,
    aspect_ratio: str,
    duration: float,
    fit_mode: str = "cover",
) -> None:
    width, height = dimensions(
        aspect_ratio
    )

    duration = max(
        0.75,
        float(duration),
    )

    fit_mode = str(
        fit_mode or "cover"
    ).strip().lower()

    if fit_mode not in {
        "contain",
        "cover",
        "blur_fill",
    }:
        fit_mode = "cover"

    fps = 30
    frames = max(
        1,
        int(round(duration * fps)),
    )

    if fit_mode == "contain":
        video_filter = (
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:"
            "(ow-iw)/2:(oh-ih)/2:"
            "color=0xFFF7EC,"
            f"zoompan=z='min(zoom+0.0007,1.045)':"
            "x='iw/2-(iw/zoom/2)':"
            "y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={width}x{height}:fps={fps},"
            "setsar=1,format=yuv420p"
        )
    elif fit_mode == "blur_fill":
        video_filter = (
            "split=2[background][foreground];"
            "[background]"
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            "boxblur=luma_radius=min(h\\,w)/30:"
            "luma_power=2,"
            "eq=brightness=-0.04:saturation=0.92"
            "[blurred];"
            "[foreground]"
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=decrease"
            "[main];"
            "[blurred][main]"
            "overlay=(main_w-overlay_w)/2:"
            "(main_h-overlay_h)/2,"
            f"zoompan=z='min(zoom+0.0008,1.050)':"
            "x='iw/2-(iw/zoom/2)':"
            "y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={width}x{height}:fps={fps},"
            "setsar=1,format=yuv420p"
        )
    else:
        video_filter = (
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"zoompan=z='min(zoom+0.0010,1.060)':"
            "x='iw/2-(iw/zoom/2)':"
            "y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={width}x{height}:fps={fps},"
            "setsar=1,format=yuv420p"
        )

    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-framerate",
        str(fps),
        "-t",
        f"{duration:.3f}",
        "-i",
        str(input_path),
        "-vf",
        video_filter,
        "-an",
        "-t",
        f"{duration:.3f}",
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
            result.stderr[-4000:]
        )

    if (
        not output_path.is_file()
        or output_path.stat().st_size < 10_000
    ):
        raise RuntimeError(
            "Segment image catalog tidak valid"
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




# B18E_CLOSING_HELPERS_START
def raw_catalog_closing_duration(
    duration_seconds: int | float,
) -> float:
    duration = max(1.0, float(duration_seconds or 0))
    if duration >= 20.0:
        return 5.0
    return round(min(5.0, max(3.5, duration * 0.22)), 3)


def raw_catalog_visual_product_name(value: str) -> str:
    original = re.sub(r"\s+", " ", str(value or "Produk").strip())
    if len(original) <= 28:
        return original

    compact = original
    for token in ("Articulated", "Fidget", "Keychain", "New"):
        compact = re.sub(
            rf"\b{re.escape(token)}\b",
            "",
            compact,
            flags=re.IGNORECASE,
        )

    compact = re.sub(
        r"^Sack\s+Of\s+",
        "",
        compact,
        flags=re.IGNORECASE,
    )
    compact = re.sub(r"\s+", " ", compact).strip()

    if len(compact) <= 30:
        return compact

    words = compact.split()
    clicker_index = next(
        (
            index
            for index, word in enumerate(words)
            if word.lower() == "clicker"
        ),
        None,
    )

    if clicker_index is not None:
        candidate = " ".join(words[: min(clicker_index + 1, 5)])
    else:
        candidate = " ".join(words[:4])

    return candidate[:34].rstrip()


def raw_catalog_promo_visual_lines(
    promo: dict[str, Any] | None,
) -> list[str]:
    source = promo if isinstance(promo, dict) else {}
    custom = str(source.get("label") or "").strip()
    custom_title = ""

    if custom:
        custom_title = re.split(r"[.!?]", custom, maxsplit=1)[0].strip()
        lowered = custom_title.lower()
        if (
            len(custom_title) > 34
            or (
                "diskon" in lowered
                and (
                    "rp" in lowered
                    or "belanja" in lowered
                    or "pembelian" in lowered
                )
            )
        ):
            custom_title = "PROMO SPESIAL"

    lines = [(custom_title or "PROMO SPESIAL").upper()]

    try:
        min_amount = int(float(source.get("min_amount") or 0))
    except (TypeError, ValueError):
        min_amount = 0

    try:
        discount = int(round(float(source.get("discount_percent") or 0)))
    except (TypeError, ValueError):
        discount = 0

    if min_amount > 0:
        lines.append("MIN. BELANJA " + format_rupiah(min_amount).upper())
    if discount > 0:
        lines.append(f"DISKON {discount}%")

    return lines[:3]
# B18E_CLOSING_HELPERS_END

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

    hook_size = 28 if width <= 720 else 38
    catalog_size = 18 if width <= 720 else 25
    promo_size = 21 if width <= 720 else 29
    cta_size = 23 if width <= 720 else 31
    brand_size = 17 if width <= 720 else 22
    top_box_x = int(width * 0.060)
    # Resolve safe-area dari snapshot/config apabila tersedia.
    # Gunakan fallback aman untuk video vertikal bila data lama
    # belum memiliki safe_area.
    _local_values = locals()

    _layout_snapshot = (
        _local_values.get("layout_snapshot")
        if isinstance(
            _local_values.get("layout_snapshot"),
            dict,
        )
        else {}
    )

    _config = (
        _local_values.get("config")
        if isinstance(
            _local_values.get("config"),
            dict,
        )
        else {}
    )

    _job_config = (
        _local_values.get("job_config")
        if isinstance(
            _local_values.get("job_config"),
            dict,
        )
        else {}
    )

    safe_area = (
        _layout_snapshot.get("safe_area")
        or _config.get("safe_area")
        or (
            _config.get("layout_snapshot", {})
            if isinstance(
                _config.get("layout_snapshot"),
                dict,
            )
            else {}
        ).get("safe_area")
        or _job_config.get("safe_area")
        or (
            _job_config.get("layout_snapshot", {})
            if isinstance(
                _job_config.get("layout_snapshot"),
                dict,
            )
            else {}
        ).get("safe_area")
        or {
            "top": 0.08,
            "bottom": 0.14,
            "left": 0.06,
            "right": 0.06,
        }
    )

    safe_area = {
        "top": max(
            0.0,
            min(
                0.40,
                float(
                    safe_area.get("top", 0.08)
                ),
            ),
        ),
        "bottom": max(
            0.0,
            min(
                0.40,
                float(
                    safe_area.get("bottom", 0.14)
                ),
            ),
        ),
        "left": max(
            0.0,
            min(
                0.30,
                float(
                    safe_area.get("left", 0.06)
                ),
            ),
        ),
        "right": max(
            0.0,
            min(
                0.30,
                float(
                    safe_area.get("right", 0.06)
                ),
            ),
        ),
    }

    # SAFE_AREA_DEFAULTS_V3_START
    # Normalize old and new layout snapshots before
    # any overlay coordinate is read.
    _safe_area_source_v3 = locals().get(
        "safe_area"
    )

    if not isinstance(
        _safe_area_source_v3,
        dict,
    ):
        _safe_area_source_v3 = {}

        for _safe_container_name_v3 in (
            "layout_snapshot",
            "config",
            "job_config",
        ):
            _safe_container_v3 = locals().get(
                _safe_container_name_v3
            )

            if not isinstance(
                _safe_container_v3,
                dict,
            ):
                continue

            _safe_candidate_v3 = (
                _safe_container_v3.get(
                    "safe_area"
                )
            )

            if not isinstance(
                _safe_candidate_v3,
                dict,
            ):
                _safe_layout_v3 = (
                    _safe_container_v3.get(
                        "layout_snapshot"
                    )
                )

                if isinstance(
                    _safe_layout_v3,
                    dict,
                ):
                    _safe_candidate_v3 = (
                        _safe_layout_v3.get(
                            "safe_area"
                        )
                    )

            if isinstance(
                _safe_candidate_v3,
                dict,
            ):
                _safe_area_source_v3 = (
                    _safe_candidate_v3
                )
                break

    safe_area = dict(
        _safe_area_source_v3
    )

    _safe_area_defaults_v3 = {
        "top": 0.08,
        "bottom": 0.14,
        "left": 0.06,
        "right": 0.06,

        "hook_y": 0.08,
        "hook_box_y": 0.08,
        "hook_box_height": 0.11,
        "hook_text_y": 0.105,

        "product_y": 0.19,
        "product_box_y": 0.19,
        "product_box_height": 0.12,
        "product_text_y": 0.22,

        "promo_y": 0.68,
        "promo_box_y": 0.68,
        "promo_box_height": 0.10,
        "promo_text_y": 0.705,

        "cta_y": 0.76,
        "cta_box_y": 0.76,
        "cta_box_height": 0.10,
        "cta_text_y": 0.785,

        "closing_y": 0.74,
        "closing_box_y": 0.74,
        "closing_box_height": 0.12,
        "closing_text_y": 0.775,

        "safe_width": 0.88,
        "content_width": 0.88,
    }

    for (
        _safe_key_v3,
        _safe_default_v3,
    ) in _safe_area_defaults_v3.items():
        try:
            safe_area[_safe_key_v3] = float(
                safe_area.get(
                    _safe_key_v3,
                    _safe_default_v3,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            safe_area[_safe_key_v3] = (
                _safe_default_v3
            )

    # SAFE_AREA_DEFAULTS_V3_END

    # SAFE_AREA_CANONICAL_V4B_START
    # Gabungkan canonical layout, snapshot campaign,
    # dan config job tanpa mengubah ekspresi f-string.
    _safe_config_v4b = locals().get(
        "config"
    )

    if not isinstance(
        _safe_config_v4b,
        dict,
    ):
        _safe_config_v4b = {}

    _aspect_ratio_v4b = (
        _safe_config_v4b.get(
            "aspect_ratio",
            "9:16",
        )
    )

    _current_safe_area_v4b = (
        locals().get("safe_area")
    )

    safe_area = (
        dict(_current_safe_area_v4b)
        if isinstance(
            _current_safe_area_v4b,
            dict,
        )
        else {}
    )

    _canonical_function_v4b = (
        globals().get(
            "raw_catalog_safe_area"
        )
    )

    _canonical_area_v4b = {}

    if callable(
        _canonical_function_v4b
    ):
        try:
            _canonical_area_v4b = (
                _canonical_function_v4b(
                    _aspect_ratio_v4b
                )
            )
        except TypeError:
            try:
                _canonical_area_v4b = (
                    _canonical_function_v4b()
                )
            except Exception:
                _canonical_area_v4b = {}
        except Exception:
            _canonical_area_v4b = {}

    if isinstance(
        _canonical_area_v4b,
        dict,
    ):
        _merged_safe_area_v4b = dict(
            _canonical_area_v4b
        )

        _merged_safe_area_v4b.update(
            safe_area
        )

        safe_area = (
            _merged_safe_area_v4b
        )

    _layout_snapshot_v4b = (
        _safe_config_v4b.get(
            "layout_snapshot"
        )
    )

    if isinstance(
        _layout_snapshot_v4b,
        dict,
    ):
        _snapshot_area_v4b = (
            _layout_snapshot_v4b.get(
                "safe_area"
            )
        )

        if isinstance(
            _snapshot_area_v4b,
            dict,
        ):
            safe_area.update(
                _snapshot_area_v4b
            )

    _config_area_v4b = (
        _safe_config_v4b.get(
            "safe_area"
        )
    )

    if isinstance(
        _config_area_v4b,
        dict,
    ):
        safe_area.update(
            _config_area_v4b
        )

    _required_safe_area_v4b = {
        "brand_y": 0.855,
        "cta_y": 0.815,
        "hook_y": 0.085,
        "product_text_y": 0.705,
    }

    for (
        _safe_key_v4b,
        _safe_default_v4b,
    ) in _required_safe_area_v4b.items():
        try:
            safe_area[_safe_key_v4b] = float(
                safe_area.get(
                    _safe_key_v4b,
                    _safe_default_v4b,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            safe_area[_safe_key_v4b] = (
                _safe_default_v4b
            )

    # SAFE_AREA_CANONICAL_V4B_END

    top_box_y = int(height * safe_area.get("top", 0.08))
    top_box_w = int(width * 0.880)
    top_box_h = int(height * 0.132)
    product_box_x = int(width * 0.065)
    product_box_y = int(height * safe_area.get("product_box_y", 0.19))
    product_box_w = int(width * 0.870)
    product_box_h = int(height * 0.086)
    catalog_box_x = int(width * 0.060)
    catalog_box_y = int(height * safe_area.get("closing_box_y", 0.74))
    catalog_box_w = int(width * 0.880)
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

    closing_duration = raw_catalog_closing_duration(
        duration
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
        wrap(config["hook"], 23),
        encoding="utf-8",
    )

    product_files: list[Path] = []

    for index, name in enumerate(product_names):
        product_file = (
            temp_dir
            / f"catalog-product-{index + 1:02d}.txt"
        )
        product_file.write_text(
            wrap(f"{index + 1}. {name}", 24),
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

    # B18E_CLOSING_SETUP_START
    display_product_names = [
        raw_catalog_visual_product_name(
            item.get("name") or item.get("label") or "Produk"
        )
        for item in product_items
    ]

    closing_product_files: list[dict[str, Any]] = []

    for index, display_name in enumerate(display_product_names[:6]):
        product_path = temp_dir / f"closing-product-{index + 1:02d}.txt"
        product_path.write_text(
            wrap(f"{index + 1}. {display_name}", 20),
            encoding="utf-8",
        )
        closing_product_files.append({
            "path": product_path,
            "column": index % 2,
            "row": index // 2,
        })

    files["closing_title"] = temp_dir / "closing-products-title.txt"
    files["closing_title"].write_text(
        "PILIH FAVORITMU ATAU KOMBINASIKAN",
        encoding="utf-8",
    )

    promo_visual_lines = (
        raw_catalog_promo_visual_lines(promo)
        if promo_enabled
        else [
            "PILIH PRODUK FAVORITMU",
            f"{len(product_names)} PRODUK TERSEDIA",
        ]
    )

    promo_visual_files: list[Path] = []
    for index, line in enumerate(promo_visual_lines):
        promo_path = temp_dir / f"closing-promo-{index + 1:02d}.txt"
        promo_path.write_text(wrap(line, 30), encoding="utf-8")
        promo_visual_files.append(promo_path)

    files["cta"].write_text(wrap(config["cta"], 34), encoding="utf-8")
    files["brand"].write_text("spacecraft.id", encoding="utf-8")

    closing_scene_product_end = min(
        float(duration),
        final_start + closing_duration * 0.54,
    )
    closing_scene_promo_start = closing_scene_product_end

    if config.get("aspect_ratio") == "9:16":
        closing_product_panel_y = 0.500
        closing_product_panel_h = 0.360
        closing_product_title_y = 0.528
        closing_product_rows = [0.592, 0.685, 0.778]
        closing_product_columns = [0.090, 0.535]
        closing_product_font = 18 if width <= 720 else 24
        closing_promo_panel_y = 0.560
        closing_promo_panel_h = 0.295
        closing_promo_start_y = 0.590
        closing_promo_step_y = 0.060
        closing_cta_y = 0.792
        closing_brand_y = 0.838
    else:
        closing_product_panel_y = 0.465
        closing_product_panel_h = 0.425
        closing_product_title_y = 0.492
        closing_product_rows = [0.555, 0.675, 0.795]
        closing_product_columns = [0.065, 0.515]
        closing_product_font = 18 if width <= 720 else 24
        closing_promo_panel_y = 0.520
        closing_promo_panel_h = 0.360
        closing_promo_start_y = 0.555
        closing_promo_step_y = 0.075
        closing_cta_y = 0.790
        closing_brand_y = 0.865
    # B18E_CLOSING_SETUP_END

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
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['hook']}':"
        "fontcolor=white:"
        "bordercolor=black@0.64:"
        "borderw=2:"
        "box=1:"
        "boxcolor=black@0.34:"
        "boxborderw=18:"
        f"fontsize={hook_size}:"
        "line_spacing=7:"
        "x=w*0.090:"
        f"y=h*{safe_area['hook_y'] + 0.018:.3f}:"
        "shadowcolor=black@0.64:"
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
            f"drawtext=fontfile='{FONT_FILE}':"
            f"textfile='{product_file}':"
            "fontcolor=white:"
            "bordercolor=black@0.66:"
            "borderw=2:"
            "box=1:"
            "boxcolor=black@0.38:"
            "boxborderw=14:"
            f"fontsize={catalog_size + 1}:"
            "line_spacing=5:"
            "x=w*0.090:"
            f"y=h*{safe_area['product_text_y'] + 0.014:.3f}:"
            "shadowcolor=black@0.62:"
            "shadowx=2:"
            "shadowy=2:"
            f"enable='{enabled}'",
        ])

    # B18E_CLOSING_FILTER_START
    product_closing_enabled = (
        f"between(t\\,{final_start:.3f}\\,{closing_scene_product_end:.3f})"
    )
    promo_closing_enabled = (
        f"between(t\\,{closing_scene_promo_start:.3f}\\,{float(duration):.3f})"
    )

    filter_parts.extend([
        "drawbox=x=iw*0.060:"
        f"y=ih*{closing_product_panel_y:.3f}:"
        "w=iw*0.880:"
        f"h=ih*{closing_product_panel_h:.3f}:"
        "color=black@0.52:t=fill:"
        f"enable='{product_closing_enabled}'",
        "drawbox=x=iw*0.060:"
        f"y=ih*{closing_product_panel_y:.3f}:"
        "w=iw*0.880:h=5:"
        "color=0x9EF0BD@0.95:t=fill:"
        f"enable='{product_closing_enabled}'",
        "drawbox=x=iw*0.060:"
        f"y=ih*{closing_product_panel_y + closing_product_panel_h:.3f}:"
        "w=iw*0.250:h=4:"
        "color=0xFFD36A@0.92:t=fill:"
        f"enable='{product_closing_enabled}'",
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['closing_title']}':"
        "expansion=none:fontcolor=0x9EF0BD:"
        "bordercolor=black@0.72:borderw=2:"
        f"fontsize={catalog_size + 3}:"
        "x=(w-text_w)/2:"
        f"y=h*{closing_product_title_y:.3f}:"
        "shadowcolor=black@0.75:shadowx=2:shadowy=2:"
        f"enable='{product_closing_enabled}'",
    ])

    for product_item in closing_product_files:
        column = int(product_item["column"])
        row = int(product_item["row"])
        filter_parts.append(
            f"drawtext=fontfile='{FONT_FILE}':"
            f"textfile='{product_item['path']}':"
            "expansion=none:fontcolor=white:"
            "bordercolor=black@0.66:borderw=2:"
            f"fontsize={closing_product_font}:line_spacing=4:"
            f"x=w*{closing_product_columns[column]:.3f}:"
            f"y=h*{closing_product_rows[row]:.3f}:"
            "shadowcolor=black@0.72:shadowx=2:shadowy=2:"
            f"enable='{product_closing_enabled}'"
        )

    filter_parts.append(
        "drawbox=x=iw*0.070:"
        f"y=ih*{closing_promo_panel_y:.3f}:"
        "w=iw*0.860:"
        f"h=ih*{closing_promo_panel_h:.3f}:"
        "color=black@0.54:t=fill:"
        f"enable='{promo_closing_enabled}'"
    )

    filter_parts.append(
        "drawbox=x=iw*0.070:"
        f"y=ih*{closing_promo_panel_y:.3f}:"
        "w=iw*0.860:h=5:"
        "color=0xFFD36A@0.95:t=fill:"
        f"enable='{promo_closing_enabled}'"
    )

    filter_parts.append(
        "drawbox=x=iw*0.070:"
        f"y=ih*{closing_promo_panel_y + closing_promo_panel_h:.3f}:"
        "w=iw*0.220:h=4:"
        "color=0x9EF0BD@0.90:t=fill:"
        f"enable='{promo_closing_enabled}'"
    )

    for index, promo_file in enumerate(promo_visual_files):
        promo_color = (
            "0xFFD36A"
            if index == 0 or "DISKON" in promo_visual_lines[index]
            else "white"
        )
        promo_font = promo_size + 3 if index == 0 else promo_size
        promo_y = closing_promo_start_y + closing_promo_step_y * index
        filter_parts.append(
            f"drawtext=fontfile='{FONT_FILE}':"
            f"textfile='{promo_file}':"
            "expansion=none:"
            f"fontcolor={promo_color}:"
            "bordercolor=black@0.70:borderw=2:"
            f"fontsize={promo_font}:line_spacing=5:"
            "x=(w-text_w)/2:"
            f"y=h*{promo_y:.3f}:"
            "shadowcolor=black@0.75:shadowx=2:shadowy=2:"
            f"enable='{promo_closing_enabled}'"
        )

    filter_parts.extend([
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['cta']}':"
        "expansion=none:fontcolor=0x9EF0BD:"
        "bordercolor=black@0.72:borderw=2:"
        f"fontsize={cta_size}:line_spacing=6:"
        "x=(w-text_w)/2:"
        f"y=h*{closing_cta_y:.3f}:"
        "shadowcolor=black@0.75:shadowx=2:shadowy=2:"
        f"enable='{promo_closing_enabled}'",
        f"drawtext=fontfile='{FONT_FILE}':"
        f"textfile='{files['brand']}':"
        "expansion=none:fontcolor=white@0.80:"
        "bordercolor=black@0.55:borderw=1:"
        f"fontsize={brand_size}:"
        "x=(w-text_w)/2:"
        f"y=h*{closing_brand_y:.3f}:"
        f"enable='{promo_closing_enabled}'",
    ])
    # B18E_CLOSING_FILTER_END

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
            preserve_natural_duration=True,
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
                preserve_natural_duration=True,
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

    closing_duration = raw_catalog_closing_duration(
        duration
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

        clip_asset_type = str(
            clip.get("asset_type")
            or clip.get("media_type")
            or "video"
        ).strip().lower()

        if clip_asset_type == "image":
            render_raw_catalog_image_segment(
                input_path=input_path,
                output_path=segment,
                aspect_ratio=config["aspect_ratio"],
                duration=segment_duration,
                fit_mode=str(
                    clip.get("fit_mode")
                    or "cover"
                ),
            )
        else:
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


def overlay_single_product_video(
    input_path: Path,
    config: dict[str, Any],
    output_path: Path,
    temp_dir: Path,
    voiceover_path: Path | None = None,
) -> None:
    width, height = dimensions(
        config.get("aspect_ratio", "9:16")
    )

    duration = int(
        config.get("duration_seconds", 20)
    )

    hook = (
        str(config.get("hook") or "").strip()
        or f"Kenalan sama {config.get('product_name') or 'produk ini'}"
    )
    product_name = str(
        config.get("product_name") or "Produk SpaceCraft"
    ).strip()
    price_label = str(
        config.get("price_label") or "Cek harga"
    ).strip()
    cta = (
        str(config.get("cta") or "").strip()
        or "Chat sekarang, pilih varian favoritmu"
    )

    files = {
        "hook": temp_dir / "single-hook.txt",
        "name": temp_dir / "single-name.txt",
        "price": temp_dir / "single-price.txt",
        "cta": temp_dir / "single-cta.txt",
        "badge": temp_dir / "single-badge.txt",
        "brand": temp_dir / "single-brand.txt",
    }

    files["hook"].write_text(wrap(hook, 24), encoding="utf-8")
    files["name"].write_text(wrap(product_name, 24), encoding="utf-8")
    files["price"].write_text(price_label, encoding="utf-8")
    files["cta"].write_text(wrap(cta, 30), encoding="utf-8")
    files["badge"].write_text("SINGLE PRODUCT ADS", encoding="utf-8")
    files["brand"].write_text("spacecraft.id", encoding="utf-8")

    hook_size = 31 if width <= 720 else 42
    name_size = 25 if width <= 720 else 34
    price_size = 32 if width <= 720 else 44
    cta_size = 24 if width <= 720 else 32
    badge_size = 14 if width <= 720 else 18
    brand_size = 15 if width <= 720 else 20

    final_start = max(
        0.0,
        float(duration) - 5.5,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    video_filter = ",".join([
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        "setsar=1",
        "fps=30",
        "format=yuv420p",
        "drawbox=x=iw*0.060:y=ih*0.075:w=iw*0.880:h=ih*0.185:color=black@0.36:t=fill:enable='between(t\\,0\\,5.8)'",
        "drawbox=x=iw*0.060:y=ih*0.075:w=iw*0.880:h=5:color=0x9EF0BD@0.95:t=fill:enable='between(t\\,0\\,5.8)'",
        "drawbox=x=iw*0.082:y=ih*0.098:w=iw*0.280:h=ih*0.034:color=0xFFD36A@0.95:t=fill:enable='between(t\\,0\\,5.8)'",
        f"drawtext=fontfile='{FONT_FILE}':textfile='{files['badge']}':expansion=none:fontcolor=black:fontsize={badge_size}:x=w*0.105:y=h*0.104:enable='between(t\\,0\\,5.8)'",
        f"drawtext=fontfile='{FONT_FILE}':textfile='{files['hook']}':expansion=none:fontcolor=white:bordercolor=black@0.68:borderw=2:fontsize={hook_size}:line_spacing=8:x=w*0.090:y=h*0.148:shadowcolor=black@0.70:shadowx=2:shadowy=2:enable='between(t\\,0\\,5.8)'",
        f"drawbox=x=iw*0.070:y=ih*0.650:w=iw*0.860:h=ih*0.195:color=black@0.46:t=fill:enable='between(t\\,3.0\\,{duration:.3f})'",
        f"drawbox=x=iw*0.070:y=ih*0.650:w=6:h=ih*0.195:color=0x9EF0BD@0.94:t=fill:enable='between(t\\,3.0\\,{duration:.3f})'",
        f"drawtext=fontfile='{FONT_FILE}':textfile='{files['name']}':expansion=none:fontcolor=white:bordercolor=black@0.65:borderw=2:fontsize={name_size}:line_spacing=7:x=w*0.105:y=h*0.675:shadowcolor=black@0.70:shadowx=2:shadowy=2:enable='between(t\\,3.0\\,{duration:.3f})'",
        f"drawtext=fontfile='{FONT_FILE}':textfile='{files['price']}':expansion=none:fontcolor=0xFFD36A:bordercolor=black@0.70:borderw=2:fontsize={price_size}:x=w*0.105:y=h*0.765:shadowcolor=black@0.74:shadowx=2:shadowy=2:enable='between(t\\,3.0\\,{duration:.3f})'",
        f"drawbox=x=iw*0.060:y=ih*0.505:w=iw*0.880:h=ih*0.280:color=black@0.50:t=fill:enable='between(t\\,{final_start:.3f}\\,{duration:.3f})'",
        f"drawbox=x=iw*0.060:y=ih*0.505:w=iw*0.880:h=5:color=0xFFD36A@0.95:t=fill:enable='between(t\\,{final_start:.3f}\\,{duration:.3f})'",
        f"drawtext=fontfile='{FONT_FILE}':textfile='{files['cta']}':expansion=none:fontcolor=0x9EF0BD:bordercolor=black@0.70:borderw=2:fontsize={cta_size}:line_spacing=8:x=(w-text_w)/2:y=h*0.585:shadowcolor=black@0.72:shadowx=2:shadowy=2:enable='between(t\\,{final_start:.3f}\\,{duration:.3f})'",
        f"drawtext=fontfile='{FONT_FILE}':textfile='{files['brand']}':expansion=none:fontcolor=white@0.82:bordercolor=black@0.55:borderw=1:fontsize={brand_size}:x=(w-text_w)/2:y=h*0.725:enable='between(t\\,{final_start:.3f}\\,{duration:.3f})'",
    ])

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
                preserve_natural_duration=True,
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
        "21",
        "-pix_fmt",
        "yuv420p",
    ])

    if voiceover_path:
        command.extend([
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-shortest",
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
            "Overlay single product gagal: "
            + result.stderr[-3000:]
        )

    if (
        not output_path.is_file()
        or output_path.stat().st_size < 10_000
    ):
        raise RuntimeError(
            "Output single product video tidak valid"
        )


def render_single_product_video(
    config: dict[str, Any],
    output_path: Path,
    temp_dir: Path,
    voiceover_path: Path | None = None,
) -> None:
    raw_clip = config.get("raw_clip") or {}
    archive = str(raw_clip.get("archive") or "").strip()

    if not archive:
        raise RuntimeError(
            "Raw video single product belum dipilih"
        )

    raw_path = STORAGE_ROOT / archive

    try:
        raw_path.resolve().relative_to(
            STORAGE_ROOT.resolve()
        )
    except ValueError:
        raise RuntimeError(
            "Raw video berada di luar storage"
        )

    if (
        not raw_path.is_file()
        or raw_path.stat().st_size < 10_000
    ):
        raise RuntimeError(
            "Raw video tidak ditemukan: " + archive
        )

    image_items = [
        item
        for item in (config.get("image_sources") or [])
        if isinstance(item, dict)
    ][:4]

    duration = int(
        config.get("duration_seconds", 20)
    )

    segment_count = max(
        1,
        1 + len(image_items),
    )
    segment_duration = max(
        2.5,
        float(duration) / segment_count,
    )

    segments: list[Path] = []

    raw_segment = temp_dir / "single-product-001-raw.mp4"
    render_raw_catalog_segment(
        input_path=raw_path,
        output_path=raw_segment,
        aspect_ratio=config.get("aspect_ratio", "9:16"),
        duration=segment_duration,
        trim_start=float(raw_clip.get("trim_start") or 0.0),
        trim_end=(
            float(raw_clip["trim_end"])
            if raw_clip.get("trim_end") is not None
            else None
        ),
        fit_mode=str(raw_clip.get("fit_mode") or "cover"),
    )
    segments.append(raw_segment)

    for index, source in enumerate(image_items, start=2):
        image_segment = (
            temp_dir
            / f"single-product-{index:03d}-image.mp4"
        )
        render_photo_segment(
            source=source,
            output_path=image_segment,
            temp_dir=temp_dir,
            aspect_ratio=config.get("aspect_ratio", "9:16"),
            duration=segment_duration,
            motion="slow_zoom",
            fit_mode="cover",
        )
        segments.append(image_segment)

    base_video = temp_dir / "single-product-base.mp4"
    crossfade_video_segments(
        segments=segments,
        output_path=base_video,
        segment_duration=segment_duration,
        transition_duration=0.26,
    )

    overlay_single_product_video(
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

    def run_command(
        command: list[str],
        timeout: int = 1200,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    # --------------------------------------------------------
    # Percobaan utama: xfade dengan CFR dan timebase eksplisit
    # --------------------------------------------------------
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
            "fps=30,"
            "settb=expr=1/30,"
            "setpts=N,"
            "format=yuv420p,"
            "setsar=1"
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
        "-vsync",
        "cfr",
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

    result = run_command(command)

    if (
        result.returncode == 0
        and output_path.is_file()
        and output_path.stat().st_size >= 10_000
    ):
        return

    xfade_error = result.stderr[-5000:]

    # Bersihkan output kosong dari percobaan xfade.
    try:
        output_path.unlink(missing_ok=True)
    except OSError:
        pass

    # --------------------------------------------------------
    # Fallback aman: concat CFR tanpa transisi.
    #
    # Ini sengaja digunakan agar render tetap selesai jika
    # build FFmpeg tidak kompatibel dengan filter xfade.
    # --------------------------------------------------------
    concat_command = [
        "ffmpeg",
        "-y",
    ]

    for segment in segments:
        concat_command.extend([
            "-i",
            str(segment),
        ])

    concat_filters: list[str] = []

    for index in range(len(segments)):
        concat_filters.append(
            f"[{index}:v]"
            "fps=30,"
            "settb=expr=1/30,"
            "setpts=N,"
            "format=yuv420p,"
            "setsar=1"
            f"[c{index}]"
        )

    concat_inputs = "".join(
        f"[c{index}]"
        for index in range(len(segments))
    )

    concat_filters.append(
        f"{concat_inputs}"
        f"concat=n={len(segments)}:"
        "v=1:a=0"
        "[concatout]"
    )

    concat_command.extend([
        "-filter_complex",
        ";".join(concat_filters),
        "-map",
        "[concatout]",
        "-an",
        "-vsync",
        "cfr",
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

    concat_result = run_command(
        concat_command
    )

    if concat_result.returncode != 0:
        raise RuntimeError(
            "Xfade gagal:\n"
            f"{xfade_error}\n\n"
            "Concat fallback juga gagal:\n"
            f"{concat_result.stderr[-5000:]}"
        )

    if (
        not output_path.is_file()
        or output_path.stat().st_size < 10_000
    ):
        raise RuntimeError(
            "Output concat fallback tidak valid.\n"
            f"Xfade error:\n{xfade_error}\n\n"
            f"Concat error:\n"
            f"{concat_result.stderr[-3000:]}"
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

    if config.get("render_mode") == "single_product":
        render_single_product_video(
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

        # B18D_RENDER_DURATION_GUARD
        if voiceover_path is not None and str(job.config.get('render_mode') or '') == 'raw_catalog':
            actual_voice_seconds = media_duration_seconds(voiceover_path)
            max_voice_seconds = voiceover_max_seconds(int(job.config.get('duration_seconds') or 25))
            if actual_voice_seconds is None:
                raise RuntimeError('Durasi voice-over tidak dapat dibaca')
            preflight = {
                'actual_duration_seconds': round(float(actual_voice_seconds), 3),
                'max_voiceover_seconds': max_voice_seconds,
                'closing_reserved_seconds': B18D_CLOSING_RESERVED_SECONDS,
                'fits_timeline': bool(actual_voice_seconds <= max_voice_seconds + 0.05),
            }
            updated_config = dict(job.config or {})
            updated_config['voiceover_preflight'] = preflight
            job.config = updated_config
            db.commit()
            if not preflight['fits_timeline']:
                over_by = round(float(actual_voice_seconds) - max_voice_seconds, 2)
                raise RuntimeError(
                    'Voice-over terlalu panjang: '
                    f'{actual_voice_seconds:.2f} detik, slot maksimum {max_voice_seconds:.2f} detik '
                    'karena 5 detik terakhir dicadangkan untuk closing. '
                    f'Ringkas sekitar {over_by:.2f} detik atau perpanjang durasi video.'
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


# B18C_OPENAI_COPY_BACKEND_START
def b18c_extract_output_text(response_data: dict[str, Any]) -> str:
    for item in response_data.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if (
                isinstance(content, dict)
                and content.get("type") == "output_text"
                and content.get("text")
            ):
                return str(content["text"]).strip()
    return ""


def b18c_clean_copy_options(
    values: Any,
    *,
    max_words: int,
    max_chars: int,
    label: str,
    expected_count: int,
) -> list[str]:
    cleaned: list[str] = []

    for raw in values if isinstance(values, list) else []:
        value = re.sub(r"\s+", " ", str(raw or "")).strip()
        value = value.strip('"“”\'`-• ')
        value = re.sub(r"[.!?]+$", "", value).strip()

        if not value:
            continue

        if len(value.split()) > max_words:
            continue

        if len(value) > max_chars:
            continue

        if value.casefold() not in {item.casefold() for item in cleaned}:
            cleaned.append(value)

    if len(cleaned) != expected_count:
        raise RuntimeError(
            f"OpenAI menghasilkan {len(cleaned)} {label}; "
            f"seharusnya {expected_count}."
        )

    return cleaned


def b18c_openai_copy_request(
    *,
    product_names: list[str],
    payload: AICopyGenerateRequest,
) -> dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY belum dikonfigurasi")

    hook_count = 0 if payload.mode == "cta" else 3
    cta_count = 0 if payload.mode == "hook" else 3

    promo_context = "Promo tidak aktif."
    if payload.promo_enabled:
        promo_parts: list[str] = []
        if payload.promo_text:
            promo_parts.append(f'Teks promo exact: "{payload.promo_text.strip()}"')
        if payload.promo_min_amount > 0:
            promo_parts.append(
                "Minimum belanja exact: "
                + format_rupiah(payload.promo_min_amount)
            )
        promo_parts.append(
            f"Diskon exact: {payload.promo_discount_percent}%"
        )
        promo_context = "; ".join(promo_parts)

    system_prompt = (
        "Kamu adalah copywriter direct-response berbahasa Indonesia untuk "
        "iklan video pendek SpaceCraft. Buat copy natural, ringkas, kuat, "
        "dan tidak berlebihan. Jangan menerjemahkan atau mengubah nama produk. "
        "Jangan mengarang promo, harga, stok terbatas, urgensi palsu, jaminan, "
        "klaim kesehatan, atau klaim yang tidak diberikan. Hook maksimal 12 kata. "
        "CTA maksimal 10 kata. Jangan pakai emoji, tanda kutip, hashtag, atau "
        "akhiran titik. Setiap opsi harus berbeda secara nyata."
    )

    user_prompt = "\n".join([
        f"Mode: {payload.mode}",
        "Produk exact: " + " | ".join(product_names),
        f"Audience: {payload.audience}",
        f"Template: {payload.creative_template}",
        f"Format: {payload.aspect_ratio}",
        f"Durasi video: {payload.duration_seconds} detik",
        promo_context,
        f"Hook saat ini: {(payload.current_hook or '-').strip()}",
        f"CTA saat ini: {(payload.current_cta or '-').strip()}",
        f"Hasilkan tepat {hook_count} hook dan tepat {cta_count} CTA.",
        "Nama produk tidak wajib disebut. Jika promo disebut, nilainya harus persis.",
    ])

    schema = {
        "type": "object",
        "properties": {
            "hooks": {
                "type": "array",
                "minItems": hook_count,
                "maxItems": hook_count,
                "items": {
                    "type": "string",
                    "minLength": 3,
                    "maxLength": 180,
                },
            },
            "ctas": {
                "type": "array",
                "minItems": cta_count,
                "maxItems": cta_count,
                "items": {
                    "type": "string",
                    "minLength": 3,
                    "maxLength": 140,
                },
            },
        },
        "required": ["hooks", "ctas"],
        "additionalProperties": False,
    }

    request_body = {
        "model": OPENAI_COPY_MODEL,
        "store": False,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "spacecraft_hook_cta_options",
                "description": "Tiga opsi hook dan CTA iklan yang tervalidasi.",
                "strict": True,
                "schema": schema,
            },
            "verbosity": "low",
        },
        "max_output_tokens": 500,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{OPENAI_BASE_URL}/responses",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"OpenAI tidak dapat dihubungi: {exc}") from exc

    if response.status_code >= 400:
        detail = ""
        try:
            body = response.json()
            detail = str(
                (body.get("error") or {}).get("message")
                or body.get("detail")
                or ""
            )
        except Exception:
            detail = response.text[:500]
        raise RuntimeError(
            f"OpenAI HTTP {response.status_code}: "
            f"{detail or 'request gagal'}"
        )

    data = response.json()
    output_text = b18c_extract_output_text(data)
    if not output_text:
        raise RuntimeError("OpenAI tidak mengembalikan output_text")

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Output OpenAI bukan JSON valid") from exc

    hooks = b18c_clean_copy_options(
        parsed.get("hooks"),
        max_words=12,
        max_chars=180,
        label="hook",
        expected_count=hook_count,
    )
    ctas = b18c_clean_copy_options(
        parsed.get("ctas"),
        max_words=10,
        max_chars=140,
        label="CTA",
        expected_count=cta_count,
    )

    return {
        "hooks": hooks,
        "ctas": ctas,
        "model": str(data.get("model") or OPENAI_COPY_MODEL),
        "response_id": data.get("id"),
    }


@router.get("/api/ai-copy/status")
def ai_copy_status():
    return {
        "ok": True,
        "provider": "openai",
        "configured": bool(OPENAI_API_KEY),
        "model": OPENAI_COPY_MODEL,
        "max_hook_words": 12,
        "max_cta_words": 10,
        "options_per_type": 3,
    }


@router.post("/api/ai-copy/generate")
def generate_ai_hook_cta(
    payload: AICopyGenerateRequest,
    db: Session = Depends(get_db),
):
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "OPENAI_API_KEY belum dikonfigurasi pada server. "
                "Tambahkan key ke /opt/product-ads-studio/.env lalu restart app."
            ),
        )

    products = list(
        db.scalars(
            select(Product).where(
                Product.id.in_(
                    payload.product_ids
                ),
                ads_published_product_condition(),
            )
        ).all()
    )
    by_id = {item.id: item for item in products}
    missing = [item for item in payload.product_ids if item not in by_id]

    if missing:
        raise HTTPException(
            status_code=404,
            detail="Produk tidak ditemukan: " + ", ".join(map(str, missing)),
        )

    ordered_names = [by_id[item].name for item in payload.product_ids]

    try:
        result = b18c_openai_copy_request(
            product_names=ordered_names,
            payload=payload,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "ok": True,
        "mode": payload.mode,
        "product_names": ordered_names,
        **result,
    }
# B18C_OPENAI_COPY_BACKEND_END


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


# VOICE_DRAFT_ROUTES_V1
@router.post('/api/voiceover/draft')
def voiceover_draft(payload: VoiceDraftRequest, db: Session = Depends(get_db)):
    product_ids = list(dict.fromkeys(int(item) for item in payload.product_ids if int(item) > 0))
    products = list(db.scalars(select(Product).where(
                Product.id.in_(product_ids),
                ads_published_product_condition(),
            )).all())
    products_by_id = {item.id: item for item in products}
    missing = [item for item in product_ids if item not in products_by_id]
    if missing:
        raise HTTPException(status_code=404, detail='Produk tidak ditemukan: ' + ', '.join(str(item) for item in missing))
    ordered_products = [products_by_id[item] for item in product_ids]
    aliases = [compact_voice_product_alias(item.name) for item in ordered_products]
    protected_terms = list(dict.fromkeys([item.name for item in ordered_products] + aliases))
    draft_text = build_catalog_voiceover_draft(
        products=ordered_products,
        audience=payload.audience,
        duration_seconds=payload.duration_seconds,
        promo_enabled=payload.promo_enabled,
        promo_min_amount=payload.promo_min_amount,
        promo_discount_percent=payload.promo_discount_percent,
        promo_text=payload.promo_text,
        compact=(payload.draft_style == 'compact'),
    )
    estimated_seconds = round(max(1, len(draft_text.split())) / 2.35, 1)
    max_seconds = voiceover_max_seconds(payload.duration_seconds)
    fits_timeline = estimated_seconds <= max_seconds
    over_by = round(max(0.0, estimated_seconds - max_seconds), 1)
    warning = None if fits_timeline else (
        'Draft diperkirakan terlalu panjang: '
        f'{estimated_seconds} detik, slot VO {max_seconds} detik. '
        'Klik Ringkas Otomatis atau perpanjang durasi sebelum preview.'
    )
    return {
        'ok': True,
        'draft_text': draft_text,
        'tts_text': draft_text,
        'draft_style': payload.draft_style,
        'protected_terms': protected_terms,
        'voice_aliases': aliases,
        'estimated_seconds': estimated_seconds,
        'target_duration_seconds': payload.duration_seconds,
        'closing_reserved_seconds': B18D_CLOSING_RESERVED_SECONDS,
        'timeline_buffer_seconds': B18D_TIMELINE_BUFFER_SECONDS,
        'max_voiceover_seconds': max_seconds,
        'fits_timeline': fits_timeline,
        'over_by_seconds': over_by,
        'warning': warning,
    }

@router.post("/api/voiceover/normalize")
def voiceover_normalize(
    payload: VoiceNormalizeRequest,
):
    normalized = normalize_tts_text_indonesian(
        payload.text,
        payload.protected_terms,
    )

    return {
        "ok": True,
        "normalized_text": normalized,
        "protected_terms": payload.protected_terms,
    }


@router.post("/api/voiceover/preview")
def voiceover_preview(payload: VoicePreviewRequest):
    asset_id = uuid.uuid4().hex
    preview_dir = STORAGE_ROOT / B18G_PREVIEW_VOICE_DIR
    destination = preview_dir / f"preview-{asset_id}.mp3"
    metadata_path = preview_dir / f"preview-{asset_id}.json"
    try:
        normalized_text = normalize_tts_text_indonesian(payload.text, payload.protected_terms)
        generate_elevenlabs_audio(
            voice_id=payload.voice_id,
            text=normalized_text,
            destination=destination,
        )
        actual_duration = media_duration_seconds(destination)
        if actual_duration is None:
            raise RuntimeError("Durasi preview ElevenLabs tidak dapat dibaca")
        fingerprint = voice_asset_fingerprint(payload.voice_id, normalized_text)
        metadata = {
            "asset_id": asset_id,
            "fingerprint": fingerprint,
            "approved": False,
            "voice_id": payload.voice_id,
            "normalized_text": normalized_text,
            "model_id": ELEVENLABS_MODEL_ID,
            "language_code": ELEVENLABS_LANGUAGE_CODE,
            "output_format": ELEVENLABS_OUTPUT_FORMAT,
            "speed": B18G_VOICE_SPEED,
            "duration_seconds": round(float(actual_duration), 3),
            "created_at": now().isoformat(),
        }
        write_voice_metadata(metadata_path, metadata)
    except Exception as error:
        destination.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        raise HTTPException(status_code=502, detail=str(error)) from error
    max_seconds = voiceover_max_seconds(
        payload.target_duration_seconds,
        payload.closing_reserved_seconds,
    )
    actual_duration = round(float(actual_duration), 3)
    fits_timeline = actual_duration <= max_seconds
    over_by = round(max(0.0, actual_duration - max_seconds), 3)
    return {
        "ok": True,
        "preview_asset_id": asset_id,
        "fingerprint": fingerprint,
        "audio_url": f"/media/{B18G_PREVIEW_VOICE_DIR}/preview-{asset_id}.mp3",
        "normalized_text": normalized_text,
        "actual_duration_seconds": actual_duration,
        "target_duration_seconds": payload.target_duration_seconds,
        "closing_reserved_seconds": payload.closing_reserved_seconds,
        "timeline_buffer_seconds": B18D_TIMELINE_BUFFER_SECONDS,
        "max_voiceover_seconds": max_seconds,
        "fits_timeline": fits_timeline,
        "over_by_seconds": over_by,
        "voice_id": payload.voice_id,
        "model_id": ELEVENLABS_MODEL_ID,
        "language_code": ELEVENLABS_LANGUAGE_CODE,
        "output_format": ELEVENLABS_OUTPUT_FORMAT,
        "speed": B18G_VOICE_SPEED,
        "warning": None if fits_timeline else (
            "Voice-over terlalu panjang "
            f"{over_by:.2f} detik. Ringkas draft atau perpanjang durasi video."
        ),
    }


@router.post("/api/voiceover/fit")
def voiceover_fit(
    payload: VoiceFitRequest,
):
    try:
        result = fit_voice_preview_asset(
            asset_id=payload.preview_asset_id,
            voice_id=payload.voice_id,
            text=payload.text,
            protected_terms=payload.protected_terms,
            target_duration_seconds=payload.target_duration_seconds,
            closing_reserved_seconds=payload.closing_reserved_seconds,
        )
    except Exception as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    return {
        "ok": True,
        **result,
        "max_over_seconds": B18H_MAX_OVER_SECONDS,
        "max_speed_multiplier": B18H_MAX_SPEED_MULTIPLIER,
    }


@router.post("/api/voiceover/approve")
def voiceover_approve(payload: VoiceApproveRequest):
    asset_id = validate_voice_asset_id(payload.preview_asset_id)
    preview_audio = voice_preview_audio_path(asset_id)
    preview_metadata_path = voice_preview_metadata_path(asset_id)
    if not preview_audio.is_file() or preview_audio.stat().st_size < 1000:
        raise HTTPException(
            status_code=404,
            detail="Preview voice tidak ditemukan. Buat preview ulang.",
        )
    try:
        preview_metadata = read_voice_metadata(preview_metadata_path)
        normalized_text = normalize_tts_text_indonesian(payload.text, payload.protected_terms)
        expected_fingerprint = voice_asset_fingerprint(payload.voice_id, normalized_text)
        if expected_fingerprint != payload.fingerprint:
            raise RuntimeError("Fingerprint preview berubah. Preview ulang sebelum approve.")
        if str(preview_metadata.get("fingerprint") or "") != expected_fingerprint:
            raise RuntimeError("Metadata preview tidak cocok")
        if str(preview_metadata.get("voice_id") or "") != payload.voice_id:
            raise RuntimeError("Voice ID preview berubah")
        if str(preview_metadata.get("normalized_text") or "") != normalized_text:
            raise RuntimeError("Teks preview berubah")
        actual_duration = media_duration_seconds(preview_audio)
        if actual_duration is None:
            raise RuntimeError("Durasi preview tidak dapat dibaca")
        approved_audio = approved_voice_audio_path(asset_id)
        approved_metadata_path = approved_voice_metadata_path(asset_id)
        approved_audio.parent.mkdir(parents=True, exist_ok=True)
        temporary_audio = approved_audio.with_suffix(".mp3.tmp")
        shutil.copy2(preview_audio, temporary_audio)
        temporary_audio.replace(approved_audio)
        approved_metadata = {
            **preview_metadata,
            "approved": True,
            "approved_at": now().isoformat(),
            "duration_seconds": round(float(actual_duration), 3),
        }
        write_voice_metadata(approved_metadata_path, approved_metadata)
        approved = resolve_approved_voice_asset(
            asset_id=asset_id,
            expected_fingerprint=expected_fingerprint,
            expected_voice_id=payload.voice_id,
            expected_text=normalized_text,
        )
    except Exception as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "ok": True,
        "approved_asset_id": asset_id,
        "fingerprint": expected_fingerprint,
        "audio_url": f"/media/{B18G_APPROVED_VOICE_DIR}/approved-{asset_id}.mp3",
        "normalized_text": normalized_text,
        "duration_seconds": approved["duration_seconds"],
        "voice_id": payload.voice_id,
        "model_id": ELEVENLABS_MODEL_ID,
        "language_code": ELEVENLABS_LANGUAGE_CODE,
        "output_format": ELEVENLABS_OUTPUT_FORMAT,
        "speed": B18G_VOICE_SPEED,
        "reusable_for_render": True,
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
                "asset_type": "video",
                "media_type": "video",
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

    image_assets = list(
        db.scalars(
            select(ProductAsset)
            .where(
                ProductAsset.product_id == product_id,
                ProductAsset.asset_type == "image",
            )
            .order_by(
                ProductAsset.created_at.desc(),
                ProductAsset.id.desc(),
            )
        ).all()
    )

    for asset in image_assets:
        absolute_path = (
            STORAGE_ROOT
            / asset.relative_path
        )

        if (
            not absolute_path.is_file()
            or absolute_path.stat().st_size < 100
        ):
            continue

        raw_videos.append(
            {
                "clip_id": f"asset-{asset.id}",
                "asset_id": asset.id,
                "asset_type": "image",
                "media_type": "image",
                "product_id": asset.product_id,
                "label": asset.original_name,
                "title": asset.original_name,
                "archive": asset.relative_path,
                "url": f"/media/{asset.relative_path}",
                "mime_type": asset.mime_type,
                "size_bytes": asset.size_bytes,
                "source": asset.source,
                "video_type": "lifestyle",
                "fit_mode": "cover",
                "is_primary": False,
                "trim_start": 0.0,
                "trim_end": None,
                "duration_seconds": None,
                "width": None,
                "height": None,
                "fps": 30,
                "orientation": None,
                "has_audio": False,
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
            0 if item.get("media_type") == "image" else 1,
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
        variations=effective_variations,
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
    db.flush()

    # B19C_ASSIGN_CAMPAIGN_ID
    b19c_creative_set.campaign_id = (
        campaign.id
    )

    b19c_creative_set.status = (
        "rendering"
        if b19c_creative_set.source_type
        == "spacecraft"
        else "internal_render"
    )

    b19c_creative_set.updated_at = now()

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


def build_unique_random_product_orders(
    product_ids: list[int],
    variations: int,
    *,
    random_source: random.Random | random.SystemRandom | None = None,
) -> list[list[int]]:
    source = random_source or random.SystemRandom()
    orders: list[list[int]] = []
    seen_orders: set[tuple[int, ...]] = set()

    for _ in range(variations):
        candidate = list(product_ids)
        source.shuffle(candidate)

        while tuple(candidate) in seen_orders:
            source.shuffle(candidate)

        seen_orders.add(tuple(candidate))
        orders.append(candidate)

    return orders


def raw_catalog_should_auto_randomize_orders(
    recipes: list[RawCatalogVariantRecipe],
    selected_product_ids: list[int],
) -> bool:
    if not recipes:
        return True

    base_order = tuple(selected_product_ids)
    recipe_orders = [
        tuple(recipe.product_order or [])
        for recipe in recipes
    ]

    if not recipe_orders:
        return True

    # The UI can generate a matrix where every variant carries ORDER-A.
    # In that case the campaign is still "auto generate variations", so
    # the backend should create a fresh clip order for each rendered video.
    return all(order == base_order for order in recipe_orders)


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

    # B18G_CAMPAIGN_APPROVED_VOICE_VALIDATE
    approved_voice_master: dict[str, Any] | None = None

    if payload.voiceover_enabled:
        if (
            not payload.approved_voice_asset_id
            or not payload.approved_voice_fingerprint
            or payload.approved_voice_duration_seconds is None
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Preview voice yang sudah di-approve wajib tersedia. "
                    "Preview dan Approve Draft ulang."
                ),
            )
        try:
            approved_voice_master = resolve_approved_voice_asset(
                asset_id=payload.approved_voice_asset_id,
                expected_fingerprint=payload.approved_voice_fingerprint,
                expected_voice_id=payload.voice_id,
            )
        except Exception as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if abs(
            float(approved_voice_master["duration_seconds"])
            - float(payload.approved_voice_duration_seconds)
        ) > 0.25:
            raise HTTPException(
                status_code=422,
                detail="Durasi approved voice berubah. Preview dan approve ulang.",
            )

    selected_product_ids = [
        item.product_id
        for item in payload.product_clips
    ]

    active_variant_recipes = [
        recipe
        for recipe in payload.variant_recipes
        if recipe.enabled
    ]

    if len(active_variant_recipes) > 24:
        raise HTTPException(
            status_code=422,
            detail=(
                "Maksimal 24 kombinasi variant "
                "dalam satu campaign."
            ),
        )

    for recipe_index, recipe in enumerate(
        active_variant_recipes,
        start=1,
    ):
        if recipe.product_order is None:
            continue

        if (
            len(recipe.product_order)
            != len(selected_product_ids)
            or set(recipe.product_order)
            != set(selected_product_ids)
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Product order recipe "
                    f"{recipe_index} tidak valid."
                ),
            )

    effective_variations = (
        len(active_variant_recipes)
        if active_variant_recipes
        else payload.variations
    )


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

    # B19A_LINKED_CATALOG_RENDER_GUARD
    b19a_linked_catalog = (
        b19a_validate_linked_catalog(
            payload,
            selected_product_ids,
            db,
        )
    )

    # B19B_RENDER_READINESS_GUARD
    b19b_readiness = (
        b19b_validate_catalog_readiness(
            payload,
            db,
        )
    )

    # B19C_CREATIVE_SET_RENDER_GUARD
    b19c_creative_set = (
        b19c_validate_for_render(
            payload,
            selected_product_ids,
            db,
        )
    )

    products = list(
        db.scalars(
            select(Product).where(
                Product.id.in_(
                    selected_product_ids
                ),
                ads_published_product_condition(),
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
    price_overrides = (
        b19a_linked_catalog.get(
            "price_overrides",
            {},
        )
        if b19a_linked_catalog
        else {}
    )

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
                and asset.asset_type in {
                    "video",
                    "image",
                }
            ):
                absolute_media_path = (
                    STORAGE_ROOT
                    / asset.relative_path
                )

                if (
                    absolute_media_path.is_file()
                    and asset.asset_type == "image"
                ):
                    clip = {
                        "clip_id": clip_id,
                        "asset_id": asset.id,
                        "asset_type": "image",
                        "media_type": "image",
                        "archive": asset.relative_path,
                        "label": asset.original_name,
                        "source": (
                            asset.source or "uploaded"
                        ),
                        "mime_type": asset.mime_type,
                        "trim_start": 0.0,
                        "trim_end": None,
                        "video_type": "lifestyle",
                        "fit_mode": (
                            selection.fit_mode
                            if selection.fit_mode
                            in {
                                "contain",
                                "cover",
                                "blur_fill",
                            }
                            else "cover"
                        ),
                        "requested_fit_mode": (
                            selection.fit_mode
                            or "cover"
                        ),
                        "source_orientation": None,
                        "source_width": None,
                        "source_height": None,
                        "source_duration_seconds": None,
                    }

                elif absolute_media_path.is_file():
                    source_metadata = (
                        probe_uploaded_raw_video(
                            absolute_media_path
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
                        "asset_type": "video",
                        "media_type": "video",
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
                    "Asset kreatif tidak ditemukan untuk "
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
        price_override = price_overrides.get(
            product.id
        )
        if (
            price_override
            and price_override.get(
                "price_label"
            )
        ):
            clip["product_price_label"] = (
                price_override[
                    "price_label"
                ]
            )
            clip["product_price_value"] = (
                price_override.get("price")
            )
            clip["pricing_layer"] = (
                price_override.get(
                    "pricing_layer"
                )
            )
        elif product.price_value is not None:
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

    layout_snapshot = (
        build_raw_catalog_layout_snapshot(
            raw_clips,
            payload.aspect_ratio,
        )
    )

    # B18I_ACQUIRE_SINGLE_SUBMISSION
    (
        request_fingerprint,
        idempotency_key,
        idempotency_client,
        existing_response,
    ) = acquire_raw_catalog_submission(
        payload,
        db,
    )

    if existing_response is not None:
        return existing_response

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
        variations=effective_variations,
        settings={
            **payload.model_dump(),
            "render_mode": "raw_catalog",
            # B19A_CAMPAIGN_CATALOG_SNAPSHOT
            "catalog_source":
                payload.catalog_source,
            "catalog_code": (
                b19a_linked_catalog[
                    "catalog_code"
                ]
                if b19a_linked_catalog
                else None
            ),
            "catalog_hash": (
                b19a_linked_catalog[
                    "catalog_hash"
                ]
                if b19a_linked_catalog
                else None
            ),
            "catalog_name": (
                b19a_linked_catalog[
                    "catalog_name"
                ]
                if b19a_linked_catalog
                else None
            ),
            "catalog_type": (
                b19a_linked_catalog[
                    "catalog_type"
                ]
                if b19a_linked_catalog
                else None
            ),
            "catalog_flow_type": (
                b19a_linked_catalog[
                    "flow_type"
                ]
                if b19a_linked_catalog
                else None
            ),
            "catalog_go_url": (
                b19a_linked_catalog[
                    "go_url"
                ]
                if b19a_linked_catalog
                else None
            ),
            "source_code": (
                b19a_linked_catalog[
                    "source_code"
                ]
                if b19a_linked_catalog
                else None
            ),
            "pricing_source": (
                b19a_linked_catalog[
                    "pricing_source"
                ]
                if b19a_linked_catalog
                else payload.pricing_source
            ),
            "pricing_source_code": (
                b19a_linked_catalog[
                    "pricing_source_code"
                ]
                if b19a_linked_catalog
                else None
            ),
            "pricing_layer": (
                b19a_linked_catalog[
                    "pricing_layer"
                ]
                if b19a_linked_catalog
                else None
            ),
            "commerce_product_ids": (
                b19a_linked_catalog[
                    "commerce_product_ids"
                ]
                if b19a_linked_catalog
                else None
            ),
            "creative_product_ids":
                selected_product_ids,
            "catalog_snapshot": (
                b19a_linked_catalog[
                    "snapshot"
                ]
                if b19a_linked_catalog
                else None
            ),
            # B19B_READINESS_SNAPSHOT
            "creative_readiness": (
                b19b_readiness
                if b19b_readiness
                else None
            ),
            # B19C_CAMPAIGN_CREATIVE_SET_LINK
            "creative_set_code": (
                b19c_creative_set
                .creative_set_code
            ),
            "creative_set_status": (
                b19c_creative_set.status
            ),
            "creative_set_source": (
                b19c_creative_set.source_type
            ),
            "creative_set_commerce_ready": (
                bool(
                    b19c_creative_set
                    .commerce_ready
                )
            ),
            "request_fingerprint": request_fingerprint,
            "idempotency_guard": "b18i",
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
            "auto_variant_generator": bool(
                active_variant_recipes
            ),
            "variant_recipe_count": len(
                active_variant_recipes
            ),
            "variant_recipes": [
                recipe.model_dump()
                for recipe
                in active_variant_recipes
            ],
        },
        created_at=now(),
        updated_at=now(),
    )

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    jobs: list[RenderJob] = []

    auto_randomize_orders = (
        raw_catalog_should_auto_randomize_orders(
            active_variant_recipes,
            selected_product_ids,
        )
    )

    auto_product_orders = (
        build_unique_random_product_orders(
            selected_product_ids,
            effective_variations,
        )
    )

    for index in range(effective_variations):
        recipe = (
            active_variant_recipes[index]
            if active_variant_recipes
            else None
        )

        if auto_randomize_orders:
            recipe_order = auto_product_orders[index]
        else:
            recipe_order = (
                recipe.product_order
                if (
                    recipe is not None
                    and recipe.product_order
                )
                else auto_product_orders[index]
            )

        recipe_products = [
            products_by_id[product_id]
            for product_id in recipe_order
        ]

        recipe_clips_by_product = {
            int(item["product_id"]): item
            for item in raw_clips
        }

        recipe_raw_clips = [
            recipe_clips_by_product[
                product_id
            ]
            for product_id in recipe_order
        ]

        recipe_layout_snapshot = (
            build_raw_catalog_layout_snapshot(
                recipe_raw_clips,
                payload.aspect_ratio,
            )
        )

        # B18C_RAW_COPY_SELECTION_START
        campaign_hook = (payload.hook or "").strip()
        campaign_cta = (payload.cta or "").strip()

        hook = (
            (recipe.hook or "").strip()
            if recipe is not None
            else ""
        ) or campaign_hook or hooks[index % len(hooks)]

        cta = (
            (recipe.cta or "").strip()
            if recipe is not None
            else ""
        ) or campaign_cta or ctas[index % len(ctas)]
        # B18C_RAW_COPY_SELECTION_END

        recipe_promo_label = (
            (recipe.promo_text or "").strip()
            if recipe is not None
            else ""
        ) or promo_label

        voiceover_script = None

        if payload.voiceover_enabled:
            voiceover_products = (
                recipe_products
                if recipe is not None
                else ordered_products
            )
            recipe_voiceover_text = (
                (recipe.voiceover_text or "").strip()
                if recipe is not None
                else ""
            )

            if recipe_voiceover_text:
                voiceover_script = (
                    recipe_voiceover_text
                )
            else:
                voiceover_script = build_voiceover_script(
                    product=recipe_products[0],
                    analysis=analyses.get(
                        recipe_products[0].id
                    ),
                    hook=hook,
                    cta=cta,
                    duration_seconds=payload.duration_seconds,
                    mode=payload.voiceover_mode,
                    custom_text=payload.voiceover_text,
                    audience=payload.audience,
                    min_order_qty=payload.min_order_qty,
                    products=voiceover_products,
                    analyses=analyses,
                )

            if (
                recipe_promo_label
                and payload.voiceover_mode == "auto"
                and not recipe_voiceover_text
            ):
                voiceover_script = (
                    f"{voiceover_script} "
                    f"{recipe_promo_label}."
                )

        # VOICE_DRAFT_RENDER_NORMALIZE_V1
        if payload.voiceover_enabled and voiceover_script:
            voiceover_script = normalize_tts_text_indonesian(
                voiceover_script,
                [
                    item.name
                    for item in voiceover_products
                ],
            )

        # B18G_VARIANT_FINGERPRINT_GUARD
        if payload.voiceover_enabled:
            if not approved_voice_master or not voiceover_script:
                raise HTTPException(
                    status_code=422,
                    detail="Approved voice master tidak tersedia",
                )
            expected_voice_fingerprint = voice_asset_fingerprint(
                voice_id=str(payload.voice_id or ""),
                text=voiceover_script,
            )
            if expected_voice_fingerprint != approved_voice_master["fingerprint"]:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Variant mengubah naskah voice-over yang sudah di-approve. "
                        "Hapus custom voice per variant atau preview ulang."
                    ),
                )

        config = {
            "render_mode": "raw_catalog",
            # B19A_JOB_CATALOG_CONTEXT
            "catalog_source":
                payload.catalog_source,
            "catalog_code": (
                b19a_linked_catalog[
                    "catalog_code"
                ]
                if b19a_linked_catalog
                else None
            ),
            "catalog_hash": (
                b19a_linked_catalog[
                    "catalog_hash"
                ]
                if b19a_linked_catalog
                else None
            ),
            "catalog_name": (
                b19a_linked_catalog[
                    "catalog_name"
                ]
                if b19a_linked_catalog
                else None
            ),
            "catalog_go_url": (
                b19a_linked_catalog[
                    "go_url"
                ]
                if b19a_linked_catalog
                else None
            ),
            "source_code": (
                b19a_linked_catalog[
                    "source_code"
                ]
                if b19a_linked_catalog
                else None
            ),
            "pricing_source": (
                b19a_linked_catalog[
                    "pricing_source"
                ]
                if b19a_linked_catalog
                else payload.pricing_source
            ),
            "pricing_source_code": (
                b19a_linked_catalog[
                    "pricing_source_code"
                ]
                if b19a_linked_catalog
                else None
            ),
            "pricing_layer": (
                b19a_linked_catalog[
                    "pricing_layer"
                ]
                if b19a_linked_catalog
                else None
            ),
            "commerce_product_ids": (
                b19a_linked_catalog[
                    "commerce_product_ids"
                ]
                if b19a_linked_catalog
                else None
            ),
            "creative_product_ids":
                recipe_order,
            # B19C_JOB_CREATIVE_SET_LINK
            "creative_set_code": (
                b19c_creative_set
                .creative_set_code
            ),
            "creative_set_status": (
                b19c_creative_set.status
            ),
            "creative_set_source": (
                b19c_creative_set.source_type
            ),
            "creative_set_commerce_ready": (
                bool(
                    b19c_creative_set
                    .commerce_ready
                )
            ),
            "creative_template": payload.creative_template,
            "creative_template_label": template_label,
            "product_name": product_collection_name(
                recipe_products
            ),
            "product_names": [
                item.name
                for item in recipe_products
            ],
            "product_ids": recipe_order,
            "product_count": len(recipe_products),
            "price_label": product_collection_price_label(
                recipe_products
            ),
            "hook": hook,
            "cta": cta,
            "audience": payload.audience,
            "min_order_qty": payload.min_order_qty,
            "duration_seconds": payload.duration_seconds,
            "aspect_ratio": payload.aspect_ratio,
            "raw_clips": recipe_raw_clips,
            "smart_visual_layout": True,
            "layout_snapshot": recipe_layout_snapshot,
            "safe_area": (
                recipe_layout_snapshot["safe_area"]
            ),
            "variant_recipe": (
                recipe.model_dump()
                if recipe is not None
                else {
                    "label": (
                        f"AUTO-{index + 1:02d}"
                    ),
                    "hook_code": (
                        f"HOOK-{index + 1:02d}"
                    ),
                    "cta_code": (
                        f"CTA-{index + 1:02d}"
                    ),
                    "promo_code": "PROMO-BASE",
                    "order_code": (
                        f"ORDER-RANDOM-{index + 1:02d}"
                    ),
                    "product_order": recipe_order,
                    "auto_randomized_order": True,
                    "voice_code": "VOICE-BASE",
                }
            ),
            "experiment_label": (
                recipe.label
                if recipe is not None
                else f"AUTO-{index + 1:02d}"
            ),
            "promo": {
                "enabled": bool(
                    payload.promo_enabled
                    and recipe_promo_label
                ),
                "min_amount": payload.promo_min_amount,
                "discount_percent": (
                    payload.promo_discount_percent
                ),
                "label": recipe_promo_label,
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
                "approved_asset_id": payload.approved_voice_asset_id,
                "approved_fingerprint": payload.approved_voice_fingerprint,
                "approved_duration_seconds": payload.approved_voice_duration_seconds,
                "reuse_approved_audio": bool(
                    payload.voiceover_enabled and payload.approved_voice_asset_id
                ),
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

    idempotency_client.set(
        idempotency_key,
        f"campaign:{campaign.id}",
        ex=RAW_CATALOG_IDEMPOTENCY_TTL_SECONDS,
    )

    return {
        "ok": True,
        "deduplicated": False,
        "request_fingerprint": request_fingerprint,
        "message": (
            f"{effective_variations} raw video catalog "
            "masuk antrean render"
        ),
        "campaign": campaign_to_dict(campaign),
    }


@router.post("/api/campaigns/single-product-video")
def create_single_product_video_campaign(
    payload: SingleProductVideoRequest,
    db: Session = Depends(get_db),
):
    product = db.get(
        Product,
        payload.product_id,
    )

    if (
        product is None
        or not str(product.status or "").strip().lower()
        == ADS_PUBLISHED_STATUS
    ):
        raise HTTPException(
            status_code=404,
            detail="Produk tidak ditemukan atau belum published",
        )

    assets = list(
        db.scalars(
            select(ProductAsset)
            .where(
                ProductAsset.product_id == product.id,
            )
            .order_by(
                ProductAsset.created_at.desc(),
                ProductAsset.id.desc(),
            )
        ).all()
    )

    video_assets = [
        asset
        for asset in assets
        if asset.asset_type == "video"
    ]

    if not video_assets:
        raise HTTPException(
            status_code=422,
            detail=(
                "Produk ini belum punya raw video. "
                "Upload minimal 1 raw video dulu."
            ),
        )

    raw_settings = load_raw_video_settings(
        product.id
    )

    selected_video = None
    requested_clip_id = str(
        payload.raw_clip_id or ""
    ).strip()

    if requested_clip_id.startswith("asset-"):
        try:
            requested_asset_id = int(
                requested_clip_id.removeprefix("asset-")
            )
        except ValueError:
            requested_asset_id = 0

        selected_video = next(
            (
                asset
                for asset in video_assets
                if asset.id == requested_asset_id
            ),
            None,
        )

    if selected_video is None:
        selected_video = next(
            (
                asset
                for asset in video_assets
                if bool(
                    raw_settings
                    .get(str(asset.id), {})
                    .get("is_primary")
                )
            ),
            video_assets[0],
        )

    absolute_video_path = (
        STORAGE_ROOT
        / selected_video.relative_path
    )

    if (
        not absolute_video_path.is_file()
        or absolute_video_path.stat().st_size < 10_000
    ):
        raise HTTPException(
            status_code=422,
            detail="File raw video produk tidak ditemukan",
        )

    selected_settings = raw_settings.get(
        str(selected_video.id),
        {},
    )

    source_metadata = probe_uploaded_raw_video(
        absolute_video_path
    )
    source_orientation = source_metadata.get(
        "orientation"
    )

    raw_clip = {
        "clip_id": f"asset-{selected_video.id}",
        "asset_id": selected_video.id,
        "archive": selected_video.relative_path,
        "label": selected_video.original_name,
        "source": "uploaded",
        "mime_type": selected_video.mime_type,
        "trim_start": float(
            selected_settings.get("trim_start")
            or 0.0
        ),
        "trim_end": (
            float(selected_settings["trim_end"])
            if selected_settings.get("trim_end")
            is not None
            else None
        ),
        "video_type": selected_settings.get(
            "video_type",
            "demo",
        ),
        "fit_mode": resolve_raw_catalog_fit_mode(
            str(
                selected_settings.get("fit_mode")
                or "auto"
            ),
            str(
                selected_settings.get("video_type")
                or "demo"
            ),
            source_orientation,
            payload.aspect_ratio,
        ),
        "source_orientation": source_orientation,
        "source_width": source_metadata.get("width"),
        "source_height": source_metadata.get("height"),
        "source_duration_seconds": (
            source_metadata.get("duration_seconds")
        ),
    }

    image_items = image_sources(
        product,
        assets,
    )[:payload.image_count]

    if not image_items:
        raise HTTPException(
            status_code=422,
            detail=(
                "Produk ini belum punya image referensi "
                "untuk single product campaign."
            ),
        )

    price_label = (
        format_rupiah(product.price_value)
        if product.price_value is not None
        else product.price_label
        or "Cek harga"
    )

    hook = (
        payload.hook
        or f"{product.name}, detailnya makin kelihatan"
    )
    cta = (
        payload.cta
        or "Klik dan pesan lewat WhatsApp"
    )

    analysis = db.scalar(
        select(ProductAnalysis).where(
            ProductAnalysis.product_id == product.id
        )
    )

    voiceover_script = None
    if payload.voiceover_enabled:
        voiceover_script = build_voiceover_script(
            product=product,
            analysis=analysis,
            hook=hook,
            cta=cta,
            duration_seconds=payload.duration_seconds,
            mode=payload.voiceover_mode,
            custom_text=payload.voiceover_text,
            audience="retail",
            min_order_qty=1,
        )

    campaign = CreativeCampaign(
        product_id=product.id,
        name=(
            payload.name
            or f"{product.name} Single Product Video"
        ),
        status="queued",
        variations=1,
        settings={
            **payload.model_dump(),
            "render_mode": "single_product",
            "product_id": product.id,
            "product_name": product.name,
            "product_ids": [product.id],
            "product_names": [product.name],
            "product_count": 1,
            "price_label": price_label,
            "raw_clip": raw_clip,
            "image_source_count": len(image_items),
            "voiceover": {
                "enabled": bool(
                    payload.voiceover_enabled
                    and payload.voice_id
                ),
                "voice_id": payload.voice_id,
                "mode": payload.voiceover_mode,
                "script": voiceover_script,
                "approved_asset_id": None,
                "approved_fingerprint": None,
            },
            "single_product_mvp": True,
        },
        created_at=now(),
        updated_at=now(),
    )

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    config = {
        "render_mode": "single_product",
        "product_id": product.id,
        "product_name": product.name,
        "product_ids": [product.id],
        "product_names": [product.name],
        "product_count": 1,
        "price_label": price_label,
        "hook": hook,
        "cta": cta,
        "duration_seconds": payload.duration_seconds,
        "aspect_ratio": payload.aspect_ratio,
        "raw_clip": raw_clip,
        "image_sources": image_items,
        "creative_template": "single_product",
        "creative_template_label": (
            "Single Product Campaign"
        ),
        "voiceover": {
            "enabled": bool(
                payload.voiceover_enabled
                and payload.voice_id
            ),
            "voice_id": payload.voice_id,
            "mode": payload.voiceover_mode,
            "script": voiceover_script,
            "approved_asset_id": None,
            "approved_fingerprint": None,
        },
        "voiceover_enabled": bool(
            payload.voiceover_enabled
            and payload.voice_id
        ),
        "audience": "retail",
        "min_order_qty": 1,
    }

    job = RenderJob(
        campaign_id=campaign.id,
        variation_index=1,
        status="queued",
        config=config,
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    queued = render_queue().enqueue(
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
            "Single product campaign masuk antrean render"
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








# B15 SPACECRAFT CATALOG SELECTOR
@router.get(
    "/api/wabot/catalogs"
)
def get_spacecraft_catalogs():
    if not SPACECRAFT_BASE_URL or not SPACECRAFT_WABOT_KEY:
        return {
            "ok": True,
            "configured": False,
            "catalogs": [],
            "count": 0,
            "message": (
                "SpaceCraft Catalog API belum dikonfigurasi"
            ),
        }

    endpoint = (
        f"{SPACECRAFT_BASE_URL}/api/wabot/catalogs"
    )

    try:
        response = httpx.get(
            endpoint,
            headers={
                "X-SpaceCraft-Wabot-Key":
                    SPACECRAFT_WABOT_KEY,
                "Accept": "application/json",
            },
            timeout=10,
            follow_redirects=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Gagal menjangkau SpaceCraft Catalog API: "
                f"{type(exc).__name__}"
            ),
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=(
                "SpaceCraft Catalog API mengembalikan HTTP "
                f"{response.status_code}"
            ),
        )

    try:
        payload = response.json()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Response SpaceCraft bukan JSON valid",
        ) from exc

    raw_catalogs = payload.get("catalogs") or []
    catalogs: list[dict[str, Any]] = []

    for item in raw_catalogs:
        if not isinstance(item, dict):
            continue

        code = wabot_normalize_code(
            item.get("catalog_id")
            or item.get("catalog_code")
            or item.get("code")
        )

        if not code:
            continue

        catalogs.append({
            "catalog_code": code,
            "catalog_id": code,
            "name": b11_clean_text(
                item.get("name")
                or item.get("headline")
                or code
            ),
            "catalog_type": item.get("catalog_type"),
            "flow_type": item.get("flow_type"),
            "source_code": item.get("source_code"),
            "campaign_name": item.get("campaign_name"),
            "products_count": int(
                item.get("products_count") or 0
            ),
            "go_url": item.get("go_url"),
        })

    return {
        "ok": True,
        "configured": True,
        "source": "spacecraft",
        "count": len(catalogs),
        "catalogs": catalogs,
        "synced_at": payload.get("synced_at"),
    }


# B16 ADS ATTRIBUTION BRIDGE
def b16_send_spacecraft_event(
    event_payload: dict[str, Any],
) -> dict[str, Any]:
    if (
        not SPACECRAFT_BASE_URL
        or not SPACECRAFT_WABOT_KEY
    ):
        return {
            "ok": False,
            "configured": False,
            "status_code": None,
            "message": (
                "SpaceCraft attribution endpoint "
                "belum dikonfigurasi"
            ),
        }

    endpoint = (
        f"{SPACECRAFT_BASE_URL}"
        "/api/wabot/events"
    )

    try:
        response = httpx.post(
            endpoint,
            headers={
                "X-SpaceCraft-Wabot-Key":
                    SPACECRAFT_WABOT_KEY,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=event_payload,
            timeout=10,
            follow_redirects=True,
        )
    except Exception as exc:
        return {
            "ok": False,
            "configured": True,
            "status_code": None,
            "message": (
                "SpaceCraft attribution tidak "
                "dapat dijangkau"
            ),
            "error": type(exc).__name__,
        }

    try:
        response_payload = response.json()
    except Exception:
        response_payload = {
            "raw": response.text[:500],
        }

    return {
        "ok": 200 <= response.status_code < 300,
        "configured": True,
        "status_code": response.status_code,
        "message": (
            "Attribution tersinkronisasi"
            if 200 <= response.status_code < 300
            else (
                "SpaceCraft mengembalikan HTTP "
                f"{response.status_code}"
            )
        ),
        "response": response_payload,
    }


# B17B LIVE FUNNEL DASHBOARD
def b17_spacecraft_performance(
    *,
    days: int,
    campaign_code: str,
    catalog_code: str = "",
    source_code: str = "",
) -> dict[str, Any]:
    if not SPACECRAFT_BASE_URL or not SPACECRAFT_WABOT_KEY:
        raise HTTPException(
            status_code=503,
            detail="SpaceCraft Performance API belum dikonfigurasi",
        )

    params: dict[str, Any] = {
        "days": max(1, min(365, int(days))),
        "campaign_code": campaign_code,
    }

    if catalog_code:
        params["catalog_code"] = catalog_code

    if source_code:
        params["source_code"] = source_code

    try:
        response = httpx.get(
            f"{SPACECRAFT_BASE_URL}/api/wabot/performance",
            headers={
                "X-SpaceCraft-Wabot-Key": SPACECRAFT_WABOT_KEY,
                "Accept": "application/json",
            },
            params=params,
            timeout=20,
            follow_redirects=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "SpaceCraft Performance API tidak dapat dijangkau: "
                + type(exc).__name__
            ),
        ) from exc

    try:
        payload = response.json()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Response SpaceCraft Performance API bukan JSON",
        ) from exc

    if response.status_code != 200 or payload.get("ok") is not True:
        raise HTTPException(
            status_code=502,
            detail=(
                "SpaceCraft Performance API mengembalikan HTTP "
                f"{response.status_code}"
            ),
        )

    return payload


@router.get(
    "/api/campaigns/{campaign_id}/wabot/performance"
)
def get_campaign_wabot_performance(
    campaign_id: int,
    days: int = 30,
    db: Session = Depends(get_db),
):
    campaign = db.get(CreativeCampaign, campaign_id)

    if campaign is None:
        raise HTTPException(
            status_code=404,
            detail="Campaign tidak ditemukan",
        )

    saved_config = wabot_load_config(campaign_id)

    campaign_code = wabot_normalize_code(
        saved_config.get("external_campaign_code")
        or b11_campaign_code(campaign)
    )

    catalog_code = wabot_normalize_code(
        saved_config.get("catalog_code")
    )

    source_code = wabot_normalize_code(
        saved_config.get("source_code")
        or "spacecraft_ads",
        "spacecraft_ads",
    )

    spacecraft = b17_spacecraft_performance(
        days=days,
        campaign_code=campaign_code,
        catalog_code=catalog_code,
        source_code=source_code,
    )

    return {
        "ok": True,
        "campaign": {
            "id": campaign.id,
            "name": campaign.name,
            "campaign_code": campaign_code,
            "catalog_code": catalog_code or None,
            "source_code": source_code,
        },
        "spacecraft": spacecraft,
        "generated_at": now().isoformat(),
    }


@router.post(
    "/api/campaigns/{campaign_id}/wabot/click"
)
def track_campaign_whatsapp_click(
    campaign_id: int,
    payload: B16WhatsAppClickRequest,
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

    # B19C_WABOT_COMMERCE_GUARD
    b19c_campaign_guard(campaign)

    saved_config = wabot_load_config(
        campaign_id
    )

    campaign_code = wabot_normalize_code(
        payload.campaign_code
        or saved_config.get(
            "external_campaign_code"
        )
        or b11_campaign_code(campaign)
    )

    catalog_code = wabot_normalize_code(
        payload.catalog_code
        or saved_config.get("catalog_code")
    )

    source_code = wabot_normalize_code(
        payload.source_code
        or saved_config.get("source_code")
        or "spacecraft_ads",
        "spacecraft_ads",
    )

    phone = wabot_normalize_phone(
        payload.phone
        or saved_config.get(
            "whatsapp_number"
        )
    )

    creative_code = wabot_normalize_code(
        payload.creative_code
        or f"{campaign_code}-MASTER"
    )

    if not campaign_code:
        raise HTTPException(
            status_code=422,
            detail="Campaign code belum tersedia",
        )

    if not catalog_code:
        raise HTTPException(
            status_code=422,
            detail="Catalog code belum tersedia",
        )

    occurred_at = now()
    event_id = (
        f"ADS-{campaign_id}-"
        f"{int(occurred_at.timestamp() * 1000)}"
    )

    event_metadata = {
        "event_id": event_id,
        "origin": "ads.spacecraft.id",
        "ads_event": "click_to_whatsapp",
        "creative_campaign_id": campaign.id,
        "creative_code": creative_code,
        "campaign_name": campaign.name,
        "opening_message":
            payload.opening_message,
        "destination_url":
            payload.destination_url,
    }

    local_event = wabot_write_event(
        campaign_id,
        {
            "event_type": "conversation",
            "phone": phone or None,
            "order_id": None,
            "campaign_code": campaign_code,
            "catalog_code": catalog_code,
            "source_code": source_code,
            "value": 0,
            "payload": event_metadata,
        },
    )

    spacecraft_event = {
        "event_type": "ads_whatsapp_click",
        "catalog_code": catalog_code,
        "source_code": source_code,
        "campaign_code": campaign_code,
        "phone": phone or None,
        "metadata": event_metadata,
        "occurred_at": occurred_at.isoformat(),
    }

    spacecraft_result = (
        b16_send_spacecraft_event(
            spacecraft_event
        )
    )

    return {
        "ok": True,
        "message": (
            "Klik WhatsApp berhasil dicatat"
        ),
        "event_id": event_id,
        "creative_code": creative_code,
        "local_event": local_event,
        "spacecraft": spacecraft_result,
    }


@router.get(
    "/api/wabot/status"
)
def get_wabot_status():
    return {
        "ok": True,
        "configured": bool(
            WABOT_BASE_URL
        ),
        "base_url": (
            WABOT_BASE_URL
            if WABOT_BASE_URL
            else None
        ),
        "api_key_configured": bool(
            WABOT_API_KEY
        ),
        "mode": "preview_safe",
        "automatic_send": False,
    }


@router.post(
    "/api/wabot/test"
)
def test_wabot_connection():
    if not WABOT_BASE_URL:
        return {
            "ok": False,
            "configured": False,
            "message": (
                "WABOT_BASE_URL belum dikonfigurasi. "
                "Preview payload tetap dapat digunakan."
            ),
        }

    headers: dict[str, str] = {}

    if WABOT_API_KEY:
        headers["Authorization"] = (
            f"Bearer {WABOT_API_KEY}"
        )

    candidates = [
        f"{WABOT_BASE_URL}/health",
        f"{WABOT_BASE_URL}/api/health",
        WABOT_BASE_URL,
    ]

    attempts: list[dict[str, Any]] = []

    for url in candidates:
        try:
            response = httpx.get(
                url,
                headers=headers,
                timeout=5,
                follow_redirects=True,
            )

            attempts.append({
                "url": url,
                "status_code":
                    response.status_code,
            })

            if response.status_code < 500:
                return {
                    "ok": True,
                    "configured": True,
                    "message": (
                        "WABot dapat dijangkau"
                    ),
                    "status_code":
                        response.status_code,
                    "endpoint": url,
                    "attempts": attempts,
                }

        except Exception as exc:
            attempts.append({
                "url": url,
                "error": str(exc)[:300],
            })

    return {
        "ok": False,
        "configured": True,
        "message": (
            "WABot belum dapat dijangkau"
        ),
        "attempts": attempts,
    }


@router.get(
    "/api/campaigns/{campaign_id}/wabot"
)
def get_campaign_wabot(
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

    saved_config = wabot_load_config(
        campaign_id
    )

    payload = wabot_campaign_payload(
        campaign,
        jobs,
        saved_config,
    )

    events = wabot_read_events(
        campaign_id,
        100,
    )

    return {
        "ok": True,
        "config": saved_config,
        "payload": payload,
        "events": events,
        "summary":
            wabot_event_summary(events),
    }


@router.put(
    "/api/campaigns/{campaign_id}/wabot"
)
def save_campaign_wabot(
    campaign_id: int,
    payload: WABotCampaignRequest,
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

    # B19C_WABOT_COMMERCE_GUARD
    b19c_campaign_guard(campaign)

    saved = wabot_save_config(
        campaign_id,
        {
            **payload.model_dump(),
            "catalog_code":
                wabot_normalize_code(
                    payload.catalog_code
                ),
            "source_code":
                wabot_normalize_code(
                    payload.source_code,
                    "spacecraft_ads",
                ),
            "external_campaign_code":
                wabot_normalize_code(
                    payload.external_campaign_code
                ),
            "whatsapp_number":
                wabot_normalize_phone(
                    payload.whatsapp_number
                ),
        },
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
        "message": (
            "Konfigurasi WABot campaign "
            "berhasil disimpan"
        ),
        "config": saved,
        "payload": wabot_campaign_payload(
            campaign,
            jobs,
            saved,
        ),
    }


@router.post(
    "/api/campaigns/{campaign_id}/wabot/events"
)
def create_campaign_wabot_event(
    campaign_id: int,
    payload: WABotEventRequest,
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

    # B19C_WABOT_COMMERCE_GUARD
    b19c_campaign_guard(campaign)

    saved_config = wabot_load_config(
        campaign_id
    )

    event = wabot_write_event(
        campaign_id,
        {
            **payload.model_dump(),
            "campaign_code": (
                saved_config.get(
                    "external_campaign_code"
                )
                or b11_campaign_code(
                    campaign
                )
            ),
            "catalog_code": (
                payload.catalog_code
                or saved_config.get(
                    "catalog_code"
                )
                or None
            ),
            "source_code": (
                payload.source_code
                or saved_config.get(
                    "source_code"
                )
                or "spacecraft_ads"
            ),
        },
    )

    return {
        "ok": True,
        "message": (
            "Attribution event berhasil dicatat"
        ),
        "event": event,
    }


@router.get(
    "/api/campaigns/{campaign_id}/performance"
)
def get_campaign_performance(
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

    dashboard = (
        performance_campaign_dashboard(
            campaign,
            jobs,
        )
    )

    return {
        "ok": True,
        "dashboard": dashboard,
    }


@router.put(
    "/api/campaigns/{campaign_id}"
    "/jobs/{job_id}/performance"
)
def save_job_performance(
    campaign_id: int,
    job_id: int,
    payload: PerformanceEntryRequest,
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
        or job.campaign_id
            != campaign_id
    ):
        raise HTTPException(
            status_code=404,
            detail="Render job tidak ditemukan",
        )

    metrics = performance_save(
        campaign_id,
        job_id,
        payload.model_dump(),
    )

    return {
        "ok": True,
        "message": (
            "Data performa berhasil disimpan"
        ),
        "job": performance_job_metadata(
            job
        ),
        "metrics": metrics,
    }


@router.delete(
    "/api/campaigns/{campaign_id}"
    "/jobs/{job_id}/performance"
)
def delete_job_performance(
    campaign_id: int,
    job_id: int,
    db: Session = Depends(get_db),
):
    job = db.get(
        RenderJob,
        job_id,
    )

    if (
        job is None
        or job.campaign_id
            != campaign_id
    ):
        raise HTTPException(
            status_code=404,
            detail="Render job tidak ditemukan",
        )

    redis_client = redis_connection()

    redis_client.delete(
        performance_key(
            campaign_id,
            job_id,
        )
    )

    redis_client.srem(
        performance_campaign_set_key(
            campaign_id
        ),
        str(job_id),
    )

    return {
        "ok": True,
        "message": (
            "Data performa berhasil dihapus"
        ),
    }


@router.get(
    "/api/campaigns/{campaign_id}"
    "/performance/export"
)
def export_campaign_performance(
    campaign_id: int,
    format: Literal[
        "json",
        "csv",
    ] = "json",
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

    dashboard = (
        performance_campaign_dashboard(
            campaign,
            jobs,
        )
    )

    return {
        "ok": True,
        "format": format,
        "filename": (
            f"{b11_campaign_code(campaign)}"
            "-performance."
            f"{format}"
        ),
        "content": (
            performance_campaign_csv(
                dashboard
            )
            if format == "csv"
            else json.dumps(
                dashboard,
                ensure_ascii=False,
                indent=2,
            )
        ),
        "dashboard": (
            dashboard
            if format == "json"
            else None
        ),
    }


@router.get(
    "/api/campaigns/{campaign_id}/ad-copy"
)
def get_campaign_ad_copy(
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
        "copy": b11_campaign_copy(
            campaign,
            jobs,
        ),
    }


@router.post(
    "/api/campaigns/{campaign_id}/export-package"
)
def create_campaign_export_package(
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

    package = b11_build_export_package(
        campaign,
        jobs,
    )

    return {
        "ok": True,
        "message": (
            "Campaign export package "
            "berhasil dibuat"
        ),
        "package": package,
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
