// B19D_SNAPSHOT_HASH_DRIFT_UI
// B19C_LINKED_CREATIVE_SET_UI
// B19B_CREATIVE_READINESS_FRONTEND
// B19A2_SELECTABLE_DROPDOWN
// B19A_LINKED_CATALOG_FRONTEND
// B18K2_FORCE_RECONCILE_FRONTEND
// B18K_PUBLISHED_PRODUCTS_FRONTEND
// B18F_APP_POLLING_OPTIMIZED
const state = {
    activeProductId: null,
    workspace: null,
    products: [],
    rawVideosByProduct: {},
    rawVideoGenerateTimers: {},
    catalogProductOrder: [],
    // B19A_CATALOG_STATE
    b19aCatalogs: [],
    b19aCatalogPreview: null,
    b19aLinkedCatalog: null,
    b19aCatalogSourceMode:
        "spacecraft",
    b19aPricingSource:
        "meta",
    filterProductsBySelectedCatalog: true,
    // B19C_CREATIVE_SET_STATE
    b19cCreativeSet: null,
    campaignVisualAssets: {
        hook: null,
        cta: null,
    },
    musicLibrary: [],
    expandedCampaignIds: new Set(),
    campaignHistoryPage: 1,
    campaignHistoryPageSize: 5,
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

const productLibraryMenuButton =
    document.getElementById("productLibraryMenuButton");

const contentImageMenuButton =
    document.getElementById("contentImageMenuButton");

const backToStudioButton =
    document.getElementById("backToStudioButton");

const studioHeroSection =
    document.getElementById("studioHeroSection");

const productLibraryHeader =
    document.getElementById("productLibraryHeader");

const productToolbar =
    document.getElementById("productToolbar");

const multiProductSection =
    document.getElementById("multiProductSection");

const contentImageSection =
    document.getElementById("contentImageSection");

const contentImageForm =
    document.getElementById("contentImageForm");

const contentImageGenerateButton =
    document.getElementById("contentImageGenerateButton");

const contentImageStatus =
    document.getElementById("contentImageStatus");

const contentImageResults =
    document.getElementById("contentImageResults");

const multiProductPicker =
    document.getElementById("multiProductPicker");

const singleProductSelect =
    document.getElementById("singleProductSelect");

const singleProductRawVideoSelect =
    document.getElementById("singleProductRawVideoSelect");

const singleProductGenerateButton =
    document.getElementById(
        "singleProductGenerateButton"
    );

const singleProductMessage =
    document.getElementById("singleProductMessage");

const singleProductVoiceoverEnabled =
    document.getElementById("singleProductVoiceoverEnabled");

const singleProductVoiceId =
    document.getElementById("singleProductVoiceId");

const singleProductVoiceMode =
    document.getElementById("singleProductVoiceMode");

const singleProductVoiceText =
    document.getElementById("singleProductVoiceText");

const singleProductVoiceTextWrap =
    document.getElementById("singleProductVoiceTextWrap");

// B19A_CATALOG_ELEMENTS
const b19aCatalogSourceMode =
    document.getElementById(
        "b19aCatalogSourceMode"
    );

const b19aCatalogSelect =
    document.getElementById(
        "b19aCatalogSelect"
    );

const b19aCatalogStatus =
    document.getElementById(
        "b19aCatalogStatus"
    );

const b19aCatalogDetail =
    document.getElementById(
        "b19aCatalogDetail"
    );

const b19aLinkedCatalogControls =
    document.getElementById(
        "b19aLinkedCatalogControls"
    );

const b19aCatalogConnectionBadge =
    document.getElementById(
        "b19aCatalogConnectionBadge"
    );

const b19aApplyCatalogButton =
    document.getElementById(
        "b19aApplyCatalogButton"
    );

// B19C_CREATIVE_SET_ELEMENTS
const b19cCreativeSetPanel =
    document.getElementById(
        "b19cCreativeSetPanel"
    );

const b19cCreativeSetCode =
    document.getElementById(
        "b19cCreativeSetCode"
    );

const b19cCreativeSetStatus =
    document.getElementById(
        "b19cCreativeSetStatus"
    );

const b19cCommerceStatus =
    document.getElementById(
        "b19cCommerceStatus"
    );

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






// B19D_CATALOG_DRIFT_FRONTEND
async function b19dRefreshCreativeSetDrift() {
    const code =
        state.b19cCreativeSet
        ?.creative_set_code;

    if (!code) {
        return null;
    }

    try {
        const data = await api(
            `/api/creative-sets/`
            + `${encodeURIComponent(code)}`
            + `/drift?_ts=${Date.now()}`
        );

        state.b19cCreativeSet =
            data.creative_set || null;

        b19cRenderCreativeSet();
        renderCatalogPreflight();

        return state.b19cCreativeSet;

    } catch (error) {
        console.warn(
            "B19D drift refresh failed",
            error
        );

        return null;
    }
}


function b19dDriftError() {
    const item = state.b19cCreativeSet;

    if (
        item
        && (
            item.is_stale
            || item.drift_status === "stale"
        )
    ) {
        return (
            item.drift_reason
            || (
                "Mini Catalog berubah. "
                + "Apply Catalog ulang."
            )
        );
    }

    return "";
}



// B19C_LINKED_CREATIVE_SET_FRONTEND
function b19cRenderCreativeSet() {
    const item =
        state.b19cCreativeSet;

    if (!b19cCreativeSetPanel) {
        return;
    }

    if (!item) {
        b19cCreativeSetPanel.classList.add(
            "is-empty"
        );

        if (b19cCreativeSetCode) {
            b19cCreativeSetCode.textContent =
                "Belum dibuat";
        }

        if (b19cCreativeSetStatus) {
            b19cCreativeSetStatus.textContent =
                "Draft";
            b19cCreativeSetStatus.className =
                "b19c-status is-neutral";
        }

        if (b19cCommerceStatus) {
            b19cCommerceStatus.textContent =
                "Commerce belum linked";
            b19cCommerceStatus.className =
                "b19c-status is-locked";
        }

        const driftWarning =
            document.getElementById(
                "b19dDriftWarning"
            );

        if (driftWarning) {
            driftWarning.hidden = true;
            driftWarning.textContent = "";
        }

        return;
    }

    b19cCreativeSetPanel.classList.remove(
        "is-empty"
    );

    if (b19cCreativeSetCode) {
        b19cCreativeSetCode.textContent =
            item.creative_set_code;
    }

    if (b19cCreativeSetStatus) {
        b19cCreativeSetStatus.textContent =
            String(
                item.status || "draft"
            )
            .replaceAll("_", " ");

        b19cCreativeSetStatus.className =
            "b19c-status "
            + (
                item.drift_status === "stale"
                ? "is-stale"
                : (
                    item.status === "ready"
                    ? "is-ready"
                    : (
                        item.status
                            === "missing_assets"
                        ? "is-warning"
                        : "is-neutral"
                    )
                )
            );
    }

    const driftWarning =
        document.getElementById(
            "b19dDriftWarning"
        );

    if (driftWarning) {
        const stale = (
            item.drift_status === "stale"
            || item.is_stale
        );

        driftWarning.hidden = !stale;
        driftWarning.textContent = stale
            ? (
                "Catalog Drift: "
                + (
                    item.drift_reason
                    || (
                        "Mini Catalog berubah. "
                        + "Apply Catalog ulang."
                    )
                )
            )
            : "";
    }

    if (b19cCommerceStatus) {
        b19cCommerceStatus.textContent =
            item.commerce_ready
            ? (
                "Commerce Ready · "
                + (
                    item.catalog_code
                    || ""
                )
            )
            : "Internal Only";

        b19cCommerceStatus.className =
            "b19c-status "
            + (
                item.commerce_ready
                ? "is-ready"
                : "is-locked"
            );
    }
}


async function b19cPrepareFromCatalog(
    catalog
) {
    if (!catalog) {
        throw new Error(
            "Mini Catalog belum dipilih"
        );
    }

    const productIds =
        b19aCatalogProductIds(catalog);

    const data = await api(
        "/api/creative-sets/prepare",
        {
            method: "POST",
            // B19C_PREPARE_JSON_CONTENT_TYPE_FIX
            headers: {
                "Content-Type":
                    "application/json",
            },
            body: JSON.stringify({
                source_type: "spacecraft",
                catalog_code:
                    catalog.catalog_code,
                catalog_hash:
                    catalog.catalog_hash,
                name: catalog.name,
                product_ids: productIds,
            }),
        }
    );

    state.b19cCreativeSet =
        data.creative_set || null;

    b19cRenderCreativeSet();

    return state.b19cCreativeSet;
}


async function b19cPrepareCustom(
    productIds
) {
    const data = await api(
        "/api/creative-sets/prepare",
        {
            method: "POST",
            headers: {
                "Content-Type":
                    "application/json",
            },
            body: JSON.stringify({
                source_type: "custom",
                name: (
                    document.getElementById(
                        "multiCampaignName"
                    )?.value?.trim()
                    || "Custom Creative Set"
                ),
                product_ids: productIds,
            }),
        }
    );

    state.b19cCreativeSet =
        data.creative_set || null;

    b19cRenderCreativeSet();

    return state.b19cCreativeSet;
}


function b19cPreflightError() {
    const item =
        state.b19cCreativeSet;

    if (!item) {
        return (
            "Creative Set belum dibuat. "
            + "Apply Catalog ulang."
        );
    }

    if (
        state.b19aCatalogSourceMode
        === "spacecraft"
    ) {
        if (
            item.source_type
            !== "spacecraft"
            || !item.catalog_code
            || !item.commerce_ready
        ) {
            return (
                "Linked Creative Set belum "
                + "commerce-ready."
            );
        }
    }

    return "";
}



// B19B_CREATIVE_READINESS_MATRIX
function b19bReadinessLabel(
    readiness
) {
    if (!readiness) {
        return "Readiness belum diperiksa";
    }

    if (readiness.ready_to_render) {
        return (
            `${readiness.products_ready}/`
            + `${readiness.products_total} siap`
        );
    }

    return (
        `${readiness.products_ready}/`
        + `${readiness.products_total} siap · `
        + `${readiness.products_missing} belum`
    );
}


function b19bReadinessClass(
    readiness
) {
    if (!readiness) {
        return "is-neutral";
    }

    if (readiness.ready_to_render) {
        return "is-ready";
    }

    if (
        Number(
            readiness.products_ready
            || 0
        ) > 0
    ) {
        return "is-warning";
    }

    return "is-missing";
}


async function b19bLoadReadiness(
    catalogCode
) {
    const data = await api(
        `/api/spacecraft/catalogs/`
        + `${encodeURIComponent(
            catalogCode
        )}/readiness`
        + `?_ts=${Date.now()}`
    );

    return data.readiness || null;
}


async function b19bUploadCatalogRaw(
    productId,
    input
) {
    const files = [
        ...(input?.files || [])
    ];

    if (!files.length) {
        return;
    }

    const invalid = files.find(file =>
        !(
            file.type === "image/jpeg"
            || file.type === "image/png"
            || file.type === "image/webp"
            || file.type === "video/mp4"
            || file.type === "video/webm"
            || file.type === "video/quicktime"
            || /\.(jpe?g|png|webp|mp4|mov|webm)$/i.test(
                file.name
            )
        )
    );

    if (invalid) {
        b19aSetStatus(
            `File tidak didukung: `
            + invalid.name,
            "error"
        );

        input.value = "";
        return;
    }

    const formData = new FormData();

    files.forEach(file => {
        formData.append(
            "files",
            file
        );
    });

    input.disabled = true;

    b19aSetStatus(
        `Mengunggah ${files.length} `
        + "asset..."
    );

    try {
        const data = await api(
            `/api/products/${productId}/assets`,
            {
                method: "POST",
                body: formData,
            }
        );

        clearRawVideoCache(productId);

        b19aSetStatus(
            data.message
            || "Asset berhasil diunggah.",
            "success"
        );

        const checkbox =
            document.querySelector(
                ".campaignProductCheckbox"
                + `[value="${productId}"]`
            );

        if (
            checkbox
            && checkbox.checked
        ) {
            await toggleCampaignProductRaw(
                checkbox
            );
        }

        await b19aPreviewSelectedCatalog();

        if (
            state.b19aLinkedCatalog
            ?.catalog_code
            === b19aCatalogSelect?.value
        ) {
            const refreshed =
                state.b19aCatalogPreview;

            if (refreshed) {
                state.b19aLinkedCatalog =
                    refreshed;
            }
        }

        renderCatalogPreflight();

    } catch (error) {
        b19aSetStatus(
            `Upload asset gagal: `
            + error.message,
            "error"
        );

    } finally {
        input.disabled = false;
        input.value = "";
    }
}



// B19A_CATALOG_SELECTOR_LOGIC
function b19aSetStatus(
    message,
    kind = ""
) {
    if (b19aCatalogStatus) {
        b19aCatalogStatus.textContent =
            message;

        b19aCatalogStatus.classList.toggle(
            "is-error",
            kind === "error"
        );

        b19aCatalogStatus.classList.toggle(
            "is-success",
            kind === "success"
        );
    }
}


function b19aCatalogByCode(
    catalogCode
) {
    return (
        state.b19aCatalogs
        || []
    ).find(
        item =>
            item.catalog_code
            === catalogCode
    ) || null;
}


function b19aRenderCatalogOptions() {
    if (!b19aCatalogSelect) return;

    const catalogs =
        state.b19aCatalogs || [];

    if (!catalogs.length) {
        b19aCatalogSelect.innerHTML = `
            <option value="">
                Tidak ada catalog published
            </option>
        `;
        return;
    }

    b19aCatalogSelect.innerHTML =
        catalogs.map(catalog => {
            const compatible =
                Boolean(
                    catalog.render_compatible
                );

            const readiness =
                `${Number(
                    catalog.raw_video_ready_count
                    || 0
                )}/${Number(
                    catalog.products_count
                    || 0
                )} raw`;

            const suffix = compatible
                ? readiness
                : (
                    "Preview only · "
                    + (
                        catalog.compatibility_reasons?.[0]
                        || "Belum kompatibel"
                    )
                );

            return `
                <option
                    value="${escapeHtml(
                        catalog.catalog_code
                    )}"
                    data-compatible="${
                        compatible
                        ? "true"
                        : "false"
                    }"
                >
                    ${escapeHtml(
                        catalog.catalog_code
                    )}
                    — ${escapeHtml(
                        catalog.name
                    )}
                    (${escapeHtml(suffix)})
                </option>
            `;
        }).join("");

    const linkedCode =
        state.b19aLinkedCatalog
        ?.catalog_code;

    const defaultCode = (
        (
            linkedCode
            && b19aCatalogByCode(
                linkedCode
            )
        )
        ? linkedCode
        : (
            catalogs[0]
            ?.catalog_code
            || ""
        )
    );

    b19aCatalogSelect.value =
        defaultCode;
}


function b19aRenderCatalogDetail(
    catalog
) {
    state.b19aCatalogPreview =
        catalog || null;

    if (!b19aCatalogDetail) return;

    if (!catalog) {
        b19aCatalogDetail.innerHTML = `
            <div class="empty compact">
                Pilih Mini Catalog untuk
                melihat anggotanya.
            </div>
        `;
        return;
    }

    const products =
        catalog.products || [];

    const compatible =
        Boolean(
            catalog.render_compatible
        );

    const activeCode =
        state.b19aLinkedCatalog
        ?.catalog_code;

    const isApplied = (
        activeCode
        === catalog.catalog_code
        && state.b19aLinkedCatalog
            ?.catalog_hash
            === catalog.catalog_hash
    );

    const reasons = (
        catalog.compatibility_reasons
        || []
    );

    b19aCatalogDetail.innerHTML = `
        <div class="b19a-catalog-summary">
            <div>
                <strong>
                    ${escapeHtml(
                        catalog.catalog_code
                    )}
                    — ${escapeHtml(
                        catalog.name
                    )}
                </strong>
                <span>
                    ${escapeHtml(
                        catalog.catalog_type
                        || "catalog"
                    )}
                    · ${escapeHtml(
                        catalog.flow_type
                        || "flow"
                    )}
                    · ${Number(
                        catalog.products_count
                        || 0
                    )} produk
                </span>
            </div>

            <div class="b19a-summary-badges">
                <span class="${
                    compatible
                    ? "is-ready"
                    : "is-blocked"
                }">
                    ${
                        compatible
                        ? "Compatible"
                        : "Blocked"
                    }
                </span>

                <span class="${
                    isApplied
                    ? "is-applied"
                    : ""
                }">
                    ${
                        isApplied
                        ? "Applied"
                        : "Not Applied"
                    }
                </span>
            </div>
        </div>

        ${
            reasons.length
            ? `
                <div class="b19a-catalog-warning">
                    ${escapeHtml(
                        reasons.join(" · ")
                    )}
                </div>
            `
            : ""
        }

        ${
            catalog.readiness
            ? `
                <div class="b19b-readiness-card">
                    <div class="b19b-readiness-head">
                        <div>
                            <span>
                                Creative Readiness
                            </span>
                            <strong>
                                ${escapeHtml(
                                    b19bReadinessLabel(
                                        catalog.readiness
                                    )
                                )}
                            </strong>
                        </div>

                        <span class="b19b-readiness-status ${
                            b19bReadinessClass(
                                catalog.readiness
                            )
                        }">
                            ${
                                catalog.readiness
                                    .ready_to_render
                                ? "Ready to Render"
                                : "Missing Assets"
                            }
                        </span>
                    </div>

                    <div class="b19b-progress">
                        <span
                            style="width: ${
                                Number(
                                    catalog.readiness
                                        .ready_percentage
                                    || 0
                                )
                            }%"
                        ></span>
                    </div>

                    <div class="b19b-readiness-meta">
                        <span>
                            ${Number(
                                catalog.readiness
                                    .products_ready
                                || 0
                            )}
                            produk memiliki raw video
                        </span>
                        <span>
                            ${Number(
                                catalog.readiness
                                    .products_with_primary
                                || 0
                            )}
                            produk memiliki primary raw
                        </span>
                    </div>
                </div>
            `
            : ""
        }

        <div class="b19a-product-list">
            ${products.map(product => {
                const readinessItem = (
                    catalog.readiness?.products
                    || []
                ).find(
                    item =>
                        Number(
                            item.local_product_id
                        )
                        === Number(
                            product.local_product_id
                        )
                );

                return `
                <div class="b19a-product-row">
                    <span class="b19a-product-order">
                        ${Number(
                            product.commerce_position
                        )}
                    </span>

                    <div>
                        <strong>
                            ${escapeHtml(
                                product.name
                            )}
                        </strong>
                        <small>
                            External:
                            ${escapeHtml(
                                product.external_product_id
                            )}
                            · Local:
                            ${
                                product.local_product_id
                                ? Number(
                                    product.local_product_id
                                )
                                : "belum mapped"
                            }
                        </small>
                    </div>

                    <div class="b19b-product-actions">
                        <span class="${
                            readinessItem?.creative_ready
                            ? "is-ready"
                            : "is-missing"
                        }">
                            ${
                                readinessItem?.creative_ready
                                ? `${Number(
                                    readinessItem
                                        .raw_video_count
                                    || 0
                                )} raw video`
                                : "Raw belum ada"
                            }
                        </span>

                        ${
                            product.local_product_id
                            ? `
                                <label
                                    class="b19b-upload-button"
                                >
                                    ${
                                        readinessItem
                                            ?.creative_ready
                                        ? "Tambah Raw"
                                        : "Upload Raw"
                                    }

                                    <input
                                        type="file"
                                        accept=".mp4,.mov,.webm,video/mp4,video/webm,video/quicktime"
                                        multiple
                                        onchange="b19bUploadCatalogRaw(
                                            ${Number(
                                                product
                                                    .local_product_id
                                            )},
                                            this
                                        )"
                                    />
                                </label>
                            `
                            : `
                                <span class="b19b-unmapped">
                                    Belum mapped
                                </span>
                            `
                        }
                    </div>
                </div>
                `;
            }).join("")}
        </div>

        <div class="b19a-catalog-footer">
            <span>
                Commerce order mengikuti
                SpaceCraft.
            </span>
            <span>
                Creative order boleh diubah
                setelah Apply.
            </span>
            ${
                catalog.go_url
                ? `
                    <a
                        href="${escapeHtml(
                            catalog.go_url
                        )}"
                        target="_blank"
                        rel="noopener"
                    >
                        Buka /go/${escapeHtml(
                            catalog.catalog_code
                        )}
                    </a>
                `
                : ""
            }
        </div>
    `;

    if (b19aApplyCatalogButton) {
        b19aApplyCatalogButton.disabled =
            !compatible;
    }
}


