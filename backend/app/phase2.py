from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import uuid
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.main import (
    Base,
    Product,
    engine,
    get_db,
    product_to_dict,
)


router = APIRouter()

STORAGE_ROOT = Path(
    os.getenv("STORAGE_PATH", "/app/storage")
)

MAX_UPLOAD_MB = int(
    os.getenv("MAX_UPLOAD_MB", "200")
)

ASSET_IMAGE_MAX_DIMENSION = int(
    os.getenv("ASSET_IMAGE_MAX_DIMENSION", "1600")
)

ASSET_IMAGE_WEBP_QUALITY = int(
    os.getenv("ASSET_IMAGE_WEBP_QUALITY", "88")
)

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    "",
).strip()

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash",
).strip()

GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta",
).strip()

STORAGE_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)


class ProductAsset(Base):
    __tablename__ = "product_assets"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey(
            "products.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    asset_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    original_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    stored_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )

    mime_type: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    relative_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )

    source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="upload",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ProductAnalysis(Base):
    __tablename__ = "product_analyses"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey(
            "products.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    model: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    result: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    raw_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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


Base.metadata.create_all(bind=engine)


ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".mp4",
    ".webm",
    ".mov",
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
}

MIME_ASSET_TYPES = {
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "image/gif": "image",
    "video/mp4": "video",
    "video/webm": "video",
    "video/quicktime": "video",
    "audio/mpeg": "audio",
    "audio/wav": "audio",
    "audio/x-wav": "audio",
    "audio/mp4": "audio",
    "audio/ogg": "audio",
}


def format_bytes(value: int) -> str:
    size = float(value)

    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"

        size /= 1024

    return f"{size:.1f} GB"


def asset_to_dict(
    asset: ProductAsset,
) -> dict[str, Any]:
    settings = load_asset_ads_settings(
        asset.product_id
    ).get(
        str(asset.id),
        {},
    )

    return {
        "id": asset.id,
        "product_id": asset.product_id,
        "asset_type": asset.asset_type,
        "original_name": asset.original_name,
        "mime_type": asset.mime_type,
        "size_bytes": asset.size_bytes,
        "size_label": format_bytes(
            asset.size_bytes
        ),
        "url": f"/media/{asset.relative_path}",
        "source": asset.source,
        "ads_enabled": bool(
            settings.get(
                "ads_enabled",
                True,
            )
        ),
        "created_at": (
            asset.created_at.isoformat()
            if asset.created_at
            else None
        ),
    }


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


