const state = {
    activeProductId: null,
    workspace: null,
    products: [],
    rawVideosByProduct: {},
    rawVideoGenerateTimers: {},
    catalogProductOrder: [],
    musicLibrary: [],
    expandedCampaignIds: new Set(),
};

const productGrid =
    document.getElementById("productGrid");

const searchInput =
    document.getElementById("searchInput");

const searchButton =
    document.getElementById("searchButton");

const syncButton =
    document.getElementById("syncButton");

const logoutButton =
    document.getElementById("logoutButton");

const multiProductMenuButton =
    document.getElementById("multiProductMenuButton");

const multiProductSection =
    document.getElementById("multiProductSection");

const multiProductPicker =
    document.getElementById("multiProductPicker");

const generateMultiCampaignButton =
    document.getElementById("generateMultiCampaignButton");

const multiCampaignMessage =
    document.getElementById("multiCampaignMessage");

const multiCampaignList =
    document.getElementById("multiCampaignList");

const globalStatus =
    document.getElementById("globalStatus");

const modal =
    document.getElementById("workspaceModal");

const workspaceTitle =
    document.getElementById("workspaceTitle");

const workspaceSubtitle =
    document.getElementById("workspaceSubtitle");

const workspaceStatus =
    document.getElementById("workspaceStatus");

const workspaceContent =
    document.getElementById("workspaceContent");


function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function errorMessage(data, fallback) {
    if (!data) {
        return fallback;
    }

    if (typeof data.detail === "string") {
        return data.detail;
    }

    if (data.detail) {
        return JSON.stringify(data.detail);
    }

    return data.message || fallback;
}


async function api(url, options = {}) {
    const response = await fetch(
        url,
        options
    );

    let data = null;

    try {
        data = await response.json();
    } catch (_) {
        data = null;
    }

    if (response.status === 401) {
        window.location.href = "/login";
        throw new Error("Login diperlukan");
    }

    if (!response.ok) {
        throw new Error(
            errorMessage(
                data,
                `HTTP ${response.status}`
            )
        );
    }

    return data;
}


function placeholderImage() {
    const svg = `
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="800"
            height="600"
        >
            <rect
                width="100%"
                height="100%"
                fill="#f3f4f6"
            />

            <text
                x="50%"
                y="50%"
                text-anchor="middle"
                fill="#6b7280"
                font-size="36"
            >
                No Image
            </text>
        </svg>
    `;

    return (
        "data:image/svg+xml;charset=UTF-8,"
        + encodeURIComponent(svg)
    );
}


function productCard(product) {
    const image =
        product.primary_image_url
        || placeholderImage();

    const description = (
        product.short_description
        || product.description
        || "Belum ada deskripsi produk."
    ).slice(0, 145);

    return `
        <article class="product-card">
            <img
                class="product-image"
                src="${escapeHtml(image)}"
                alt="${escapeHtml(product.name)}"
                loading="lazy"
            >

            <div class="product-body">
                <span class="tag">
                    ${escapeHtml(
                        product.category_name
                        || "Tanpa kategori"
                    )}
                </span>

                <h3>
                    ${escapeHtml(product.name)}
                </h3>

                <div class="price">
                    ${escapeHtml(
                        product.price_label
                        || "Harga belum tersedia"
                    )}
                </div>

                <div class="product-description">
                    ${escapeHtml(description)}
                </div>

                <div class="card-actions">
                    <a
                        href="${escapeHtml(
                            product.product_url || "#"
                        )}"
                        target="_blank"
                        rel="noopener"
                    >
                        Lihat Katalog
                    </a>

                    <button
                        class="studio-button"
                        onclick="openWorkspace(
                            ${Number(product.id)}
                        )"
                    >
                        Buka Studio
                    </button>
                </div>
            </div>
        </article>
    `;
}


function renderMultiProductPicker() {
    if (!multiProductPicker) return;

    const products = state.products || [];

    if (!products.length) {
        multiProductPicker.innerHTML = `
            <div class="empty">
                Produk belum dimuat.
            </div>
        `;
        return;
    }

    const sorted = [...products].sort((a, b) =>
        String(a.name || "").localeCompare(String(b.name || ""))
    );

    multiProductPicker.innerHTML = `
        <div class="picker-head">
            <div>
                <strong>Produk dan Raw Video Real</strong>
                <span>Pilih 5–6 produk, lalu pilih raw video real yang akan digabung menjadi catalog ads.</span>
            </div>
            <button
                type="button"
                class="mini-button"
                onclick="selectVisibleCampaignProducts()"
            >
                Pilih maksimal 6
            </button>
        </div>
        <div class="campaign-product-options">
            ${sorted.map(product => {
                const image = product.primary_image_url || placeholderImage();
                return `
                    <label
                        class="campaign-product-option"
                        data-product-id="${Number(product.id)}"
                    >
                        <input
                            type="checkbox"
                            class="campaignProductCheckbox"
                            value="${Number(product.id)}"
                            onchange="toggleCampaignProductRaw(this)"
                        >
                        <img
                            src="${escapeHtml(image)}"
                            alt="${escapeHtml(product.name)}"
                            loading="lazy"
                        >
                        <span class="campaign-product-copy">
                            <strong>${escapeHtml(product.name)}</strong>
                            <small
                                class="campaignRawVideoStatus"
                                data-product-id="${Number(product.id)}"
                            >
                                Pilih produk untuk memuat raw video
                            </small>
                        </span>
                        <div class="campaign-raw-tools">
                            <select
                                class="campaignRawVideoSelect"
                                data-product-id="${Number(product.id)}"
                                onchange="renderCatalogPreflight()"
                                disabled
                            >
                                <option value="">Centang untuk memuat raw video</option>
                            </select>

                            <div
                                class="catalog-order-controls"
                                data-order-product-id="${Number(product.id)}"
                            >
                                <span
                                    class="catalog-order-number"
                                    data-order-number="${Number(product.id)}"
                                >
                                    –
                                </span>

                                <button
                                    type="button"
                                    title="Naikkan urutan"
                                    onclick="
                                        event.preventDefault();
                                        event.stopPropagation();
                                        moveCatalogProduct(
                                            ${Number(product.id)},
                                            -1
                                        );
                                    "
                                >
                                    ↑
                                </button>

                                <button
                                    type="button"
                                    title="Turunkan urutan"
                                    onclick="
                                        event.preventDefault();
                                        event.stopPropagation();
                                        moveCatalogProduct(
                                            ${Number(product.id)},
                                            1
                                        );
                                    "
                                >
                                    ↓
                                </button>
                            </div>
                        </div>
                    </label>
                `;
            }).join("")}
        </div>
    `;
}


function campaignProductName(productId) {
    const product = (state.products || []).find(
        item => Number(item.id) === Number(productId)
    );

    return product?.name || `Produk ${productId}`;
}


function setRawVideoGenerateState(productId, text, isBusy = false) {
    const status = document.querySelector(
        `.campaignRawVideoStatus[data-product-id="${productId}"]`
    );
    const button = document.querySelector(
        `.raw-generate-button[data-product-id="${productId}"]`
    );

    if (status) {
        status.textContent = text;
        status.classList.toggle("is-busy", Boolean(isBusy));
    }

    if (button) {
        button.disabled = Boolean(isBusy);
        button.textContent = isBusy ? "Generating..." : "Upload Raw Video";
    }
}


function rawVideoLabel(video) {
    const title =
        video.title
        || video.label
        || video.original_name
        || `Raw Video ${video.asset_id || ""}`;

    const sizeMb = video.size_bytes
        ? ` • ${(Number(video.size_bytes) / 1024 / 1024).toFixed(1)} MB`
        : "";

    const primaryLabel =
        video.is_primary
        ? "★ Utama • "
        : "";

    const typeLabel =
        video.video_type
        ? ` • ${video.video_type}`
        : "";

    const fitLabel =
        video.fit_mode
        ? ` • ${video.fit_mode}`
        : "";

    return (
        `${primaryLabel}${title}`
        + `${typeLabel}${fitLabel}${sizeMb}`
    );
}


async function loadRawVideosForProduct(productId) {
    if (state.rawVideosByProduct[productId]) {
        return state.rawVideosByProduct[productId];
    }

    const data = await api(`/api/products/${productId}/raw-videos`);
    state.rawVideosByProduct[productId] = data.raw_videos || [];
    return state.rawVideosByProduct[productId];
}


async function populateRawVideoSelect(productId, preferredClipId = "") {
    const select = document.querySelector(
        `.campaignRawVideoSelect[data-product-id="${productId}"]`
    );

    if (!select) return;

    select.disabled = true;
    select.innerHTML = '<option value="">Memuat raw video...</option>';

    try {
        const rawVideos = await loadRawVideosForProduct(productId);

        if (!rawVideos.length) {
            select.innerHTML = '<option value="">Belum ada raw video real</option>';
            setRawVideoGenerateState(
                productId,
                "Belum ada raw video real. Upload video dari workspace produk."
            );
            return;
        }

        select.innerHTML = rawVideos.map(video => `
            <option value="${escapeHtml(video.clip_id)}">
                ${escapeHtml(rawVideoLabel(video))}
            </option>
        `).join("");
        select.disabled = false;

        if (preferredClipId) {
            select.value = preferredClipId;
        } else if (rawVideos.length) {
            select.value = rawVideos[0].clip_id;
        }
        setRawVideoGenerateState(
            productId,
            `${rawVideos.length} video real tersedia`
        );
    } catch (error) {
        select.innerHTML = `
            <option value="">
                Gagal memuat: ${escapeHtml(error.message)}
            </option>
        `;
        setRawVideoGenerateState(
            productId,
            `Gagal memuat raw video: ${error.message}`
        );
    }
}


async function toggleCampaignProductRaw(input) {
    const productId = Number(input.value);
    const select = document.querySelector(
        `.campaignRawVideoSelect[data-product-id="${productId}"]`
    );

    if (!select) return;

    const checkedInputs = [
        ...document.querySelectorAll(
            ".campaignProductCheckbox:checked"
        )
    ];

    if (
        input.checked
        && checkedInputs.length > 6
    ) {
        input.checked = false;

        if (multiCampaignMessage) {
            multiCampaignMessage.textContent =
                "Maksimal 6 produk per video katalog.";
        }

        return;
    }

    if (!input.checked) {
        state.catalogProductOrder =
            state.catalogProductOrder.filter(
                item =>
                    Number(item)
                    !== Number(productId)
            );

        select.disabled = true;
        select.innerHTML =
            '<option value="">Centang untuk memuat raw video</option>';

        setRawVideoGenerateState(
            productId,
            "Pilih produk untuk memuat raw video"
        );

        updateCatalogOrderUI();
        renderCatalogPreflight();
        return;
    }

    if (
        !state.catalogProductOrder.includes(
            productId
        )
    ) {
        state.catalogProductOrder.push(
            productId
        );
    }

    await populateRawVideoSelect(productId);

    updateCatalogOrderUI();
    renderCatalogPreflight();
}



function selectedCatalogOrder() {
    const checkedIds = new Set(
        [
            ...document.querySelectorAll(
                ".campaignProductCheckbox:checked"
            ),
        ].map(input => Number(input.value))
    );

    state.catalogProductOrder =
        state.catalogProductOrder.filter(
            productId =>
                checkedIds.has(Number(productId))
        );

    checkedIds.forEach(productId => {
        if (
            !state.catalogProductOrder.includes(
                Number(productId)
            )
        ) {
            state.catalogProductOrder.push(
                Number(productId)
            );
        }
    });

    return [...state.catalogProductOrder];
}


function updateCatalogOrderUI() {
    const order = selectedCatalogOrder();

    document.querySelectorAll(
        ".campaign-product-option"
    ).forEach(card => {
        const productId = Number(
            card.dataset.productId
        );

        const position =
            order.indexOf(productId);

        card.classList.toggle(
            "is-active",
            position >= 0
        );

        const number = card.querySelector(
            `[data-order-number="${productId}"]`
        );

        const controls = card.querySelector(
            `[data-order-product-id="${productId}"]`
        );

        if (number) {
            number.textContent =
                position >= 0
                ? String(position + 1)
                : "–";
        }

        if (controls) {
            controls.classList.toggle(
                "is-disabled",
                position < 0
            );
        }
    });
}


function moveCatalogProduct(
    productId,
    direction
) {
    selectedCatalogOrder();

    const currentIndex =
        state.catalogProductOrder.indexOf(
            Number(productId)
        );

    if (currentIndex < 0) {
        return;
    }

    const targetIndex =
        currentIndex + Number(direction);

    if (
        targetIndex < 0
        || targetIndex
            >= state.catalogProductOrder.length
    ) {
        return;
    }

    const nextOrder = [
        ...state.catalogProductOrder,
    ];

    [
        nextOrder[currentIndex],
        nextOrder[targetIndex],
    ] = [
        nextOrder[targetIndex],
        nextOrder[currentIndex],
    ];

    state.catalogProductOrder = nextOrder;

    updateCatalogOrderUI();
    renderCatalogPreflight();
}


function selectedRawVideoForProduct(
    productId
) {
    const select = document.querySelector(
        `.campaignRawVideoSelect`
        + `[data-product-id="${productId}"]`
    );

    const clipId = select?.value || "";

    const videos =
        state.rawVideosByProduct[
            Number(productId)
        ] || [];

    return videos.find(
        video => video.clip_id === clipId
    ) || null;
}