async function loadB19aCatalogs(
    preview = true
) {
    if (
        !b19aCatalogSelect
        || !b19aCatalogStatus
    ) {
        return;
    }

    b19aSetStatus(
        "Memuat cache Mini Catalog..."
    );

    try {
        const data = await api(
            "/api/spacecraft/catalogs"
            + `?_ts=${Date.now()}`
        );

        state.b19aCatalogs =
            data.catalogs || [];

        b19aRenderCatalogOptions();

        if (b19aCatalogConnectionBadge) {
            b19aCatalogConnectionBadge
                .textContent =
                    `${Number(
                        data.count || 0
                    )} catalog`;

            b19aCatalogConnectionBadge
                .classList.add(
                    "is-connected"
                );
        }

        b19aSetStatus(
            `${Number(
                data.count || 0
            )} Mini Catalog published `
            + "tersedia dari cache.",
            "success"
        );

        if (
            preview
            && b19aCatalogSelect.value
        ) {
            await b19aPreviewSelectedCatalog();
        }

    } catch (error) {
        state.b19aCatalogs = [];

        b19aRenderCatalogOptions();

        b19aSetStatus(
            `Gagal memuat catalog: `
            + error.message,
            "error"
        );

        if (b19aCatalogConnectionBadge) {
            b19aCatalogConnectionBadge
                .textContent = "Offline";
        }
    }
}


async function syncB19aCatalogs() {
    b19aSetStatus(
        "Menyinkronkan Mini Catalog "
        + "dari SpaceCraft..."
    );

    try {
        const data = await api(
            "/api/spacecraft/catalogs/sync",
            {
                method: "POST",
            }
        );

        const staleCount = Number(
            data.drift?.stale_count
            || 0
        );

        b19aSetStatus(
            `${Number(
                data.count || 0
            )} Mini Catalog berhasil `
            + "disinkronkan."
            + (
                staleCount
                ? (
                    ` ${staleCount} Creative Set `
                    + "ditandai stale."
                )
                : ""
            ),
            staleCount
                ? "warning"
                : "success"
        );

        if (state.b19cCreativeSet) {
            await b19dRefreshCreativeSetDrift();
        }

        state.b19aLinkedCatalog = null;

        await loadB19aCatalogs(true);

        renderCatalogPreflight();

    } catch (error) {
        b19aSetStatus(
            `Sinkronisasi gagal: `
            + error.message,
            "error"
        );
    }
}


async function b19aPreviewSelectedCatalog() {
    const code = (
        b19aCatalogSelect?.value
        || ""
    ).trim();

    if (!code) {
        b19aRenderCatalogDetail(null);
        return null;
    }

    b19aSetStatus(
        `Memuat detail ${code}...`
    );

    try {
        const data = await api(
            `/api/spacecraft/catalogs/`
            + `${encodeURIComponent(code)}`
            + `?_ts=${Date.now()}`
        );

        const catalog =
            data.catalog || null;

        if (catalog) {
            try {
                catalog.readiness =
                    await b19bLoadReadiness(
                        catalog.catalog_code
                    );
            } catch (readinessError) {
                catalog.readiness = null;

                console.warn(
                    "B19B readiness load failed",
                    readinessError
                );
            }
        }

        b19aRenderCatalogDetail(
            catalog
        );

        b19aSetStatus(
            `${code} siap direview.`,
            "success"
        );

        return catalog;

    } catch (error) {
        b19aRenderCatalogDetail(null);

        b19aSetStatus(
            `Gagal memuat ${code}: `
            + error.message,
            "error"
        );

        return null;
    }
}


function b19aResetProductSelection() {
    document.querySelectorAll(
        ".campaignProductCheckbox"
    ).forEach(input => {
        input.checked = false;

        const productId = Number(
            input.value
        );

        const select = document.querySelector(
            ".campaignRawVideoSelect"
            + `[data-product-id="${productId}"]`
        );

        if (select) {
            select.disabled = true;
            select.innerHTML = (
                '<option value="">'
                + "Centang untuk memuat raw video"
                + "</option>"
            );
        }

        setRawVideoGenerateState(
            productId,
            "Pilih produk untuk memuat "
            + "raw video"
        );
    });

    state.catalogProductOrder = [];

    updateCatalogOrderUI();
    renderCatalogPreflight();
}


async function b19aApplyCatalogObject(
    catalog,
    showMessage = true
) {
    if (
        !catalog
        || !catalog.render_compatible
    ) {
        if (showMessage) {
            b19aSetStatus(
                "Catalog belum kompatibel "
                + "untuk render.",
                "error"
            );
        }
        return false;
    }

    const productIds = (
        catalog.products || []
    ).map(
        item =>
            Number(
                item.local_product_id
            )
    ).filter(Boolean);

    if (
        productIds.length
        !== Number(
            catalog.products_count
        )
    ) {
        b19aSetStatus(
            "Ada anggota catalog yang "
            + "belum terpetakan ke Ads.",
            "error"
        );
        return false;
    }

    const availableProductIds = new Set(
        (state.products || []).map(
            product => Number(product.id)
        )
    );

    const missingInPicker =
        productIds.filter(
            productId =>
                !availableProductIds.has(
                    Number(productId)
                )
        );

    if (missingInPicker.length) {
        b19aSetStatus(
            "Produk catalog belum tersedia "
            + "di picker Ads. Sinkronkan "
            + "produk SpaceCraft dahulu.",
            "error"
        );
        return false;
    }

    b19aResetProductSelection();

    state.b19aLinkedCatalog =
        catalog;

    state.b19aCatalogSourceMode =
        "spacecraft";

    // B19C_PREPARE_ON_APPLY
    await b19cPrepareFromCatalog(
        catalog
    );

    if (b19aCatalogSourceMode) {
        b19aCatalogSourceMode.value =
            "spacecraft";
    }

    state.catalogProductOrder =
        [...productIds];

    renderMultiProductPicker();

    for (const productId of productIds) {
        const input = document.querySelector(
            ".campaignProductCheckbox"
            + `[value="${productId}"]`
        );

        input.checked = true;

        await toggleCampaignProductRaw(
            input
        );
    }

    const nameInput =
        document.getElementById(
            "multiCampaignName"
        );

    if (
        nameInput
        && !nameInput.value.trim()
    ) {
        nameInput.value = (
            `${catalog.catalog_code} — `
            + `${catalog.name}`
        );
    }

    b19aRenderCatalogDetail(
        catalog
    );

    renderCatalogPreflight();

    if (showMessage) {
        b19aSetStatus(
            `${catalog.catalog_code} `
            + "berhasil diterapkan. "
            + "Lengkapi raw video sebelum "
            + "render.",
            "success"
        );
    }

    return true;
}


async function b19aApplySelectedCatalog() {
    let catalog =
        state.b19aCatalogPreview;

    const selectedCode = (
        b19aCatalogSelect?.value
        || ""
    ).trim();

    if (
        !catalog
        || catalog.catalog_code
            !== selectedCode
    ) {
        catalog = (
            await b19aPreviewSelectedCatalog()
        );
    }

    await b19aApplyCatalogObject(
        catalog,
        true
    );
}


function b19aSetCatalogSourceMode() {
    const mode = (
        b19aCatalogSourceMode?.value
        || "custom"
    );

    state.b19aCatalogSourceMode =
        mode;

    b19aLinkedCatalogControls
        ?.classList.toggle(
            "is-hidden",
            mode !== "spacecraft"
        );

    if (mode === "custom") {
        state.b19aLinkedCatalog = null;
        state.b19cCreativeSet = null;
        b19cRenderCreativeSet();

        b19aSetStatus(
            "Mode Custom Creative Set aktif. "
            + "Creative ini belum terhubung "
            + "ke Mini Catalog commerce."
        );

        b19aRenderCatalogDetail(null);

    } else {
        b19aSetStatus(
            "Pilih dan Apply Mini Catalog "
            + "SpaceCraft."
        );

        if (b19aCatalogSelect?.value) {
            b19aPreviewSelectedCatalog();
        }
    }

    renderCatalogPreflight();
}


function b19aSetPricingSource() {
    state.b19aPricingSource = (
        document.getElementById(
            "b19aPricingSource"
        )?.value
        || "meta"
    );

    renderCatalogPreflight();
}


function b19aCatalogSelectionError(
    productIds
) {
    if (
        state.b19aCatalogSourceMode
        !== "spacecraft"
    ) {
        return "";
    }

    const catalog =
        state.b19aLinkedCatalog;

    if (!catalog) {
        return (
            "Pilih dan Apply Mini Catalog "
            + "SpaceCraft."
        );
    }

    const readiness =
        catalog.readiness;

    if (
        readiness
        && !readiness.ready_to_render
    ) {
        return (
            "Creative Readiness belum "
            + "lengkap: "
            + `${readiness.products_ready}/`
            + `${readiness.products_total} `
            + "produk memiliki raw video."
        );
    }

    const expected =
        b19aCatalogProductIds(catalog);

    if (
        expected.length
        !== productIds.length
        || expected.some(
            item =>
                !productIds.includes(
                    item
                )
        )
    ) {
        return (
            "Anggota Creative Set harus "
            + "sama dengan anggota "
            + catalog.catalog_code
            + ". Apply Catalog ulang."
        );
    }

    return "";
}


function b19aCatalogProductIds(catalog) {
    return (
        catalog?.products || []
    ).map(
        item =>
            Number(
                item.local_product_id
                || item.product_id
                || item.id
            )
    ).filter(Boolean);
}


function multiProductPickerProducts() {
    const products = state.products || [];
    const catalogIds =
        b19aCatalogProductIds(
            state.b19aLinkedCatalog
        );

    if (
        !state.filterProductsBySelectedCatalog
        || !catalogIds.length
    ) {
        return {
            products,
            filtered: false,
            catalogIds,
        };
    }

    const catalogIdSet = new Set(
        catalogIds.map(Number)
    );

    return {
        products: products.filter(
            product =>
                catalogIdSet.has(
                    Number(product.id)
                )
        ),
        filtered: true,
        catalogIds,
    };
}


function toggleCatalogProductFilter(input) {
    state.filterProductsBySelectedCatalog =
        Boolean(input?.checked);

    renderMultiProductPicker();
    updateCatalogOrderUI();
    renderCatalogPreflight();
}


function currentPage() {
    return new URLSearchParams(
        window.location.search
    ).get("page") || "studio";
}


function isProductLibraryPage() {
    return currentPage() === "products";
}


function isContentImagePage() {
    return currentPage() === "content-images";
}


function applyPageLayout() {
    const productPage = isProductLibraryPage();
    const contentPage = isContentImagePage();
    document.body.classList.toggle(
        "page-products",
        productPage
    );
    document.body.classList.toggle(
        "page-content-images",
        contentPage
    );
    document.body.classList.toggle(
        "page-studio",
        !productPage && !contentPage
    );

    if (studioHeroSection) {
        studioHeroSection.hidden = productPage || contentPage;
    }

    if (multiProductSection) {
        multiProductSection.hidden = productPage || contentPage;
    }

    if (contentImageSection) {
        contentImageSection.hidden = !contentPage;
    }

    if (productLibraryHeader) {
        productLibraryHeader.hidden = !productPage;
    }

    if (productToolbar) {
        productToolbar.hidden = !productPage;
    }

    if (productGrid) {
        productGrid.hidden = !productPage;
    }

    if (multiProductMenuButton) {
        multiProductMenuButton.textContent = productPage || contentPage
            ? "Studio Generator"
            : "Multi Produk";
    }

    productLibraryMenuButton?.classList.toggle(
        "is-active",
        productPage
    );

    contentImageMenuButton?.classList.toggle(
        "is-active",
        contentPage
    );
}


function openProductLibraryPage() {
    const target = new URL(
        window.location.href
    );
    target.searchParams.set(
        "page",
        "products"
    );
    window.location.href = target.toString();
}


function openStudioPage() {
    const target = new URL(
        window.location.href
    );
    target.search = "";
    target.hash = "";
    window.location.href = target.toString();
}


function openContentImagePage() {
    const target = new URL(
        window.location.href
    );
    target.searchParams.set(
        "page",
        "content-images"
    );
    window.location.href = target.toString();
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

    const previousSelections = new Map(
        [
            ...document.querySelectorAll(
                ".campaignRawVideoSelect"
            ),
        ].map(select => [
            Number(select.dataset.productId),
            select.value,
        ])
    );

    const pickerProducts =
        multiProductPickerProducts();

    const sorted = [
        ...pickerProducts.products,
    ].sort((a, b) =>
        String(a.name || "").localeCompare(String(b.name || ""))
    );

    const linkedCatalog =
        state.b19aLinkedCatalog;

    const filterLabel = linkedCatalog?.catalog_code
        ? `Filter produk ${escapeHtml(linkedCatalog.catalog_code)}`
        : "Filter berdasarkan catalog terpilih";

    multiProductPicker.innerHTML = `
        <div class="picker-head">
            <div>
                <strong>Produk dan Raw Video Real</strong>
                <span>Pilih 5–6 produk, lalu pilih raw video real yang akan digabung menjadi catalog ads.</span>
            </div>
            <div class="picker-head-actions">
                <label class="catalog-filter-toggle">
                    <input
                        type="checkbox"
                        ${state.filterProductsBySelectedCatalog ? "checked" : ""}
                        onchange="toggleCatalogProductFilter(this)"
                    >
                    <span>${filterLabel}</span>
                </label>
                <button
                    type="button"
                    class="mini-button"
                    onclick="selectVisibleCampaignProducts()"
                >
                    Pilih maksimal 6
                </button>
            </div>
        </div>
        <div class="campaign-product-options">
            ${sorted.length ? sorted.map(product => {
                const image = product.primary_image_url || placeholderImage();
                const productId = Number(product.id);
                const checked =
                    state.catalogProductOrder
                        .map(Number)
                        .includes(productId);
                return `
                    <label
                        class="campaign-product-option"
                        data-product-id="${productId}"
                    >
                        <input
                            type="checkbox"
                            class="campaignProductCheckbox"
                            value="${productId}"
                            onchange="toggleCampaignProductRaw(this)"
                            ${checked ? "checked" : ""}
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
                                data-product-id="${productId}"
                            >
                                Pilih produk untuk memuat raw video
                            </small>
                        </span>
                        <div class="campaign-raw-tools">
                            <select
                                class="campaignRawVideoSelect"
                                data-product-id="${productId}"
                                onclick="event.stopPropagation()"
                                onmousedown="event.stopPropagation()"
                                onchange="
                                    event.stopPropagation();
                                    updateRawVideoSelectionStatus(${productId});
                                    renderCatalogPreflight();
                                "
                                disabled
                            >
                                <option value="">Centang untuk memuat raw video</option>
                            </select>

                            <div
                                class="catalog-order-controls"
                                data-order-product-id="${productId}"
                            >
                                <span
                                    class="catalog-order-number"
                                    data-order-number="${productId}"
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
                                            ${productId},
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
                                            ${productId},
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
            }).join("") : `
                <div class="empty compact">
                    Tidak ada produk yang cocok dengan catalog terpilih.
                </div>
            `}
        </div>
    `;

    sorted.forEach(product => {
        const productId = Number(product.id);
        if (
            state.catalogProductOrder
                .map(Number)
                .includes(productId)
        ) {
            populateRawVideoSelect(
                productId,
                previousSelections.get(productId)
                || ""
            );
        }
    });
}


function renderSingleProductControls() {
    if (!singleProductSelect) return;

    const products = [...(state.products || [])]
        .sort((a, b) =>
            String(a.name || "").localeCompare(String(b.name || ""))
        );

    const currentValue = singleProductSelect.value;

    singleProductSelect.innerHTML = `
        <option value="">Pilih produk single campaign</option>
        ${products.map(product => `
            <option value="${Number(product.id)}">
                ${escapeHtml(product.name)}
                ${product.price_label ? ` - ${escapeHtml(product.price_label)}` : ""}
            </option>
        `).join("")}
    `;

    if (
        currentValue
        && products.some(
            product => String(product.id) === String(currentValue)
        )
    ) {
        singleProductSelect.value = currentValue;
    }
}


async function loadSingleProductRawVideos(productId) {
    if (!singleProductRawVideoSelect) return;

    singleProductRawVideoSelect.innerHTML = `
        <option value="">Memuat raw video...</option>
    `;
    singleProductRawVideoSelect.disabled = true;

    if (!productId) {
        singleProductRawVideoSelect.innerHTML = `
            <option value="">Pilih produk dulu</option>
        `;
        return;
    }

    try {
        const data = await api(
            `/api/products/${productId}/raw-videos?ads_only=1`
        );

        const rawVideos = Array.isArray(data.raw_videos)
            ? data.raw_videos
            : [];

        if (!rawVideos.length) {
            singleProductRawVideoSelect.innerHTML = `
                <option value="">Belum ada raw video</option>
            `;
            return;
        }

        singleProductRawVideoSelect.innerHTML = rawVideos.map(video => `
            <option value="${escapeHtml(video.clip_id)}">
                ${video.is_primary ? "Utama - " : ""}
                ${escapeHtml(video.label || video.title || video.clip_id)}
            </option>
        `).join("");
        singleProductRawVideoSelect.disabled = false;
    } catch (error) {
        singleProductRawVideoSelect.innerHTML = `
            <option value="">Gagal memuat raw video</option>
        `;
        if (singleProductMessage) {
            singleProductMessage.textContent =
                `Raw video gagal dimuat: ${error.message}`;
        }
    }
}


function toggleSingleProductVoiceControls() {
    const enabled =
        Boolean(singleProductVoiceoverEnabled?.checked)
        && voiceoverConfigured;

    if (singleProductVoiceId) {
        singleProductVoiceId.disabled = !enabled;
    }

    if (singleProductVoiceMode) {
        singleProductVoiceMode.disabled = !enabled;
    }

    if (singleProductVoiceTextWrap) {
        const showCustom =
            enabled
            && singleProductVoiceMode?.value === "custom";

        singleProductVoiceTextWrap.style.display =
            showCustom ? "block" : "none";
    }

    if (singleProductVoiceText) {
        singleProductVoiceText.disabled =
            !enabled
            || singleProductVoiceMode?.value !== "custom";
    }
}


async function loadSingleProductVoiceOptions() {
    if (
        !singleProductVoiceoverEnabled
        || !singleProductVoiceId
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
            singleProductVoiceoverEnabled.checked = false;
            singleProductVoiceoverEnabled.disabled = true;
            singleProductVoiceId.innerHTML = `
                <option value="">
                    ElevenLabs belum aktif
                </option>
            `;
            toggleSingleProductVoiceControls();
            return;
        }

        const data = await api(
            "/api/voiceover/voices"
        );

        const voices = data.voices || [];
        const savedVoice =
            localStorage.getItem(
                "productAdsSingleVoiceId"
            )
            || localStorage.getItem(
                "productAdsElevenLabsVoiceId"
            );

        singleProductVoiceId.innerHTML = `
            <option value="">
                Pilih voice...
            </option>
            ${voices.map(voice => {
                const labels = voice.labels || {};
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
                voice => voice.voice_id === savedVoice
            )
        ) {
            singleProductVoiceId.value = savedVoice;
        } else if (voices.length) {
            singleProductVoiceId.value = voices[0].voice_id;
        }

        singleProductVoiceoverEnabled.disabled = false;
        toggleSingleProductVoiceControls();

    } catch (error) {
        voiceoverConfigured = false;
        singleProductVoiceoverEnabled.checked = false;
        singleProductVoiceoverEnabled.disabled = true;
        singleProductVoiceId.innerHTML = `
            <option value="">
                Gagal memuat voice
            </option>
        `;
        toggleSingleProductVoiceControls();
    }
}


