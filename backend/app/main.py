from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    func,
    or_,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Spacecraft Product Ads Studio"
    app_env: str = "production"
    app_secret_key: str

    database_url: str
    redis_url: str

    spacecraft_api_url: str
    spacecraft_api_token: str

    storage_path: str = "/app/storage"
    ads_auth_username: str = "admin"
    ads_auth_password: str = ""
    ads_auth_session_days: int = 7


settings = Settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    external_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    sku: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    slug: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    category_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    category_slug: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    short_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    material: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    dimensions: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    production_time: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    price_mode: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    price_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    price_label: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    compare_at_price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    product_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    primary_image_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    source_updated_at: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def product_to_dict(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "external_id": product.external_id,
        "sku": product.sku,
        "name": product.name,
        "slug": product.slug,
        "category_name": product.category_name,
        "category_slug": product.category_slug,
        "short_description": product.short_description,
        "description": product.description,
        "material": product.material,
        "dimensions": product.dimensions,
        "production_time": product.production_time,
        "price_mode": product.price_mode,
        "price_value": product.price_value,
        "price_label": product.price_label,
        "compare_at_price": product.compare_at_price,
        "product_url": product.product_url,
        "primary_image_url": product.primary_image_url,
        "status": product.status,
        "is_available": product.is_available,
        "source_updated_at": product.source_updated_at,
        "synced_at": product.synced_at.isoformat()
        if product.synced_at
        else None,
        "media": product.payload.get("media", []),
        "variants": product.payload.get("variants", []),
        "raw": product.payload,
    }


async def fetch_spacecraft_products() -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    page = 1
    last_page = 1

    headers = {
        "Authorization": (
            f"Bearer {settings.spacecraft_api_token}"
        ),
        "Accept": "application/json",
    }

    timeout = httpx.Timeout(
        connect=15.0,
        read=60.0,
        write=30.0,
        pool=30.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        while page <= last_page:
            response = await client.get(
                f"{settings.spacecraft_api_url.rstrip('/')}/products",
                headers=headers,
                params={
                    "per_page": 100,
                    "page": page,
                },
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": (
                            "Spacecraft API gagal diakses"
                        ),
                        "status_code": response.status_code,
                        "response": response.text[:1000],
                    },
                )

            payload = response.json()

            if not payload.get("ok"):
                raise HTTPException(
                    status_code=502,
                    detail="Spacecraft API mengembalikan status gagal",
                )

            page_products = payload.get("products", [])
            products.extend(page_products)

            pagination = payload.get("pagination", {})
            last_page = int(
                pagination.get("last_page", 1)
            )

            page += 1

    return products


def sync_product_record(
    db: Session,
    source: dict[str, Any],
) -> Product:
    external_id = str(
        source.get("external_id")
        or source.get("id")
    )

    product = db.scalar(
        select(Product).where(
            Product.external_id == external_id
        )
    )

    if product is None:
        product = Product(
            external_id=external_id,
            name=source.get("name") or "Unnamed Product",
            slug=source.get("slug") or external_id,
        )

        db.add(product)

    category = source.get("category") or {}
    price = source.get("price") or {}

    product.sku = source.get("sku")
    product.name = (
        source.get("name")
        or product.name
    )
    product.slug = (
        source.get("slug")
        or product.slug
    )

    product.category_name = category.get("name")
    product.category_slug = category.get("slug")

    product.short_description = source.get(
        "short_description"
    )

    product.description = source.get("description")
    product.material = source.get("material")
    product.dimensions = source.get("dimensions")
    product.production_time = source.get(
        "production_time"
    )

    product.price_mode = price.get("mode")
    product.price_value = price.get("value")
    product.price_label = price.get("label")
    product.compare_at_price = price.get(
        "compare_at_price"
    )

    product.product_url = source.get("product_url")
    product.primary_image_url = source.get(
        "primary_image_url"
    )

    product.status = source.get("status")
    product.is_available = bool(
        source.get("is_available", True)
    )

    product.source_updated_at = source.get(
        "updated_at"
    )

    product.payload = source
    product.synced_at = datetime.now(timezone.utc)

    return product


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)

    storage = Path(settings.storage_path)
    storage.mkdir(parents=True, exist_ok=True)

    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

SESSION_COOKIE = "ads_session"


def auth_password() -> str:
    return (
        settings.ads_auth_password
        or settings.app_secret_key
    )