function calculateCatalogPreflight() {
    const productIds =
        selectedCatalogOrder();

    const duration = Number(
        document.getElementById(
            "multiCampaignDuration"
        )?.value || 25
    );

    const closingDuration = Math.min(
        4,
        Math.max(
            3,
            duration * 0.16
        )
    );

    const productDuration = Math.max(
        1,
        duration - closingDuration
    );

    const transitionDuration = Math.min(
        0.30,
        Math.max(
            0.24,
            productDuration * 0.012
        )
    );

    const transitionTotal =
        transitionDuration
        * Math.max(
            0,
            productIds.length - 1
        );

    const segmentDuration =
        productIds.length
        ? (
            productDuration
            + transitionTotal
        ) / productIds.length
        : 0;

    const errors = [];
    const warnings = [];

    if (
        productIds.length < 5
        || productIds.length > 6
    ) {
        errors.push(
            "Pilih tepat 5 sampai 6 produk."
        );
    }

    const items = productIds.map(
        (productId, index) => {
            const video =
                selectedRawVideoForProduct(
                    productId
                );

            const productName =
                campaignProductName(
                    productId
                );

            if (!video) {
                errors.push(
                    `${productName}: raw video belum dipilih.`
                );

                return {
                    productId,
                    productName,
                    index,
                    valid: false,
                    message:
                        "Raw video belum dipilih",
                };
            }

            const sourceDuration = Number(
                video.duration_seconds
            );

            const trimStart = Number(
                video.trim_start || 0
            );

            const trimEnd = (
                video.trim_end !== null
                && video.trim_end !== undefined
                ? Number(video.trim_end)
                : (
                    Number.isFinite(
                        sourceDuration
                    )
                    ? sourceDuration
                    : null
                )
            );

            let effectiveDuration = null;
            let valid = true;
            let message = "Siap";

            if (
                Number.isFinite(
                    sourceDuration
                )
                && trimStart >= sourceDuration
            ) {
                valid = false;
                message =
                    "Trim mulai di luar durasi video";

                errors.push(
                    `${productName}: ${message}.`
                );
            }

            if (
                trimEnd !== null
                && Number.isFinite(
                    sourceDuration
                )
                && trimEnd
                    > sourceDuration + 0.05
            ) {
                valid = false;
                message =
                    "Trim selesai melebihi durasi video";

                errors.push(
                    `${productName}: ${message}.`
                );
            }

            if (
                trimEnd !== null
                && trimEnd <= trimStart
            ) {
                valid = false;
                message =
                    "Trim selesai harus lebih besar";

                errors.push(
                    `${productName}: ${message}.`
                );
            }

            if (trimEnd !== null) {
                effectiveDuration = Math.max(
                    0,
                    trimEnd - trimStart
                );

                if (effectiveDuration < 0.5) {
                    valid = false;
                    message =
                        "Bagian video terlalu pendek";

                    errors.push(
                        `${productName}: ${message}.`
                    );
                } else if (
                    effectiveDuration
                        < segmentDuration
                ) {
                    warnings.push(
                        `${productName}: frame terakhir `
                        + "akan ditahan agar cukup durasi."
                    );
                }
            }

            const fitMode =
                video.fit_mode || "auto";

            const orientation =
                video.orientation || "unknown";

            const width = Number(
                video.width
            );

            const height = Number(
                video.height
            );

            const targetAspect =
                document.getElementById(
                    "multiCampaignAspect"
                )?.value || "9:16";

            if (
                targetAspect === "9:16"
                && orientation === "landscape"
                && fitMode === "contain"
            ) {
                warnings.push(
                    `${productName}: video landscape `
                    + "dengan Contain akan memiliki "
                    + "area kosong."
                );
            }

            if (
                Number.isFinite(width)
                && Number.isFinite(height)
                && (
                    width < 720
                    || height < 720
                )
            ) {
                warnings.push(
                    `${productName}: resolusi source `
                    + `${width}×${height} cukup rendah.`
                );
            }

            return {
                productId,
                productName,
                index,
                valid,
                message,
                video,
                sourceDuration,
                trimStart,
                trimEnd,
                effectiveDuration,
                fitMode,
                orientation,
                width,
                height,
            };
        }
    );

    return {
        ok: errors.length === 0,
        duration,
        closingDuration,
        productDuration,
        transitionDuration,
        transitionTotal,
        segmentDuration,
        productIds,
        items,
        errors,
        warnings,
    };
}


function catalogSeconds(value) {
    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "–";
    }

    return `${number.toFixed(2)} dtk`;
}


function renderCatalogPreflight() {
    updateCatalogOrderUI();

    const badge =
        document.getElementById(
            "catalogPreflightBadge"
        );

    const summary =
        document.getElementById(
            "catalogPreflightSummary"
        );

    const target =
        document.getElementById(
            "catalogPreflightItems"
        );

    if (!badge || !summary || !target) {
        return calculateCatalogPreflight();
    }

    const preflight =
        calculateCatalogPreflight();

    badge.textContent =
        preflight.ok
        ? "Siap Render"
        : "Belum Siap";

    badge.classList.toggle(
        "is-ready",
        preflight.ok
    );

    summary.innerHTML = `
        <span>
            <b>${preflight.productIds.length}</b>
            produk
        </span>
        <span>
            Output:
            <b>${preflight.duration} detik</b>
        </span>
        <span>
            Per produk:
            <b>${catalogSeconds(
                preflight.segmentDuration
            )}</b>
        </span>
        <span>
            Crossfade:
            <b>${catalogSeconds(
                preflight.transitionDuration
            )}</b>
        </span>
        <span>
            Closing:
            <b>${catalogSeconds(
                preflight.closingDuration
            )}</b>
        </span>
    `;

    if (!preflight.items.length) {
        target.innerHTML = `
            <div class="empty compact">
                Belum ada produk dipilih.
            </div>
        `;
    } else {
        target.innerHTML =
            preflight.items.map(item => {
                if (!item.video) {
                    return `
                        <article
                            class="catalog-preflight-item is-error"
                        >
                            <span class="catalog-preflight-order">
                                ${item.index + 1}
                            </span>

                            <div>
                                <strong>
                                    ${escapeHtml(
                                        item.productName
                                    )}
                                </strong>
                                <small>
                                    ${escapeHtml(
                                        item.message
                                    )}
                                </small>
                            </div>
                        </article>
                    `;
                }

                const videoName =
                    item.video.title
                    || item.video.label
                    || item.video.clip_id;

                return `
                    <article
                        class="catalog-preflight-item
                            ${item.valid
                                ? ""
                                : "is-error"}"
                    >
                        <span class="catalog-preflight-order">
                            ${item.index + 1}
                        </span>

                        <div class="catalog-preflight-copy">
                            <strong>
                                ${escapeHtml(
                                    item.productName
                                )}
                            </strong>

                            <small>
                                ${escapeHtml(videoName)}
                            </small>

                            <small>
                                Tipe:
                                ${escapeHtml(
                                    item.video.video_type
                                    || "demo"
                                )}
                                • Layout:
                                ${escapeHtml(
                                    item.fitMode
                                    || "auto"
                                )}
                                • Orientasi:
                                ${escapeHtml(
                                    item.orientation
                                    || "unknown"
                                )}
                                • Source:
                                ${catalogSeconds(
                                    item.sourceDuration
                                )}
                                • Trim:
                                ${catalogSeconds(
                                    item.trimStart
                                )}
                                –
                                ${item.trimEnd !== null
                                    ? catalogSeconds(
                                        item.trimEnd
                                    )
                                    : "akhir"}
                            </small>
                        </div>

                        <span
                            class="catalog-preflight-status"
                        >
                            ${escapeHtml(
                                item.message
                            )}
                        </span>
                    </article>
                `;
            }).join("");
    }

    if (
        preflight.errors.length
        || preflight.warnings.length
    ) {
        target.insertAdjacentHTML(
            "beforeend",
            `
                <div class="catalog-preflight-notes">
                    ${preflight.errors.map(
                        message => `
                            <div class="is-error">
                                • ${escapeHtml(message)}
                            </div>
                        `
                    ).join("")}

                    ${preflight.warnings.map(
                        message => `
                            <div class="is-warning">
                                • ${escapeHtml(message)}
                            </div>
                        `
                    ).join("")}
                </div>
            `
        );
    }

    return preflight;
}



function rawVideoIds(videos) {
    return new Set(
        (videos || [])
            .map(video => video.clip_id)
            .filter(Boolean)
    );
}


function stopRawVideoPolling(productId) {
    const timer = state.rawVideoGenerateTimers[productId];
    if (timer) clearTimeout(timer);
    delete state.rawVideoGenerateTimers[productId];
}













async function loadHealth() {
    try {
        const health = await api("/health");

        document.getElementById(
            "productCount"
        ).textContent = health.products ?? 0;

        document.getElementById(
            "assetCount"
        ).textContent = health.assets ?? 0;

    } catch (_) {
    }
}


async function loadProducts() {
    globalStatus.textContent =
        "Memuat produk...";

    const params = new URLSearchParams({
        limit: "100",
    });

    const keyword =
        searchInput.value.trim();

    if (keyword) {
        params.set("search", keyword);
    }

    try {
        const data = await api(
            `/api/products?${params}`
        );
        state.products = data.products || [];
        renderMultiProductPicker();

        if (!data.products.length) {
            productGrid.innerHTML = `
                <div class="empty">
                    Produk tidak ditemukan.
                </div>
            `;
        } else {
            productGrid.innerHTML =
                data.products
                    .map(productCard)
                    .join("");
        }

        globalStatus.textContent =
            `${data.products.length} dari `
            + `${data.total} produk ditampilkan`;

    } catch (error) {
        productGrid.innerHTML = `
            <div class="empty">
                ${escapeHtml(error.message)}
            </div>
        `;

        globalStatus.textContent =
            "Gagal memuat produk";
    }
}


async function syncProducts() {
    syncButton.disabled = true;
    syncButton.textContent =
        "Sinkronisasi...";

    globalStatus.textContent =
        "Mengambil produk dari Spacecraft...";

    try {
        const data = await api(
            "/api/products/sync",
            {
                method: "POST",
            }
        );

        globalStatus.textContent =
            `Sinkronisasi selesai: `
            + `${data.created} baru, `
            + `${data.updated} diperbarui`;

        await loadProducts();
        await loadHealth();

    } catch (error) {
        globalStatus.textContent =
            `Sinkronisasi gagal: `
            + error.message;

    } finally {
        syncButton.disabled = false;
        syncButton.textContent =
            "Sinkronkan Spacecraft";
    }
}


async function logout() {
    try {
        await api(
            "/api/auth/logout",
            {
                method: "POST",
            }
        );
    } finally {
        window.location.href = "/login";
    }
}


function sourceMediaCard(item) {
    const type =
        item.type || "image";

    const url =
        item.url || item.thumbnail_url;

    if (!url) {
        return "";
    }

    let preview = "";

    if (type === "video") {
        preview = `
            <video
                class="asset-preview"
                src="${escapeHtml(url)}"
                controls
                preload="metadata"
            ></video>
        `;
    } else {
        preview = `
            <img
                class="asset-preview"
                src="${escapeHtml(url)}"
                alt="Product media"
                loading="lazy"
            >
        `;
    }

    return `
        <article class="asset">
            ${preview}

            <div class="asset-info">
                <strong>
                    Media Spacecraft
                </strong>

                <small>
                    ${escapeHtml(type)}
                </small>
            </div>
        </article>
    `;
}


function uploadedAssetCard(asset) {
    let preview = "";

    if (asset.asset_type === "video") {
        preview = `
            <video
                class="asset-preview"
                src="${escapeHtml(asset.url)}"
                controls
                preload="metadata"
            ></video>
        `;
    } else if (asset.asset_type === "audio") {
        preview = `
            <div class="asset-audio">
                <audio
                    src="${escapeHtml(asset.url)}"
                    controls
                ></audio>
            </div>
        `;
    } else {
        preview = `
            <img
                class="asset-preview"
                src="${escapeHtml(asset.url)}"
                alt="${escapeHtml(
                    asset.original_name
                )}"
                loading="lazy"
            >
        `;
    }

    return `
        <article class="asset">
            ${preview}

            <div class="asset-info">
                <strong title="${escapeHtml(
                    asset.original_name
                )}">
                    ${escapeHtml(
                        asset.original_name
                    )}
                </strong>

                <small>
                    ${escapeHtml(
                        asset.asset_type
                    )}
                    •
                    ${escapeHtml(
                        asset.size_label
                    )}
                </small>

                <button
                    onclick="deleteAsset(
                        ${Number(asset.id)}
                    )"
                >
                    Hapus
                </button>
            </div>
        </article>
    `;
}


function renderList(items) {
    if (!Array.isArray(items) || !items.length) {
        return "<p>Belum tersedia.</p>";
    }

    return `
        <ul>
            ${items.map(item => `
                <li>${escapeHtml(item)}</li>
            `).join("")}
        </ul>
    `;
}


function imageVariationSourceOptions(data) {
    const product = data.product || {};
    const assets = data.assets || [];
    const sourceMedia = product.media || [];
    const options = [];

    if (product.primary_image_url) {
        options.push(`
            <option value="primary|">
                Primary image
            </option>
        `);
    }

    sourceMedia
        .filter(item =>
            (item.type || "image") === "image"
            && item.url
        )
        .forEach((item, index) => {
            options.push(`
                <option value="url|${encodeURIComponent(item.url)}">
                    Spacecraft media ${index + 1}
                </option>
            `);
        });

    assets
        .filter(asset => asset.asset_type === "image")
        .forEach(asset => {
            options.push(`
                <option value="asset|${Number(asset.id)}">
                    ${escapeHtml(asset.original_name)}
                </option>
            `);
        });

    if (!options.length) {
        return `
            <option value="">
                Tidak ada source image
            </option>
        `;
    }

    return options.join("");
}