async function generateSingleProductCampaign() {
    if (!singleProductSelect) return;

    const productId = Number(singleProductSelect.value || 0);

    if (!productId) {
        if (singleProductMessage) {
            singleProductMessage.textContent =
                "Pilih produk dulu.";
        }
        return;
    }

    const rawClipId =
        singleProductRawVideoSelect?.value || null;

    if (!rawClipId) {
        if (singleProductMessage) {
            singleProductMessage.textContent =
                "Produk ini belum punya raw video yang dipilih.";
        }
        return;
    }

    const singleVoiceEnabled =
        Boolean(singleProductVoiceoverEnabled?.checked)
        && voiceoverConfigured;

    const singleVoiceId =
        singleProductVoiceId?.value || "";

    if (singleVoiceEnabled && !singleVoiceId) {
        if (singleProductMessage) {
            singleProductMessage.textContent =
                "Pilih voice ElevenLabs dulu.";
        }
        return;
    }

    if (singleVoiceId) {
        localStorage.setItem(
            "productAdsSingleVoiceId",
            singleVoiceId
        );
    }

    if (singleProductGenerateButton) {
        singleProductGenerateButton.disabled = true;
        singleProductGenerateButton.textContent =
            "Mengirim render...";
    }

    if (singleProductMessage) {
        singleProductMessage.textContent =
            "Membuat single product campaign...";
    }

    try {
        const selectedProduct = (state.products || []).find(
            product => Number(product.id) === productId
        );

        const payload = {
            product_id: productId,
            raw_clip_id: rawClipId,
            name: selectedProduct
                ? `${selectedProduct.name} Single Product Video`
                : null,
            duration_seconds: Number(
                document.getElementById(
                    "singleProductDuration"
                )?.value || 20
            ),
            aspect_ratio: "9:16",
            hook:
                document.getElementById(
                    "singleProductHook"
                )?.value.trim() || null,
            cta:
                document.getElementById(
                    "singleProductCta"
                )?.value.trim() || null,
            image_count: 4,
            voiceover_enabled: singleVoiceEnabled,
            voice_id: singleVoiceEnabled
                ? singleVoiceId
                : null,
            voiceover_mode:
                singleProductVoiceMode?.value || "auto",
            voiceover_text:
                singleProductVoiceText?.value.trim() || null,
        };

        const data = await api(
            "/api/campaigns/single-product-video",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(payload),
            }
        );

        if (singleProductMessage) {
            singleProductMessage.textContent = data.message;
        }

        await loadMultiProductCampaigns();
    } catch (error) {
        if (singleProductMessage) {
            singleProductMessage.textContent =
                `Generate gagal: ${error.message}`;
        }
    } finally {
        if (singleProductGenerateButton) {
            singleProductGenerateButton.disabled = false;
            singleProductGenerateButton.textContent =
                "Render Single Product Video";
        }
    }
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
    const mediaType =
        video.media_type
        || video.asset_type
        || "video";

    const mediaLabel =
        mediaType === "image"
            ? "Image"
            : "Video";

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
        `${primaryLabel}${mediaLabel} - ${title}`
        + `${typeLabel}${fitLabel}${sizeMb}`
    );
}


function rawVideoCacheKey(productId, adsOnly = true) {
    return `${Number(productId)}:${adsOnly ? "ads" : "all"}`;
}


function clearRawVideoCache(productId) {
    delete state.rawVideosByProduct[
        rawVideoCacheKey(productId, true)
    ];
    delete state.rawVideosByProduct[
        rawVideoCacheKey(productId, false)
    ];
    delete state.rawVideosByProduct[
        Number(productId)
    ];
}


async function loadRawVideosForProduct(
    productId,
    options = {}
) {
    const adsOnly =
        options.adsOnly !== false;
    const cacheKey =
        rawVideoCacheKey(
            productId,
            adsOnly
        );

    if (state.rawVideosByProduct[cacheKey]) {
        return state.rawVideosByProduct[cacheKey];
    }

    const url = (
        `/api/products/${productId}/raw-videos`
        + (adsOnly ? "?ads_only=1" : "")
    );

    const data = await api(url);
    state.rawVideosByProduct[cacheKey] = data.raw_videos || [];
    return state.rawVideosByProduct[cacheKey];
}