def load_asset_ads_settings(
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


def analysis_to_dict(
    analysis: ProductAnalysis | None,
) -> dict[str, Any] | None:
    if analysis is None:
        return None

    return {
        "id": analysis.id,
        "product_id": analysis.product_id,
        "provider": analysis.provider,
        "model": analysis.model,
        "result": analysis.result,
        "created_at": (
            analysis.created_at.isoformat()
            if analysis.created_at
            else None
        ),
        "updated_at": (
            analysis.updated_at.isoformat()
            if analysis.updated_at
            else None
        ),
    }


def clean_filename(
    filename: str | None,
) -> str:
    value = Path(
        filename or "asset"
    ).name

    value = re.sub(
        r"[^A-Za-z0-9._() -]+",
        "_",
        value,
    )

    return value[:500] or "asset"


def infer_asset_type(
    mime_type: str,
    extension: str,
) -> str:
    if mime_type in MIME_ASSET_TYPES:
        return MIME_ASSET_TYPES[mime_type]

    guessed, _ = mimetypes.guess_type(
        f"asset{extension}"
    )

    if guessed in MIME_ASSET_TYPES:
        return MIME_ASSET_TYPES[guessed]

    raise HTTPException(
        status_code=415,
        detail=(
            "Format file tidak didukung. "
            "Gunakan JPG, PNG, WEBP, GIF, "
            "MP4, WEBM, MOV, MP3, WAV, "
            "M4A, atau OGG."
        ),
    )


def compress_uploaded_image(
    raw_bytes: bytes,
) -> tuple[bytes, str, str]:
    try:
        with Image.open(BytesIO(raw_bytes)) as image:
            image = ImageOps.exif_transpose(image)

            if ASSET_IMAGE_MAX_DIMENSION > 0:
                image.thumbnail(
                    (
                        ASSET_IMAGE_MAX_DIMENSION,
                        ASSET_IMAGE_MAX_DIMENSION,
                    ),
                    Image.Resampling.LANCZOS,
                )

            has_alpha = image.mode in {
                "RGBA",
                "LA",
            } or (
                image.mode == "P"
                and "transparency" in image.info
            )

            output_image = image.convert(
                "RGBA" if has_alpha else "RGB"
            )

            output = BytesIO()
            output_image.save(
                output,
                format="WEBP",
                quality=max(
                    1,
                    min(
                        100,
                        ASSET_IMAGE_WEBP_QUALITY,
                    ),
                ),
                method=6,
            )

            return (
                output.getvalue(),
                ".webp",
                "image/webp",
            )

    except UnidentifiedImageError as error:
        raise HTTPException(
            status_code=415,
            detail="File image tidak bisa dibaca",
        ) from error


def parse_ai_json(
    text: str,
) -> dict[str, Any]:
    value = text.strip()

    if value.startswith("```"):
        value = re.sub(
            r"^```(?:json)?\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )

        value = re.sub(
            r"\s*```$",
            "",
            value,
        )

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        start = value.find("{")
        end = value.rfind("}")

        if start < 0 or end <= start:
            raise ValueError(
                "AI tidak mengembalikan JSON valid"
            )

        parsed = json.loads(
            value[start:end + 1]
        )

    if not isinstance(parsed, dict):
        raise ValueError(
            "Hasil AI bukan objek JSON"
        )

    return parsed


def fallback_analysis(
    product: Product,
    assets: list[ProductAsset],
) -> dict[str, Any]:
    category = (
        product.category_name
        or "produk kreatif"
    )

    price = (
        product.price_label
        or "harga sesuai katalog"
    )

    material = (
        product.material
        or "material pilihan"
    )

    dimensions = (
        product.dimensions
        or "ukuran praktis"
    )

    source_media = (
        product.payload.get("media", [])
        if product.payload
        else []
    )

    image_count = sum(
        item.asset_type == "image"
        for item in assets
    )

    video_count = sum(
        item.asset_type == "video"
        for item in assets
    )

    audio_count = sum(
        item.asset_type == "audio"
        for item in assets
    )

    hooks = [
        {
            "style": "curiosity",
            "text": (
                "Kelihatannya sederhana, "
                "tapi produk ini bikin penasaran."
            ),
        },
        {
            "style": "problem-solution",
            "text": (
                f"Butuh {category} yang unik "
                "dan nggak pasaran?"
            ),
        },
        {
            "style": "demonstration",
            "text": (
                "Lihat cara kerja dan detail "
                "produk ini dalam beberapa detik."
            ),
        },
        {
            "style": "gift",
            "text": (
                "Bingung cari hadiah kecil "
                "yang tetap berkesan?"
            ),
        },
        {
            "style": "detail",
            "text": (
                "Detail kecilnya justru yang "
                "membuat produk ini menarik."
            ),
        },
        {
            "style": "price",
            "text": (
                f"Produk unik ini tersedia "
                f"dengan harga {price}."
            ),
        },
        {
            "style": "personal",
            "text": (
                "Bikin barang sehari-hari "
                "terasa lebih personal."
            ),
        },
        {
            "style": "social",
            "text": (
                "Produk kecil yang gampang "
                "jadi pembuka obrolan."
            ),
        },
        {
            "style": "quality",
            "text": (
                f"Kenapa material {material} "
                "membuat hasilnya berbeda?"
            ),
        },
        {
            "style": "direct",
            "text": (
                f"Kenalan dengan {product.name} "
                "dari Spacecraft."
            ),
        },
    ]

    angles = [
        {
            "name": "Product Demonstration",
            "concept": (
                "Tampilkan bentuk, ukuran, "
                "detail, dan cara penggunaan."
            ),
            "tone": "cepat dan satisfying",
        },
        {
            "name": "Problem to Solution",
            "concept": (
                "Mulai dari kebutuhan pelanggan "
                "lalu tampilkan produk."
            ),
            "tone": "relatable dan solutif",
        },
        {
            "name": "Gift Idea",
            "concept": (
                "Posisikan produk sebagai "
                "hadiah unik dan personal."
            ),
            "tone": "hangat",
        },
        {
            "name": "Craftsmanship",
            "concept": (
                f"Tonjolkan proses, {material}, "
                "detail, dan finishing."
            ),
            "tone": "premium",
        },
        {
            "name": "Price and Value",
            "concept": (
                f"Tampilkan manfaat lalu "
                f"tutup dengan harga {price}."
            ),
            "tone": "langsung",
        },
        {
            "name": "Lifestyle",
            "concept": (
                "Tampilkan produk digunakan "
                "dalam aktivitas sehari-hari."
            ),
            "tone": "natural",
        },
    ]

    storyboards = [
        {
            "title": "Fast Product Reveal",
            "duration_seconds": 15,
            "scenes": [
                {
                    "time": "0-3s",
                    "visual": (
                        "Close-up atau gerakan "
                        "produk paling menarik."
                    ),
                    "overlay": hooks[0]["text"],
                    "voiceover": hooks[0]["text"],
                },
                {
                    "time": "3-7s",
                    "visual": (
                        "Tampilkan detail produk "
                        "dari beberapa angle."
                    ),
                    "overlay": (
                        product.material
                        or "Detail berkualitas"
                    ),
                    "voiceover": (
                        f"Ini {product.name}, "
                        "dibuat untuk tampil beda."
                    ),
                },
                {
                    "time": "7-11s",
                    "visual": (
                        "Demonstrasikan fungsi "
                        "atau cara penggunaan."
                    ),
                    "overlay": dimensions,
                    "voiceover": (
                        "Praktis digunakan dan "
                        "menarik secara visual."
                    ),
                },
                {
                    "time": "11-15s",
                    "visual": (
                        "Hero shot produk, harga, "
                        "dan logo Spacecraft."
                    ),
                    "overlay": (
                        f"{price} • Lihat detail"
                    ),
                    "voiceover": (
                        "Cek detail lengkapnya "
                        "di Spacecraft."
                    ),
                },
            ],
        },
        {
            "title": "Problem Solution",
            "duration_seconds": 20,
            "scenes": [
                {
                    "time": "0-4s",
                    "visual": (
                        "Visual kebutuhan atau "
                        "masalah pelanggan."
                    ),
                    "overlay": hooks[1]["text"],
                    "voiceover": hooks[1]["text"],
                },
                {
                    "time": "4-9s",
                    "visual": (
                        "Reveal produk dengan "
                        "transisi cepat."
                    ),
                    "overlay": product.name,
                    "voiceover": (
                        f"Coba lihat "
                        f"{product.name} ini."
                    ),
                },
                {
                    "time": "9-15s",
                    "visual": (
                        "Tampilkan fungsi, ukuran, "
                        "dan detail material."
                    ),
                    "overlay": material,
                    "voiceover": (
                        "Desainnya memadukan "
                        "fungsi dan tampilan."
                    ),
                },
                {
                    "time": "15-20s",
                    "visual": (
                        "Hero shot dan tombol CTA."
                    ),
                    "overlay": (
                        f"{price} • Pesan sekarang"
                    ),
                    "voiceover": (
                        "Temukan produk ini "
                        "di katalog Spacecraft."
                    ),
                },
            ],
        },
        {
            "title": "Gift Recommendation",
            "duration_seconds": 15,
            "scenes": [
                {
                    "time": "0-3s",
                    "visual": (
                        "Produk atau kemasan "
                        "masuk ke dalam frame."
                    ),
                    "overlay": hooks[3]["text"],
                    "voiceover": hooks[3]["text"],
                },
                {
                    "time": "3-8s",
                    "visual": (
                        "Tampilkan bentuk, warna, "
                        "dan detail produk."
                    ),
                    "overlay": (
                        "Unik • Ringkas • Berkesan"
                    ),
                    "voiceover": (
                        "Pilih hadiah yang kecil, "
                        "unik, dan tetap berkesan."
                    ),
                },
                {
                    "time": "8-12s",
                    "visual": (
                        "Lifestyle shot atau "
                        "produk di tangan."
                    ),
                    "overlay": product.name,
                    "voiceover": (
                        f"{product.name} cocok "
                        "untuk berbagai momen."
                    ),
                },
                {
                    "time": "12-15s",
                    "visual": (
                        "Harga, produk, logo, CTA."
                    ),
                    "overlay": (
                        f"{price} • Spacecraft"
                    ),
                    "voiceover": (
                        "Lihat pilihan lengkapnya "
                        "di Spacecraft."
                    ),
                },
            ],
        },
    ]

    return {
        "summary": (
            f"{product.name} adalah {category} "
            "dengan kekuatan utama pada desain, "
            "fungsi, dan daya tarik visual. "
            "Format konten terbaik adalah demo, "
            "close-up, dan lifestyle."
        ),
        "ideal_customers": [
            (
                "Pembeli yang mencari produk "
                "unik dan tidak pasaran"
            ),
            (
                "Pencari hadiah personal dengan "
                "harga terjangkau"
            ),
            (
                "Penggemar produk kreatif dan "
                "hasil cetak 3D"
            ),
            (
                "Pengguna media sosial yang "
                "menyukai produk visual"
            ),
        ],
        "selling_points": [
            (
                product.short_description
                or "Desain unik dan menarik"
            ),
            f"Dibuat menggunakan {material}.",
            f"Ukuran produk: {dimensions}.",
            f"Tersedia dengan {price}.",
            (
                "Cocok untuk koleksi pribadi "
                "atau hadiah."
            ),
        ],
        "customer_objections": [
            {
                "objection": (
                    "Belum memahami ukuran produk."
                ),
                "response": (
                    "Tampilkan produk di tangan "
                    f"dan cantumkan {dimensions}."
                ),
            },
            {
                "objection": (
                    "Belum yakin dengan material."
                ),
                "response": (
                    "Gunakan close-up dan jelaskan "
                    f"material {material}."
                ),
            },
            {
                "objection": (
                    "Belum mengetahui cara pakai."
                ),
                "response": (
                    "Tambahkan demonstrasi singkat "
                    "tanpa potongan terlalu cepat."
                ),
            },
        ],
        "content_angles": angles,
        "hooks": hooks,
        "cta_options": [
            (
                "Lihat detail produknya "
                "di Spacecraft."
            ),
            (
                "Klik untuk cek harga dan "
                "pilihan produknya."
            ),
            (
                "Pesan melalui katalog resmi "
                "Spacecraft."
            ),
            (
                "Tambahkan produk ini ke "
                "koleksimu sekarang."
            ),
            (
                "Cek detail lengkapnya "
                "sekarang."
            ),
        ],
        "compliance_notes": [
            (
                "Hindari klaim medis seperti "
                "menyembuhkan stres atau "
                "mengatasi kecemasan."
            ),
            (
                "Gunakan harga dan informasi "
                "faktual dari katalog terbaru."
            ),
            (
                "Visual iklan harus sesuai "
                "dengan produk sebenarnya."
            ),
        ],
        "asset_readiness": {
            "source_media": len(source_media),
            "uploaded_images": image_count,
            "uploaded_videos": video_count,
            "uploaded_audio": audio_count,
            "recommendations": [
                (
                    "Tambahkan minimal tiga foto "
                    "dari sudut berbeda."
                    if image_count < 3
                    else (
                        "Jumlah foto tambahan "
                        "sudah mencukupi."
                    )
                ),
                (
                    "Tambahkan minimal satu video "
                    "demonstrasi 5-15 detik."
                    if video_count < 1
                    else (
                        "Video demonstrasi "
                        "sudah tersedia."
                    )
                ),
                (
                    "Tambahkan audio produk bila "
                    "suara menjadi nilai jual."
                    if audio_count < 1
                    else "Audio produk tersedia."
                ),
            ],
        },
        "storyboards": storyboards,
    }


def build_ai_prompt(
    product: Product,
    assets: list[ProductAsset],
) -> str:
    product_data = product_to_dict(
        product
    )

    product_data.pop(
        "raw",
        None,
    )

    asset_data = [
        {
            "type": asset.asset_type,
            "filename": asset.original_name,
            "mime_type": asset.mime_type,
        }
        for asset in assets
    ]

    return f"""
Anda adalah senior performance creative strategist
untuk Meta Ads, Instagram Reels, dan TikTok Indonesia.

Analisis produk berikut dan buat creative brief.
Gunakan Bahasa Indonesia natural dan mudah dipahami.

Jangan membuat:
- klaim medis;
- klaim hasil yang tidak terbukti;
- data stok atau diskon yang tidak tersedia;
- informasi produk yang tidak ada.

Untuk produk fidget gunakan bahasa seperti
"satisfying dimainkan". Jangan mengklaim dapat
menyembuhkan stres, kecemasan, atau gangguan fokus.

DATA PRODUK:
{json.dumps(product_data, ensure_ascii=False, indent=2)}

ASSET TAMBAHAN:
{json.dumps(asset_data, ensure_ascii=False, indent=2)}

Keluarkan JSON valid tanpa markdown dengan struktur:

{{
  "summary": "string",
  "ideal_customers": ["4-6 item"],
  "selling_points": ["5-8 item"],
  "customer_objections": [
    {{
      "objection": "string",
      "response": "string"
    }}
  ],
  "content_angles": [
    {{
      "name": "string",
      "concept": "string",
      "tone": "string"
    }}
  ],
  "hooks": [
    {{
      "style": "string",
      "text": "string"
    }}
  ],
  "cta_options": ["5 item"],
  "compliance_notes": ["minimal 3 item"],
  "asset_readiness": {{
    "source_media": 0,
    "uploaded_images": 0,
    "uploaded_videos": 0,
    "uploaded_audio": 0,
    "recommendations": ["string"]
  }},
  "storyboards": [
    {{
      "title": "string",
      "duration_seconds": 15,
      "scenes": [
        {{
          "time": "0-3s",
          "visual": "string",
          "overlay": "string",
          "voiceover": "string"
        }}
      ]
    }}
  ]
}}

Buat tepat:
- 6 content angles;
- 10 hooks;
- 5 CTA;
- 3 storyboard berdurasi 15-30 detik.
""".strip()


async def analyze_with_gemini(
    product: Product,
    assets: list[ProductAsset],
) -> tuple[dict[str, Any], str]:
    endpoint = (
        f"{GEMINI_BASE_URL.rstrip('/')}"
        f"/models/{GEMINI_MODEL}:generateContent"
    )

    request_payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": build_ai_prompt(
                            product,
                            assets,
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.75,
            "responseMimeType": (
                "application/json"
            ),
        },
    }

    timeout = httpx.Timeout(
        connect=20,
        read=180,
        write=60,
        pool=30,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        response = await client.post(
            endpoint,
            params={
                "key": GEMINI_API_KEY,
            },
            json=request_payload,
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Gemini HTTP {response.status_code}: "
            f"{response.text[:700]}"
        )

    response_data = response.json()

    try:
        text = response_data[
            "candidates"
        ][0]["content"]["parts"][0]["text"]
    except (
        KeyError,
        IndexError,
        TypeError,
    ) as error:
        raise RuntimeError(
            "Struktur respons Gemini tidak dikenali"
        ) from error

    return parse_ai_json(text), text


@router.get(
    "/api/products/{product_id}/workspace"
)
def product_workspace(
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

    assets = db.scalars(
        select(ProductAsset)
        .where(
            ProductAsset.product_id
            == product_id
        )
        .order_by(
            ProductAsset.created_at.desc()
        )
    ).all()


    return {
        "ok": True,
        "product": product_to_dict(product),
        "assets": [
            asset_to_dict(asset)
            for asset in assets
        ],
"limits": {
            "max_upload_mb": MAX_UPLOAD_MB,
            "max_files_per_request": 20,
            "allowed_extensions": sorted(
                ALLOWED_EXTENSIONS
            ),
        },
    }


@router.post(
    "/api/products/{product_id}/assets"
)
async def upload_assets(
    product_id: int,
    files: list[UploadFile] = File(...),
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

    if not files:
        raise HTTPException(
            status_code=400,
            detail="Tidak ada file dipilih",
        )

    if len(files) > 20:
        raise HTTPException(
            status_code=400,
            detail=(
                "Maksimal 20 file "
                "per proses upload"
            ),
        )

    destination = (
        STORAGE_ROOT
        / "products"
        / str(product_id)
        / "assets"
    )

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    max_bytes = (
        MAX_UPLOAD_MB
        * 1024
        * 1024
    )

    saved_records = []
    created_files = []

    try:
        for upload in files:
            original_name = clean_filename(
                upload.filename
            )

            extension = Path(
                original_name
            ).suffix.lower()

            if extension not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=415,
                    detail=(
                        "Ekstensi tidak didukung: "
                        f"{original_name}"
                    ),
                )

            mime_type = (
                upload.content_type
                or mimetypes.guess_type(
                    original_name
                )[0]
                or "application/octet-stream"
            )

            asset_type = infer_asset_type(
                mime_type,
                extension,
            )

            raw_bytes = await upload.read()
            await upload.close()

            original_size = len(raw_bytes)

            if original_size > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"{original_name} "
                        f"melebihi "
                        f"{MAX_UPLOAD_MB} MB"
                    ),
                )

            stored_extension = extension
            stored_mime_type = mime_type
            file_bytes = raw_bytes

            if asset_type == "image":
                (
                    file_bytes,
                    stored_extension,
                    stored_mime_type,
                ) = compress_uploaded_image(
                    raw_bytes
                )

            stored_name = (
                f"{uuid.uuid4().hex}"
                f"{stored_extension}"
            )

            absolute_path = (
                destination
                / stored_name
            )

            created_files.append(
                absolute_path
            )

            absolute_path.write_bytes(
                file_bytes
            )

            file_size = len(file_bytes)

            relative_path = (
                absolute_path
                .relative_to(STORAGE_ROOT)
                .as_posix()
            )

            record = ProductAsset(
                product_id=product_id,
                asset_type=asset_type,
                original_name=original_name,
                stored_name=stored_name,
                mime_type=stored_mime_type,
                size_bytes=file_size,
                relative_path=relative_path,
                source="upload",
            )

            db.add(record)
            saved_records.append(record)

        db.commit()

        for record in saved_records:
            db.refresh(record)

    except Exception:
        db.rollback()

        for created_file in created_files:
            created_file.unlink(
                missing_ok=True
            )

        raise

    return {
        "ok": True,
        "message": (
            f"{len(saved_records)} asset "
            "berhasil diunggah"
        ),
        "assets": [
            asset_to_dict(record)
            for record in saved_records
        ],
    }