function renderWorkspace(data) {
    state.workspace = data;

    const product = data.product;
    const assets = data.assets || [];
    const sourceMedia =
        product.media || [];

    workspaceTitle.textContent =
        product.name;

    workspaceSubtitle.textContent =
        `${product.category_name || "Tanpa kategori"}`
        + ` • `
        + `${product.price_label || "Harga belum tersedia"}`;

    const mainImage =
        product.primary_image_url
        || placeholderImage();

    workspaceContent.innerHTML = `
        <div class="workspace-grid">
            <section class="panel">
                <img
                    class="hero-product-image"
                    src="${escapeHtml(mainImage)}"
                    alt="${escapeHtml(product.name)}"
                >

                <div class="detail-list">
                    <div>
                        <span>Harga</span>

                        <strong>
                            ${escapeHtml(
                                product.price_label
                                || "-"
                            )}
                        </strong>
                    </div>

                    <div>
                        <span>Material</span>

                        <strong>
                            ${escapeHtml(
                                product.material
                                || "-"
                            )}
                        </strong>
                    </div>

                    <div>
                        <span>Dimensi</span>

                        <strong>
                            ${escapeHtml(
                                product.dimensions
                                || "-"
                            )}
                        </strong>
                    </div>

                    <div>
                        <span>Production Time</span>

                        <strong>
                            ${escapeHtml(
                                product.production_time
                                || "-"
                            )}
                        </strong>
                    </div>
                </div>
            </section>

            <section class="panel">
                <h3>Asset Library</h3>

                <div class="upload-box">
                    <input
                        id="assetFiles"
                        type="file"
                        multiple
                        accept="
                            image/*,
                            video/mp4,
                            video/webm,
                            video/quicktime,
                            audio/*
                        "
                    >

                    <button
                        id="uploadButton"
                        class="button primary"
                        onclick="uploadAssets()"
                    >
                        Upload Foto / Raw Video / Audio
                    </button>

                    <p>
                        Maksimal
                        ${escapeHtml(
                            data.limits.max_upload_mb
                        )}
                        MB per file dan 20 file
                        per proses.
                    </p>
                </div>

                <div class="image-variation-box">
                    <div class="voiceover-heading">
                        <strong>
                            Generate Image Variations
                        </strong>

                        <span class="voiceover-status">
                            Background berubah, produk tetap
                        </span>
                    </div>

                    <div class="image-variation-controls">
                        <div class="field">
                            <label>Source Image</label>
                            <select id="imageVariationSource">
                                ${imageVariationSourceOptions(data)}
                            </select>
                        </div>

                        <div class="field">
                            <label>Jumlah</label>
                            <input
                                id="imageVariationCount"
                                type="number"
                                min="1"
                                max="10"
                                value="10"
                            >
                        </div>

                        <div class="field">
                            <label>Preset</label>
                            <select id="imageVariationPreset">
                                <option value="background_only">
                                    Background Only
                                </option>
                                <option value="lifestyle_desk">
                                    Lifestyle Desk
                                </option>
                                <option value="hand_holding">
                                    Hand Holding
                                </option>
                                <option value="gift_display">
                                    Gift Display
                                </option>
                                <option value="macro_detail">
                                    Macro Detail
                                </option>
                                <option value="marketplace_clean">
                                    Marketplace Clean
                                </option>
                                <option value="social_ads_hero">
                                    Social Ads Hero
                                </option>
                            </select>
                        </div>

                        <button
                            id="generateImageVariationsButton"
                            class="mini-button"
                            onclick="generateImageVariations()"
                            type="button"
                        >
                            Generate
                        </button>
                    </div>

                    <input
                        id="imageVariationPrompt"
                        class="image-variation-prompt"
                        placeholder="Opsional: contoh background pastel, meja kayu, cahaya pagi"
                    >

                    <p class="voiceover-help">
                        Pilih foto source yang paling akurat. AI hanya boleh mengubah latar, lighting, surface, dan properti sekitar.
                    </p>
                </div>

                <div class="asset-grid">
                    ${sourceMedia
                        .map(sourceMediaCard)
                        .join("")}

                    ${assets
                        .map(uploadedAssetCard)
                        .join("")}

                    ${
                        !sourceMedia.length
                        && !assets.length
                        ? `
                            <div class="empty">
                                Belum ada asset.
                            </div>
                        `
                        : ""
                    }
                </div>
            </section>

            <section class="panel full raw-video-library-panel">
                <div class="raw-video-library-head">
                    <div>
                        <h3>Raw Product Videos</h3>
                        <p>
                            Upload video produk asli untuk digunakan
                            pada Catalog Ads.
                        </p>
                    </div>

                    <div class="raw-video-upload-actions">
                        <input
                            id="rawVideoFiles"
                            type="file"
                            multiple
                            accept="
                                video/mp4,
                                video/webm,
                                video/quicktime
                            "
                        >

                        <button
                            id="uploadRawVideoButton"
                            type="button"
                            class="button primary"
                            onclick="uploadRawVideos()"
                        >
                            Upload Raw Video
                        </button>
                    </div>
                </div>

                <div
                    id="rawVideoLibraryStatus"
                    class="status"
                ></div>

                <div
                    id="rawVideoLibrary"
                    class="raw-video-library-grid"
                >
                    <div class="empty">
                        Memuat raw video...
                    </div>
                </div>
            </section>


            <section class="panel full">
                <h3>Product Information</h3>

                <p>
                    ${escapeHtml(
                        product.short_description
                        || product.description
                        || "Belum ada deskripsi."
                    )}
                </p>
            </section>

            

        </div>
    `;
}


async function openWorkspace(productId) {
    state.activeProductId =
        Number(productId);

    modal.classList.remove("hidden");
    document.body.style.overflow =
        "hidden";

    workspaceTitle.textContent =
        "Memuat workspace...";

    workspaceSubtitle.textContent = "";
    workspaceContent.innerHTML = "";
    workspaceStatus.textContent =
        "Mengambil data produk...";

    try {
        const data = await api(
            `/api/products/${productId}/workspace`
        );

        workspaceStatus.textContent = "";
        state.workspace = data;
        renderWorkspace(data);
        await loadWorkspaceRawVideoLibrary(productId);
        await loadCampaigns(productId);
        await loadVoiceOptions();
        startCampaignPolling();

    } catch (error) {
        workspaceStatus.textContent =
            `Gagal membuka workspace: `
            + error.message;
    }
}


function closeWorkspace() {
    modal.classList.add("hidden");
    document.body.style.overflow = "";
    state.activeProductId = null;
    state.workspace = null;
    state.expandedCampaignIds.clear();
    stopCampaignPolling();
    startCampaignPolling();
}


function rawVideoOrientationLabel(value) {
    const labels = {
        portrait: "Portrait",
        landscape: "Landscape",
        square: "Square",
    };

    return labels[value] || "Tidak diketahui";
}


function rawVideoMetadata(video) {
    const parts = [];

    if (video.duration_seconds !== null
        && video.duration_seconds !== undefined) {
        parts.push(
            `${Number(video.duration_seconds).toFixed(1)} detik`
        );
    }

    if (video.width && video.height) {
        parts.push(
            `${video.width}×${video.height}`
        );
    }

    if (video.fps) {
        parts.push(
            `${Number(video.fps).toFixed(1)} fps`
        );
    }

    if (video.orientation) {
        parts.push(
            rawVideoOrientationLabel(
                video.orientation
            )
        );
    }

    if (video.has_audio) {
        parts.push("Ada audio");
    } else {
        parts.push("Tanpa audio");
    }

    return parts.join(" • ");
}


function rawVideoSizeLabel(bytes) {
    const value = Number(bytes || 0);

    if (!value) return "-";

    if (value >= 1024 * 1024) {
        return (
            value / 1024 / 1024
        ).toFixed(1) + " MB";
    }

    return (
        value / 1024
    ).toFixed(1) + " KB";
}


function rawVideoTypeOptions(
    selectedValue
) {
    const options = [
        ["hero", "Hero / Opening"],
        ["demo", "Demo Produk"],
        ["detail", "Detail Produk"],
        ["lifestyle", "Lifestyle"],
        ["packaging", "Packaging"],
        ["testimonial", "Testimonial"],
    ];

    return options.map(([value, label]) => `
        <option
            value="${value}"
            ${selectedValue === value
                ? "selected"
                : ""}
        >
            ${label}
        </option>
    `).join("");
}



function rawVideoFitModeOptions(
    selectedValue = "auto"
) {
    const options = [
        ["auto", "Auto Smart Layout"],
        ["blur_fill", "Blur Fill"],
        ["cover", "Cover / Full Frame"],
        ["contain", "Contain / Tidak Terpotong"],
    ];

    return options.map(([value, label]) => `
        <option
            value="${value}"
            ${selectedValue === value
                ? "selected"
                : ""}
        >
            ${label}
        </option>
    `).join("");
}



function workspaceRawVideoCard(video) {
    const assetId = Number(
        video.asset_id
    );

    const trimStart = Number(
        video.trim_start || 0
    );

    const trimEnd = (
        video.trim_end !== null
        && video.trim_end !== undefined
        ? Number(video.trim_end)
        : ""
    );

    const primaryBadge = video.is_primary
        ? `
            <span class="raw-video-primary-badge">
                Video Utama
            </span>
        `
        : "";

    return `
        <article
            class="raw-video-card
                ${video.is_primary
                    ? "is-primary"
                    : ""}"
            data-asset-id="${assetId}"
        >
            <div class="raw-video-preview-wrap">
                <video
                    class="raw-video-preview"
                    src="${escapeHtml(video.url)}"
                    controls
                    preload="metadata"
                    playsinline
                ></video>

                ${primaryBadge}
            </div>

            <div class="raw-video-card-body">
                <strong
                    title="${escapeHtml(
                        video.title
                        || video.label
                        || "Raw Video"
                    )}"
                >
                    ${escapeHtml(
                        video.title
                        || video.label
                        || "Raw Video"
                    )}
                </strong>

                <small>
                    ${escapeHtml(
                        rawVideoMetadata(video)
                    )}
                </small>

                <small>
                    ${escapeHtml(
                        rawVideoSizeLabel(
                            video.size_bytes
                        )
                    )}
                </small>

                <div class="raw-video-setting-grid">
                    <label>
                        <span>Tipe video</span>

                        <select
                            id="rawVideoType-${assetId}"
                        >
                            ${rawVideoTypeOptions(
                                video.video_type
                                || "demo"
                            )}
                        </select>
                    </label>

                    <label>
                        <span>Layout video</span>

                        <select
                            id="rawVideoFitMode-${assetId}"
                        >
                            ${rawVideoFitModeOptions(
                                video.fit_mode
                                || "auto"
                            )}
                        </select>
                    </label>

                    <label>
                        <span>Trim mulai</span>

                        <input
                            id="rawVideoTrimStart-${assetId}"
                            type="number"
                            min="0"
                            step="0.1"
                            value="${trimStart}"
                        >
                    </label>

                    <label>
                        <span>Trim selesai</span>

                        <input
                            id="rawVideoTrimEnd-${assetId}"
                            type="number"
                            min="0"
                            step="0.1"
                            value="${trimEnd}"
                            placeholder="Sampai akhir"
                        >
                    </label>

                    <label
                        class="raw-video-primary-toggle"
                    >
                        <input
                            id="rawVideoPrimary-${assetId}"
                            type="checkbox"
                            ${video.is_primary
                                ? "checked"
                                : ""}
                        >

                        <span>Jadikan video utama</span>
                    </label>
                </div>

                <div class="raw-video-card-actions">
                    <button
                        type="button"
                        class="mini-button primary"
                        onclick="saveRawVideoSettings(
                            ${assetId}
                        )"
                    >
                        Simpan
                    </button>

                    <a
                        class="mini-button"
                        href="${escapeHtml(video.url)}"
                        target="_blank"
                        rel="noopener"
                    >
                        Buka
                    </a>

                    <button
                        type="button"
                        class="mini-button danger"
                        onclick="deleteRawVideo(
                            ${assetId}
                        )"
                    >
                        Hapus
                    </button>
                </div>

                <div
                    id="rawVideoSettingStatus-${assetId}"
                    class="raw-video-setting-status"
                ></div>
            </div>
        </article>
    `;
}


async function saveRawVideoSettings(
    assetId
) {
    const typeInput =
        document.getElementById(
            `rawVideoType-${assetId}`
        );

    const fitModeInput =
        document.getElementById(
            `rawVideoFitMode-${assetId}`
        );

    const trimStartInput =
        document.getElementById(
            `rawVideoTrimStart-${assetId}`
        );

    const trimEndInput =
        document.getElementById(
            `rawVideoTrimEnd-${assetId}`
        );

    const primaryInput =
        document.getElementById(
            `rawVideoPrimary-${assetId}`
        );

    const status =
        document.getElementById(
            `rawVideoSettingStatus-${assetId}`
        );

    if (
        !typeInput
        || !fitModeInput
        || !trimStartInput
        || !trimEndInput
        || !primaryInput
    ) {
        return;
    }

    const trimStart = Number(
        trimStartInput.value || 0
    );

    const trimEnd = (
        trimEndInput.value.trim()
        ? Number(trimEndInput.value)
        : null
    );

    if (
        trimEnd !== null
        && trimEnd <= trimStart
    ) {
        if (status) {
            status.textContent =
                "Trim selesai harus lebih besar "
                + "daripada trim mulai.";
        }

        return;
    }

    const payload = {
        video_type: typeInput.value,
        fit_mode: fitModeInput.value || "auto",
        is_primary: primaryInput.checked,
        trim_start: trimStart,
        trim_end: trimEnd,
    };

    if (status) {
        status.textContent =
            "Menyimpan pengaturan...";
    }

    try {
        const data = await api(
            `/api/products/`
            + `${state.activeProductId}`
            + `/raw-videos/${assetId}/settings`,
            {
                method: "PUT",
                headers: {
                    "Content-Type":
                        "application/json",
                },
                body: JSON.stringify(payload),
            }
        );

        if (status) {
            status.textContent =
                data.message;
        }

        delete state.rawVideosByProduct[
            Number(state.activeProductId)
        ];

        await loadWorkspaceRawVideoLibrary(
            state.activeProductId
        );

    } catch (error) {
        if (status) {
            status.textContent =
                `Gagal menyimpan: ${error.message}`;
        }
    }
}


async function loadWorkspaceRawVideoLibrary(
    productId = state.activeProductId
) {
    const target =
        document.getElementById(
            "rawVideoLibrary"
        );

    const status =
        document.getElementById(
            "rawVideoLibraryStatus"
        );

    if (!target || !productId) return;

    target.innerHTML = `
        <div class="empty">
            Memuat raw video...
        </div>
    `;

    try {
        delete state.rawVideosByProduct[
            Number(productId)
        ];

        const videos =
            await loadRawVideosForProduct(
                Number(productId)
            );

        if (!videos.length) {
            target.innerHTML = `
                <div class="empty">
                    Belum ada raw video.
                    Upload MP4, MOV, atau WebM.
                </div>
            `;

            if (status) {
                status.textContent =
                    "Belum ada video produk.";
            }

            return;
        }

        target.innerHTML = videos
            .map(workspaceRawVideoCard)
            .join("");

        if (status) {
            status.textContent =
                `${videos.length} raw video tersedia.`;
        }

    } catch (error) {
        target.innerHTML = `
            <div class="empty">
                Gagal memuat raw video:
                ${escapeHtml(error.message)}
            </div>
        `;

        if (status) {
            status.textContent =
                `Gagal memuat: ${error.message}`;
        }
    }
}