async function populateRawVideoSelect(productId, preferredClipId = "") {
    const select = document.querySelector(
        `.campaignRawVideoSelect[data-product-id="${productId}"]`
    );

    if (!select) return;

    select.disabled = true;
    select.innerHTML = '<option value="">Memuat asset...</option>';

    try {
        const rawVideos = await loadRawVideosForProduct(
            productId,
            {adsOnly: true}
        );

        if (!rawVideos.length) {
            select.innerHTML = '<option value="">Belum ada video/image</option>';
            setRawVideoGenerateState(
                productId,
                "Belum ada asset Ads. Centang image/video di Product Workspace."
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
        updateRawVideoSelectionStatus(productId);
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


function updateRawVideoSelectionStatus(productId) {
    const video = selectedRawVideoForProduct(productId);
    const videos = state.rawVideosByProduct[
        rawVideoCacheKey(productId, true)
    ] || [];

    if (!video) {
        setRawVideoGenerateState(
            productId,
            videos.length
                ? `${videos.length} asset tersedia, pilih salah satu`
                : "Belum ada video/image"
        );
        return;
    }

    const label = rawVideoLabel(video);
    setRawVideoGenerateState(
        productId,
        `Dipakai: ${label}`
    );
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
            rawVideoCacheKey(productId, true)
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

    // B19A_LINKED_PREFLIGHT
    const b19aError =
        b19aCatalogSelectionError(
            productIds
        );

    if (b19aError) {
        errors.push(
            b19aError
        );
    }

    // B19C_PREFLIGHT_GUARD
    const b19cError =
        b19cPreflightError();

    if (b19cError) {
        errors.push(
            b19cError
        );
    }

    // B19D_PREFLIGHT_DRIFT_GUARD
    const b19dError =
        b19dDriftError();

    if (b19dError) {
        errors.push(
            b19dError
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
                    `${productName}: asset belum dipilih.`
                );

                return {
                    productId,
                    productName,
                    index,
                    valid: false,
                    message:
                        "Asset belum dipilih",
                };
            }

            const mediaType =
                video.media_type
                || video.asset_type
                || "video";

            if (mediaType === "image") {
                return {
                    productId,
                    productName,
                    index,
                    valid: true,
                    message:
                        "Image motion siap",
                    video,
                    segmentDuration,
                    effectiveDuration:
                        segmentDuration,
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
    const productPage =
        isProductLibraryPage();

    if (productPage) {
        globalStatus.textContent =
            "Memuat produk published...";
    }

    const params = new URLSearchParams({
        limit: "100",
        _ts: String(Date.now()),
    });

    const keyword =
        searchInput.value.trim();

    if (keyword) {
        params.set(
            "search",
            keyword
        );
    }

    try {
        const data = await api(
            `/api/products?${params}`
        );

        const publishedProducts = (
            Array.isArray(data.products)
                ? data.products
                : []
        ).filter(
            product =>
                String(
                    product?.status || ""
                )
                .trim()
                .toLowerCase()
                === "published"
        );

        state.products =
            publishedProducts;

        renderMultiProductPicker();
        renderSingleProductControls();

        if (productPage) {
            if (!publishedProducts.length) {
                productGrid.innerHTML = `
                    <div class="empty">
                        Tidak ada produk published.
                        Produk draft dan archived
                        disembunyikan dari Ads.
                    </div>
                `;
            } else {
                productGrid.innerHTML =
                    publishedProducts
                        .map(productCard)
                        .join("");
            }

            globalStatus.textContent =
                `${publishedProducts.length} dari `
                + `${Number(data.total || 0)} `
                + "produk published ditampilkan";
        } else if (productGrid) {
            productGrid.innerHTML = "";
            globalStatus.textContent = "";
        }

    } catch (error) {
        if (productPage) {
            productGrid.innerHTML = `
                <div class="empty">
                    ${escapeHtml(
                        error.message
                    )}
                </div>
            `;
        }

        globalStatus.textContent =
            "Gagal memuat produk";
    }
}

async function syncProducts() {
    syncButton.disabled = true;
    syncButton.textContent =
        "Sinkronisasi...";

    globalStatus.textContent =
        "Mengambil status produk dari Spacecraft...";

    try {
        const data = await api(
            "/api/products/sync",
            {
                method: "POST",
            }
        );

        globalStatus.textContent =
            `Sinkronisasi selesai: `
            + `${Number(
                data.published_local || 0
            )} published ditampilkan, `
            + `${Number(
                data.hidden_received || 0
            )} draft/archived disembunyikan`;

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
    const canUseInAds = [
        "image",
        "video",
    ].includes(asset.asset_type);

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

                ${canUseInAds ? `
                    <label class="asset-ads-toggle">
                        <input
                            id="assetAdsEnabled-${Number(asset.id)}"
                            type="checkbox"
                            ${asset.ads_enabled ? "checked" : ""}
                            onchange="saveAssetAdsEnabled(
                                ${Number(asset.id)},
                                this.checked
                            )"
                        >
                        <span>Pakai di dropdown Ads</span>
                    </label>
                ` : ""}

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
                        .filter(asset => ![
                            "image",
                            "video",
                        ].includes(asset.asset_type))
                        .map(uploadedAssetCard)
                        .join("")}

                    ${
                        !sourceMedia.length
                        && !assets.filter(asset => ![
                            "image",
                            "video",
                        ].includes(asset.asset_type)).length
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
                        <h3>Asset Image / Video Ads</h3>
                        <p>
                            Pilih image/video yang boleh muncul
                            di dropdown Catalog Ads.
                        </p>
                    </div>

                    <div class="raw-video-upload-actions">
                        <input
                            id="rawVideoFiles"
                            type="file"
                            multiple
                            accept="
                                image/jpeg,
                                image/png,
                                image/webp,
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
                            Upload Image / Video
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

    const mediaType =
        video.media_type
        || video.asset_type
        || "video";

    const preview = mediaType === "image"
        ? `
            <img
                class="raw-video-preview"
                src="${escapeHtml(video.url)}"
                alt="${escapeHtml(video.title || video.label || "Image")}"
                loading="lazy"
            >
        `
        : `
            <video
                class="raw-video-preview"
                src="${escapeHtml(video.url)}"
                controls
                preload="metadata"
                playsinline
            ></video>
        `;

    return `
        <article
            class="raw-video-card
                ${video.is_primary
                    ? "is-primary"
                    : ""}"
            data-asset-id="${assetId}"
        >
            <div class="raw-video-preview-wrap">
                ${preview}

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
                            ${mediaType === "image"
                                ? "disabled"
                                : ""}
                            ${video.is_primary
                                ? "checked"
                                : ""}
                        >

                        <span>Jadikan video utama</span>
                    </label>

                    <label
                        class="raw-video-primary-toggle"
                    >
                        <input
                            id="rawVideoAdsEnabled-${assetId}"
                            type="checkbox"
                            ${video.ads_enabled
                                ? "checked"
                                : ""}
                            onchange="saveAssetAdsEnabled(
                                ${assetId},
                                this.checked
                            )"
                        >

                        <span>Pakai di dropdown Ads</span>
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

    const adsEnabledInput =
        document.getElementById(
            `rawVideoAdsEnabled-${assetId}`
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
        is_primary: primaryInput.checked
            && !primaryInput.disabled,
        ads_enabled: Boolean(
            adsEnabledInput?.checked
        ),
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

        clearRawVideoCache(state.activeProductId);

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


async function saveAssetAdsEnabled(
    assetId,
    enabled
) {
    const checkbox =
        document.getElementById(
            `rawVideoAdsEnabled-${assetId}`
        );
    const status =
        document.getElementById(
            `rawVideoSettingStatus-${assetId}`
        )
        || workspaceStatus;

    if (!state.activeProductId) return;

    if (status) {
        status.textContent = enabled
            ? "Mengaktifkan asset untuk Ads..."
            : "Menghapus asset dari dropdown Ads...";
    }

    try {
        const typeInput =
            document.getElementById(
                `rawVideoType-${assetId}`
            );
        const fitInput =
            document.getElementById(
                `rawVideoFitMode-${assetId}`
            );
        const primaryInput =
            document.getElementById(
                `rawVideoPrimary-${assetId}`
            );
        const trimStartInput =
            document.getElementById(
                `rawVideoTrimStart-${assetId}`
            );
        const trimEndInput =
            document.getElementById(
                `rawVideoTrimEnd-${assetId}`
            );
        const trimStartValue =
            Number.parseFloat(
                trimStartInput?.value
            );
        const trimEndRaw =
            trimEndInput?.value?.trim();
        const trimEndValue =
            trimEndRaw
                ? Number.parseFloat(trimEndRaw)
                : null;
        const payload = {
            video_type:
                typeInput?.value || "lifestyle",
            fit_mode:
                fitInput?.value || "cover",
            is_primary:
                Boolean(
                    primaryInput
                    && !primaryInput.disabled
                    && primaryInput.checked
                ),
            ads_enabled: Boolean(enabled),
            trim_start:
                Number.isFinite(trimStartValue)
                    ? Math.max(0, trimStartValue)
                    : 0,
            trim_end:
                Number.isFinite(trimEndValue)
                    ? Math.max(0, trimEndValue)
                    : null,
        };

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
                data.message
                || "Tersimpan. Dropdown Ads diperbarui.";
        }

        const activeProductId =
            state.activeProductId;
        const activeSelect =
            document.querySelector(
                `.campaignRawVideoSelect[data-product-id="${activeProductId}"]`
            );
        const preferredClipId =
            activeSelect && enabled
                ? activeSelect.value
                : "";

        clearRawVideoCache(state.activeProductId);

        if (activeSelect) {
            await populateRawVideoSelect(
                activeProductId,
                preferredClipId
            );
        }

        if (status) {
            window.setTimeout(
                () => {
                    if (
                        status.textContent === data.message
                        || status.textContent === "Tersimpan. Dropdown Ads diperbarui."
                    ) {
                        status.textContent = "";
                    }
                },
                2200
            );
        }

    } catch (error) {
        if (checkbox) {
            checkbox.checked = !enabled;
        }

        if (status) {
            status.textContent =
                `Gagal menyimpan filter Ads: ${error.message}`;
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
        clearRawVideoCache(productId);

        const videos =
            await loadRawVideosForProduct(
                Number(productId),
                {adsOnly: false}
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
                "Pilih file image atau video terlebih dahulu.";
        }
        return;
    }

    const files = [...input.files];

    const invalid = files.find(file =>
        !(
            file.type === "image/jpeg"
            || file.type === "image/png"
            || file.type === "image/webp"
            || file.type === "video/mp4"
            || file.type === "video/webm"
            || file.type === "video/quicktime"
            || /\.(jpe?g|png|webp|mp4|mov|webm)$/i.test(file.name)
        )
    );

    if (invalid) {
        if (status) {
            status.textContent =
                `File bukan image/video yang didukung: `
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
            `Mengunggah ${files.length} asset...`;
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

        clearRawVideoCache(state.activeProductId);

        await loadWorkspaceRawVideoLibrary(
            state.activeProductId
        );

        await loadHealth();

    } catch (error) {
        if (status) {
            status.textContent =
                `Upload image/video gagal: `
                + error.message;
        }

    } finally {
        button.disabled = false;
        button.textContent =
            "Upload Image / Video";
    }
}


function campaignVisualElements(slot) {
    const normalizedSlot = slot === "cta" ? "cta" : "hook";
    const prefix = normalizedSlot === "cta"
        ? "campaignCtaImage"
        : "campaignHookImage";

    return {
        slot: normalizedSlot,
        input: document.getElementById(`${prefix}File`),
        button: document.getElementById(`${prefix}UploadButton`),
        status: document.getElementById(`${prefix}Status`),
    };
}


function updateCampaignVisualStatus(slot, message, stateClass = "") {
    const { status } = campaignVisualElements(slot);

    if (!status) return;

    status.classList.remove("is-ready", "is-error");
    if (stateClass) {
        status.classList.add(stateClass);
    }
    status.textContent = message;
}


async function uploadCampaignVisualAsset(slot) {
    const elements = campaignVisualElements(slot);
    const file = elements.input?.files?.[0];

    if (!file) {
        updateCampaignVisualStatus(
            slot,
            "Pilih image terlebih dahulu.",
            "is-error"
        );
        return;
    }

    const formData = new FormData();
    formData.append("slot", elements.slot);
    formData.append("file", file);

    if (elements.button) {
        elements.button.disabled = true;
        elements.button.textContent = "Mengupload...";
    }

    updateCampaignVisualStatus(
        slot,
        "Mengupload visual campaign..."
    );

    try {
        const data = await api(
            "/api/campaign-visual-assets",
            {
                method: "POST",
                body: formData,
            }
        );

        state.campaignVisualAssets[elements.slot] = data.asset || null;
        updateCampaignVisualStatus(
            slot,
            `${data.message}: ${data.asset?.original_name || file.name}`,
            "is-ready"
        );
    } catch (error) {
        state.campaignVisualAssets[elements.slot] = null;
        updateCampaignVisualStatus(
            slot,
            `Upload gagal: ${error.message}`,
            "is-error"
        );
    } finally {
        if (elements.button) {
            elements.button.disabled = false;
            elements.button.textContent = elements.slot === "cta"
                ? "Upload CTA"
                : "Upload Hook";
        }
    }
}


function clearCampaignVisualAsset(slot) {
    const elements = campaignVisualElements(slot);

    state.campaignVisualAssets[elements.slot] = null;
    if (elements.input) {
        elements.input.value = "";
    }

    updateCampaignVisualStatus(
        slot,
        elements.slot === "cta"
            ? "Belum ada custom CTA image."
            : "Belum ada custom hook image."
    );
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

        clearRawVideoCache(state.activeProductId);

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

        clearRawVideoCache(state.activeProductId);

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

        clearRawVideoCache(state.activeProductId);

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

        clearRawVideoCache(state.activeProductId);

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


function renderContentImageCard(image) {
    const url = escapeHtml(image.url || "");
    const filename = escapeHtml(
        image.filename || "content-image.webp"
    );
    const sizeLabel = escapeHtml(image.size_label || "");

    return `
        <article class="content-image-card">
            <img src="${url}" alt="${filename}" loading="lazy">
            <div class="content-image-card-body">
                <strong>${filename}</strong>
                <span>${sizeLabel}</span>
                <div class="content-image-actions">
                    <a class="button secondary" href="${url}" target="_blank" rel="noreferrer">
                        Buka
                    </a>
                    <a class="button primary" href="${url}" download="${filename}">
                        Download
                    </a>
                </div>
            </div>
        </article>
    `;
}


function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}


function renderContentImageResult(data) {
    const images = data.images || [];
    contentImageResults.innerHTML = images.length
        ? `
            <div class="content-image-result-heading">
                <div>
                    <strong>${images.length} image selesai dibuat</strong>
                    <span>${escapeHtml(data.model || "")}</span>
                </div>
            </div>
            <div class="content-image-grid">
                ${images.map(renderContentImageCard).join("")}
            </div>
        `
        : `<div class="empty">Belum ada image yang dibuat.</div>`;
}


async function pollContentImageJob(jobId) {
    for (let attempt = 0; attempt < 90; attempt += 1) {
        const job = await api(
            `/api/content-images/jobs/${encodeURIComponent(jobId)}`
        );
        const progress = Number(job.progress || 0);
        const message = job.message || "Generate berjalan...";
        contentImageStatus.textContent =
            `${message} ${progress ? `(${progress}%)` : ""}`;

        if (job.status === "completed") {
            renderContentImageResult(job.result || {});
            contentImageStatus.textContent =
                "Selesai. Output sudah dikompres ke WebP dan siap dipakai.";
            return;
        }

        if (job.status === "failed") {
            throw new Error(job.message || "Generate gagal");
        }

        await sleep(2500);
    }

    throw new Error(
        "Generate masih berjalan terlalu lama. Coba cek lagi beberapa saat."
    );
}


async function generateContentImage(event) {
    event.preventDefault();

    const productNameInput =
        document.getElementById("contentImageProductName");
    const productTypeInput =
        document.getElementById("contentImageProductType");
    const sceneInput =
        document.getElementById("contentImageScene");
    const ratioInput =
        document.getElementById("contentImageRatio");
    const countInput =
        document.getElementById("contentImageCount");
    const promptInput =
        document.getElementById("contentImagePrompt");
    const fileInput =
        document.getElementById("contentImageFile");

    const productName =
        String(productNameInput?.value || "").trim();
    const file = fileInput?.files?.[0];

    if (!productName) {
        contentImageStatus.textContent =
            "Isi nama produk dulu ya.";
        return;
    }

    if (!file) {
        contentImageStatus.textContent =
            "Upload raw image produk dulu.";
        return;
    }

    const formData = new FormData();
    formData.append("product_name", productName);
    formData.append(
        "product_type",
        productTypeInput?.value || "keychain_clicker"
    );
    formData.append(
        "scene",
        sceneInput?.value || "toy_shelf"
    );
    formData.append(
        "aspect_ratio",
        ratioInput?.value || "4:5"
    );
    formData.append(
        "count",
        countInput?.value || "1"
    );
    formData.append(
        "prompt",
        promptInput?.value || ""
    );
    formData.append(
        "raw_image",
        file
    );

    contentImageGenerateButton.disabled = true;
    contentImageGenerateButton.textContent =
        "Generating...";
    contentImageStatus.textContent =
        "Membuat image content dari raw image...";

    try {
        const data = await api(
            "/api/content-images/jobs",
            {
                method: "POST",
                body: formData,
            }
        );

        contentImageStatus.textContent =
            "Generate sudah masuk antrean. Menunggu hasil...";
        await pollContentImageJob(data.job_id);

    } catch (error) {
        contentImageStatus.textContent =
            `Generate image gagal: ${error.message}`;

    } finally {
        contentImageGenerateButton.disabled = false;
        contentImageGenerateButton.textContent =
            "Generate Content Image";
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
        if (isProductLibraryPage() || isContentImagePage()) {
            openStudioPage();
            return;
        }

        loadMultiVoiceOptions();
        loadCatalogMusicLibrary();
        multiProductSection?.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
    }
);

productLibraryMenuButton?.addEventListener(
    "click",
    openProductLibraryPage
);

contentImageMenuButton?.addEventListener(
    "click",
    openContentImagePage
);

backToStudioButton?.addEventListener(
    "click",
    openStudioPage
);

contentImageForm?.addEventListener(
    "submit",
    generateContentImage
);

generateMultiCampaignButton?.addEventListener(
    "click",
    generateMultiProductCampaign
);

singleProductSelect?.addEventListener(
    "change",
    event => {
        loadSingleProductRawVideos(
            Number(event.target.value || 0)
        );
    }
);

singleProductGenerateButton?.addEventListener(
    "click",
    generateSingleProductCampaign
);

singleProductVoiceoverEnabled?.addEventListener(
    "change",
    toggleSingleProductVoiceControls
);

singleProductVoiceMode?.addEventListener(
    "change",
    toggleSingleProductVoiceControls
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
window.saveAssetAdsEnabled = saveAssetAdsEnabled;
window.deleteAsset = deleteAsset;
window.generateImageVariations =
    generateImageVariations;

applyPageLayout();
loadHealth();
loadProducts();
loadB19aCatalogs();
b19cRenderCreativeSet();
loadMultiVoiceOptions();
loadSingleProductVoiceOptions();


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

function campaignHistoryMeta(campaign) {
    const settings = campaign.settings || {};
    const productCount = Number(settings.product_count || 1);
    const productLabel = productCount > 1
        ? ` | ${productCount} produk`
        : "";

    return `${campaignTemplateLabel(settings)} | ${campaignAudienceLabel(settings)}${productLabel} | ${campaign.status} | ${campaign.completed_count}/${campaign.variations} selesai | ${campaign.failed_count} gagal${settings.voiceover_enabled ? " | VO ElevenLabs" : ""}`;
}

function renderCampaignHistoryPagination(total, page, pageSize) {
    const pageCount = Math.max(1, Math.ceil(total / pageSize));
    const start = total ? ((page - 1) * pageSize) + 1 : 0;
    const end = Math.min(total, page * pageSize);

    return `
        <div class="campaign-pagination">
            <label class="campaign-page-size">
                Tampilkan
                <select onchange="setCampaignHistoryPageSize(this.value)">
                    <option value="5" ${pageSize === 5 ? "selected" : ""}>5</option>
                    <option value="10" ${pageSize === 10 ? "selected" : ""}>10</option>
                </select>
                row
            </label>
            <div class="campaign-page-actions">
                <small>${start}-${end} dari ${total}</small>
                <button type="button" class="mini-button" onclick="setCampaignHistoryPage(${page - 1})" ${page <= 1 ? "disabled" : ""}>Sebelumnya</button>
                <span>${page}/${pageCount}</span>
                <button type="button" class="mini-button" onclick="setCampaignHistoryPage(${page + 1})" ${page >= pageCount ? "disabled" : ""}>Berikutnya</button>
            </div>
        </div>
    `;
}

function renderCampaignHistoryTable(campaigns) {
    if (!campaigns.length) {
        return `
            <div class="empty">
                Belum ada raw video catalog ads.
            </div>
        `;
    }

    const pageSize = Number(state.campaignHistoryPageSize || 5);
    const pageCount = Math.max(1, Math.ceil(campaigns.length / pageSize));
    const page = Math.min(
        Math.max(1, Number(state.campaignHistoryPage || 1)),
        pageCount
    );
    state.campaignHistoryPage = page;

    const visibleCampaigns = campaigns.slice(
        (page - 1) * pageSize,
        page * pageSize
    );

    return `
        <div class="campaign-table">
            ${renderCampaignHistoryPagination(campaigns.length, page, pageSize)}
            <div class="campaign-table-head">
                <span>Campaign</span>
                <span>Progress</span>
                <span>Status</span>
                <span>Aksi</span>
            </div>
            ${visibleCampaigns.map(campaign => {
                const progress = campaignProgress(campaign);
                return `
                    <article class="campaign-row">
                        <div class="campaign-main">
                            <strong>${escapeHtml(campaign.name)}</strong>
                            <small>${escapeHtml(campaignHistoryMeta(campaign))}</small>
                        </div>
                        <div class="campaign-progress-cell">
                            <div class="campaign-progress-meta">
                                <span>${campaign.completed_count}/${campaign.variations}</span>
                                <b>${progress}%</b>
                            </div>
                            <div class="progress is-compact">
                                <span style="width:${progress}%"></span>
                            </div>
                        </div>
                        <div class="campaign-status-cell">
                            <span class="campaign-pill">${escapeHtml(campaign.status)}</span>
                            ${campaign.failed_count ? `<span class="campaign-pill is-error">${campaign.failed_count} gagal</span>` : ""}
                        </div>
                        <div class="campaign-actions">
                            <button type="button" class="mini-button" onclick="viewCampaign(${campaign.id}, event)">Lihat</button>
                            ${campaign.failed_count ? `<button type="button" class="mini-button" onclick="retryCampaign(${campaign.id}, event)">Retry</button>` : ""}
                            <button type="button" class="mini-button" onclick="deleteCampaign(${campaign.id}, event)">Hapus</button>
                        </div>
                        <div id="campaignJobs-${campaign.id}" class="render-grid"></div>
                    </article>
                `;
            }).join("")}
            ${renderCampaignHistoryPagination(campaigns.length, page, pageSize)}
        </div>
    `;
}

function setCampaignHistoryPage(page) {
    state.campaignHistoryPage = Math.max(1, Number(page || 1));
    loadMultiProductCampaigns();
}

function setCampaignHistoryPageSize(pageSize) {
    state.campaignHistoryPageSize = Number(pageSize) === 10 ? 10 : 5;
    state.campaignHistoryPage = 1;
    loadMultiProductCampaigns();
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



let b13VariantRecipes = [];


function b13Lines(elementId) {
    return (
        document.getElementById(
            elementId
        )?.value || ""
    )
        .split(/\r?\n/)
        .map(value => value.trim())
        .filter(Boolean);
}


function b13AlphaCode(
    prefix,
    index
) {
    const alphabet =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

    const letter =
        alphabet[index % alphabet.length];

    const round =
        Math.floor(index / alphabet.length);

    return (
        `${prefix}-${letter}`
        + (
            round > 0
                ? `${round + 1}`
                : ""
        )
    );
}


function b13ProductOrders(
    productClips
) {
    const base = productClips.map(
        item => item.product_id
    );

    const result = [
        {
            code: "ORDER-A",
            label: "Urutan Asli",
            order: base,
        },
    ];

    if (
        document.getElementById(
            "b13OrderReverse"
        )?.checked
    ) {
        result.push({
            code: "ORDER-B",
            label: "Urutan Terbalik",
            order: [...base].reverse(),
        });
    }

    if (
        document.getElementById(
            "b13OrderRotate"
        )?.checked
        && base.length > 1
    ) {
        result.push({
            code: "ORDER-C",
            label: "Rotasi Produk",
            order: [
                ...base.slice(1),
                base[0],
            ],
        });
    }

    return result;
}


function b13BuildRecipes() {
    const productClips =
        selectedCampaignProductClips();

    if (
        productClips.length < 5
        || productClips.length > 6
    ) {
        throw new Error(
            "Pilih 5–6 produk sebelum "
            + "membuat variant matrix."
        );
    }

    const hooks = (
        b13Lines("b13HookVariants")
        .length
            ? b13Lines(
                "b13HookVariants"
            )
            : [null]
    );

    const ctas = (
        b13Lines("b13CtaVariants")
        .length
            ? b13Lines(
                "b13CtaVariants"
            )
            : [null]
    );

    const promos = (
        b13Lines("b13PromoVariants")
        .length
            ? b13Lines(
                "b13PromoVariants"
            )
            : [null]
    );

    const voices = (
        b13Lines("b13VoiceVariants")
        .length
            ? b13Lines(
                "b13VoiceVariants"
            )
            : [null]
    );

    const orders =
        b13ProductOrders(productClips);

    const hardLimit = 24;

    const requestedLimit = Math.max(
        1,
        Math.min(
            hardLimit,
            Number(
                document.getElementById(
                    "b13MaxVariants"
                )?.value || 12
            )
        )
    );

    const recipes = [];
    const duplicateKeys = new Set();

    outer:
    for (
        let hookIndex = 0;
        hookIndex < hooks.length;
        hookIndex += 1
    ) {
        for (
            let ctaIndex = 0;
            ctaIndex < ctas.length;
            ctaIndex += 1
        ) {
            for (
                let promoIndex = 0;
                promoIndex < promos.length;
                promoIndex += 1
            ) {
                for (
                    let orderIndex = 0;
                    orderIndex < orders.length;
                    orderIndex += 1
                ) {
                    for (
                        let voiceIndex = 0;
                        voiceIndex < voices.length;
                        voiceIndex += 1
                    ) {
                        const recipe = {
                            hook:
                                hooks[hookIndex],
                            cta:
                                ctas[ctaIndex],
                            promo_text:
                                promos[promoIndex],
                            voiceover_text:
                                voices[voiceIndex],
                            product_order:
                                orders[orderIndex]
                                    .order,
                            hook_code:
                                b13AlphaCode(
                                    "HOOK",
                                    hookIndex
                                ),
                            cta_code:
                                b13AlphaCode(
                                    "CTA",
                                    ctaIndex
                                ),
                            promo_code:
                                b13AlphaCode(
                                    "PROMO",
                                    promoIndex
                                ),
                            order_code:
                                orders[orderIndex]
                                    .code,
                            voice_code:
                                b13AlphaCode(
                                    "VOICE",
                                    voiceIndex
                                ),
                            enabled: true,
                        };

                        recipe.label = [
                            recipe.hook_code,
                            recipe.cta_code,
                            recipe.promo_code,
                            recipe.order_code,
                            recipe.voice_code,
                        ].join(" · ");

                        const key = JSON.stringify({
                            hook: recipe.hook,
                            cta: recipe.cta,
                            promo:
                                recipe.promo_text,
                            voice:
                                recipe.voiceover_text,
                            order:
                                recipe.product_order,
                        });

                        if (
                            duplicateKeys.has(key)
                        ) {
                            continue;
                        }

                        duplicateKeys.add(key);
                        recipes.push(recipe);

                        if (
                            recipes.length
                            >= requestedLimit
                        ) {
                            break outer;
                        }
                    }
                }
            }
        }
    }

    return {
        recipes,
        theoreticalCount:
            hooks.length
            * ctas.length
            * promos.length
            * voices.length
            * orders.length,
        requestedLimit,
    };
}


function renderB13VariantPreview() {
    const target = document.getElementById(
        "b13VariantPreview"
    );

    const summary = document.getElementById(
        "b13VariantSummary"
    );

    if (!target || !summary) return;

    try {
        const result =
            b13BuildRecipes();

        b13VariantRecipes =
            result.recipes;

        summary.className =
            "b13-variant-summary is-ready";

        summary.textContent =
            `${result.recipes.length} kombinasi `
            + `dipilih dari `
            + `${result.theoreticalCount} kemungkinan.`;

        target.innerHTML =
            result.recipes.map(
                (recipe, index) => `
                    <label
                        class="b13-recipe-card"
                        data-recipe-index="${index}"
                    >
                        <input
                            type="checkbox"
                            class="b13RecipeCheckbox"
                            data-index="${index}"
                            checked
                            onchange="
                                updateB13VariantCount()
                            "
                        >

                        <div class="b13-recipe-copy">
                            <strong>
                                Variant ${index + 1}
                            </strong>

                            <span>
                                ${escapeHtml(
                                    recipe.label
                                )}
                            </span>

                            <small>
                                Hook:
                                ${escapeHtml(
                                    recipe.hook
                                    || "Auto system"
                                )}
                            </small>

                            <small>
                                CTA:
                                ${escapeHtml(
                                    recipe.cta
                                    || "Auto system"
                                )}
                            </small>

                            <small>
                                Promo:
                                ${escapeHtml(
                                    recipe.promo_text
                                    || "Promo campaign"
                                )}
                            </small>
                        </div>
                    </label>
                `
            ).join("");

        updateB13VariantCount();

    } catch (error) {
        b13VariantRecipes = [];

        summary.className =
            "b13-variant-summary is-error";

        summary.textContent =
            error.message;

        target.innerHTML = `
            <div class="b13-empty">
                Lengkapi produk dan raw video,
                lalu buat preview matrix.
            </div>
        `;
    }
}


function updateB13VariantCount() {
    const checked = [
        ...document.querySelectorAll(
            ".b13RecipeCheckbox:checked"
        )
    ];

    const count = checked.length;

    const countTarget =
        document.getElementById(
            "b13SelectedCount"
        );

    if (countTarget) {
        countTarget.textContent =
            `${count} variant dipilih`;
    }

    const variationInput =
        document.getElementById(
            "multiCampaignVariations"
        );

    if (
        variationInput
        && count > 0
    ) {
        variationInput.value =
            Math.min(count, 20);
    }
}


function getSelectedB13Recipes() {
    return [
        ...document.querySelectorAll(
            ".b13RecipeCheckbox:checked"
        )
    ]
        .map(input => (
            b13VariantRecipes[
                Number(input.dataset.index)
            ]
        ))
        .filter(Boolean)
        .slice(0, 24);
}


function clearB13VariantMatrix() {
    b13VariantRecipes = [];

    document.querySelectorAll(
        "#b13HookVariants,"
        + "#b13CtaVariants,"
        + "#b13PromoVariants,"
        + "#b13VoiceVariants"
    ).forEach(element => {
        element.value = "";
    });

    const reverse =
        document.getElementById(
            "b13OrderReverse"
        );

    const rotate =
        document.getElementById(
            "b13OrderRotate"
        );

    if (reverse) reverse.checked = false;
    if (rotate) rotate.checked = false;

    const target =
        document.getElementById(
            "b13VariantPreview"
        );

    const summary =
        document.getElementById(
            "b13VariantSummary"
        );

    if (target) {
        target.innerHTML = `
            <div class="b13-empty">
                Belum ada variant matrix.
            </div>
        `;
    }

    if (summary) {
        summary.className =
            "b13-variant-summary";

        summary.textContent =
            "Mode variasi standar aktif.";
    }

    updateB13VariantCount();
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
        "multiCampaignVoiceId",
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

        variations: (
            getSelectedB13Recipes().length
            || Number(
                document.getElementById(
                    "multiCampaignVariations"
                )?.value || 1
            )
        ),

        variant_recipes:
            getSelectedB13Recipes(),

        product_clips: productClips,

        audience:
            document.getElementById(
                "multiCampaignAudience"
            )?.value
            || "retail_bulk",

        min_order_qty: 6,

        // B18C_RAW_COPY_PAYLOAD

        hook: document.getElementById("multiCampaignHook")?.value.trim() || null,

        cta: document.getElementById("multiCampaignCta")?.value.trim() || null,

        hook_image_asset_id:
            state.campaignVisualAssets?.hook?.asset_id || null,

        cta_image_asset_id:
            state.campaignVisualAssets?.cta?.asset_id || null,

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




// B18I_SINGLE_SUBMIT_STATE
let rawCatalogSubmissionInFlight = false;
let rawCatalogSubmissionStartedAt = 0;

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
        message.textContent = "Setiap produk terpilih harus punya asset video/image.";
        return;
    }

    const missingVisuals = [];
    if (!state.campaignVisualAssets?.hook?.asset_id) {
        missingVisuals.push("Hook");
    }
    if (!state.campaignVisualAssets?.cta?.asset_id) {
        missingVisuals.push("CTA");
    }

    if (missingVisuals.length) {
        const proceed = confirm(
            `${missingVisuals.join(" dan ")} image belum diupload.\n\n`
            + "Sistem akan membuat visual otomatis dari template, hook, "
            + "CTA, promo, dan daftar produk yang sudah ada.\n\n"
            + "Lanjut generate?"
        );

        if (!proceed) {
            message.textContent =
                "Generate dibatalkan. Upload image hook/CTA jika ingin custom visual.";
            return;
        }
    }

    if (rawCatalogSubmissionInFlight) {
        message.textContent =
            "Permintaan render sedang diproses. "
            + "Mohon tunggu, jangan klik ulang.";
        return;
    }

    rawCatalogSubmissionInFlight = true;
    rawCatalogSubmissionStartedAt = Date.now();

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

        const selectedVariantRecipes =
            getSelectedB13Recipes();

        if (selectedVariantRecipes.length > 24) {
            message.textContent =
                "Maksimal 24 variant per campaign.";
            return;
        }

        if (
            state.b19aCatalogSourceMode
            === "custom"
            && !state.b19cCreativeSet
        ) {
            await b19cPrepareCustom(
                selectedProductIds()
            );
        }

        const payload = {
            // B19A_LINKED_CATALOG_PAYLOAD
            catalog_source:
                state.b19aCatalogSourceMode
                || "custom",
            catalog_code: (
                state.b19aCatalogSourceMode
                === "spacecraft"
                ? (
                    state.b19aLinkedCatalog
                    ?.catalog_code
                    || null
                )
                : null
            ),
            catalog_hash: (
                state.b19aCatalogSourceMode
                === "spacecraft"
                ? (
                    state.b19aLinkedCatalog
                    ?.catalog_hash
                    || null
                )
                : null
            ),
            pricing_source: (
                document.getElementById(
                    "b19aPricingSource"
                )?.value
                || state.b19aPricingSource
                || "meta"
            ),
            // B19C_CREATIVE_SET_PAYLOAD
            creative_set_code: (
                state.b19cCreativeSet
                ?.creative_set_code
                || null
            ),
            name: document.getElementById("multiCampaignName").value.trim() || null,
            creative_template:
                document.getElementById(
                    "multiCampaignTemplate"
                )?.value || "custom_manual",
            variations: (
                selectedVariantRecipes.length
                    || Number(
                        document.getElementById(
                            "multiCampaignVariations"
                        ).value
                    )
            ),
            variant_recipes:
                selectedVariantRecipes,
            product_clips: productClips,
            audience: document.getElementById("multiCampaignAudience").value,
            min_order_qty: 6,
            // B18C_RAW_COPY_PAYLOAD
            hook: document.getElementById("multiCampaignHook")?.value.trim() || null,
            cta: document.getElementById("multiCampaignCta")?.value.trim() || null,
            hook_image_asset_id:
                state.campaignVisualAssets?.hook?.asset_id || null,
            cta_image_asset_id:
                state.campaignVisualAssets?.cta?.asset_id || null,
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
            approved_voice_asset_id: multiVoiceoverEnabled
                ? (window.B18GApprovedVoiceAsset?.asset_id || null)
                : null,
            approved_voice_fingerprint: multiVoiceoverEnabled
                ? (window.B18GApprovedVoiceAsset?.fingerprint || null)
                : null,
            approved_voice_duration_seconds: multiVoiceoverEnabled
                ? (Number(window.B18GApprovedVoiceAsset?.duration_seconds) || null)
                : null,
        };

        const data = await api("/api/campaigns/raw-video-catalog", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Client-Submission": (
                    `catalog-${rawCatalogSubmissionStartedAt}`
                ),
            },
            body: JSON.stringify(payload),
        });

        message.textContent = data.message;
        await loadMultiProductCampaigns();
    } catch (error) {
        message.textContent = `Generate gagal: ${error.message}`;
    } finally {
        rawCatalogSubmissionInFlight = false;
        rawCatalogSubmissionStartedAt = 0;
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
    // B18B_CAMPAIGN_HISTORY_DYNAMIC_TARGET_START
    // Jangan memakai referensi DOM yang ditangkap saat startup.
    // Bagian form dapat dirender ulang sehingga node lama terlepas
    // dari document setelah hard refresh atau perubahan setting.
    const target = document.getElementById(
        "multiCampaignList"
    );

    if (!target || !target.isConnected) {
        return;
    }

    try {
        const data = await api(
            "/api/campaigns/multi-product"
        );

        const campaigns = Array.isArray(
            data?.campaigns
        )
            ? data.campaigns
            : [];

        target.hidden = false;
        target.style.removeProperty("display");
        target.dataset.campaignHistoryCount = String(
            campaigns.length
        );
        target.dataset.campaignHistoryLoadedAt = (
            new Date().toISOString()
        );

        target.innerHTML = renderCampaignHistoryTable(
            campaigns
        );

        await restoreExpandedCampaigns();
    } catch (error) {
        const currentTarget = document.getElementById(
            "multiCampaignList"
        );

        if (!currentTarget) {
            return;
        }

        currentTarget.hidden = false;
        currentTarget.style.removeProperty("display");
        currentTarget.innerHTML = `
            <div class="empty">
                Gagal memuat catalog ads:
                ${escapeHtml(error.message)}
            </div>
        `;
    }
    // B18B_CAMPAIGN_HISTORY_DYNAMIC_TARGET_END
}

function scheduleMultiCampaignHistoryRefresh() {
    if (
        window.__b18fLegacyCampaignBootstrapBound
    ) {
        return;
    }

    window.__b18fLegacyCampaignBootstrapBound =
        true;

    const refresh = () => {
        if (
            window.B18FCampaignHistory
            || window.B18BCampaignHistoryV3
        ) {
            return;
        }

        Promise.resolve(
            loadMultiProductCampaigns()
        ).catch(() => {});
    };

    refresh();

    setTimeout(
        refresh,
        800
    );

    window.addEventListener(
        "pageshow",
        refresh,
        {passive: true}
    );

    document.addEventListener(
        "visibilitychange",
        () => {
            if (!document.hidden) {
                refresh();
            }
        }
    );
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


// B18J_DESCRIPTIVE_DOWNLOAD_FILENAMES
function b18jFileSlug(value, fallback = "campaign") {
    const slug = String(value || "")
        .trim()
        .toLowerCase()
        .normalize("NFKD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 40);

    return slug || fallback;
}

function b18jCampaignCode(campaign) {
    return `CMP${String(
        Number(campaign?.id || 0)
    ).padStart(6, "0")}`;
}

function b18jDownloadFilename(
    campaign,
    job,
    kind = "video"
) {
    const review =
        job?.review
        || job?.config?.review
        || {};

    const parts = [
        "spacecraft",
        b18jCampaignCode(campaign),
        b18jFileSlug(
            campaign?.name,
            "campaign"
        ),
    ];

    const templateSlug = b18jFileSlug(
        job?.config?.creative_template_label
        || job?.config?.creative_template
        || "",
        ""
    );

    if (
        templateSlug
        && !parts.includes(templateSlug)
    ) {
        parts.push(templateSlug);
    }

    parts.push(
        `v${String(
            Number(job?.variation_index || 1)
        ).padStart(2, "0")}`
    );

    if (review.status === "approved") {
        parts.push("approved");
    }

    if (review.winner) {
        parts.push("winner");
    }

    if (kind === "thumbnail") {
        parts.push("thumbnail");
    }

    return `${parts.join("-")}.${
        kind === "thumbnail" ? "jpg" : "mp4"
    }`;
}


function renderJobCard(
    job,
    campaign
) {
    const campaignId = campaign.id;
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
                            download="${escapeHtml(
                                b18jDownloadFilename(
                                    campaign,
                                    job,
                                    "video"
                                )
                            )}"
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
                            download="${escapeHtml(
                                b18jDownloadFilename(
                                    campaign,
                                    job,
                                    "thumbnail"
                                )
                            )}"
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


function b11CopyGroup(
    title,
    items
) {
    return `
        <section class="b11-copy-group">
            <h5>${escapeHtml(title)}</h5>

            ${(items || []).map(
                (item, index) => `
                    <div class="b11-copy-item">
                        <span>
                            ${escapeHtml(item)}
                        </span>

                        <button
                            type="button"
                            class="mini-button"
                            onclick="
                                copyB11Text(
                                    this,
                                    ${JSON.stringify(item)}
                                )
                            "
                        >
                            Copy
                        </button>
                    </div>
                `
            ).join("")}
        </section>
    `;
}


function renderCampaignAdCopy(
    campaignId,
    copy
) {
    const target = document.getElementById(
        `campaignAdCopy-${campaignId}`
    );

    if (!target) return;

    target.innerHTML = `
        <div class="b11-copy-header">
            <div>
                <strong>
                    ${escapeHtml(
                        copy.campaign_code
                    )}
                </strong>

                <small>
                    ${escapeHtml(
                        copy.template || ""
                    )}
                    •
                    ${escapeHtml(
                        copy.audience || ""
                    )}
                </small>
            </div>
        </div>

        ${b11CopyGroup(
            "Primary Text",
            copy.primary_texts
        )}

        ${b11CopyGroup(
            "Headlines",
            copy.headlines
        )}

        ${b11CopyGroup(
            "Descriptions",
            copy.descriptions
        )}

        ${b11CopyGroup(
            "CTA Recommendation",
            [copy.cta_recommendation]
        )}

        ${b11CopyGroup(
            "WhatsApp Opening",
            [copy.whatsapp_opening]
        )}
    `;

    target.hidden = false;
}


async function generateCampaignAdCopy(
    campaignId
) {
    const target = document.getElementById(
        `campaignAdCopy-${campaignId}`
    );

    if (target) {
        target.hidden = false;
        target.innerHTML = `
            <div class="b11-loading">
                Menyiapkan ad copy...
            </div>
        `;
    }

    try {
        const data = await api(
            `/api/campaigns/${campaignId}/ad-copy`
        );

        renderCampaignAdCopy(
            campaignId,
            data.copy
        );
    } catch (error) {
        if (target) {
            target.innerHTML = `
                <div class="b11-error">
                    Gagal: ${escapeHtml(
                        error.message
                    )}
                </div>
            `;
        }
    }
}


async function downloadCampaignPackage(
    campaignId
) {
    const message = document.getElementById(
        `campaignExportMessage-${campaignId}`
    );

    if (message) {
        message.textContent =
            "Membuat ZIP campaign...";
    }

    try {
        const data = await api(
            `/api/campaigns/${campaignId}/export-package`,
            {
                method: "POST",
            }
        );

        if (message) {
            message.textContent =
                `${data.package.approved_count} `
                + "video Approved masuk paket.";
        }

        const link = document.createElement(
            "a"
        );

        link.href =
            data.package.package_url;

        link.download =
            data.package.package_name;

        document.body.appendChild(link);
        link.click();
        link.remove();

    } catch (error) {
        if (message) {
            message.textContent =
                `Gagal: ${error.message}`;
        }
    }
}


async function copyB11Text(
    button,
    value
) {
    try {
        await navigator.clipboard.writeText(
            value
        );

        const original =
            button.textContent;

        button.textContent = "Copied";

        setTimeout(() => {
            button.textContent =
                original;
        }, 1200);

    } catch (error) {
        const textarea =
            document.createElement(
                "textarea"
            );

        textarea.value = value;
        document.body.appendChild(
            textarea
        );

        textarea.select();
        document.execCommand("copy");
        textarea.remove();

        button.textContent = "Copied";
    }
}


function b12Currency(value) {
    return new Intl.NumberFormat(
        "id-ID",
        {
            style: "currency",
            currency: "IDR",
            maximumFractionDigits: 0,
        }
    ).format(
        Number(value || 0)
    );
}


function b12Number(value) {
    return new Intl.NumberFormat(
        "id-ID"
    ).format(
        Number(value || 0)
    );
}


function b12Percent(value) {
    return (
        Number(value || 0)
        .toFixed(2)
        + "%"
    );
}


function b12RecommendationClass(
    recommendation
) {
    return (
        `b12-recommendation-${recommendation
            || "keep_testing"}`
    );
}


function renderPerformanceMetric(
    label,
    value
) {
    return `
        <div class="b12-summary-metric">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
        </div>
    `;
}


function renderPerformanceEntry(
    campaignId,
    item
) {
    const metrics = item.metrics || {};

    return `
        <article class="b12-performance-entry">
            <div class="b12-entry-head">
                <div class="b12-entry-title">
                    ${item.thumbnail_url
                        ? `
                            <img
                                src="${escapeHtml(
                                    item.thumbnail_url
                                )}"
                                alt="Video ${item.variation_index}"
                            >
                        `
                        : `
                            <div class="b12-thumb-placeholder">
                                V${item.variation_index}
                            </div>
                        `}

                    <div>
                        <strong>
                            #${item.rank || "-"}
                            Video ${item.variation_index}
                        </strong>

                        <small>
                            ${escapeHtml(
                                item.template || "Custom"
                            )}
                        </small>
                    </div>
                </div>

                <span
                    class="
                        b12-recommendation
                        ${b12RecommendationClass(
                            metrics.recommendation
                        )}
                    "
                >
                    ${escapeHtml(
                        metrics.recommendation_label
                        || "Keep Testing"
                    )}
                </span>
            </div>

            <div class="b12-entry-score">
                <span>
                    Score
                    <b>${Number(
                        metrics.score || 0
                    ).toFixed(1)}</b>
                </span>

                <span>
                    CTR
                    <b>${b12Percent(
                        metrics.ctr
                    )}</b>
                </span>

                <span>
                    ROAS
                    <b>${Number(
                        metrics.roas || 0
                    ).toFixed(2)}x</b>
                </span>

                <span>
                    Closing
                    <b>${b12Number(
                        metrics.closings
                    )}</b>
                </span>
            </div>

            <div class="b12-performance-form">
                <label>
                    <span>Impressions</span>
                    <input
                        id="perfImpressions-${item.job_id}"
                        type="number"
                        min="0"
                        value="${Number(
                            metrics.impressions || 0
                        )}"
                    >
                </label>

                <label>
                    <span>Clicks</span>
                    <input
                        id="perfClicks-${item.job_id}"
                        type="number"
                        min="0"
                        value="${Number(
                            metrics.clicks || 0
                        )}"
                    >
                </label>

                <label>
                    <span>Spend (Rp)</span>
                    <input
                        id="perfSpend-${item.job_id}"
                        type="number"
                        min="0"
                        step="1000"
                        value="${Number(
                            metrics.spend || 0
                        )}"
                    >
                </label>

                <label>
                    <span>Leads</span>
                    <input
                        id="perfLeads-${item.job_id}"
                        type="number"
                        min="0"
                        value="${Number(
                            metrics.leads || 0
                        )}"
                    >
                </label>

                <label>
                    <span>Closing</span>
                    <input
                        id="perfClosings-${item.job_id}"
                        type="number"
                        min="0"
                        value="${Number(
                            metrics.closings || 0
                        )}"
                    >
                </label>

                <label>
                    <span>Revenue (Rp)</span>
                    <input
                        id="perfRevenue-${item.job_id}"
                        type="number"
                        min="0"
                        step="1000"
                        value="${Number(
                            metrics.revenue || 0
                        )}"
                    >
                </label>
            </div>

            <label class="b12-notes-field">
                <span>Catatan</span>

                <textarea
                    id="perfNotes-${item.job_id}"
                    rows="2"
                    placeholder="Catatan performa, audience, placement, atau hasil testing..."
                >${escapeHtml(
                    metrics.notes || ""
                )}</textarea>
            </label>

            <div class="b12-entry-detail">
                <span>
                    CPM:
                    <b>${b12Currency(
                        metrics.cpm
                    )}</b>
                </span>

                <span>
                    CPC:
                    <b>${b12Currency(
                        metrics.cpc
                    )}</b>
                </span>

                <span>
                    CPL:
                    <b>${b12Currency(
                        metrics.cpl
                    )}</b>
                </span>

                <span>
                    Lead CVR:
                    <b>${b12Percent(
                        metrics.lead_conversion
                    )}</b>
                </span>

                <span>
                    Closing CVR:
                    <b>${b12Percent(
                        metrics.closing_conversion
                    )}</b>
                </span>

                <span>
                    Profit:
                    <b>${b12Currency(
                        metrics.profit
                    )}</b>
                </span>
            </div>

            <div class="b12-recommendation-reason">
                ${escapeHtml(
                    metrics.recommendation_reason
                    || ""
                )}
            </div>

            <div class="b12-entry-actions">
                <button
                    type="button"
                    class="mini-button"
                    onclick="
                        savePerformanceEntry(
                            ${campaignId},
                            ${item.job_id}
                        )
                    "
                >
                    Simpan Performa
                </button>

                <button
                    type="button"
                    class="mini-button danger"
                    onclick="
                        deletePerformanceEntry(
                            ${campaignId},
                            ${item.job_id}
                        )
                    "
                >
                    Reset
                </button>
            </div>

            <div
                id="perfMessage-${item.job_id}"
                class="b12-entry-message"
            ></div>
        </article>
    `;
}


function renderPerformanceDimension(
    title,
    items
) {
    return `
        <section class="b12-dimension-card">
            <h5>${escapeHtml(title)}</h5>

            ${(items || []).length
                ? items.slice(0, 5).map(
                    (item, index) => `
                        <div class="b12-dimension-row">
                            <span>
                                ${index + 1}.
                                ${escapeHtml(
                                    item.label || "-"
                                )}
                            </span>

                            <b>
                                ${Number(
                                    item.average_score
                                    || 0
                                ).toFixed(1)}
                            </b>
                        </div>
                    `
                ).join("")
                : `
                    <div class="b12-empty-small">
                        Belum ada data.
                    </div>
                `}
        </section>
    `;
}


function renderCampaignPerformance(
    campaignId,
    dashboard
) {
    const target = document.getElementById(
        `campaignPerformanceContent-${campaignId}`
    );

    if (!target) return;

    const totals =
        dashboard.totals || {};

    const winner =
        dashboard.performance_winner;

    target.innerHTML = `
        <div class="b12-summary-grid">
            ${renderPerformanceMetric(
                "Impressions",
                b12Number(totals.impressions)
            )}

            ${renderPerformanceMetric(
                "Clicks",
                b12Number(totals.clicks)
            )}

            ${renderPerformanceMetric(
                "CTR",
                b12Percent(totals.ctr)
            )}

            ${renderPerformanceMetric(
                "Spend",
                b12Currency(totals.spend)
            )}

            ${renderPerformanceMetric(
                "Leads",
                b12Number(totals.leads)
            )}

            ${renderPerformanceMetric(
                "Closing",
                b12Number(totals.closings)
            )}

            ${renderPerformanceMetric(
                "Revenue",
                b12Currency(totals.revenue)
            )}

            ${renderPerformanceMetric(
                "ROAS",
                `${Number(
                    totals.roas || 0
                ).toFixed(2)}x`
            )}
        </div>

        ${winner
            ? `
                <div class="b12-winner-banner">
                    <div>
                        <span>
                            PERFORMANCE WINNER
                        </span>

                        <strong>
                            Video ${winner.variation_index}
                        </strong>

                        <small>
                            Score ${Number(
                                winner.metrics.score || 0
                            ).toFixed(1)}
                            • ROAS ${Number(
                                winner.metrics.roas || 0
                            ).toFixed(2)}x
                            • ${winner.metrics.closings || 0}
                            closing
                        </small>
                    </div>
                </div>
            `
            : `
                <div class="b12-no-winner">
                    Belum ada performance winner.
                    Masukkan data iklan terlebih dahulu.
                </div>
            `}

        <div class="b12-dimension-grid">
            ${renderPerformanceDimension(
                "Top Hooks",
                dashboard.dimensions?.hooks
            )}

            ${renderPerformanceDimension(
                "Top Templates",
                dashboard.dimensions?.templates
            )}

            ${renderPerformanceDimension(
                "Top CTA",
                dashboard.dimensions?.ctas
            )}
        </div>

        <div class="b12-entry-grid">
            ${(dashboard.items || [])
                .map(
                    item => renderPerformanceEntry(
                        campaignId,
                        item
                    )
                )
                .join("")}
        </div>
    `;

    target.hidden = false;
}


async function loadCampaignPerformance(
    campaignId
) {
    const target = document.getElementById(
        `campaignPerformanceContent-${campaignId}`
    );

    if (!target) return;

    target.hidden = false;
    target.innerHTML = `
        <div class="b12-loading">
            Memuat performance dashboard...
        </div>
    `;

    try {
        const data = await api(
            `/api/campaigns/${campaignId}/performance`
        );

        renderCampaignPerformance(
            campaignId,
            data.dashboard
        );

    } catch (error) {
        target.innerHTML = `
            <div class="b12-error">
                Gagal memuat performa:
                ${escapeHtml(error.message)}
            </div>
        `;
    }
}


async function savePerformanceEntry(
    campaignId,
    jobId
) {
    const message = document.getElementById(
        `perfMessage-${jobId}`
    );

    if (message) {
        message.textContent =
            "Menyimpan performa...";
    }

    const getNumber = id => Number(
        document.getElementById(id)?.value
        || 0
    );

    try {
        const data = await api(
            `/api/campaigns/${campaignId}`
            + `/jobs/${jobId}/performance`,
            {
                method: "PUT",
                headers: {
                    "Content-Type":
                        "application/json",
                },
                body: JSON.stringify({
                    impressions: getNumber(
                        `perfImpressions-${jobId}`
                    ),
                    clicks: getNumber(
                        `perfClicks-${jobId}`
                    ),
                    spend: getNumber(
                        `perfSpend-${jobId}`
                    ),
                    leads: getNumber(
                        `perfLeads-${jobId}`
                    ),
                    closings: getNumber(
                        `perfClosings-${jobId}`
                    ),
                    revenue: getNumber(
                        `perfRevenue-${jobId}`
                    ),
                    notes:
                        document.getElementById(
                            `perfNotes-${jobId}`
                        )?.value.trim()
                        || null,
                    source: "manual",
                }),
            }
        );

        if (message) {
            message.textContent =
                data.message;
        }

        await loadCampaignPerformance(
            campaignId
        );

    } catch (error) {
        if (message) {
            message.textContent =
                `Gagal: ${error.message}`;
        }
    }
}


async function deletePerformanceEntry(
    campaignId,
    jobId
) {
    if (
        !confirm(
            "Reset data performa video ini?"
        )
    ) {
        return;
    }

    try {
        await api(
            `/api/campaigns/${campaignId}`
            + `/jobs/${jobId}/performance`,
            {
                method: "DELETE",
            }
        );

        await loadCampaignPerformance(
            campaignId
        );

    } catch (error) {
        alert(
            `Gagal: ${error.message}`
        );
    }
}


async function exportCampaignPerformance(
    campaignId,
    format
) {
    try {
        const data = await api(
            `/api/campaigns/${campaignId}`
            + `/performance/export`
            + `?format=${encodeURIComponent(
                format
            )}`
        );

        const mimeType =
            format === "csv"
                ? "text/csv;charset=utf-8"
                : "application/json;charset=utf-8";

        const blob = new Blob(
            [data.content],
            {
                type: mimeType,
            }
        );

        const url =
            URL.createObjectURL(blob);

        const link =
            document.createElement("a");

        link.href = url;
        link.download = data.filename;

        document.body.appendChild(link);
        link.click();
        link.remove();

        URL.revokeObjectURL(url);

    } catch (error) {
        alert(
            `Export gagal: ${error.message}`
        );
    }
}


function b14FormatJson(value) {
    return JSON.stringify(
        value,
        null,
        2
    );
}


function b14PhoneLink(
    phone,
    message
) {
    const normalized = String(
        phone || ""
    ).replace(/[^0-9]/g, "");

    if (!normalized) {
        return "";
    }

    return (
        `https://wa.me/${normalized}`
        + `?text=${encodeURIComponent(
            message || ""
        )}`
    );
}