@router.delete(
    "/api/assets/{asset_id}"
)
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    asset = db.get(
        ProductAsset,
        asset_id,
    )

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail="Asset tidak ditemukan",
        )

    absolute_path = (
        STORAGE_ROOT
        / asset.relative_path
    )

    try:
        absolute_path.resolve().relative_to(
            STORAGE_ROOT.resolve()
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="Path asset tidak valid",
        ) from error

    db.delete(asset)
    db.commit()

    absolute_path.unlink(
        missing_ok=True
    )

    parent = absolute_path.parent

    if (
        parent.exists()
        and not any(parent.iterdir())
    ):
        shutil.rmtree(
            parent,
            ignore_errors=True,
        )

    return {
        "ok": True,
        "message": "Asset berhasil dihapus",
    }


@router.post(
    "/api/products/{product_id}/analyze"
)
def analyze_product_disabled(
    product_id: int,
):
    raise HTTPException(
        status_code=410,
        detail="AI Product Analyzer sudah dinonaktifkan.",
    )



@router.get(
    "/api/products/{product_id}/analysis"
)
def get_analysis(
    product_id: int,
    db: Session = Depends(get_db),
):
    product_exists = db.scalar(
        select(
            func.count(Product.id)
        ).where(
            Product.id == product_id
        )
    )

    if not product_exists:
        raise HTTPException(
            status_code=404,
            detail="Produk tidak ditemukan",
        )

    analysis = db.scalar(
        select(ProductAnalysis).where(
            ProductAnalysis.product_id
            == product_id
        )
    )

    return {
        "ok": True,
        "analysis": analysis_to_dict(
            analysis
        ),
    }