async function uploadRawVideos() {
    const input =
        document.getElementById(
            "rawVideoFiles"
        );

    const button =
        document.getElementById(
            "uploadRawVideoButton"
        );

    const status =
        document.getElementById(
            "rawVideoLibraryStatus"
        );

    if (!input || !input.files.length) {
        if (status) {
            status.textContent =
                "Pilih file video terlebih dahulu.";
        }
        return;
    }

    const files = [...input.files];

    const invalid = files.find(file =>
        !(
            file.type === "video/mp4"
            || file.type === "video/webm"
            || file.type === "video/quicktime"
            || /\.(mp4|mov|webm)$/i.test(file.name)
        )
    );

    if (invalid) {
        if (status) {
            status.textContent =
                `File bukan video yang didukung: `
                + invalid.name;
        }
        return;
    }

    const formData = new FormData();

    files.forEach(file => {
        formData.append("files", file);
    });

    button.disabled = true;
    button.textContent = "Mengunggah...";

    if (status) {
        status.textContent =
            `Mengunggah ${files.length} video...`;
    }

    try {
        const data = await api(
            `/api/products/`
            + `${state.activeProductId}/assets`,
            {
                method: "POST",
                body: formData,
            }
        );

        if (status) {
            status.textContent =
                data.message;
        }

        input.value = "";

        delete state.rawVideosByProduct[
            Number(state.activeProductId)
        ];

        await loadWorkspaceRawVideoLibrary(
            state.activeProductId
        );

        await loadHealth();

    } catch (error) {
        if (status) {
            status.textContent =
                `Upload video gagal: `
                + error.message;
        }

    } finally {
        button.disabled = false;
        button.textContent =
            "Upload Raw Video";
    }
}


async function deleteRawVideo(assetId) {
    if (!confirm(
        "Hapus raw video ini?"
    )) {
        return;
    }

    const status =
        document.getElementById(
            "rawVideoLibraryStatus"
        );

    if (status) {
        status.textContent =
            "Menghapus raw video...";
    }

    try {
        const data = await api(
            `/api/assets/${assetId}`,
            {
                method: "DELETE",
            }
        );

        if (status) {
            status.textContent =
                data.message;
        }

        delete state.rawVideosByProduct[
            Number(state.activeProductId)
        ];

        await loadWorkspaceRawVideoLibrary(
            state.activeProductId
        );

        await loadHealth();

    } catch (error) {
        if (status) {
            status.textContent =
                `Gagal menghapus video: `
                + error.message;
        }
    }
}



async function uploadAssets() {
    const input =
        document.getElementById("assetFiles");

    const button =
        document.getElementById("uploadButton");

    if (!input.files.length) {
        workspaceStatus.textContent =
            "Pilih file terlebih dahulu.";
        return;
    }

    const formData = new FormData();

    for (const file of input.files) {
        formData.append("files", file);
    }

    button.disabled = true;
    button.textContent =
        "Mengunggah...";

    workspaceStatus.textContent =
        `Mengunggah ${input.files.length} file...`;

    try {
        const data = await api(
            `/api/products/`
            + `${state.activeProductId}/assets`,
            {
                method: "POST",
                body: formData,
            }
        );

        workspaceStatus.textContent =
            data.message;

        await openWorkspace(
            state.activeProductId
        );

        await loadHealth();

    } catch (error) {
        workspaceStatus.textContent =
            `Upload gagal: ${error.message}`;

    } finally {
        button.disabled = false;
        button.textContent =
            "Upload Foto / Raw Video / Audio";
    }
}


async function generateImageVariations() {
    const source =
        document.getElementById(
            "imageVariationSource"
        );

    const count =
        document.getElementById(
            "imageVariationCount"
        );

    const preset =
        document.getElementById(
            "imageVariationPreset"
        );

    const prompt =
        document.getElementById(
            "imageVariationPrompt"
        );

    const button =
        document.getElementById(
            "generateImageVariationsButton"
        );

    if (!source?.value) {
        workspaceStatus.textContent =
            "Pilih source image terlebih dahulu.";
        return;
    }

    const [sourceKind, sourceValue = ""] =
        source.value.split("|");

    const payload = {
        source_kind: sourceKind,
        count: Number(count.value || 10),
        preset: preset.value,
        custom_prompt:
            prompt.value.trim() || null,
    };

    if (sourceKind === "asset") {
        payload.source_asset_id =
            Number(sourceValue);
    } else if (sourceKind === "url") {
        payload.source_url =
            decodeURIComponent(sourceValue);
    }

    button.disabled = true;
    button.textContent = "Generating...";
    workspaceStatus.textContent =
        `Membuat ${payload.count} image variation...`;

    try {
        const data = await api(
            `/api/products/`
            + `${state.activeProductId}`
            + `/image-variations`,
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json",
                },
                body: JSON.stringify(payload),
            }
        );

        workspaceStatus.textContent =
            data.message;

        await openWorkspace(
            state.activeProductId
        );

        await loadHealth();

    } catch (error) {
        workspaceStatus.textContent =
            `Generate image gagal: ${error.message}`;

    } finally {
        button.disabled = false;
        button.textContent = "Generate";
    }
}


async function deleteAsset(assetId) {
    if (!confirm("Hapus asset ini?")) {
        return;
    }

    workspaceStatus.textContent =
        "Menghapus asset...";

    try {
        const data = await api(
            `/api/assets/${assetId}`,
            {
                method: "DELETE",
            }
        );

        workspaceStatus.textContent =
            data.message;

        await openWorkspace(
            state.activeProductId
        );

        await loadHealth();

    } catch (error) {
        workspaceStatus.textContent =
            `Gagal menghapus: `
            + error.message;
    }
}


searchButton.addEventListener(
    "click",
    loadProducts
);

searchInput.addEventListener(
    "keydown",
    event => {
        if (event.key === "Enter") {
            loadProducts();
        }
    }
);

syncButton.addEventListener(
    "click",
    syncProducts
);

logoutButton.addEventListener(
    "click",
    logout
);

multiProductMenuButton?.addEventListener(
    "click",
    () => {
        loadMultiVoiceOptions();
        loadCatalogMusicLibrary();
        multiProductSection?.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
    }
);

generateMultiCampaignButton?.addEventListener(
    "click",
    generateMultiProductCampaign
);

document.addEventListener(
    "keydown",
    event => {
        if (event.key === "Escape") {
            closeWorkspace();
        }
    }
);

window.openWorkspace = openWorkspace;
window.closeWorkspace = closeWorkspace;
window.uploadAssets = uploadAssets;
window.uploadRawVideos = uploadRawVideos;
window.deleteRawVideo = deleteRawVideo;
window.saveRawVideoSettings = saveRawVideoSettings;
window.deleteAsset = deleteAsset;
window.generateImageVariations =
    generateImageVariations;

loadHealth();
loadProducts();
loadMultiVoiceOptions();


let campaignPollTimer = null;

function campaignProgress(campaign) {
    if (!campaign.variations) return 0;
    return Math.round(((campaign.completed_count + campaign.failed_count) / campaign.variations) * 100);
}


function campaignTemplateLabel(
    settings = {}
) {
    const labels = {
        custom_manual: "Custom Manual",
        retail_fast: "Retail Cepat Closing",
        bundle_hemat: "Bundle Hemat",
        reseller: "Reseller",
        flash_sale: "Flash Sale",
        product_showcase: "Product Showcase",
    };

    return (
        settings.creative_template_label
        || labels[
            settings.creative_template
        ]
        || "Custom Manual"
    );
}



function campaignAudienceLabel(settings = {}) {
    const labels = {
        retail: "Retail",
        retail_bulk: "Bundle Hemat",
        reseller: "Reseller",
        custom_bulk: "Custom/Bulk",
    };

    return labels[settings.audience] || "Retail";
}

function campaignCard(campaign) {
    const productCount = Number(campaign.settings?.product_count || 1);
    const productLabel = productCount > 1
        ? ` | ${productCount} produk`
        : "";
    return `
        <article class="campaign-card">
            <div class="campaign-head">
                <div><h5>${escapeHtml(campaign.name)}</h5><small>${escapeHtml(campaignTemplateLabel(campaign.settings || {}))} | ${escapeHtml(campaignAudienceLabel(campaign.settings || {}))}${productLabel} | ${escapeHtml(campaign.status)} | ${campaign.completed_count}/${campaign.variations} selesai | ${campaign.failed_count} gagal${campaign.settings?.voiceover_enabled ? " | VO ElevenLabs" : ""}</small></div>
                <strong>${campaignProgress(campaign)}%</strong>
            </div>
            <div class="progress"><span style="width:${campaignProgress(campaign)}%"></span></div>
            <div class="campaign-actions">
                <button type="button" class="mini-button" onclick="viewCampaign(${campaign.id}, event)">Lihat Hasil</button>
                ${campaign.failed_count ? `<button type="button" class="mini-button" onclick="retryCampaign(${campaign.id}, event)">Retry Gagal</button>` : ''}
                <button type="button" class="mini-button" onclick="deleteCampaign(${campaign.id}, event)">Hapus</button>
            </div>
            <div id="campaignJobs-${campaign.id}" class="render-grid"></div>
        </article>`;
}

async function loadCampaigns(productId = state.activeProductId) {
    if (!productId || !document.getElementById('campaignList')) return;
    try {
        const data = await api(`/api/products/${productId}/campaigns`);
        document.getElementById('campaignList').innerHTML = data.campaigns.length ? data.campaigns.map(campaignCard).join('') : '<div class="empty">Belum ada campaign render.</div>';
        await restoreExpandedCampaigns();
    } catch (error) {
        document.getElementById('campaignMessage').textContent = `Gagal memuat campaign: ${error.message}`;
    }
}