function renderB14Events(events) {
    if (!(events || []).length) {
        return `
            <div class="b14-empty">
                Belum ada attribution event.
            </div>
        `;
    }

    return events.slice(0, 20).map(
        event => `
            <div class="b14-event-row">
                <div>
                    <strong>
                        ${escapeHtml(
                            event.event_type
                            || "event"
                        )}
                    </strong>

                    <span>
                        ${escapeHtml(
                            event.phone
                            || event.order_id
                            || "-"
                        )}
                    </span>
                </div>

                <small>
                    ${escapeHtml(
                        event.created_at
                        || ""
                    )}
                </small>
            </div>
        `
    ).join("");
}


// B15 CATALOG SELECTOR + TRACKED CLICK-TO-WHATSAPP
function b15StripTrackingLines(message) {
    return String(message || "")
        .split("\n")
        .filter(line => !/^\s*(Campaign|Catalog)\s*:/i.test(line))
        .join("\n")
        .replace(/\n{3,}/g, "\n\n")
        .trim();
}


function b15TrackedOpening(
    message,
    campaignCode,
    catalogCode
) {
    const base = b15StripTrackingLines(message);
    const tracking = [];

    if (campaignCode) {
        tracking.push(`Campaign: ${campaignCode}`);
    }

    if (catalogCode) {
        tracking.push(`Catalog: ${catalogCode}`);
    }

    return [base, tracking.join("\n")]
        .filter(Boolean)
        .join("\n\n")
        .trim();
}