def session_signature(
    username: str,
    expires_at: int,
) -> str:
    payload = f"{username}|{expires_at}".encode("utf-8")

    return hmac.new(
        settings.app_secret_key.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()


def create_session_cookie(
    username: str,
) -> str:
    expires_at = int(
        time.time()
        + max(1, settings.ads_auth_session_days)
        * 86400
    )
    signature = session_signature(
        username,
        expires_at,
    )

    return f"{username}|{expires_at}|{signature}"


def verify_session_cookie(
    value: str | None,
) -> str | None:
    if not value:
        return None

    try:
        username, expires_raw, signature = value.split(
            "|",
            2,
        )
        expires_at = int(expires_raw)
    except ValueError:
        return None

    if expires_at < int(time.time()):
        return None

    expected = session_signature(
        username,
        expires_at,
    )

    if not hmac.compare_digest(
        signature,
        expected,
    ):
        return None

    return username


def wants_json(request: Request) -> bool:
    accept = request.headers.get(
        "accept",
        "",
    ).lower()

    return (
        request.url.path.startswith("/api")
        or "application/json" in accept
    )


def login_page(
    error: str | None = None,
) -> HTMLResponse:
    error_html = (
        f'<p class="error">{error}</p>'
        if error
        else ""
    )

    return HTMLResponse(f"""<!doctype html>
<html lang="id">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Login - Spacecraft Ads Studio</title>
    <style>
        :root {{
            color: #f7f8ff;
            background: #070a12;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            min-height: 100vh;
            margin: 0;
            display: grid;
            place-items: center;
            padding: 28px;
            background:
                radial-gradient(circle at 85% 8%, rgba(39, 94, 254, .28), transparent 30%),
                radial-gradient(circle at 12% 18%, rgba(158, 240, 189, .14), transparent 24%),
                #070a12;
        }}
        main {{
            width: min(420px, 100%);
            border: 1px solid rgba(255, 255, 255, .12);
            border-radius: 8px;
            background: rgba(12, 17, 29, .88);
            box-shadow: 0 24px 80px rgba(0, 0, 0, .38);
            padding: 30px;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 13px;
            margin-bottom: 26px;
        }}
        .badge {{
            display: grid;
            place-items: center;
            width: 44px;
            height: 44px;
            border-radius: 8px;
            background: linear-gradient(135deg, #275efe, #9ef0bd);
            color: #07101d;
            font-weight: 900;
        }}
        h1 {{
            margin: 0;
            font-size: 22px;
            letter-spacing: 0;
        }}
        p {{
            margin: 5px 0 0;
            color: #9aa7bd;
            font-size: 14px;
            line-height: 1.5;
        }}
        label {{
            display: grid;
            gap: 8px;
            margin-top: 16px;
            color: #dce5f5;
            font-size: 13px;
            font-weight: 700;
        }}
        input {{
            width: 100%;
            border: 1px solid #2a3448;
            border-radius: 8px;
            background: #0a0f1d;
            color: #fff;
            padding: 13px 14px;
            font: inherit;
            outline: none;
        }}
        input:focus {{
            border-color: #7db2ff;
            box-shadow: 0 0 0 3px rgba(125, 178, 255, .16);
        }}
        button {{
            width: 100%;
            margin-top: 22px;
            border: 0;
            border-radius: 8px;
            background: #275efe;
            color: white;
            padding: 13px 16px;
            font: inherit;
            font-weight: 800;
            cursor: pointer;
        }}
        button:hover {{ background: #1f4fe0; }}
        .error {{
            margin: 0 0 16px;
            border: 1px solid rgba(255, 112, 112, .35);
            border-radius: 8px;
            background: rgba(255, 112, 112, .10);
            color: #ffc3c3;
            padding: 10px 12px;
        }}
    </style>
</head>
<body>
    <main>
        <div class="brand">
            <div class="badge">SC</div>
            <div>
                <h1>Ads Studio</h1>
                <p>Masuk untuk mengelola creative video Spacecraft.</p>
            </div>
        </div>
        {error_html}
        <form method="post" action="/login">
            <label>
                Username
                <input name="username" autocomplete="username" required autofocus>
            </label>
            <label>
                Password
                <input name="password" type="password" autocomplete="current-password" required>
            </label>
            <button type="submit">Masuk</button>
        </form>
    </main>
</body>
</html>""")


@app.middleware("http")
async def require_login(
    request: Request,
    call_next,
):
    path = request.url.path

    public_paths = {
        "/login",
        "/health",
        "/favicon.ico",
    }

    if (
        path in public_paths
        or path.startswith("/static/")
    ):
        return await call_next(request)

    username = verify_session_cookie(
        request.cookies.get(SESSION_COOKIE)
    )

    if username:
        request.state.auth_user = username
        return await call_next(request)

    if wants_json(request):
        return JSONResponse(
            {
                "ok": False,
                "detail": "Login diperlukan",
            },
            status_code=401,
        )

    return RedirectResponse(
        url="/login",
        status_code=303,
    )


@app.get("/login", include_in_schema=False)
def login_form(
    request: Request,
):
    if verify_session_cookie(
        request.cookies.get(SESSION_COOKIE)
    ):
        return RedirectResponse(
            url="/",
            status_code=303,
        )

    return login_page()


@app.post("/login", include_in_schema=False)
async def login_submit(
    request: Request,
):
    body = (
        await request.body()
    ).decode(
        "utf-8",
        errors="ignore",
    )
    form = parse_qs(body)
    username = str(
        (form.get("username") or [""])[0]
        or ""
    ).strip()
    password = str(
        (form.get("password") or [""])[0]
        or ""
    )

    if not (
        secrets.compare_digest(
            username,
            settings.ads_auth_username,
        )
        and secrets.compare_digest(
            password,
            auth_password(),
        )
    ):
        return login_page(
            "Username atau password salah."
        )

    response = RedirectResponse(
        url="/",
        status_code=303,
    )
    response.set_cookie(
        SESSION_COOKIE,
        create_session_cookie(username),
        max_age=max(1, settings.ads_auth_session_days) * 86400,
        httponly=True,
        secure=(settings.app_env == "production"),
        samesite="lax",
    )

    return response


@app.post("/api/auth/logout")
def logout():
    response = JSONResponse({
        "ok": True,
    })
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(
        Path(__file__).parent
        / "static"
        / "index.html"
    )


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))

    total = db.scalar(
        select(func.count(Product.id))
    ) or 0

    return {
        "ok": True,
        "service": "product-ads-studio",
        "database": "connected",
        "products": total,
    }