async function generateCampaign() {
    const button = document.getElementById('generateCampaignButton');
    const message = document.getElementById('campaignMessage');
    button.disabled = true;
    button.textContent = 'Membuat Antrean...';
    message.textContent = 'Menyiapkan variasi creative dan antrean FFmpeg...';
    try {
        const payload = {
            name: document.getElementById('campaignName').value.trim() || null,
            variations: Number(document.getElementById('campaignVariations').value),
            audience: document.getElementById('campaignAudience').value,
            min_order_qty: Number(document.getElementById('campaignMinOrderQty').value || 6),
            duration_seconds: Number(document.getElementById('campaignDuration').value),
            aspect_ratio: document.getElementById('campaignAspect').value,
            render_mode: document.getElementById('campaignRenderMode').value || "slideshow",
            voiceover_enabled: document.getElementById('campaignVoiceoverEnabled').checked,
            voice_id: document.getElementById('campaignVoiceId').value || null,
            voiceover_mode: document.getElementById('campaignVoiceMode').value,
            voiceover_text: document.getElementById('campaignVoiceText').value.trim() || null,
        };
        const data = await api(`/api/products/${state.activeProductId}/campaigns`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
        message.textContent = data.message;
        await loadCampaigns();
        startCampaignPolling();
    } catch (error) {
        message.textContent = `Generate gagal: ${error.message}`;
    } finally {
        button.disabled = false;
        button.textContent = 'Generate Video';
    }
}



function selectedCampaignProductIds() {
    const ids = [];
    document.querySelectorAll(".campaignProductCheckbox").forEach(input => {
        const id = Number(input.value);
        if (input.checked && id && !ids.includes(id)) {
            ids.push(id);
        }
    });
    return ids;
}

function selectedCampaignProductClips() {
    return selectedCatalogOrder().map(
        productId => {
            const select =
                document.querySelector(
                    `.campaignRawVideoSelect`
                    + `[data-product-id="${productId}"]`
                );

            const clipId =
                select?.value || "";

            const selectedVideo =
                selectedRawVideoForProduct(
                    productId
                );

            return {
                product_id: productId,
                clip_id: clipId,
                trim_start: Number(
                    selectedVideo?.trim_start
                    || 0
                ),
                trim_end: (
                    selectedVideo?.trim_end
                    ?? null
                ),
                video_type: (
                    selectedVideo?.video_type
                    || "demo"
                ),
                fit_mode: (
                    selectedVideo?.fit_mode
                    || "auto"
                ),
            };
        }
    );
}

async function selectVisibleCampaignProducts() {
    const inputs = [
        ...document.querySelectorAll(
            ".campaignProductCheckbox"
        )
    ];

    let selectedCount = 0;

    for (const input of inputs) {
        if (selectedCount >= 6) {
            input.checked = false;
            continue;
        }

        input.checked = true;
        selectedCount += 1;

        await toggleCampaignProductRaw(input);
    }
}


function musicSizeLabel(bytes) {
    const value = Number(bytes || 0);

    if (!value) return "0 MB";

    return (
        `${(value / 1024 / 1024).toFixed(1)} MB`
    );
}


function musicDurationLabel(seconds) {
    const value = Number(seconds || 0);

    if (!Number.isFinite(value) || value <= 0) {
        return "Durasi tidak diketahui";
    }

    const minutes = Math.floor(value / 60);
    const remainder = Math.round(value % 60);

    return (
        `${minutes}:${String(remainder).padStart(2, "0")}`
    );
}


function renderCatalogMusicLibrary() {
    const target = document.getElementById(
        "catalogMusicLibrary"
    );

    const select = document.getElementById(
        "multiCampaignMusicId"
    );

    if (!target || !select) return;

    const selectedValue = select.value;
    const music = state.musicLibrary || [];

    select.innerHTML = music.length
        ? (
            '<option value="">Pilih musik...</option>'
            + music.map(item => `
                <option
                    value="${escapeHtml(item.music_id)}"
                >
                    ${escapeHtml(item.title)}
                    •
                    ${escapeHtml(
                        musicDurationLabel(
                            item.duration_seconds
                        )
                    )}
                </option>
            `).join("")
        )
        : `
            <option value="">
                Belum ada musik
            </option>
        `;

    if (
        selectedValue
        && music.some(
            item =>
                item.music_id === selectedValue
        )
    ) {
        select.value = selectedValue;
    }

    target.innerHTML = music.length
        ? music.map(item => `
            <article class="catalog-music-item">
                <div>
                    <strong>
                        ${escapeHtml(item.title)}
                    </strong>

                    <small>
                        ${escapeHtml(
                            musicDurationLabel(
                                item.duration_seconds
                            )
                        )}
                        •
                        ${escapeHtml(
                            musicSizeLabel(
                                item.size_bytes
                            )
                        )}
                    </small>
                </div>

                <audio
                    src="${escapeHtml(item.url)}"
                    controls
                    preload="metadata"
                ></audio>

                <button
                    type="button"
                    class="mini-button danger"
                    onclick="
                        deleteCatalogMusic(
                            '${escapeHtml(item.music_id)}'
                        )
                    "
                >
                    Hapus
                </button>
            </article>
        `).join("")
        : `
            <div class="empty compact">
                Belum ada background music.
            </div>
        `;

    toggleMusicControls();
}


async function loadCatalogMusicLibrary() {
    const status = document.getElementById(
        "catalogMusicStatus"
    );

    try {
        const data = await api(
            "/api/music-library"
        );

        state.musicLibrary =
            data.music || [];

        renderCatalogMusicLibrary();

        if (status) {
            status.textContent =
                `${state.musicLibrary.length} musik tersedia.`;
        }

    } catch (error) {
        if (status) {
            status.textContent =
                `Gagal memuat musik: ${error.message}`;
        }
    }
}


function toggleMusicControls() {
    const enabled = Boolean(
        document.getElementById(
            "multiCampaignMusicEnabled"
        )?.checked
    );

    const controls = document.getElementById(
        "multiMusicControls"
    );

    const select = document.getElementById(
        "multiCampaignMusicId"
    );

    const volume = document.getElementById(
        "multiCampaignMusicVolume"
    );

    const ducking = document.getElementById(
        "multiCampaignMusicDucking"
    );

    controls?.classList.toggle(
        "voiceover-disabled",
        !enabled
    );

    if (select) select.disabled = !enabled;
    if (volume) volume.disabled = !enabled;
    if (ducking) ducking.disabled = !enabled;

    if (!enabled) {
        const preview = document.getElementById(
            "catalogMusicPreview"
        );

        if (preview) {
            preview.pause();
        }
    }
}


function updateMusicVolumeLabel() {
    const input = document.getElementById(
        "multiCampaignMusicVolume"
    );

    const label = document.getElementById(
        "musicVolumeLabel"
    );

    if (input && label) {
        label.textContent =
            `${Number(input.value || 22)}%`;
    }
}


function previewSelectedMusic() {
    const select = document.getElementById(
        "multiCampaignMusicId"
    );

    const preview = document.getElementById(
        "catalogMusicPreview"
    );

    if (!select || !preview) return;

    const item = (
        state.musicLibrary || []
    ).find(
        music =>
            music.music_id === select.value
    );

    preview.pause();

    if (!item?.url) {
        preview.removeAttribute("src");
        preview.load();
        return;
    }

    preview.src = item.url;
    preview.load();
}


async function uploadCatalogMusic() {
    const input = document.getElementById(
        "catalogMusicFiles"
    );

    const button = document.getElementById(
        "uploadCatalogMusicButton"
    );

    const status = document.getElementById(
        "catalogMusicStatus"
    );

    if (!input?.files?.length) {
        if (status) {
            status.textContent =
                "Pilih file musik terlebih dahulu.";
        }
        return;
    }

    const formData = new FormData();

    [...input.files].forEach(file => {
        formData.append("files", file);
    });

    button.disabled = true;
    button.textContent = "Mengunggah...";

    try {
        const data = await api(
            "/api/music-library",
            {
                method: "POST",
                body: formData,
            }
        );

        input.value = "";

        if (status) {
            status.textContent = data.message;
        }

        await loadCatalogMusicLibrary();

    } catch (error) {
        if (status) {
            status.textContent =
                `Upload musik gagal: ${error.message}`;
        }

    } finally {
        button.disabled = false;
        button.textContent = "Upload Musik";
    }
}


async function deleteCatalogMusic(
    musicId
) {
    if (!confirm(
        "Hapus musik ini dari library?"
    )) {
        return;
    }

    const status = document.getElementById(
        "catalogMusicStatus"
    );

    try {
        const data = await api(
            `/api/music-library/${musicId}`,
            {
                method: "DELETE",
            }
        );

        if (status) {
            status.textContent = data.message;
        }

        await loadCatalogMusicLibrary();

    } catch (error) {
        if (status) {
            status.textContent =
                `Gagal menghapus musik: ${error.message}`;
        }
    }
}





const EXPORT_PRESETS = {
    meta_reels: {
        label: "Meta Reels",
        aspect: "9:16",
        resolution: "720×1280",
        fps: 30,
        videoCodec: "H.264",
        audioCodec: "AAC",
    },

    tiktok: {
        label: "TikTok",
        aspect: "9:16",
        resolution: "720×1280",
        fps: 30,
        videoCodec: "H.264",
        audioCodec: "AAC",
    },

    instagram_feed: {
        label: "Instagram Feed",
        aspect: "1:1",
        resolution: "1080×1080",
        fps: 30,
        videoCodec: "H.264",
        audioCodec: "AAC",
    },

    youtube_landscape: {
        label: "YouTube Landscape",
        aspect: "16:9",
        resolution: "1280×720",
        fps: 30,
        videoCodec: "H.264",
        audioCodec: "AAC",
    },

    custom: {
        label: "Custom",
        aspect: null,
        resolution: "Mengikuti format",
        fps: 30,
        videoCodec: "H.264",
        audioCodec: "AAC",
    },
};


function applyExportPreset() {
    const presetSelect = document.getElementById(
        "multiCampaignExportPreset"
    );

    const aspectSelect = document.getElementById(
        "multiCampaignAspect"
    );

    if (!presetSelect || !aspectSelect) {
        return;
    }

    const preset =
        EXPORT_PRESETS[presetSelect.value]
        || EXPORT_PRESETS.custom;

    if (preset.aspect) {
        aspectSelect.value = preset.aspect;
    }

    renderCatalogPreflight();
}


function syncExportPresetFromAspect(
    aspect
) {
    const select = document.getElementById(
        "multiCampaignExportPreset"
    );

    if (!select) return;

    const current =
        EXPORT_PRESETS[select.value];

    if (
        current
        && current.aspect === aspect
    ) {
        return;
    }

    if (aspect === "1:1") {
        select.value = "instagram_feed";
    } else if (aspect === "16:9") {
        select.value = "youtube_landscape";
    } else {
        select.value = "meta_reels";
    }
}


function exportPresetLabel(
    presetKey
) {
    return (
        EXPORT_PRESETS[presetKey]?.label
        || "Custom"
    );
}



const CREATIVE_TEMPLATE_PRESETS = {
    retail_fast: {
        label: "Retail Cepat Closing",
        description:
            "Iklan singkat dengan CTA langsung untuk mendorong pembelian cepat.",
        audience: "retail",
        duration: 20,
        variations: 3,
        aspect: "9:16",
        promoEnabled: false,
        promoMinAmount: 100000,
        promoDiscount: 10,
        promoText: "",
        voiceoverEnabled: true,
        voiceoverMode: "auto",
        musicEnabled: true,
        musicVolume: 18,
        musicDucking: true,
    },

    bundle_hemat: {
        label: "Bundle Hemat",
        description:
            "Menawarkan beberapa produk sebagai pilihan satuan atau bundle hemat.",
        audience: "retail_bulk",
        duration: 25,
        variations: 5,
        aspect: "9:16",
        promoEnabled: true,
        promoMinAmount: 100000,
        promoDiscount: 10,
        promoText: "",
        voiceoverEnabled: true,
        voiceoverMode: "auto",
        musicEnabled: true,
        musicVolume: 22,
        musicDucking: true,
    },

    reseller: {
        label: "Reseller",
        description:
            "Menonjolkan peluang jual ulang, katalog produk, dan harga reseller.",
        audience: "reseller",
        duration: 30,
        variations: 4,
        aspect: "9:16",
        promoEnabled: false,
        promoMinAmount: 100000,
        promoDiscount: 10,
        promoText: "",
        voiceoverEnabled: true,
        voiceoverMode: "auto",
        musicEnabled: true,
        musicVolume: 18,
        musicDucking: true,
    },

    flash_sale: {
        label: "Flash Sale",
        description:
            "Iklan cepat dengan promo kuat, urgensi, dan CTA terbatas waktu.",
        audience: "retail_bulk",
        duration: 20,
        variations: 5,
        aspect: "9:16",
        promoEnabled: true,
        promoMinAmount: 75000,
        promoDiscount: 15,
        promoText:
            "Flash Sale: Diskon 15% untuk pembelian hari ini",
        voiceoverEnabled: true,
        voiceoverMode: "auto",
        musicEnabled: true,
        musicVolume: 25,
        musicDucking: true,
    },

    product_showcase: {
        label: "Product Showcase",
        description:
            "Fokus pada visual dan detail produk dengan musik tanpa narasi panjang.",
        audience: "retail",
        duration: 25,
        variations: 3,
        aspect: "9:16",
        promoEnabled: false,
        promoMinAmount: 100000,
        promoDiscount: 10,
        promoText: "",
        voiceoverEnabled: false,
        voiceoverMode: "auto",
        musicEnabled: true,
        musicVolume: 28,
        musicDucking: false,
    },

    custom_manual: {
        label: "Custom Manual",
        description:
            "Semua pengaturan dapat diubah secara manual.",
    },
};


function templateElement(id) {
    return document.getElementById(id);
}


function setTemplateValue(
    id,
    value
) {
    const element = templateElement(id);

    if (!element) return;

    if (element.type === "checkbox") {
        element.checked = Boolean(value);
    } else {
        element.value = String(value);
    }
}


function selectFirstAvailableMusic() {
    const select = templateElement(
        "multiCampaignMusicId"
    );

    if (
        !select
        || !(state.musicLibrary || []).length
    ) {
        return false;
    }

    const currentExists = (
        state.musicLibrary || []
    ).some(
        item =>
            item.music_id === select.value
    );

    if (!currentExists) {
        select.value =
            state.musicLibrary[0].music_id;
    }

    previewSelectedMusic();
    return true;
}


function updateCreativeTemplateBadge(
    presetKey
) {
    const preset =
        CREATIVE_TEMPLATE_PRESETS[presetKey]
        || CREATIVE_TEMPLATE_PRESETS.custom_manual;

    const badge = templateElement(
        "creativeTemplateBadge"
    );

    const description = templateElement(
        "creativeTemplateDescription"
    );

    if (badge) {
        badge.textContent = preset.label;
        badge.dataset.template = presetKey;
    }

    if (description) {
        description.textContent =
            preset.description;
    }
}


function markCreativeTemplateManual() {
    const select = templateElement(
        "multiCampaignTemplate"
    );

    if (!select) return;

    if (select.value !== "custom_manual") {
        select.value = "custom_manual";
        updateCreativeTemplateBadge(
            "custom_manual"
        );
    }
}


function applyCreativeTemplate() {
    const select = templateElement(
        "multiCampaignTemplate"
    );

    const notice = templateElement(
        "creativeTemplateNotice"
    );

    if (!select) return;

    const presetKey =
        select.value || "custom_manual";

    const preset =
        CREATIVE_TEMPLATE_PRESETS[presetKey]
        || CREATIVE_TEMPLATE_PRESETS.custom_manual;

    updateCreativeTemplateBadge(
        presetKey
    );

    if (presetKey === "custom_manual") {
        if (notice) {
            notice.textContent =
                "Mode manual aktif. Semua field dapat disesuaikan.";
        }

        return;
    }

    setTemplateValue(
        "multiCampaignAudience",
        preset.audience
    );

    setTemplateValue(
        "multiCampaignDuration",
        preset.duration
    );

    setTemplateValue(
        "multiCampaignVariations",
        preset.variations
    );

    setTemplateValue(
        "multiCampaignAspect",
        preset.aspect
    );

    syncExportPresetFromAspect(
        preset.aspect
    );

    setTemplateValue(
        "multiCampaignPromoEnabled",
        preset.promoEnabled
    );

    setTemplateValue(
        "multiCampaignPromoMinAmount",
        preset.promoMinAmount
    );

    setTemplateValue(
        "multiCampaignPromoDiscount",
        preset.promoDiscount
    );

    setTemplateValue(
        "multiCampaignPromoText",
        preset.promoText
    );

    setTemplateValue(
        "multiCampaignVoiceMode",
        preset.voiceoverMode
    );

    const voiceCheckbox = templateElement(
        "multiCampaignVoiceoverEnabled"
    );

    const voiceCanBeEnabled = Boolean(
        preset.voiceoverEnabled
        && voiceoverConfigured
    );

    if (voiceCheckbox) {
        voiceCheckbox.checked =
            voiceCanBeEnabled;
    }

    const musicAvailable = Boolean(
        (state.musicLibrary || []).length
    );

    const musicCheckbox = templateElement(
        "multiCampaignMusicEnabled"
    );

    if (musicCheckbox) {
        musicCheckbox.checked = Boolean(
            preset.musicEnabled
            && musicAvailable
        );
    }

    setTemplateValue(
        "multiCampaignMusicVolume",
        preset.musicVolume
    );

    setTemplateValue(
        "multiCampaignMusicDucking",
        preset.musicDucking
    );

    if (
        preset.musicEnabled
        && musicAvailable
    ) {
        selectFirstAvailableMusic();
    }

    toggleMultiPromoControls();
    toggleMultiVoiceoverControls();
    toggleMultiCustomVoiceText();
    toggleMusicControls();
    updateMusicVolumeLabel();
    renderCatalogPreflight();

    const warnings = [];

    if (
        preset.voiceoverEnabled
        && !voiceoverConfigured
    ) {
        warnings.push(
            "Voice-over preset dinonaktifkan karena ElevenLabs belum tersedia."
        );
    }

    if (
        preset.musicEnabled
        && !musicAvailable
    ) {
        warnings.push(
            "Background music dinonaktifkan karena library musik masih kosong."
        );
    }

    if (notice) {
        notice.textContent = warnings.length
            ? warnings.join(" ")
            : (
                `${preset.label} diterapkan. `
                + "Field tetap dapat disesuaikan sebelum render."
            );

        notice.classList.toggle(
            "has-warning",
            warnings.length > 0
        );
    }
}


function resetCreativeTemplateManual() {
    const select = templateElement(
        "multiCampaignTemplate"
    );

    if (select) {
        select.value = "custom_manual";
    }

    updateCreativeTemplateBadge(
        "custom_manual"
    );

    const notice = templateElement(
        "creativeTemplateNotice"
    );

    if (notice) {
        notice.textContent =
            "Mode manual aktif. Pengaturan saat ini tidak dihapus.";
        notice.classList.remove(
            "has-warning"
        );
    }
}


function bindCreativeTemplateManualTracking() {
    const trackedIds = [
        "multiCampaignVariations",
        "multiCampaignAudience",
        "multiCampaignDuration",
        "multiCampaignAspect",
        "multiCampaignPromoEnabled",
        "multiCampaignPromoMinAmount",
        "multiCampaignPromoDiscount",
        "multiCampaignPromoText",
        "multiCampaignVoiceoverEnabled",
        "multiCampaignVoiceMode",
        "multiCampaignVoiceText",
        "multiCampaignMusicEnabled",
        "multiCampaignMusicId",
        "multiCampaignMusicVolume",
        "multiCampaignMusicDucking",
    ];

    trackedIds.forEach(id => {
        const element = templateElement(id);

        if (!element) return;

        element.addEventListener(
            "change",
            event => {
                if (
                    event.isTrusted
                    && templateElement(
                        "multiCampaignTemplate"
                    )?.value !== "custom_manual"
                ) {
                    markCreativeTemplateManual();

                    const notice = templateElement(
                        "creativeTemplateNotice"
                    );

                    if (notice) {
                        notice.textContent =
                            "Pengaturan diubah manual. Template berpindah ke Custom Manual.";
                    }
                }
            }
        );
    });
}



function buildAutomationCampaignPayload() {
    const productClips =
        selectedCampaignProductClips();

    const voiceEnabled = Boolean(
        document.getElementById(
            "multiCampaignVoiceoverEnabled"
        )?.checked
        && voiceoverConfigured
    );

    const promoEnabled = Boolean(
        document.getElementById(
            "multiCampaignPromoEnabled"
        )?.checked
    );

    const musicEnabled = Boolean(
        document.getElementById(
            "multiCampaignMusicEnabled"
        )?.checked
    );

    const musicId = (
        document.getElementById(
            "multiCampaignMusicId"
        )?.value || null
    );

    return {
        name:
            document.getElementById(
                "multiCampaignName"
            )?.value.trim()
            || null,

        creative_template:
            document.getElementById(
                "multiCampaignTemplate"
            )?.value
            || "custom_manual",

        variations: Number(
            document.getElementById(
                "multiCampaignVariations"
            )?.value || 1
        ),

        product_clips: productClips,

        audience:
            document.getElementById(
                "multiCampaignAudience"
            )?.value
            || "retail_bulk",

        min_order_qty: 6,

        duration_seconds: Number(
            document.getElementById(
                "multiCampaignDuration"
            )?.value || 25
        ),

        aspect_ratio:
            document.getElementById(
                "multiCampaignAspect"
            )?.value
            || "9:16",

        export_preset:
            document.getElementById(
                "multiCampaignExportPreset"
            )?.value
            || "meta_reels",

        promo_enabled: promoEnabled,

        promo_min_amount: Number(
            document.getElementById(
                "multiCampaignPromoMinAmount"
            )?.value || 100000
        ),

        promo_discount_percent: Number(
            document.getElementById(
                "multiCampaignPromoDiscount"
            )?.value || 10
        ),

        promo_text:
            document.getElementById(
                "multiCampaignPromoText"
            )?.value.trim()
            || null,

        music_enabled: musicEnabled,

        music_id:
            musicEnabled
                ? musicId
                : null,

        music_volume: Number(
            document.getElementById(
                "multiCampaignMusicVolume"
            )?.value || 22
        ) / 100,

        music_ducking: Boolean(
            document.getElementById(
                "multiCampaignMusicDucking"
            )?.checked
        ),

        voiceover_enabled:
            voiceEnabled,

        voice_id:
            voiceEnabled
                ? (
                    document.getElementById(
                        "multiCampaignVoiceId"
                    )?.value || null
                )
                : null,

        voiceover_mode:
            document.getElementById(
                "multiCampaignVoiceMode"
            )?.value
            || "auto",

        voiceover_text:
            document.getElementById(
                "multiCampaignVoiceText"
            )?.value.trim()
            || null,
    };
}


function automationDateLabel(value) {
    if (!value) return "Manual";

    const parsed = new Date(value);

    if (
        Number.isNaN(parsed.getTime())
    ) {
        return value;
    }

    return parsed.toLocaleString(
        "id-ID"
    );
}


function automationScheduleLabel(type) {
    const labels = {
        manual: "Manual",
        once: "Sekali",
        daily: "Setiap Hari",
        weekly: "Setiap Minggu",
    };

    return labels[type] || type;
}


function renderAutomationRules(rules) {
    const target = document.getElementById(
        "automationRuleList"
    );

    if (!target) return;

    if (!rules.length) {
        target.innerHTML = `
            <div class="automation-empty">
                Belum ada automation rule.
            </div>
        `;
        return;
    }

    target.innerHTML = rules.map(rule => {
        const summary =
            rule.campaign_summary || {};

        return `
            <article class="automation-rule-card">
                <div class="automation-rule-head">
                    <div>
                        <strong>
                            ${escapeHtml(rule.name)}
                        </strong>

                        <small>
                            ${escapeHtml(
                                automationScheduleLabel(
                                    rule.schedule_type
                                )
                            )}
                            •
                            ${escapeHtml(
                                automationDateLabel(
                                    rule.next_run_at
                                )
                            )}
                        </small>
                    </div>

                    <span
                        class="
                            automation-status
                            ${rule.enabled
                                ? "is-enabled"
                                : "is-disabled"}
                        "
                    >
                        ${rule.enabled
                            ? "Aktif"
                            : "Nonaktif"}
                    </span>
                </div>

                <div class="automation-rule-summary">
                    <span>
                        ${escapeHtml(
                            summary.template
                            || "custom"
                        )}
                    </span>

                    <span>
                        ${Number(
                            summary.product_count
                            || 0
                        )} produk
                    </span>

                    <span>
                        ${Number(
                            summary.variations
                            || 1
                        )} variasi
                    </span>

                    <span>
                        ${escapeHtml(
                            summary.aspect_ratio
                            || "-"
                        )}
                    </span>
                </div>

                <div class="automation-last-run">
                    <b>Terakhir:</b>
                    ${escapeHtml(
                        rule.last_status || "never"
                    )}

                    ${rule.last_campaign_id
                        ? ` • Campaign #${rule.last_campaign_id}`
                        : ""}

                    ${rule.last_message
                        ? `
                            <br>
                            ${escapeHtml(
                                rule.last_message
                            )}
                        `
                        : ""}
                </div>

                <div class="automation-rule-actions">
                    <button
                        class="mini-button"
                        onclick="
                            runAutomationRule(
                                '${rule.id}'
                            )
                        "
                    >
                        Run Now
                    </button>

                    <button
                        class="mini-button"
                        onclick="
                            toggleAutomationRule(
                                '${rule.id}',
                                ${rule.enabled
                                    ? "false"
                                    : "true"}
                            )
                        "
                    >
                        ${rule.enabled
                            ? "Disable"
                            : "Enable"}
                    </button>

                    <button
                        class="mini-button danger"
                        onclick="
                            deleteAutomationRule(
                                '${rule.id}'
                            )
                        "
                    >
                        Delete
                    </button>
                </div>
            </article>
        `;
    }).join("");
}


async function loadAutomationRules() {
    const target = document.getElementById(
        "automationRuleList"
    );

    if (!target) return;

    try {
        const data = await api(
            "/api/automation/rules"
        );

        renderAutomationRules(
            data.rules || []
        );
    } catch (error) {
        target.innerHTML = `
            <div class="automation-empty">
                Gagal memuat automation:
                ${escapeHtml(error.message)}
            </div>
        `;
    }
}


function toggleAutomationScheduleFields() {
    const scheduleType =
        document.getElementById(
            "automationScheduleType"
        )?.value || "manual";

    const runAt =
        document.getElementById(
            "automationRunAt"
        );

    if (runAt) {
        runAt.disabled =
            scheduleType === "manual";
    }
}


async function createAutomationRule() {
    const message =
        document.getElementById(
            "automationMessage"
        );

    const preflight =
        renderCatalogPreflight();

    if (!preflight.ok) {
        if (message) {
            message.textContent =
                preflight.errors[0]
                || "Preflight belum valid.";
        }
        return;
    }

    const campaignPayload =
        buildAutomationCampaignPayload();

    if (
        campaignPayload.product_clips.length
            < 5
        || campaignPayload.product_clips.length
            > 6
    ) {
        if (message) {
            message.textContent =
                "Pilih 5–6 produk terlebih dahulu.";
        }
        return;
    }

    const scheduleType =
        document.getElementById(
            "automationScheduleType"
        )?.value || "manual";

    const runAtInput =
        document.getElementById(
            "automationRunAt"
        )?.value || "";

    let runAt = null;

    if (scheduleType !== "manual") {
        if (!runAtInput) {
            if (message) {
                message.textContent =
                    "Isi tanggal dan waktu jadwal.";
            }
            return;
        }

        runAt = new Date(
            runAtInput
        ).toISOString();
    }

    const name = (
        document.getElementById(
            "automationName"
        )?.value.trim()
        || campaignPayload.name
        || `Automation ${new Date()
            .toLocaleDateString("id-ID")}`
    );

    const webhookUrl = (
        document.getElementById(
            "automationWebhookUrl"
        )?.value.trim()
        || null
    );

    if (message) {
        message.textContent =
            "Menyimpan automation...";
    }

    try {
        const data = await api(
            "/api/automation/rules",
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json",
                },
                body: JSON.stringify({
                    name,
                    enabled: true,
                    schedule_type:
                        scheduleType,
                    run_at: runAt,
                    webhook_url:
                        webhookUrl,
                    campaign_payload:
                        campaignPayload,
                }),
            }
        );

        if (message) {
            message.textContent =
                data.message;
        }

        await loadAutomationRules();

    } catch (error) {
        if (message) {
            message.textContent =
                `Gagal: ${error.message}`;
        }
    }
}


async function runAutomationRule(ruleId) {
    const message =
        document.getElementById(
            "automationMessage"
        );

    if (message) {
        message.textContent =
            "Menjalankan automation...";
    }

    try {
        const data = await api(
            `/api/automation/rules/${ruleId}/run`,
            {
                method: "POST",
            }
        );

        if (message) {
            message.textContent =
                data.message;
        }

        await Promise.all([
            loadAutomationRules(),
            loadMultiProductCampaigns(),
        ]);

    } catch (error) {
        if (message) {
            message.textContent =
                `Run gagal: ${error.message}`;
        }
    }
}


async function toggleAutomationRule(
    ruleId,
    enabled
) {
    try {
        await api(
            `/api/automation/rules/${ruleId}/toggle`,
            {
                method: "PUT",
                headers: {
                    "Content-Type":
                        "application/json",
                },
                body: JSON.stringify({
                    enabled,
                }),
            }
        );

        await loadAutomationRules();

    } catch (error) {
        alert(
            `Gagal: ${error.message}`
        );
    }
}


async function deleteAutomationRule(
    ruleId
) {
    if (
        !confirm(
            "Hapus automation rule ini?"
        )
    ) {
        return;
    }

    try {
        await api(
            `/api/automation/rules/${ruleId}`,
            {
                method: "DELETE",
            }
        );

        await loadAutomationRules();

    } catch (error) {
        alert(
            `Gagal: ${error.message}`
        );
    }
}




async function generateMultiProductCampaign() {
    const button = generateMultiCampaignButton;
    const message = multiCampaignMessage;

    if (!button || !message) return;

    const productClips = selectedCampaignProductClips();
    const preflight = renderCatalogPreflight();

    if (!preflight.ok) {
        message.textContent =
            preflight.errors[0]
            || "Preflight catalog belum valid.";
        return;
    }

    if (
        productClips.length < 5
        || productClips.length > 6
    ) {
        message.textContent =
            "Pilih 5 sampai 6 produk untuk satu video katalog.";
        return;
    }

    if (productClips.some(item => !item.clip_id)) {
        message.textContent = "Setiap produk terpilih harus punya raw video real.";
        return;
    }

    button.disabled = true;
    button.textContent = "Membuat Antrean...";
    message.textContent = "Menyiapkan video katalog...";

    try {
        const multiVoiceoverEnabled =
            document.getElementById("multiCampaignVoiceoverEnabled")?.checked
            && voiceoverConfigured;
        const promoEnabled =
            document.getElementById("multiCampaignPromoEnabled")?.checked;

        const musicEnabled = Boolean(
            document.getElementById(
                "multiCampaignMusicEnabled"
            )?.checked
        );

        const musicId = (
            document.getElementById(
                "multiCampaignMusicId"
            )?.value || null
        );

        if (musicEnabled && !musicId) {
            message.textContent =
                "Pilih background music terlebih dahulu.";
            return;
        }

        const payload = {
            name: document.getElementById("multiCampaignName").value.trim() || null,
            creative_template:
                document.getElementById(
                    "multiCampaignTemplate"
                )?.value || "custom_manual",
            variations: Number(document.getElementById("multiCampaignVariations").value),
            product_clips: productClips,
            audience: document.getElementById("multiCampaignAudience").value,
            min_order_qty: 6,
            duration_seconds: Number(document.getElementById("multiCampaignDuration").value),
            aspect_ratio: document.getElementById("multiCampaignAspect").value,
            export_preset:
                document.getElementById(
                    "multiCampaignExportPreset"
                )?.value || "custom",
            promo_enabled: Boolean(promoEnabled),
            promo_min_amount: Number(document.getElementById("multiCampaignPromoMinAmount")?.value || 100000),
            promo_discount_percent: Number(document.getElementById("multiCampaignPromoDiscount")?.value || 10),
            promo_text: document.getElementById("multiCampaignPromoText")?.value.trim() || null,
            music_enabled: musicEnabled,
            music_id: musicEnabled ? musicId : null,
            music_volume: Number(
                document.getElementById(
                    "multiCampaignMusicVolume"
                )?.value || 22
            ) / 100,
            music_ducking: Boolean(
                document.getElementById(
                    "multiCampaignMusicDucking"
                )?.checked
            ),
            voiceover_enabled: Boolean(multiVoiceoverEnabled),
            voice_id: multiVoiceoverEnabled
                ? document.getElementById("multiCampaignVoiceId").value || null
                : null,
            voiceover_mode: document.getElementById("multiCampaignVoiceMode")?.value || "auto",
            voiceover_text: document.getElementById("multiCampaignVoiceText")?.value.trim() || null,
        };

        const data = await api("/api/campaigns/raw-video-catalog", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload),
        });

        message.textContent = data.message;
        await loadMultiProductCampaigns();
    } catch (error) {
        message.textContent = `Generate gagal: ${error.message}`;
    } finally {
        button.disabled = false;
        button.textContent = "Render Catalog Video";
    }
}

async function restoreExpandedCampaigns() {
    const ids = [...state.expandedCampaignIds];

    for (const campaignId of ids) {
        const target = document.getElementById(`campaignJobs-${campaignId}`);

        if (!target) {
            state.expandedCampaignIds.delete(campaignId);
            continue;
        }

        try {
            const data = await api(`/api/campaigns/${campaignId}`);
            target.innerHTML = renderCampaignJobs(data.campaign);
        } catch (error) {
            target.innerHTML = `
                <div class="render-item">
                    Gagal memuat hasil: ${escapeHtml(error.message)}
                </div>
            `;
        }
    }
}

async function loadMultiProductCampaigns() {
    if (!multiCampaignList) return;

    try {
        const data = await api("/api/campaigns/multi-product");
        multiCampaignList.innerHTML = data.campaigns.length
            ? data.campaigns.map(campaignCard).join("")
            : '<div class="empty">Belum ada raw video catalog ads.</div>';
        await restoreExpandedCampaigns();
    } catch (error) {
        multiCampaignList.innerHTML = `
            <div class="empty">
                Gagal memuat catalog ads: ${escapeHtml(error.message)}
            </div>
        `;
    }
}

function qaStatusClass(
    status
) {
    if (status === "passed") {
        return "qa-passed";
    }

    if (status === "warning") {
        return "qa-warning";
    }

    if (status === "failed") {
        return "qa-failed";
    }

    return "qa-pending";
}


function renderQaMetadata(
    job
) {
    const qa = job.qa || job.config?.qa;

    if (!qa) {
        return `
            <div class="render-qa qa-pending">
                <span>QA Pending</span>
            </div>
        `;
    }

    const status =
        qa.status || "pending";

    const metadata = [
        qa.width && qa.height
            ? `${qa.width}×${qa.height}`
            : null,
        qa.duration_seconds !== null
            && qa.duration_seconds !== undefined
            ? `${Number(
                qa.duration_seconds
            ).toFixed(2)} dtk`
            : null,
        qa.fps
            ? `${Number(qa.fps).toFixed(2)} FPS`
            : null,
        qa.video_codec
            ? String(qa.video_codec).toUpperCase()
            : null,
        qa.audio_codec
            ? String(qa.audio_codec).toUpperCase()
            : "Tanpa audio",
        qa.size_mb !== null
            && qa.size_mb !== undefined
            ? `${Number(qa.size_mb).toFixed(2)} MB`
            : null,
    ].filter(Boolean);

    const notes = [
        ...(qa.errors || []),
        ...(qa.warnings || []),
    ];

    return `
        <div
            class="render-qa ${qaStatusClass(status)}"
        >
            <div class="render-qa-head">
                <span>
                    ${escapeHtml(
                        qa.label || "QA"
                    )}
                </span>

                <small>
                    ${escapeHtml(
                        metadata.join(" • ")
                    )}
                </small>
            </div>

            ${notes.length
                ? `
                    <div class="render-qa-notes">
                        ${notes.map(
                            note => `
                                <div>
                                    • ${escapeHtml(note)}
                                </div>
                            `
                        ).join("")}
                    </div>
                `
                : ""}
        </div>
    `;
}


function reviewStatusLabel(status) {
    const labels = {
        draft: "Draft",
        review: "In Review",
        approved: "Approved",
        rejected: "Rejected",
    };

    return labels[status] || "Draft";
}


function reviewStatusClass(status) {
    return `review-status-${status || "draft"}`;
}


function renderReviewRatingOptions(
    selectedRating
) {
    const rating = Number(
        selectedRating || 0
    );

    return [0, 1, 2, 3, 4, 5]
        .map(value => `
            <option
                value="${value}"
                ${rating === value
                    ? "selected"
                    : ""}
            >
                ${value === 0
                    ? "Belum dinilai"
                    : `${value} Bintang`}
            </option>
        `)
        .join("");
}


function renderJobCard(
    job,
    campaignId
) {
    const templateLabel =
        job.config?.creative_template_label
        || "Custom Manual";

    const productNames =
        job.config?.product_names || [];

    const exportLabel = exportPresetLabel(
        job.config?.export_preset
        || "custom"
    );

    const review =
        job.review
        || job.config?.review
        || {
            status: "draft",
            rating: 0,
            notes: "",
            winner: false,
        };

    const qa =
        job.qa
        || job.config?.qa
        || {};

    const completed =
        job.status === "completed";

    const approved =
        review.status === "approved";

    return `
        <article
            class="
                render-item
                ${review.winner
                    ? "render-winner"
                    : ""}
            "
            data-review-status="${escapeHtml(
                review.status || "draft"
            )}"
            data-qa-status="${escapeHtml(
                qa.status || "pending"
            )}"
            data-winner="${review.winner
                ? "true"
                : "false"}"
        >
            ${review.winner
                ? `
                    <div class="render-winner-ribbon">
                        ★ Campaign Winner
                    </div>
                `
                : ""}

            ${job.thumbnail_url
                ? `
                    <a
                        class="render-thumbnail-link"
                        href="${escapeHtml(
                            job.output_url
                            || job.thumbnail_url
                        )}"
                        target="_blank"
                    >
                        <img
                            class="render-thumbnail"
                            src="${escapeHtml(
                                job.thumbnail_url
                            )}"
                            alt="Thumbnail Video ${job.variation_index}"
                            loading="lazy"
                        >
                    </a>
                `
                : `
                    <div class="render-thumbnail-placeholder">
                        Thumbnail belum tersedia
                    </div>
                `}

            <div class="render-result-head">
                <strong>
                    Video ${job.variation_index}
                </strong>

                <div class="render-result-statuses">
                    <span>
                        ${escapeHtml(job.status)}
                    </span>

                    <span
                        class="
                            render-review-badge
                            ${reviewStatusClass(
                                review.status
                            )}
                        "
                    >
                        ${escapeHtml(
                            reviewStatusLabel(
                                review.status
                            )
                        )}
                    </span>
                </div>
            </div>

            ${job.config?.render_mode === "raw_catalog"
                ? `
                    <small class="vo-script">
                        <b>Template:</b>
                        ${escapeHtml(templateLabel)}
                        <br>

                        <b>Export:</b>
                        ${escapeHtml(exportLabel)}
                        <br>

                        <b>Catalog:</b>
                        ${escapeHtml(
                            productNames.join(" | ")
                        )}
                    </small>
                `
                : ""}

            ${job.config?.voiceover?.enabled
                ? `
                    <small class="vo-script">
                        <b>VO:</b>
                        ${escapeHtml(
                            job.config.voiceover.script
                            || ""
                        )}
                    </small>
                `
                : ""}

            ${renderQaMetadata(job)}

            <div class="render-review-panel">
                <div class="render-review-fields">
                    <label>
                        <span>Status Review</span>

                        <select
                            id="reviewStatus-${job.id}"
                            ${completed
                                ? ""
                                : "disabled"}
                        >
                            ${[
                                ["draft", "Draft"],
                                ["review", "In Review"],
                                ["approved", "Approved"],
                                ["rejected", "Rejected"],
                            ].map(
                                ([value, label]) => `
                                    <option
                                        value="${value}"
                                        ${review.status === value
                                            ? "selected"
                                            : ""}
                                    >
                                        ${label}
                                    </option>
                                `
                            ).join("")}
                        </select>
                    </label>

                    <label>
                        <span>Rating</span>

                        <select
                            id="reviewRating-${job.id}"
                        >
                            ${renderReviewRatingOptions(
                                review.rating
                            )}
                        </select>
                    </label>
                </div>

                <label class="render-review-notes">
                    <span>Catatan Reviewer</span>

                    <textarea
                        id="reviewNotes-${job.id}"
                        rows="3"
                        placeholder="Catatan revisi, alasan approve, atau alasan reject..."
                    >${escapeHtml(
                        review.notes || ""
                    )}</textarea>
                </label>

                <div class="render-review-actions">
                    <button
                        type="button"
                        class="mini-button"
                        onclick="
                            saveRenderReview(
                                ${campaignId},
                                ${job.id},
                                false
                            )
                        "
                    >
                        Simpan Review
                    </button>

                    <button
                        type="button"
                        class="mini-button render-winner-button"
                        ${completed
                            ? ""
                            : "disabled"}
                        onclick="
                            saveRenderReview(
                                ${campaignId},
                                ${job.id},
                                true
                            )
                        "
                    >
                        ★ Set Winner
                    </button>
                </div>

                <div
                    id="reviewMessage-${job.id}"
                    class="render-review-message"
                ></div>
            </div>

            <div class="render-download-actions">
                ${job.output_url
                    ? `
                        <a
                            href="${escapeHtml(
                                job.output_url
                            )}"
                            target="_blank"
                        >
                            Preview MP4
                        </a>
                    `
                    : ""}

                ${job.output_url && approved
                    ? `
                        <a
                            href="${escapeHtml(
                                job.output_url
                            )}"
                            target="_blank"
                            download
                        >
                            Download Approved MP4
                        </a>
                    `
                    : ""}

                ${job.thumbnail_url
                    ? `
                        <a
                            href="${escapeHtml(
                                job.thumbnail_url
                            )}"
                            target="_blank"
                            download
                        >
                            Download Thumbnail
                        </a>
                    `
                    : ""}
            </div>

            ${job.error_message
                ? `
                    <small class="render-error-message">
                        ${escapeHtml(
                            job.error_message.slice(-500)
                        )}
                    </small>
                `
                : ""}
        </article>
    `;
}


function renderCampaignReviewToolbar(
    campaign
) {
    const jobs = campaign.jobs || [];

    const approvedCount = jobs.filter(
        job => (
            job.review?.status
            || job.config?.review?.status
        ) === "approved"
    ).length;

    const winner = jobs.find(
        job => Boolean(
            job.review?.winner
            || job.config?.review?.winner
        )
    );

    return `
        <div class="campaign-review-toolbar">
            <div>
                <strong>
                    Review & Approval
                </strong>

                <small>
                    ${approvedCount} approved
                    ${winner
                        ? ` • Winner Video ${winner.variation_index}`
                        : " • Belum ada winner"}
                </small>
            </div>

            <select
                onchange="
                    filterCampaignResults(
                        ${campaign.id},
                        this.value
                    )
                "
            >
                <option value="all">
                    Semua Video
                </option>

                <option value="qa_passed">
                    QA Passed
                </option>

                <option value="approved">
                    Approved
                </option>

                <option value="review">
                    In Review
                </option>

                <option value="rejected">
                    Rejected
                </option>

                <option value="winner">
                    Winner
                </option>
            </select>
        </div>
    `;
}


function renderCampaignJobs(
    campaign
) {
    return `
        ${renderCampaignReviewToolbar(
            campaign
        )}

        <div
            id="campaignResultCards-${campaign.id}"
            class="campaign-result-cards"
        >
            ${(campaign.jobs || [])
                .map(
                    job => renderJobCard(
                        job,
                        campaign.id
                    )
                )
                .join("")}
        </div>
    `;
}


function filterCampaignResults(
    campaignId,
    filter
) {
    const container = document.getElementById(
        `campaignResultCards-${campaignId}`
    );

    if (!container) return;

    container
        .querySelectorAll(".render-item")
        .forEach(card => {
            let visible = true;

            if (filter === "qa_passed") {
                visible =
                    card.dataset.qaStatus
                    === "passed";
            } else if (filter === "winner") {
                visible =
                    card.dataset.winner
                    === "true";
            } else if (filter !== "all") {
                visible =
                    card.dataset.reviewStatus
                    === filter;
            }

            card.hidden = !visible;
        });
}


async function refreshCampaignResults(
    campaignId
) {
    const target = document.getElementById(
        `campaignJobs-${campaignId}`
    );

    if (!target) return;

    const data = await api(
        `/api/campaigns/${campaignId}`
    );

    target.innerHTML = renderCampaignJobs(
        data.campaign
    );

    state.expandedCampaignIds.add(
        Number(campaignId)
    );
}


async function saveRenderReview(
    campaignId,
    jobId,
    setWinner = false
) {
    const statusElement =
        document.getElementById(
            `reviewStatus-${jobId}`
        );

    const ratingElement =
        document.getElementById(
            `reviewRating-${jobId}`
        );

    const notesElement =
        document.getElementById(
            `reviewNotes-${jobId}`
        );

    const messageElement =
        document.getElementById(
            `reviewMessage-${jobId}`
        );

    let status =
        statusElement?.value || "draft";

    if (setWinner) {
        status = "approved";
    }

    if (messageElement) {
        messageElement.textContent =
            setWinner
                ? "Menetapkan winner..."
                : "Menyimpan review...";
    }

    try {
        const data = await api(
            `/api/campaigns/${campaignId}`
            + `/jobs/${jobId}/review`,
            {
                method: "PUT",
                headers: {
                    "Content-Type":
                        "application/json",
                },
                body: JSON.stringify({
                    status,
                    rating: Number(
                        ratingElement?.value
                        || 0
                    ),
                    notes:
                        notesElement?.value.trim()
                        || null,
                    winner: Boolean(setWinner),
                }),
            }
        );

        if (messageElement) {
            messageElement.textContent =
                data.message;
        }

        await refreshCampaignResults(
            campaignId
        );
    } catch (error) {
        if (messageElement) {
            messageElement.textContent =
                `Gagal: ${error.message}`;
        }
    }
}

async function viewCampaign(
    campaignId,
    event = null
) {
    event?.preventDefault();
    event?.stopPropagation();

    const numericId = Number(campaignId);

    const target = document.getElementById(
        `campaignJobs-${campaignId}`
    );

    if (
        state.expandedCampaignIds.has(numericId)
        && target
        && target.innerHTML.trim()
    ) {
        state.expandedCampaignIds.delete(
            numericId
        );

        target.innerHTML = "";
        return;
    }

    state.expandedCampaignIds.add(
        numericId
    );

    const data = await api(
        `/api/campaigns/${campaignId}`
    );

    target.innerHTML = renderCampaignJobs(
        data.campaign
    );
}


async function retryCampaign(campaignId, event = null) {
    event?.preventDefault();
    event?.stopPropagation();

    const data = await api(`/api/campaigns/${campaignId}/retry-failed`, {method:'POST'});
    const message = document.getElementById('campaignMessage') || multiCampaignMessage;
    if (message) message.textContent = data.message;
    await loadCampaigns();
    await loadMultiProductCampaigns();
}

async function deleteCampaign(campaignId, event = null) {
    event?.preventDefault();
    event?.stopPropagation();

    if (!confirm('Hapus campaign dan semua hasil render?')) return;
    state.expandedCampaignIds.delete(Number(campaignId));
    const data = await api(`/api/campaigns/${campaignId}`, {method:'DELETE'});
    const message = document.getElementById('campaignMessage') || multiCampaignMessage;
    if (message) message.textContent = data.message;
    await loadCampaigns();
    await loadMultiProductCampaigns();
}

function startCampaignPolling() {
    stopCampaignPolling();
    campaignPollTimer = setInterval(() => {
        if (state.activeProductId) loadCampaigns();
        loadMultiProductCampaigns();
    }, 5000);
}

function stopCampaignPolling() {
    if (campaignPollTimer) clearInterval(campaignPollTimer);
    campaignPollTimer = null;
}

window.generateCampaign = generateCampaign;

window.generateMultiProductCampaign = generateMultiProductCampaign;
window.applyCreativeTemplate = applyCreativeTemplate;
window.applyExportPreset = applyExportPreset;
window.createAutomationRule = createAutomationRule;
window.loadAutomationRules = loadAutomationRules;
window.runAutomationRule = runAutomationRule;
window.toggleAutomationRule = toggleAutomationRule;
window.deleteAutomationRule = deleteAutomationRule;
window.toggleAutomationScheduleFields = toggleAutomationScheduleFields;
window.resetCreativeTemplateManual = resetCreativeTemplateManual;
window.loadCatalogMusicLibrary = loadCatalogMusicLibrary;
window.toggleMusicControls = toggleMusicControls;
window.updateMusicVolumeLabel = updateMusicVolumeLabel;
window.previewSelectedMusic = previewSelectedMusic;
window.uploadCatalogMusic = uploadCatalogMusic;
window.deleteCatalogMusic = deleteCatalogMusic;
window.selectVisibleCampaignProducts = selectVisibleCampaignProducts;
window.moveCatalogProduct = moveCatalogProduct;
window.renderCatalogPreflight = renderCatalogPreflight;

window.viewCampaign = viewCampaign;
window.retryCampaign = retryCampaign;
window.deleteCampaign = deleteCampaign;
window.saveRenderReview = saveRenderReview;
window.filterCampaignResults = filterCampaignResults;



let voiceoverConfigured = false;

async function loadVoiceOptions() {
    const statusElement =
        document.getElementById("voiceoverStatus");

    const checkbox =
        document.getElementById(
            "campaignVoiceoverEnabled"
        );

    const select =
        document.getElementById(
            "campaignVoiceId"
        );

    if (
        !statusElement
        || !checkbox
        || !select
    ) {
        return;
    }

    try {
        const status = await api(
            "/api/voiceover/status"
        );

        voiceoverConfigured =
            Boolean(status.configured);

        if (!voiceoverConfigured) {
            statusElement.textContent =
                "API key belum dikonfigurasi";

            checkbox.checked = false;
            checkbox.disabled = true;

            select.innerHTML = `
                <option value="">
                    ElevenLabs belum aktif
                </option>
            `;

            toggleVoiceoverControls();
            return;
        }

        statusElement.textContent =
            `${status.model_id} • Bahasa Indonesia`;

        const data = await api(
            "/api/voiceover/voices"
        );

        const voices =
            data.voices || [];

        const savedVoice =
            localStorage.getItem(
                "productAdsElevenLabsVoiceId"
            );

        select.innerHTML = `
            <option value="">
                Pilih voice...
            </option>
            ${voices.map(voice => {
                const labels =
                    voice.labels || {};

                const detail = [
                    labels.gender,
                    labels.age,
                    labels.accent,
                    voice.category,
                ]
                    .filter(Boolean)
                    .join(" • ");

                return `
                    <option
                        value="${escapeHtml(
                            voice.voice_id
                        )}"
                    >
                        ${escapeHtml(voice.name)}
                        ${detail
                            ? ` — ${escapeHtml(detail)}`
                            : ""}
                    </option>
                `;
            }).join("")}
        `;

        if (
            savedVoice
            && voices.some(
                voice =>
                    voice.voice_id
                    === savedVoice
            )
        ) {
            select.value = savedVoice;
        } else if (voices.length) {
            select.value =
                voices[0].voice_id;
        }

        checkbox.disabled = false;
        toggleVoiceoverControls();

    } catch (error) {
        voiceoverConfigured = false;

        statusElement.textContent =
            `ElevenLabs error: ${error.message}`;

        checkbox.checked = false;
        checkbox.disabled = true;

        select.innerHTML = `
            <option value="">
                Gagal memuat voice
            </option>
        `;

        toggleVoiceoverControls();
    }
}


function toggleVoiceoverControls() {
    const checkbox =
        document.getElementById(
            "campaignVoiceoverEnabled"
        );

    const controls =
        document.getElementById(
            "voiceoverControls"
        );

    const customWrap =
        document.getElementById(
            "customVoiceTextWrap"
        );

    if (
        !checkbox
        || !controls
        || !customWrap
    ) {
        return;
    }

    const enabled =
        checkbox.checked
        && voiceoverConfigured;

    controls.classList.toggle(
        "voiceover-disabled",
        !enabled
    );

    controls
        .querySelectorAll(
            "select, button"
        )
        .forEach(element => {
            element.disabled = !enabled;
        });

    toggleCustomVoiceText();
}


function toggleCustomVoiceText() {
    const checkbox =
        document.getElementById(
            "campaignVoiceoverEnabled"
        );

    const mode =
        document.getElementById(
            "campaignVoiceMode"
        );

    const wrap =
        document.getElementById(
            "customVoiceTextWrap"
        );

    if (!checkbox || !mode || !wrap) {
        return;
    }

    const show =
        checkbox.checked
        && voiceoverConfigured
        && mode.value === "custom";

    wrap.classList.toggle(
        "hidden",
        !show
    );
}


async function loadMultiVoiceOptions() {
    const checkbox =
        document.getElementById(
            "multiCampaignVoiceoverEnabled"
        );

    const select =
        document.getElementById(
            "multiCampaignVoiceId"
        );

    if (!checkbox || !select) {
        return;
    }

    try {
        const status = await api(
            "/api/voiceover/status"
        );

        voiceoverConfigured =
            Boolean(status.configured);

        if (!voiceoverConfigured) {
            checkbox.checked = false;
            checkbox.disabled = true;
            select.innerHTML = `
                <option value="">
                    ElevenLabs belum aktif
                </option>
            `;
            toggleMultiVoiceoverControls();
            return;
        }

        const data = await api(
            "/api/voiceover/voices"
        );

        const voices =
            data.voices || [];

        const savedVoice =
            localStorage.getItem(
                "productAdsElevenLabsVoiceId"
            );

        select.innerHTML = `
            <option value="">
                Pilih voice...
            </option>
            ${voices.map(voice => {
                const labels =
                    voice.labels || {};

                const detail = [
                    labels.gender,
                    labels.age,
                    labels.accent,
                    voice.category,
                ]
                    .filter(Boolean)
                    .join(" • ");

                return `
                    <option value="${escapeHtml(voice.voice_id)}">
                        ${escapeHtml(voice.name)}
                        ${detail ? ` — ${escapeHtml(detail)}` : ""}
                    </option>
                `;
            }).join("")}
        `;

        if (
            savedVoice
            && voices.some(
                voice =>
                    voice.voice_id
                    === savedVoice
            )
        ) {
            select.value = savedVoice;
        } else if (voices.length) {
            select.value =
                voices[0].voice_id;
        }

        select.disabled = false;
        checkbox.disabled = false;
        toggleMultiVoiceoverControls();

    } catch (error) {
        voiceoverConfigured = false;
        checkbox.checked = false;
        checkbox.disabled = true;
        select.innerHTML = `
            <option value="">
                Gagal memuat voice
            </option>
        `;
        toggleMultiVoiceoverControls();
    }
}


function toggleMultiVoiceoverControls() {
    const checkbox =
        document.getElementById(
            "multiCampaignVoiceoverEnabled"
        );

    const select =
        document.getElementById(
            "multiCampaignVoiceId"
        );

    const controls =
        document.getElementById(
            "multiVoiceoverControls"
        );

    const customWrap =
        document.getElementById(
            "multiCustomVoiceTextWrap"
        );

    if (!checkbox || !select || !controls || !customWrap) {
        return;
    }

    const configured = voiceoverConfigured;
    const enabled =
        checkbox.checked
        && configured;

    select.disabled = !configured;
    controls.classList.toggle(
        "voiceover-disabled",
        !enabled
    );
    controls
        .querySelectorAll("select")
        .forEach(element => {
            element.disabled = !enabled;
        });

    toggleMultiCustomVoiceText();
}


function toggleMultiCustomVoiceText() {
    const checkbox =
        document.getElementById(
            "multiCampaignVoiceoverEnabled"
        );

    const mode =
        document.getElementById(
            "multiCampaignVoiceMode"
        );

    const wrap =
        document.getElementById(
            "multiCustomVoiceTextWrap"
        );

    if (!checkbox || !mode || !wrap) {
        return;
    }

    const show =
        checkbox.checked
        && voiceoverConfigured
        && mode.value === "custom";

    wrap.classList.toggle(
        "hidden",
        !show
    );
}


function toggleMultiPromoControls() {
    const checkbox =
        document.getElementById(
            "multiCampaignPromoEnabled"
        );
    const controls =
        document.getElementById(
            "multiPromoControls"
        );

    if (!checkbox || !controls) {
        return;
    }

    const enabled = checkbox.checked;

    controls.classList.toggle(
        "voiceover-disabled",
        !enabled
    );
    controls
        .querySelectorAll("input")
        .forEach(element => {
            element.disabled = !enabled;
        });
}


function rememberVoiceSelection() {
    const select =
        document.getElementById(
            "campaignVoiceId"
        );
    const multiSelect =
        document.getElementById(
            "multiCampaignVoiceId"
        );

    const selectedVoice =
        select?.value
        || multiSelect?.value;

    if (selectedVoice) {
        localStorage.setItem(
            "productAdsElevenLabsVoiceId",
            selectedVoice
        );
    }
}


async function previewVoiceover() {
    const voiceId =
        document.getElementById(
            "campaignVoiceId"
        )?.value;

    const button =
        document.getElementById(
            "previewVoiceButton"
        );

    const player =
        document.getElementById(
            "voicePreviewPlayer"
        );

    const message =
        document.getElementById(
            "campaignMessage"
        );

    if (!voiceId) {
        message.textContent =
            "Pilih voice terlebih dahulu.";
        return;
    }

    button.disabled = true;
    button.textContent =
        "Generating...";

    message.textContent =
        "Membuat preview voice-over ElevenLabs...";

    try {
        const productName =
            state.workspace?.product?.name
            || "produk Spacecraft";

        const data = await api(
            "/api/voiceover/preview",
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json",
                },
                body: JSON.stringify({
                    voice_id: voiceId,
                    text:
                        `Kenalan dengan `
                        + `${productName}. `
                        + `Lihat detailnya dan `
                        + `pesan melalui `
                        + `Spacecraft sekarang.`,
                }),
            }
        );

        player.src =
            data.audio_url
            + `?t=${Date.now()}`;

        player.classList.remove(
            "hidden"
        );

        await player.play();

        message.textContent =
            "Preview voice berhasil dibuat.";

    } catch (error) {
        message.textContent =
            `Preview gagal: ${error.message}`;

    } finally {
        button.disabled = false;
        button.textContent =
            "Test Voice";
    }
}


window.loadVoiceOptions = loadVoiceOptions;
window.loadAiVideoStatus = loadAiVideoStatus;
window.toggleAiVideoControls =
    toggleAiVideoControls;
window.toggleVoiceoverControls =
    toggleVoiceoverControls;
window.toggleCustomVoiceText =
    toggleCustomVoiceText;
window.toggleMultiVoiceoverControls =
    toggleMultiVoiceoverControls;
window.toggleMultiCustomVoiceText =
    toggleMultiCustomVoiceText;
window.toggleMultiPromoControls =
    toggleMultiPromoControls;
window.rememberVoiceSelection =
    rememberVoiceSelection;
window.previewVoiceover =
    previewVoiceover;

bindCreativeTemplateManualTracking();
updateCreativeTemplateBadge(
    document.getElementById(
        "multiCampaignTemplate"
    )?.value || "bundle_hemat"
);
applyCreativeTemplate();

loadMultiProductCampaigns();
startCampaignPolling();