function b15CatalogOptions(
    catalogs,
    selectedCode
) {
    const selected = String(selectedCode || "")
        .toUpperCase();

    const options = [
        `<option value="">Pilih Catalog Bundle...</option>`
    ];

    (catalogs || []).forEach(catalog => {
        const code = String(
            catalog.catalog_code
            || catalog.catalog_id
            || ""
        ).trim();

        if (!code) return;

        const name = String(
            catalog.name || code
        ).trim();
        const count = Number(
            catalog.products_count || 0
        );
        const label = `${code} — ${name}`
            + (count ? ` (${count} produk)` : "");

        options.push(`
            <option
                value="${escapeHtml(code)}"
                data-name="${escapeHtml(name)}"
                data-products="${count}"
                data-go-url="${escapeHtml(
                    catalog.go_url || ""
                )}"
                ${code.toUpperCase() === selected
                    ? "selected"
                    : ""}
            >${escapeHtml(label)}</option>
        `);
    });

    if (
        selectedCode
        && !(catalogs || []).some(
            catalog => String(
                catalog.catalog_code
                || catalog.catalog_id
                || ""
            ).toUpperCase() === selected
        )
    ) {
        options.push(`
            <option
                value="${escapeHtml(selectedCode)}"
                selected
            >${escapeHtml(selectedCode)} — tersimpan</option>
        `);
    }

    return options.join("");
}


function b15CampaignState(campaignId) {
    const campaignCode = document.getElementById(
        `b14CampaignCode-${campaignId}`
    )?.value.trim() || "";
    const catalogCode = document.getElementById(
        `b14CatalogCode-${campaignId}`
    )?.value.trim() || "";
    const sourceCode = document.getElementById(
        `b14SourceCode-${campaignId}`
    )?.value.trim() || "spacecraft_ads";
    const phone = document.getElementById(
        `b14Phone-${campaignId}`
    )?.value.trim() || "";
    const opening = document.getElementById(
        `b14Opening-${campaignId}`
    )?.value || "";

    const trackedOpening = b15TrackedOpening(
        opening,
        campaignCode,
        catalogCode
    );
    const normalizedPhone = phone.replace(/\D+/g, "");

    const errors = [];
    if (!campaignCode) errors.push("campaign code");
    if (!catalogCode) errors.push("Catalog Bundle");
    if (normalizedPhone.length < 8) errors.push("nomor WhatsApp");
    if (
        campaignCode
        && !trackedOpening.toLowerCase().includes(
            campaignCode.toLowerCase()
        )
    ) errors.push("tracking campaign");
    if (
        catalogCode
        && !trackedOpening.toLowerCase().includes(
            catalogCode.toLowerCase()
        )
    ) errors.push("tracking catalog");

    return {
        campaignCode,
        catalogCode,
        sourceCode,
        phone,
        normalizedPhone,
        opening,
        trackedOpening,
        errors,
        valid: errors.length === 0,
    };
}


function b15RefreshCampaignState(
    campaignId,
    updateOpening = false
) {
    let state = b15CampaignState(campaignId);
    const opening = document.getElementById(
        `b14Opening-${campaignId}`
    );

    if (updateOpening && opening) {
        opening.value = state.trackedOpening;
        state = b15CampaignState(campaignId);
    }

    const select = document.getElementById(
        `b14CatalogCode-${campaignId}`
    );
    const option = select?.selectedOptions?.[0];
    const info = document.getElementById(
        `b15CatalogInfo-${campaignId}`
    );

    if (info) {
        if (state.catalogCode) {
            const name = option?.dataset?.name || state.catalogCode;
            const products = Number(
                option?.dataset?.products || 0
            );
            info.textContent = `${name}`
                + (products ? ` • ${products} produk` : "");
        } else {
            info.textContent = "Pilih katalog yang akan dibuka oleh WABot.";
        }
    }

    const validation = document.getElementById(
        `b15Validation-${campaignId}`
    );
    if (validation) {
        validation.className = state.valid
            ? "b15-validation is-valid"
            : "b15-validation is-invalid";
        validation.textContent = state.valid
            ? "Siap digunakan untuk Click-to-WhatsApp."
            : `Lengkapi: ${state.errors.join(", ")}.`;
    }

    const openButton = document.getElementById(
        `b15OpenWhatsApp-${campaignId}`
    );
    if (openButton) {
        openButton.disabled = !state.valid;
    }

    return state;
}


function b15ApplyCatalog(campaignId) {
    b15RefreshCampaignState(campaignId, true);
}


function b15GenerateOpening(campaignId) {
    const state = b15RefreshCampaignState(
        campaignId,
        true
    );
    const message = document.getElementById(
        `b14Message-${campaignId}`
    );
    if (message) {
        message.textContent = state.valid
            ? "Opening tracking berhasil disiapkan."
            : `Belum lengkap: ${state.errors.join(", ")}.`;
    }
}


// B16 ADS ATTRIBUTION BRIDGE
async function b16TrackWhatsAppClick(
    campaignId,
    state,
    destinationUrl
) {
    const message = document.getElementById(
        `b14Message-${campaignId}`
    );

    try {
        const data = await api(
            `/api/campaigns/${campaignId}/wabot/click`,
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json",
                },
                body: JSON.stringify({
                    campaign_code:
                        state.campaignCode,
                    catalog_code:
                        state.catalogCode,
                    source_code:
                        state.sourceCode,
                    creative_code:
                        `${state.campaignCode}-MASTER`,
                    phone:
                        state.normalizedPhone,
                    opening_message:
                        state.trackedOpening,
                    destination_url:
                        destinationUrl,
                }),
                keepalive: true,
            }
        );

        const spacecraftOk =
            data.spacecraft?.ok === true;

        if (message) {
            message.textContent = spacecraftOk
                ? (
                    "WhatsApp dibuka dan attribution "
                    + "tersinkronisasi ke SpaceCraft."
                )
                : (
                    "WhatsApp dibuka. Event lokal tercatat, "
                    + "sinkronisasi SpaceCraft masih pending."
                );
        }

        return data;

    } catch (error) {
        if (message) {
            message.textContent =
                "WhatsApp tetap dibuka. "
                + "Pencatatan attribution gagal: "
                + error.message;
        }

        return null;
    }
}


function openB15WhatsApp(campaignId) {
    const state = b15RefreshCampaignState(
        campaignId,
        true
    );
    const message = document.getElementById(
        `b14Message-${campaignId}`
    );

    if (!state.valid) {
        if (message) {
            message.textContent =
                `Belum bisa dibuka: ${state.errors.join(", ")}.`;
        }
        return;
    }

    const link = b14PhoneLink(
        state.normalizedPhone,
        state.trackedOpening
    );

    if (!link) return;

    window.open(
        link,
        "_blank",
        "noopener,noreferrer"
    );

    void b16TrackWhatsAppClick(
        campaignId,
        state,
        link
    );
}


function renderCampaignWABot(
    campaignId,
    data
) {
    const target = document.getElementById(
        `campaignWABotContent-${campaignId}`
    );

    if (!target) return;

    const config = data.config || {};
    const payload = data.payload || {};
    const campaign =
        payload.campaign || {};
    const offer =
        payload.offer || {};
    const wabot =
        payload.wabot || {};
    const summary =
        data.summary || {};
    const catalogs = Array.isArray(data.catalogs)
        ? data.catalogs
        : [];
    const selectedCampaignCode =
        config.external_campaign_code
        || campaign.code
        || "";
    const selectedCatalogCode =
        config.catalog_code
        || campaign.catalog_code
        || "";
    const selectedPhone =
        config.whatsapp_number
        || wabot.phone
        || "";
    const selectedOpening = b15TrackedOpening(
        config.opening_message
        || offer.opening_message
        || "",
        selectedCampaignCode,
        selectedCatalogCode
    );

    target.innerHTML = `
        <div class="b14-config-grid">
            <label>
                <span>Campaign Code</span>
                <input
                    id="b14CampaignCode-${campaignId}"
                    type="text"
                    value="${escapeHtml(
                        config.external_campaign_code
                        || campaign.code
                        || ""
                    )}"
                    placeholder="CMP000001"
                >
            </label>

            <label>
                <span>Catalog Bundle</span>
                <select
                    id="b14CatalogCode-${campaignId}"
                    onchange="b15ApplyCatalog(${campaignId})"
                >
                    ${b15CatalogOptions(
                        catalogs,
                        selectedCatalogCode
                    )}
                </select>
                <small
                    id="b15CatalogInfo-${campaignId}"
                    class="b15-catalog-info"
                ></small>
            </label>

            <label>
                <span>Source Code</span>
                <input
                    id="b14SourceCode-${campaignId}"
                    type="text"
                    value="${escapeHtml(
                        config.source_code
                        || campaign.source_code
                        || "spacecraft_ads"
                    )}"
                    placeholder="meta_ads"
                >
            </label>

            <label>
                <span>Nomor WhatsApp</span>
                <input
                    id="b14Phone-${campaignId}"
                    type="text"
                    value="${escapeHtml(
                        selectedPhone
                    )}"
                    placeholder="628123456789"
                    oninput="b15RefreshCampaignState(${campaignId})"
                >
            </label>
        </div>

        <label class="b14-opening-field">
            <span>WhatsApp Opening Message</span>

            <textarea
                id="b14Opening-${campaignId}"
                rows="4"
                oninput="b15RefreshCampaignState(${campaignId})"
            >${escapeHtml(
                selectedOpening
            )}</textarea>
        </label>

        <div class="b14-toggle-row">
            <label>
                <input
                    id="b14WebhookEnabled-${campaignId}"
                    type="checkbox"
                    ${config.webhook_enabled
                        ? "checked"
                        : ""}
                >
                Aktifkan webhook setelah endpoint
                WABot dikonfigurasi
            </label>
        </div>

        <div class="b14-action-row">
            <button
                type="button"
                class="mini-button b14-save-button"
                onclick="
                    saveCampaignWABot(
                        ${campaignId}
                    )
                "
            >
                Simpan Konfigurasi
            </button>

            <button
                type="button"
                class="mini-button"
                onclick="
                    copyB14Payload(
                        ${campaignId}
                    )
                "
            >
                Copy Payload
            </button>

            <button
                type="button"
                class="mini-button"
                onclick="b15GenerateOpening(${campaignId})"
            >
                Generate Tracking
            </button>

            <button
                type="button"
                class="mini-button"
                onclick="
                    copyB14Opening(
                        ${campaignId}
                    )
                "
            >
                Copy Opening
            </button>

            <button
                id="b15OpenWhatsApp-${campaignId}"
                type="button"
                class="mini-button b14-wa-button"
                onclick="openB15WhatsApp(${campaignId})"
            >
                Buka WhatsApp
            </button>
        </div>

        <div
            id="b15Validation-${campaignId}"
            class="b15-validation"
        ></div>

        <div
            id="b14Message-${campaignId}"
            class="b14-message"
        ></div>

        <div class="b14-summary-grid">
            <div>
                <span>Total Event</span>
                <strong>
                    ${Number(
                        summary.total_events || 0
                    )}
                </strong>
            </div>

            <div>
                <span>Lead</span>
                <strong>
                    ${Number(
                        summary.counts?.lead || 0
                    )}
                </strong>
            </div>

            <div>
                <span>Checkout</span>
                <strong>
                    ${Number(
                        summary.counts?.checkout || 0
                    )}
                </strong>
            </div>

            <div>
                <span>Closing</span>
                <strong>
                    ${Number(
                        summary.counts?.closing || 0
                    )}
                </strong>
            </div>
        </div>

        <div class="b14-content-grid">
            <section class="b14-json-card">
                <h5>WABot Payload Preview</h5>

                <pre
                    id="b14Payload-${campaignId}"
                >${escapeHtml(
                    b14FormatJson(payload)
                )}</pre>
            </section>

            <section class="b14-events-card">
                <h5>Attribution Events</h5>

                ${renderB14Events(
                    data.events
                )}
            </section>
        </div>
    `;

    target.dataset.payload =
        JSON.stringify(payload);

    target.hidden = false;
    queueMicrotask(() => {
        b15RefreshCampaignState(
            campaignId,
            true
        );
    });
}


async function loadCampaignWABot(
    campaignId
) {
    const target = document.getElementById(
        `campaignWABotContent-${campaignId}`
    );

    if (!target) return;

    target.hidden = false;
    target.innerHTML = `
        <div class="b14-loading">
            Menyiapkan WABot payload...
        </div>
    `;

    try {
        const data = await api(
            `/api/campaigns/${campaignId}/wabot`
        );

        try {
            const catalogData = await api(
                "/api/wabot/catalogs"
            );
            data.catalogs = catalogData.catalogs || [];
            data.catalog_sync = catalogData;
        } catch (catalogError) {
            data.catalogs = [];
            data.catalog_sync = {
                ok: false,
                message: catalogError.message,
            };
        }

        renderCampaignWABot(
            campaignId,
            data
        );

    } catch (error) {
        target.innerHTML = `
            <div class="b14-error">
                ${escapeHtml(error.message)}
            </div>
        `;
    }
}


async function saveCampaignWABot(
    campaignId
) {
    const message = document.getElementById(
        `b14Message-${campaignId}`
    );

    if (message) {
        message.textContent =
            "Menyimpan konfigurasi...";
    }

    try {
        b15RefreshCampaignState(
            campaignId,
            true
        );

        const data = await api(
            `/api/campaigns/${campaignId}/wabot`,
            {
                method: "PUT",
                headers: {
                    "Content-Type":
                        "application/json",
                },
                body: JSON.stringify({
                    external_campaign_code:
                        document.getElementById(
                            `b14CampaignCode-${campaignId}`
                        )?.value.trim()
                        || null,

                    catalog_code:
                        document.getElementById(
                            `b14CatalogCode-${campaignId}`
                        )?.value.trim()
                        || null,

                    source_code:
                        document.getElementById(
                            `b14SourceCode-${campaignId}`
                        )?.value.trim()
                        || "spacecraft_ads",

                    whatsapp_number:
                        document.getElementById(
                            `b14Phone-${campaignId}`
                        )?.value.trim()
                        || null,

                    opening_message:
                        document.getElementById(
                            `b14Opening-${campaignId}`
                        )?.value.trim()
                        || null,

                    webhook_enabled:
                        Boolean(
                            document.getElementById(
                                `b14WebhookEnabled-${campaignId}`
                            )?.checked
                        ),

                    metadata: {},
                }),
            }
        );

        if (message) {
            message.textContent =
                data.message;
        }

        await loadCampaignWABot(
            campaignId
        );

    } catch (error) {
        if (message) {
            message.textContent =
                `Gagal: ${error.message}`;
        }
    }
}


function copyB14Payload(
    campaignId
) {
    const target = document.getElementById(
        `campaignWABotContent-${campaignId}`
    );

    const payload =
        target?.dataset.payload || "{}";

    navigator.clipboard.writeText(
        payload
    ).then(() => {
        const message =
            document.getElementById(
                `b14Message-${campaignId}`
            );

        if (message) {
            message.textContent =
                "Payload berhasil disalin.";
        }
    });
}


function copyB14Opening(
    campaignId
) {
    const value =
        document.getElementById(
            `b14Opening-${campaignId}`
        )?.value || "";

    navigator.clipboard.writeText(
        value
    ).then(() => {
        const message =
            document.getElementById(
                `b14Message-${campaignId}`
            );

        if (message) {
            message.textContent =
                "Opening message berhasil disalin.";
        }
    });
}


async function testWABotConnection(
    campaignId
) {
    const message = document.getElementById(
        `b14Message-${campaignId}`
    );

    if (message) {
        message.textContent =
            "Menguji koneksi WABot...";
    }

    try {
        const data = await api(
            "/api/wabot/test",
            {
                method: "POST",
            }
        );

        if (message) {
            message.textContent =
                data.message;
        }

    } catch (error) {
        if (message) {
            message.textContent =
                `Gagal: ${error.message}`;
        }
    }
}


function renderCampaignWABotToolbar(
    campaign
) {
    return `
        <section class="b14-wabot-panel">
            <div class="b14-wabot-head">
                <div>
                    <span class="eyebrow">
                        B15 CLICK-TO-WHATSAPP
                    </span>

                    <strong>
                        Catalog Binding & Campaign Tracking
                    </strong>

                    <small>
                        Pilih Catalog Bundle, buat opening
                        message terukur, lalu gunakan link
                        Click-to-WhatsApp pada Meta Ads.
                    </small>
                </div>

                <div class="b14-toolbar-actions">
                    <button
                        type="button"
                        class="mini-button b14-open-button"
                        onclick="
                            loadCampaignWABot(
                                ${campaign.id}
                            )
                        "
                    >
                        Buka WABot
                    </button>

                    <button
                        type="button"
                        class="mini-button"
                        onclick="
                            loadCampaignWABot(
                                ${campaign.id}
                            )
                        "
                    >
                        Refresh Catalog
                    </button>
                </div>
            </div>

            <div
                id="campaignWABotContent-${campaign.id}"
                class="b14-wabot-content"
                hidden
            ></div>
        </section>
    `;
}




// B17B LIVE FUNNEL DASHBOARD
function b17DateLabel(value) {
    if (!value) return "-";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return String(value);
    }

    return new Intl.DateTimeFormat(
        "id-ID",
        {
            dateStyle: "medium",
            timeStyle: "short",
        }
    ).format(date);
}