@app.post("/api/products/sync")
async def sync_products(
    db: Session = Depends(get_db),
):
    source_products = await fetch_spacecraft_products()

    created = 0
    updated = 0

    for source in source_products:
        external_id = str(
            source.get("external_id")
            or source.get("id")
        )

        exists = db.scalar(
            select(Product.id).where(
                Product.external_id == external_id
            )
        )

        sync_product_record(db, source)

        if exists:
            updated += 1
        else:
            created += 1

    db.commit()

    return {
        "ok": True,
        "message": "Sinkronisasi selesai",
        "received": len(source_products),
        "created": created,
        "updated": updated,
    }


@app.get("/api/products")
def list_products(
    search: str | None = Query(
        default=None,
        max_length=100,
    ),
    category: str | None = Query(
        default=None,
        max_length=100,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: Session = Depends(get_db),
):
    query = select(Product)

    if search:
        keyword = f"%{search.strip()}%"

        query = query.where(
            or_(
                Product.name.ilike(keyword),
                Product.sku.ilike(keyword),
                Product.slug.ilike(keyword),
            )
        )

    if category:
        query = query.where(
            Product.category_slug == category
        )

    total_query = select(
        func.count()
    ).select_from(
        query.subquery()
    )

    total = db.scalar(total_query) or 0

    records = db.scalars(
        query
        .order_by(Product.synced_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return {
        "ok": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "products": [
            product_to_dict(product)
            for product in records
        ],
    }


@app.get("/api/products/{product_id}")
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Produk tidak ditemukan",
        )

    return {
        "ok": True,
        "product": product_to_dict(product),
    }

# PRODUCT_ADS_PHASE2_BEGIN
from fastapi.staticfiles import StaticFiles as Phase2StaticFiles
from app.phase2 import (
    STORAGE_ROOT as phase2_storage_root,
    router as phase2_router,
)

app.include_router(phase2_router)

app.mount(
    "/media",
    Phase2StaticFiles(
        directory=phase2_storage_root
    ),
    name="phase2-media",
)

app.mount(
    "/static",
    Phase2StaticFiles(
        directory=Path(__file__).parent / "static"
    ),
    name="phase2-static",
)
# PRODUCT_ADS_PHASE2_END



# PRODUCT_ADS_PHASE3_BEGIN
from app.phase3 import router as phase3_router
app.include_router(phase3_router)
# PRODUCT_ADS_PHASE3_END