function renderB17Metric(
    label,
    value,
    helper = ""
) {
    return `
        <div class="b17-metric">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
            ${helper
                ? `<small>${escapeHtml(helper)}</small>`
                : ""}
        </div>
    `;
}


function renderB17CreativeRow(row) {
    return `
        <tr>
            <td>
                <strong>${escapeHtml(
                    row.creative_code || "MASTER"
                )}</strong>
                <small>${escapeHtml(
                    row.campaign_code || "-"
                )}</small>
            </td>
            <td>${escapeHtml(row.catalog_code || "-")}</td>
            <td>${b12Number(row.whatsapp_clicks || 0)}</td>
            <td>${b12Number(row.leads || 0)}</td>
            <td>${b12Number(row.product_selected || 0)}</td>
            <td>${b12Number(row.orders || 0)}</td>
            <td>${b12Currency(row.order_value || 0)}</td>
            <td>${b12Percent(row.lead_to_order_rate || 0)}</td>
            <td>${escapeHtml(b17DateLabel(row.last_activity_at))}</td>
        </tr>
    `;
}


function renderB17Dashboard(
    campaignId,
    data
) {
    const target = document.getElementById(
        `campaignFunnelContent-${campaignId}`
    );

    if (!target) return;

    const spacecraft = data.spacecraft || {};
    const summary = spacecraft.summary || {};
    const rows = Array.isArray(spacecraft.campaigns)
        ? spacecraft.campaigns
        : [];
    const period = spacecraft.period || {};

    target.innerHTML = `
        <div class="b17-summary-grid">
            ${renderB17Metric(
                "WhatsApp Click",
                b12Number(summary.whatsapp_clicks || 0),
                "Klik dari Ads Studio / go link"
            )}
            ${renderB17Metric(
                "Lead",
                b12Number(summary.leads || 0),
                `${b12Percent(summary.click_to_lead_rate || 0)} click → lead`
            )}
            ${renderB17Metric(
                "Pilih Produk",
                b12Number(summary.product_selected || 0),
                "Buyer memilih produk"
            )}
            ${renderB17Metric(
                "Order",
                b12Number(summary.orders || 0),
                `${b12Percent(summary.lead_to_order_rate || 0)} lead → order`
            )}
            ${renderB17Metric(
                "Nilai Order",
                b12Currency(summary.order_value || 0),
                "Termasuk QRIS manual"
            )}
            ${renderB17Metric(
                "Creative",
                b12Number(summary.creatives || rows.length),
                `${b12Number(summary.campaigns || 0)} campaign`
            )}
        </div>

        ${rows.length
            ? `
                <div class="b17-table-wrap">
                    <table class="b17-table">
                        <thead>
                            <tr>
                                <th>Creative / Campaign</th>
                                <th>Catalog</th>
                                <th>Click WA</th>
                                <th>Lead</th>
                                <th>Pilih Produk</th>
                                <th>Order</th>
                                <th>Nilai Order</th>
                                <th>Lead → Order</th>
                                <th>Aktivitas Terakhir</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rows.map(renderB17CreativeRow).join("")}
                        </tbody>
                    </table>
                </div>
            `
            : `
                <div class="b17-empty">
                    <strong>Belum ada attribution untuk campaign ini.</strong>
                    <span>
                        Data akan muncul setelah link WhatsApp campaign dipakai
                        dan buyer masuk ke funnel WABot.
                    </span>
                </div>
            `}

        <div class="b17-footer">
            <span>
                Periode ${b12Number(period.days || 30)} hari
            </span>
            <span>
                Source: SpaceCraft Funnel API
            </span>
        </div>
    `;

    target.hidden = false;
}


async function loadCampaignFunnelPerformance(
    campaignId
) {
    const target = document.getElementById(
        `campaignFunnelContent-${campaignId}`
    );

    const days = Number(
        document.getElementById(
            `campaignFunnelDays-${campaignId}`
        )?.value || 30
    );

    if (!target) return;

    target.hidden = false;
    target.innerHTML = `
        <div class="b17-loading">
            Memuat live funnel dari SpaceCraft...
        </div>
    `;

    try {
        const data = await api(
            `/api/campaigns/${campaignId}/wabot/performance?days=${days}`
        );

        renderB17Dashboard(
            campaignId,
            data
        );

    } catch (error) {
        target.innerHTML = `
            <div class="b17-error">
                Gagal memuat live funnel:
                ${escapeHtml(error.message)}
            </div>
        `;
    }
}


function renderCampaignFunnelToolbar(
    campaign
) {
    return `
        <section class="b17-funnel-panel">
            <div class="b17-funnel-head">
                <div>
                    <span class="eyebrow">
                        B17 LIVE ADS → WABOT FUNNEL
                    </span>
                    <strong>
                        Campaign & Creative Performance
                    </strong>
                    <small>
                        Data aktual click WhatsApp, lead, pilihan produk,
                        order, dan nilai order dari SpaceCraft.
                    </small>
                </div>

                <div class="b17-funnel-actions">
                    <select
                        id="campaignFunnelDays-${campaign.id}"
                        aria-label="Periode funnel"
                    >
                        <option value="7">7 hari</option>
                        <option value="30" selected>30 hari</option>
                        <option value="90">90 hari</option>
                        <option value="365">365 hari</option>
                    </select>

                    <button
                        type="button"
                        class="mini-button b17-refresh-button"
                        onclick="loadCampaignFunnelPerformance(${campaign.id})"
                    >
                        Buka Live Funnel
                    </button>
                </div>
            </div>

            <div
                id="campaignFunnelContent-${campaign.id}"
                class="b17-funnel-content"
                hidden
            ></div>
        </section>
    `;
}


function renderCampaignPerformanceToolbar(
    campaign
) {
    return `
        <section class="b12-performance-panel">
            <div class="b12-performance-head">
                <div>
                    <span class="eyebrow">
                        B12 CREATIVE PERFORMANCE
                    </span>

                    <strong>
                        Performance Dashboard
                    </strong>

                    <small>
                        Masukkan data Meta Ads untuk
                        menentukan creative winner
                        berdasarkan performa nyata.
                    </small>
                </div>

                <div class="b12-performance-actions">
                    <button
                        type="button"
                        class="mini-button"
                        onclick="
                            loadCampaignPerformance(
                                ${campaign.id}
                            )
                        "
                    >
                        Buka Dashboard
                    </button>

                    <button
                        type="button"
                        class="mini-button"
                        onclick="
                            exportCampaignPerformance(
                                ${campaign.id},
                                'json'
                            )
                        "
                    >
                        Export JSON
                    </button>

                    <button
                        type="button"
                        class="mini-button b12-csv-button"
                        onclick="
                            exportCampaignPerformance(
                                ${campaign.id},
                                'csv'
                            )
                        "
                    >
                        Export CSV
                    </button>
                </div>
            </div>

            <div
                id="campaignPerformanceContent-${campaign.id}"
                class="b12-performance-content"
                hidden
            ></div>
        </section>
    `;
}




function renderCampaignExportToolbar(
    campaign
) {
    return `
        <section class="b11-export-panel">
            <div class="b11-export-head">
                <div>
                    <span class="eyebrow">
                        B11 AD COPY & EXPORT
                    </span>

                    <strong>
                        Campaign Export Package
                    </strong>

                    <small>
                        Generate ad copy dan ZIP dari
                        video yang sudah Approved.
                    </small>
                </div>

                <div class="b11-export-actions">
                    <button
                        type="button"
                        class="mini-button"
                        onclick="
                            generateCampaignAdCopy(
                                ${campaign.id}
                            )
                        "
                    >
                        Generate Ad Copy
                    </button>

                    <button
                        type="button"
                        class="mini-button b11-download-button"
                        onclick="
                            downloadCampaignPackage(
                                ${campaign.id}
                            )
                        "
                    >
                        Download ZIP
                    </button>
                </div>
            </div>

            <div
                id="campaignExportMessage-${campaign.id}"
                class="b11-export-message"
            ></div>

            <div
                id="campaignAdCopy-${campaign.id}"
                class="b11-copy-panel"
                hidden
            ></div>
        </section>
    `;
}




function renderCampaignJobs(
    campaign
) {
    return `
        ${renderCampaignWABotToolbar(
            campaign
        )}

        ${renderCampaignFunnelToolbar(
            campaign
        )}

        ${renderCampaignPerformanceToolbar(
            campaign
        )}

        ${renderCampaignExportToolbar(
            campaign
        )}

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
                        campaign
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

    const intervalMs =
        state.activeProductId
            ? 7000
            : 20000;

    campaignPollTimer = setInterval(
        () => {
            if (document.hidden) {
                return;
            }

            if (state.activeProductId) {
                Promise.resolve(
                    loadCampaigns()
                ).catch(() => {});
            }

            if (
                !window.B18FCampaignHistory
                && !window.B18BCampaignHistoryV3
            ) {
                Promise.resolve(
                    loadMultiProductCampaigns()
                ).catch(() => {});
            }
        },
        intervalMs
    );
}

function stopCampaignPolling() {
    if (campaignPollTimer) clearInterval(campaignPollTimer);
    campaignPollTimer = null;
}

window.generateCampaign = generateCampaign;

window.generateMultiProductCampaign = generateMultiProductCampaign;
window.generateSingleProductCampaign = generateSingleProductCampaign;
window.b19aSetPricingSource = b19aSetPricingSource;
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
window.uploadCampaignVisualAsset = uploadCampaignVisualAsset;
window.clearCampaignVisualAsset = clearCampaignVisualAsset;
window.selectVisibleCampaignProducts = selectVisibleCampaignProducts;
window.toggleCatalogProductFilter = toggleCatalogProductFilter;
window.renderB13VariantPreview = renderB13VariantPreview;
window.updateB13VariantCount = updateB13VariantCount;
window.clearB13VariantMatrix = clearB13VariantMatrix;
window.moveCatalogProduct = moveCatalogProduct;
window.renderCatalogPreflight = renderCatalogPreflight;

window.viewCampaign = viewCampaign;
window.retryCampaign = retryCampaign;
window.deleteCampaign = deleteCampaign;
window.setCampaignHistoryPage = setCampaignHistoryPage;
window.setCampaignHistoryPageSize = setCampaignHistoryPageSize;
window.saveRenderReview = saveRenderReview;
window.filterCampaignResults = filterCampaignResults;
window.generateCampaignAdCopy = generateCampaignAdCopy;
window.downloadCampaignPackage = downloadCampaignPackage;
window.copyB11Text = copyB11Text;
window.loadCampaignWABot = loadCampaignWABot;
window.saveCampaignWABot = saveCampaignWABot;
window.copyB14Payload = copyB14Payload;
window.copyB14Opening = copyB14Opening;
window.testWABotConnection = testWABotConnection;
window.b15RefreshCampaignState = b15RefreshCampaignState;
window.b15ApplyCatalog = b15ApplyCatalog;
window.b15GenerateOpening = b15GenerateOpening;
window.openB15WhatsApp = openB15WhatsApp;
window.b16TrackWhatsAppClick = b16TrackWhatsAppClick;
window.loadCampaignFunnelPerformance = loadCampaignFunnelPerformance;
window.loadCampaignPerformance = loadCampaignPerformance;
window.savePerformanceEntry = savePerformanceEntry;
window.deletePerformanceEntry = deletePerformanceEntry;
window.exportCampaignPerformance = exportCampaignPerformance;



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


// B18F1_LEGACY_AI_COMPAT_START
// Legacy AI-video UI telah dihapus, tetapi export lama masih dipanggil oleh app.js.
// Stub berikut mencegah seluruh bundle berhenti sebelum fungsi Voice Draft diregistrasikan.
async function loadAiVideoStatus() {
    return {
        ok: false,
        configured: false,
        disabled: true,
        reason: "legacy_ai_video_removed",
    };
}
function toggleAiVideoControls() {
    return false;
}
// B18F1_LEGACY_AI_COMPAT_END
window.loadVoiceOptions = loadVoiceOptions;
window.loadAiVideoStatus =
    typeof loadAiVideoStatus === "function"
        ? loadAiVideoStatus
        : async function () {
            return {
                ok: false,
                configured: false,
                disabled: true,
            };
        };
window.toggleAiVideoControls =
    typeof toggleAiVideoControls === "function"
        ? toggleAiVideoControls
        : function () {
            return false;
        };
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

scheduleMultiCampaignHistoryRefresh();
startCampaignPolling();

// B18H_SMART_VOICE_TIMELINE_FIT_FRONTEND
// B18G_APPROVED_VOICE_FRONTEND
window.B18GApprovedVoiceAsset = null;

// VOICE_DRAFT_APPROVAL_FRONTEND_V1
(() => {
    const draftState = {
        approved: false,
        approvedText: "",
        approvedSignature: "",
        protectedTerms: [],
        estimatedDurationSeconds: null,
        previewDurationSeconds: null,
        maxDurationSeconds: null,
        fitsTimeline: false,
        previewSignature: "",
        previewAssetId: "",
        previewFingerprint: "",
        previewAudioUrl: "",
        approvedAssetId: "",
        approvedFingerprint: "",
        approvedDurationSeconds: null,
        fitEligible: false,
        fitRequiredSpeed: null,
        fitOverBySeconds: null,
        fitApplied: false,


    };

    const element = id =>
        document.getElementById(id);

    function draftProductIds() {
        if (
            typeof selectedCampaignProductClips
            !== "function"
        ) {
            return [];
        }

        return selectedCampaignProductClips()
            .map(item => Number(item.product_id))
            .filter(Boolean);
    }

    function draftContextSignature(textValue = null) {
        const text = textValue === null
            ? (element("multiCampaignVoiceText")?.value || "").trim()
            : String(textValue || "").trim();

        return JSON.stringify({
            product_ids: draftProductIds(),
            audience:
                element("multiCampaignAudience")?.value || "retail",
            duration_seconds: Number(
                element("multiCampaignDuration")?.value || 25
            ),
            promo_enabled: Boolean(
                element("multiCampaignPromoEnabled")?.checked
            ),
            promo_min_amount: Number(
                element("multiCampaignPromoMinAmount")?.value || 100000
            ),
            promo_discount_percent: Number(
                element("multiCampaignPromoDiscount")?.value || 10
            ),
            promo_text:
                element("multiCampaignPromoText")?.value.trim() || null,
            voice_id:
                element("multiCampaignVoiceId")?.value || "",
            text,
        });
    }

    function setDraftStatus(label, stateName) {
        const status = element("multiVoiceDraftStatus");
        if (!status) return;

        status.textContent = label;
        status.classList.remove(
            "pending",
            "previewed",
            "approved"
        );
        status.classList.add(stateName || "pending");
    }

    function setDraftMessage(value) {
        const target = element("multiVoiceDraftMessage");
        if (target) target.textContent = value || "";
    }

    // B18D_DURATION_PREFLIGHT_FRONTEND
    function currentVoiceLimit() {
        const duration = Number(element("multiCampaignDuration")?.value || 25);
        return Math.max(1, duration - 5.5);
    }

    function setDurationPanel({ actual = null, estimated = null, limit = null, fits = null, previewed = false } = {}) {
        const actualTarget = element("multiVoiceDurationActual");
        const limitTarget = element("multiVoiceDurationLimit");
        const stateTarget = element("multiVoiceDurationState");
        const effectiveLimit = Number(limit ?? currentVoiceLimit());
        const displayValue = Number(actual ?? estimated);
        if (actualTarget) actualTarget.textContent = Number.isFinite(displayValue) ? `${displayValue.toFixed(2)} detik` : "-";
        if (limitTarget) limitTarget.textContent = `${effectiveLimit.toFixed(2)} detik`;
        draftState.maxDurationSeconds = effectiveLimit;
        draftState.estimatedDurationSeconds = Number.isFinite(Number(estimated)) ? Number(estimated) : null;
        if (previewed) {
            draftState.previewDurationSeconds = Number.isFinite(Number(actual)) ? Number(actual) : null;
            draftState.fitsTimeline = Boolean(fits);
        }
        if (stateTarget) {
            stateTarget.classList.remove("pending", "ok", "danger");
            if (!previewed) {
                stateTarget.textContent = Number.isFinite(displayValue) ? (fits === false ? "Estimasi terlalu panjang" : "Perlu preview aktual") : "Belum preview";
                stateTarget.classList.add(fits === false ? "danger" : "pending");
            } else if (fits) {
                stateTarget.textContent = "Aman untuk render";
                stateTarget.classList.add("ok");
            } else {
                stateTarget.textContent = "Terlalu panjang";
                stateTarget.classList.add("danger");
            }
        }
    }

    function setVoiceFitAvailability({
        eligible = false,
        requiredSpeed = null,
        overBy = null,
        applied = false,
    } = {}) {
        const button = element("multiVoiceFitButton");

        draftState.fitEligible = Boolean(eligible);
        draftState.fitRequiredSpeed = Number.isFinite(Number(requiredSpeed))
            ? Number(requiredSpeed)
            : null;
        draftState.fitOverBySeconds = Number.isFinite(Number(overBy))
            ? Number(overBy)
            : null;
        draftState.fitApplied = Boolean(applied);

        if (!button) return;

        button.classList.toggle("hidden", !draftState.fitEligible);
        button.disabled = !draftState.fitEligible;

        if (draftState.fitEligible && draftState.fitRequiredSpeed) {
            button.textContent =
                `Sesuaikan ke Timeline (${draftState.fitRequiredSpeed.toFixed(2)}x)`;
        } else {
            button.textContent = "Sesuaikan ke Timeline";
        }
    }

    function invalidateDraft(
        message = "Draft berubah. Preview dan approve ulang sebelum render."
    ) {
        draftState.approved = false;
        draftState.approvedText = "";
        draftState.approvedSignature = "";
        draftState.previewDurationSeconds = null;
        draftState.fitsTimeline = false;
        draftState.previewSignature = "";
        draftState.previewAssetId = "";
        draftState.previewFingerprint = "";
        draftState.previewAudioUrl = "";
        draftState.approvedAssetId = "";
        draftState.approvedFingerprint = "";
        draftState.approvedDurationSeconds = null;
        window.B18GApprovedVoiceAsset = null;
        setVoiceFitAvailability();
        setDraftStatus("Belum disetujui", "pending");
        setDraftMessage(message);
        setDurationPanel({ limit: currentVoiceLimit() });
    }

    window.invalidateMultiVoiceDraft = invalidateDraft;

    async function normalizeDraftText(text) {
        return api(
            "/api/voiceover/normalize",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    text,
                    protected_terms:
                        draftState.protectedTerms,
                }),
            }
        );
    }

    async function requestMultiVoiceDraft(draftStyle = "standard") {
        const button = element(draftStyle === "compact" ? "multiVoiceCompactButton" : "multiVoiceDraftGenerateButton");
        const textarea = element("multiCampaignVoiceText");
        const mode = element("multiCampaignVoiceMode");
        const checkbox = element("multiCampaignVoiceoverEnabled");
        if (!checkbox?.checked) { setDraftMessage("Aktifkan Voice Over terlebih dahulu."); return; }
        const productIds = draftProductIds();
        if (productIds.length < 5 || productIds.length > 6) { setDraftMessage("Pilih 5 sampai 6 produk sebelum membuat draft."); return; }
        if (button) { button.disabled = true; button.textContent = draftStyle === "compact" ? "Meringkas..." : "Generating..."; }
        setDraftMessage(draftStyle === "compact" ? "Membuat draft ringkas untuk slot voice-over..." : "Membuat draft TTS dengan nama produk yang dilindungi...");
        try {
            const data = await api("/api/voiceover/draft", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    product_ids: productIds,
                    audience: element("multiCampaignAudience")?.value || "retail",
                    duration_seconds: Number(element("multiCampaignDuration")?.value || 25),
                    promo_enabled: Boolean(element("multiCampaignPromoEnabled")?.checked),
                    promo_min_amount: Number(element("multiCampaignPromoMinAmount")?.value || 100000),
                    promo_discount_percent: Number(element("multiCampaignPromoDiscount")?.value || 10),
                    promo_text: element("multiCampaignPromoText")?.value.trim() || null,
                    draft_style: draftStyle,
                }),
            });
            draftState.protectedTerms = data.protected_terms || [];
            if (textarea) textarea.value = data.tts_text || data.draft_text || "";
            if (mode) mode.value = "custom";
            const termsTarget = element("multiVoiceProtectedTerms");
            if (termsTarget) termsTarget.textContent = draftState.protectedTerms.length ? "Nama/alias produk dikunci: " + draftState.protectedTerms.join(" • ") : "";
            invalidateDraft(data.warning || `Draft siap direview. Estimasi ${data.estimated_seconds || "-"} detik.`);
            setDurationPanel({ estimated: Number(data.estimated_seconds), limit: Number(data.max_voiceover_seconds), fits: Boolean(data.fits_timeline), previewed: false });
            setDraftStatus("Draft siap", "previewed");
        } catch (error) {
            setDraftMessage(`Generate draft gagal: ${error.message}`);
        } finally {
            if (button) { button.disabled = false; button.textContent = draftStyle === "compact" ? "Ringkas Otomatis" : "Generate Draft"; }
        }
    }

    window.generateMultiVoiceDraft = async function() { return requestMultiVoiceDraft("standard"); };
    window.compactMultiVoiceDraft = async function() { return requestMultiVoiceDraft("compact"); };
    window.extendMultiVoiceDuration = function() {
        const select = element("multiCampaignDuration");
        if (!select) return;
        const current = Number(select.value || 25);
        const next = current < 25 ? 25 : (current < 30 ? 30 : null);
        if (next === null) { setDraftMessage("Durasi sudah 30 detik. Ringkas atau edit draft agar muat."); return; }
        select.value = String(next);
        select.dispatchEvent(new Event("change", { bubbles: true }));
        invalidateDraft(`Durasi diperpanjang menjadi ${next} detik. Preview ulang untuk mengukur durasi aktual.`);
    };

    window.previewMultiVoiceDraft = async function() {
        const button = element("multiVoiceDraftPreviewButton");
        const player = element("multiVoiceDraftPlayer");
        const textarea = element("multiCampaignVoiceText");
        const voiceId = element("multiCampaignVoiceId")?.value;
        const rawText = textarea?.value.trim() || "";
        if (!voiceId) {
            setDraftMessage("Pilih voice ElevenLabs terlebih dahulu.");
            return;
        }
        if (!rawText) {
            setDraftMessage("Generate atau isi draft terlebih dahulu.");
            return;
        }
        if (button) {
            button.disabled = true;
            button.textContent = "Generating...";
        }
        setDraftMessage("Membuat dan mengukur preview ElevenLabs...");
        try {
            const normalized = await normalizeDraftText(rawText);
            const normalizedText = normalized.normalized_text || rawText;
            if (textarea) textarea.value = normalizedText;
            invalidateDraft("Preview dibuat. Sistem sedang memeriksa kecocokan timeline.");
            const data = await api("/api/voiceover/preview", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    voice_id: voiceId,
                    text: normalizedText,
                    protected_terms: draftState.protectedTerms,
                    target_duration_seconds: Number(
                        element("multiCampaignDuration")?.value || 25
                    ),
                    closing_reserved_seconds: 5,
                }),
            });
            draftState.previewAssetId = data.preview_asset_id || "";
            draftState.previewFingerprint = data.fingerprint || "";
            draftState.previewAudioUrl = data.audio_url || "";
            if (!draftState.previewAssetId || !draftState.previewFingerprint) {
                throw new Error("Preview asset tidak lengkap");
            }
            if (player) {
                player.src = data.audio_url + `?t=${Date.now()}`;
                player.classList.remove("hidden");
                try { await player.play(); } catch (_) {}
            }
            draftState.previewSignature = draftContextSignature(normalizedText);
            const actual = Number(data.actual_duration_seconds);
            const limit = Number(data.max_voiceover_seconds);
            const fits = Boolean(data.fits_timeline);
            const overBy = Math.max(0, actual - limit);
            const requiredSpeed = limit > 0 ? actual / limit : Infinity;
            const fitEligible = Boolean(
                !fits
                && overBy <= 1.20 + 0.001
                && requiredSpeed <= 1.06 + 0.001
            );
            setVoiceFitAvailability({
                eligible: fitEligible,
                requiredSpeed,
                overBy,
            });
            setDurationPanel({
                actual,
                limit,
                fits,
                previewed: true,
            });
            if (fits) {
                setDraftStatus("Preview aman", "previewed");
                setDraftMessage(
                    `Preview ${actual.toFixed(2)} detik aman. `
                    + "Dengarkan, lalu approve sebagai master audio render."
                );
            } else if (fitEligible) {
                setDraftStatus("Bisa disesuaikan", "previewed");
                setDraftMessage(
                    `Voice-over lebih panjang ${overBy.toFixed(2)} detik. `
                    + `Auto Fit membutuhkan sekitar ${requiredSpeed.toFixed(2)}x. `
                    + "Klik Sesuaikan ke Timeline, dengarkan ulang, lalu approve."
                );
            } else {
                setDraftStatus("Terlalu panjang", "pending");
                setDraftMessage(
                    data.warning || "Voice-over terlalu panjang. Ringkas atau perpanjang durasi."
                );
            }
        } catch (error) {
            invalidateDraft(`Preview gagal: ${error.message}`);
        } finally {
            if (button) {
                button.disabled = false;
                button.textContent = "Preview Voice";
            }
        }
    };

    window.fitMultiVoiceToTimeline = async function() {
        const button = element("multiVoiceFitButton");
        const player = element("multiVoiceDraftPlayer");
        const textarea = element("multiCampaignVoiceText");
        const voiceId = element("multiCampaignVoiceId")?.value;
        const text = textarea?.value.trim() || "";

        if (!draftState.fitEligible) {
            setDraftMessage(
                "Auto Fit hanya tersedia untuk kelebihan ringan maksimal 1,2 detik dan 1,06x."
            );
            return;
        }
        if (!draftState.previewAssetId || !draftState.previewFingerprint) {
            setDraftMessage("Preview terbaru tidak tersedia. Buat preview ulang.");
            return;
        }
        if (!voiceId || !text) {
            setDraftMessage("Voice atau draft belum lengkap.");
            return;
        }

        if (button) {
            button.disabled = true;
            button.textContent = "Menyesuaikan...";
        }
        setDraftMessage("Memangkas silence dan menyesuaikan tempo secara ringan...");

        try {
            const data = await api("/api/voiceover/fit", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    preview_asset_id: draftState.previewAssetId,
                    voice_id: voiceId,
                    text,
                    protected_terms: draftState.protectedTerms,
                    target_duration_seconds: Number(
                        element("multiCampaignDuration")?.value || 25
                    ),
                    closing_reserved_seconds: 5,
                }),
            });

            if (!data.fits_timeline) {
                throw new Error("Hasil Auto Fit masih melebihi timeline");
            }

            draftState.previewAssetId = data.preview_asset_id || "";
            draftState.previewFingerprint = data.fingerprint || "";
            draftState.previewAudioUrl = data.audio_url || "";
            draftState.previewDurationSeconds = Number(data.actual_duration_seconds);
            draftState.fitsTimeline = true;
            draftState.previewSignature = draftContextSignature(text);

            if (!draftState.previewAssetId || !draftState.previewFingerprint) {
                throw new Error("Asset hasil Auto Fit tidak lengkap");
            }

            if (player) {
                player.src = data.audio_url + `?t=${Date.now()}`;
                player.classList.remove("hidden");
                try { await player.play(); } catch (_) {}
            }

            setDurationPanel({
                actual: Number(data.actual_duration_seconds),
                limit: Number(data.max_voiceover_seconds),
                fits: true,
                previewed: true,
            });
            setVoiceFitAvailability({ applied: true });
            setDraftStatus("Sudah disesuaikan", "previewed");
            setDraftMessage(
                `Auto Fit selesai: ${Number(data.actual_duration_seconds).toFixed(2)} detik. `
                + `Silence dipangkas ${Number(data.trimmed_seconds || 0).toFixed(2)} detik, `
                + `tempo ${Number(data.speed_multiplier || 1).toFixed(2)}x. `
                + "Dengarkan hasilnya, lalu Approve Draft."
            );
        } catch (error) {
            setDraftStatus("Auto Fit gagal", "pending");
            setDraftMessage(`Auto Fit gagal: ${error.message}`);
        } finally {
            if (button) {
                button.disabled = !draftState.fitEligible;
                button.textContent = "Sesuaikan ke Timeline";
            }
        }
    };

    window.approveMultiVoiceDraft = async function() {
        const button = element("multiVoiceDraftApproveButton");
        const textarea = element("multiCampaignVoiceText");
        const voiceId = element("multiCampaignVoiceId")?.value;
        const rawText = textarea?.value.trim() || "";
        if (!rawText) {
            setDraftMessage("Draft masih kosong.");
            return;
        }
        if (!voiceId) {
            setDraftMessage("Pilih voice ElevenLabs terlebih dahulu.");
            return;
        }
        const currentSignature = draftContextSignature(rawText);
        if (
            !draftState.previewDurationSeconds
            || draftState.previewSignature !== currentSignature
            || !draftState.previewAssetId
            || !draftState.previewFingerprint
        ) {
            setDraftMessage("Preview voice terbaru wajib dibuat sebelum approve.");
            setDraftStatus("Belum dipreview", "pending");
            return;
        }
        if (!draftState.fitsTimeline) {
            setDraftMessage("Draft belum dapat di-approve karena durasi voice-over melebihi slot.");
            setDraftStatus("Terlalu panjang", "pending");
            return;
        }
        if (button) button.disabled = true;
        try {
            const normalized = await normalizeDraftText(rawText);
            const approvedText = normalized.normalized_text || rawText;
            if (textarea) textarea.value = approvedText;
            const approvedSignature = draftContextSignature(approvedText);
            if (approvedSignature !== draftState.previewSignature) {
                invalidateDraft("Normalisasi mengubah teks. Preview ulang sebelum approve.");
                return;
            }
            const data = await api("/api/voiceover/approve", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    preview_asset_id: draftState.previewAssetId,
                    fingerprint: draftState.previewFingerprint,
                    voice_id: voiceId,
                    text: approvedText,
                    protected_terms: draftState.protectedTerms,
                }),
            });
            draftState.approved = true;
            draftState.approvedText = data.normalized_text || approvedText;
            draftState.approvedSignature = draftContextSignature(draftState.approvedText);
            draftState.approvedAssetId = data.approved_asset_id || "";
            draftState.approvedFingerprint = data.fingerprint || "";
            draftState.approvedDurationSeconds = Number(data.duration_seconds);
            if (
                !draftState.approvedAssetId
                || !draftState.approvedFingerprint
                || !Number.isFinite(draftState.approvedDurationSeconds)
            ) {
                throw new Error("Approved voice master tidak lengkap");
            }
            window.B18GApprovedVoiceAsset = {
                asset_id: draftState.approvedAssetId,
                fingerprint: draftState.approvedFingerprint,
                duration_seconds: draftState.approvedDurationSeconds,
                audio_url: data.audio_url || "",
                voice_id: voiceId,
                signature: draftState.approvedSignature,
            };
            setDraftStatus("Approved master", "approved");
            setDraftMessage(
                `Master audio disetujui (${draftState.approvedDurationSeconds.toFixed(2)} detik). `
                + "Render akan memakai file ini tanpa generate ElevenLabs ulang."
            );
        } catch (error) {
            invalidateDraft(`Approve gagal: ${error.message}`);
        } finally {
            if (button) button.disabled = false;
        }
    };

    function draftReadyForRender() {
        const approvedAsset = window.B18GApprovedVoiceAsset;
        return Boolean(
            draftState.approved
            && draftState.approvedText
            && draftState.fitsTimeline
            && draftState.previewDurationSeconds
            && draftState.approvedAssetId
            && draftState.approvedFingerprint
            && Number.isFinite(draftState.approvedDurationSeconds)
            && draftState.previewSignature === draftContextSignature(draftState.approvedText)
            && draftState.approvedSignature === draftContextSignature(draftState.approvedText)
            && approvedAsset
            && approvedAsset.asset_id === draftState.approvedAssetId
            && approvedAsset.fingerprint === draftState.approvedFingerprint
            && approvedAsset.signature === draftState.approvedSignature
        );
    }

    function prepareDraftForRender(messageTarget) {
        const voiceEnabled = Boolean(
            element("multiCampaignVoiceoverEnabled")?.checked
            && voiceoverConfigured
        );

        if (!voiceEnabled) return true;

        if (!element("multiCampaignVoiceId")?.value) {
            if (messageTarget) {
                messageTarget.textContent =
                    "Pilih voice ElevenLabs terlebih dahulu.";
            }
            return false;
        }

        if (!draftReadyForRender()) {
            if (messageTarget) {
                messageTarget.textContent =
                    "Voice-over belum siap. Preview harus muat dalam slot timeline, lalu klik Approve Draft.";
            }
            setDraftStatus("Belum disetujui", "pending");
            return false;
        }

        const mode = element("multiCampaignVoiceMode");
        const textarea = element("multiCampaignVoiceText");
        if (mode) mode.value = "custom";
        if (textarea) textarea.value =
            draftState.approvedText;

        return true;
    }

    const originalToggleVoice =
        window.toggleMultiVoiceoverControls;

    window.toggleMultiVoiceoverControls = function(...args) {
        if (typeof originalToggleVoice === "function") {
            originalToggleVoice.apply(this, args);
        }

        const enabled = Boolean(
            element("multiCampaignVoiceoverEnabled")?.checked
            && voiceoverConfigured
        );
        const mode = element("multiCampaignVoiceMode");
        const wrap = element("multiCustomVoiceTextWrap");

        if (mode) {
            mode.value = "custom";
            mode.disabled = true;
        }
        if (wrap) wrap.classList.toggle("hidden", !enabled);

        if (!enabled) {
            invalidateDraft(
                "Aktifkan Voice Over untuk membuat draft."
            );
        }
    };

    window.toggleMultiCustomVoiceText = function() {
        const enabled = Boolean(
            element("multiCampaignVoiceoverEnabled")?.checked
            && voiceoverConfigured
        );
        const mode = element("multiCampaignVoiceMode");
        const wrap = element("multiCustomVoiceTextWrap");

        if (mode) {
            mode.value = "custom";
            mode.disabled = true;
        }
        if (wrap) wrap.classList.toggle("hidden", !enabled);
    };

    const originalGenerateCampaign =
        window.generateMultiProductCampaign;

    window.generateMultiProductCampaign = async function(...args) {
        if (!prepareDraftForRender(multiCampaignMessage)) {
            return;
        }
        return originalGenerateCampaign.apply(this, args);
    };

    if (
        typeof generateMultiProductCampaign === "function"
        && generateMultiCampaignButton
    ) {
        generateMultiCampaignButton.removeEventListener(
            "click",
            generateMultiProductCampaign
        );
        generateMultiCampaignButton.addEventListener(
            "click",
            window.generateMultiProductCampaign
        );
    }

    const originalCreateAutomation =
        window.createAutomationRule;

    if (typeof originalCreateAutomation === "function") {
        window.createAutomationRule = async function(...args) {
            const target = element("automationMessage");
            if (!prepareDraftForRender(target)) {
                return;
            }
            return originalCreateAutomation.apply(this, args);
        };
    }

    [
        "multiCampaignAudience",
        "multiCampaignDuration",
        "multiCampaignPromoEnabled",
        "multiCampaignPromoMinAmount",
        "multiCampaignPromoDiscount",
        "multiCampaignPromoText",
    ].forEach(id => {
        element(id)?.addEventListener(
            "change",
            () => invalidateDraft()
        );
    });
})();

// VOICE_DRAFT_UI_FIX_V3
(() => {
    const byId = id => document.getElementById(id);

    function draftPanelEnabled() {
        return Boolean(
            byId("multiCampaignVoiceoverEnabled")?.checked
        );
    }

    function syncDraftPanel() {
        const enabled = draftPanelEnabled();
        const controls = byId("multiVoiceoverControls");
        const wrap = byId("multiCustomVoiceTextWrap");
        const mode = byId("multiCampaignVoiceMode");
        const textarea = byId("multiCampaignVoiceText");

        if (mode) {
            mode.value = "custom";
            mode.disabled = true;
        }

        if (controls) {
            controls.classList.toggle(
                "voiceover-disabled",
                !enabled
            );
        }

        if (wrap) {
            wrap.classList.toggle("hidden", !enabled);
            wrap.setAttribute(
                "aria-hidden",
                enabled ? "false" : "true"
            );
        }

        if (textarea) {
            textarea.disabled = !enabled;
        }

        [
            "multiVoiceDraftGenerateButton",
            "multiVoiceDraftPreviewButton",
            "multiVoiceDraftApproveButton",
        ].forEach(id => {
            const button = byId(id);
            if (button) button.disabled = !enabled;
        });
    }

    function draftIsApproved() {
        const status = byId("multiVoiceDraftStatus");
        const text = (
            byId("multiCampaignVoiceText")?.value || ""
        ).trim();

        return Boolean(
            text
            && status?.classList.contains("approved")
        );
    }

    function showDraftRequiredMessage() {
        const message = byId("multiCampaignMessage");
        const draftMessage = byId(
            "multiVoiceDraftMessage"
        );
        const wrap = byId("multiCustomVoiceTextWrap");
        const value = (
            "Voice-over belum disetujui. "
            + "Generate Draft, Preview Voice, lalu Approve Draft sebelum render."
        );

        if (message) message.textContent = value;
        if (draftMessage) draftMessage.textContent = value;

        wrap?.classList.remove("hidden");
        wrap?.scrollIntoView({
            behavior: "smooth",
            block: "center",
        });
    }

    function bindDraftUi() {
        const checkbox = byId(
            "multiCampaignVoiceoverEnabled"
        );
        const voiceSelect = byId(
            "multiCampaignVoiceId"
        );
        const generateButton = byId(
            "generateMultiCampaignButton"
        );

        if (
            checkbox
            && checkbox.dataset.b18aUiFixBound !== "1"
        ) {
            checkbox.dataset.b18aUiFixBound = "1";
            checkbox.addEventListener(
                "change",
                () => setTimeout(syncDraftPanel, 0)
            );
        }

        if (
            voiceSelect
            && voiceSelect.dataset.b18aUiFixBound !== "1"
        ) {
            voiceSelect.dataset.b18aUiFixBound = "1";
            voiceSelect.addEventListener(
                "change",
                () => setTimeout(syncDraftPanel, 0)
            );
        }

        [
            "multiCampaignTemplate",
            "multiCampaignAudience",
            "multiCampaignDuration",
            "multiCampaignPromoEnabled",
            "multiCampaignPromoMinAmount",
            "multiCampaignPromoDiscount",
            "multiCampaignPromoText",
        ].forEach(id => {
            const target = byId(id);
            if (
                target
                && target.dataset.b18aUiFixBound !== "1"
            ) {
                target.dataset.b18aUiFixBound = "1";
                target.addEventListener(
                    "change",
                    () => setTimeout(syncDraftPanel, 0)
                );
            }
        });

        if (
            generateButton
            && generateButton.dataset.b18aDraftGuard !== "1"
        ) {
            generateButton.dataset.b18aDraftGuard = "1";

            // Capture phase: hentikan handler render lama sebelum
            // campaign dibuat ketika draft belum approved.
            generateButton.addEventListener(
                "click",
                event => {
                    syncDraftPanel();

                    if (!draftPanelEnabled()) return;

                    if (!draftIsApproved()) {
                        event.preventDefault();
                        event.stopImmediatePropagation();
                        showDraftRequiredMessage();
                    }
                },
                true
            );
        }

        syncDraftPanel();
    }

    window.syncB18AVoiceDraftPanel = syncDraftPanel;

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            bindDraftUi,
            {once: true}
        );
    } else {
        bindDraftUi();
    }

    // Voice list dan template di-load async. Sinkronkan ulang
    // sesudah proses awal selesai.
    setTimeout(bindDraftUi, 250);
    setTimeout(syncDraftPanel, 1000);
    setTimeout(syncDraftPanel, 2500);
})();
