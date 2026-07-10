(() => {
    "use strict";

    const VERSION = "B18F-HISTORY-1.0";
    const ENDPOINT = "/api/campaigns/multi-product";
    const ACTIVE_POLL_MS = 5000;
    const IDLE_POLL_MS = 20000;

    let pollTimer = null;
    let loading = false;
    let lastPayloadSignature = "";
    let hasActiveCampaign = false;
    let latestCampaigns = [];
    let currentPage = 1;
    let pageSize = 5;

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function numberValue(value, fallback = 0) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function progress(campaign) {
        const total = Math.max(
            1,
            numberValue(campaign?.variations, 1),
        );
        const completed = numberValue(
            campaign?.completed_count,
            0,
        );
        const failed = numberValue(
            campaign?.failed_count,
            0,
        );

        return Math.max(
            0,
            Math.min(
                100,
                Math.round(
                    ((completed + failed) / total) * 100,
                ),
            ),
        );
    }

    function templateLabel(settings = {}) {
        const labels = {
            bundle_hemat: "Bundle Hemat",
            product_showcase: "Product Showcase",
            flash_sale: "Flash Sale",
        };

        return (
            settings.creative_template_label
            || labels[settings.creative_template]
            || "Product Showcase"
        );
    }

    function audienceLabel(settings = {}) {
        const labels = {
            retail: "Retail",
            retail_bulk: "Bundle Hemat",
            reseller: "Reseller",
            custom_bulk: "Custom/Bulk",
        };

        return labels[settings.audience] || "Retail";
    }

    function ensureTarget() {
        let target = document.getElementById(
            "multiCampaignList",
        );

        if (target && target.isConnected) {
            target.hidden = false;
            target.style.removeProperty("display");
            target.dataset.b18bVersion = VERSION;
            return target;
        }

        const preflight = document.getElementById(
            "catalogPreflight",
        );

        if (!preflight || !preflight.parentElement) {
            return null;
        }

        target = document.createElement("div");
        target.id = "multiCampaignList";
        target.className = "campaign-list";
        target.dataset.b18bVersion = VERSION;

        preflight.parentElement.insertBefore(
            target,
            preflight,
        );

        return target;
    }

    function row(campaign) {
        const settings = (
            campaign?.settings
            && typeof campaign.settings === "object"
        )
            ? campaign.settings
            : {};

        const productCount = Math.max(
            1,
            numberValue(settings.product_count, 1),
        );
        const productLabel = productCount > 1
            ? ` · ${productCount} produk`
            : "";
        const pct = progress(campaign);
        const status = String(campaign?.status || "unknown");
        const completed = numberValue(
            campaign?.completed_count,
            0,
        );
        const failed = numberValue(
            campaign?.failed_count,
            0,
        );
        const variations = Math.max(
            1,
            numberValue(campaign?.variations, 1),
        );
        const campaignId = numberValue(campaign?.id, 0);
        const voiceLabel = settings.voiceover_enabled
            ? "VO"
            : "";
        const failedLabel = failed > 0
            ? `<span class="campaign-pill is-error">${failed} gagal</span>`
            : "";
        const voicePill = voiceLabel
            ? `<span class="campaign-pill">${voiceLabel}</span>`
            : "";

        return `
            <article
                class="campaign-row"
                data-b18b-campaign-id="${campaignId}"
            >
                <div class="campaign-main">
                    <strong>${escapeHtml(campaign?.name || "Campaign")}</strong>
                    <small>
                        ${escapeHtml(templateLabel(settings))}
                        · ${escapeHtml(audienceLabel(settings))}
                        ${escapeHtml(productLabel)}
                    </small>
                </div>
                <div class="campaign-progress-cell">
                    <div class="campaign-progress-meta">
                        <span>${completed}/${variations}</span>
                        <b>${pct}%</b>
                    </div>
                    <div class="progress is-compact">
                        <span style="width:${pct}%"></span>
                    </div>
                </div>
                <div class="campaign-status-cell">
                    <span class="campaign-pill">${escapeHtml(status)}</span>
                    ${failedLabel}
                    ${voicePill}
                </div>
                <div class="campaign-actions">
                    <button
                        type="button"
                        class="mini-button"
                        data-b18b-action="view"
                        data-campaign-id="${campaignId}"
                    >
                        Lihat Hasil
                    </button>
                    ${failed > 0 ? `
                        <button
                            type="button"
                            class="mini-button"
                            data-b18b-action="retry"
                            data-campaign-id="${campaignId}"
                        >
                            Retry Gagal
                        </button>
                    ` : ""}
                    <button
                        type="button"
                        class="mini-button"
                        data-b18b-action="delete"
                        data-campaign-id="${campaignId}"
                    >
                        Hapus
                    </button>
                </div>
                <div
                    id="campaignJobs-${campaignId}"
                    class="render-grid"
                ></div>
            </article>
        `;
    }

    function pagination(totalItems) {
        const totalPages = Math.max(
            1,
            Math.ceil(totalItems / pageSize),
        );
        currentPage = Math.max(
            1,
            Math.min(currentPage, totalPages),
        );
        const start = totalItems
            ? ((currentPage - 1) * pageSize) + 1
            : 0;
        const end = Math.min(
            totalItems,
            currentPage * pageSize,
        );

        return `
            <div class="campaign-pagination">
                <div class="campaign-page-info">
                    ${start}-${end} dari ${totalItems} campaign
                </div>
                <label class="campaign-page-size">
                    Row
                    <select data-b18b-page-size>
                        <option value="5" ${pageSize === 5 ? "selected" : ""}>5</option>
                        <option value="10" ${pageSize === 10 ? "selected" : ""}>10</option>
                    </select>
                </label>
                <div class="campaign-page-actions">
                    <button
                        type="button"
                        class="mini-button"
                        data-b18b-page="prev"
                        ${currentPage <= 1 ? "disabled" : ""}
                    >
                        Prev
                    </button>
                    <span>${currentPage}/${totalPages}</span>
                    <button
                        type="button"
                        class="mini-button"
                        data-b18b-page="next"
                        ${currentPage >= totalPages ? "disabled" : ""}
                    >
                        Next
                    </button>
                </div>
            </div>
        `;
    }

    function table(campaigns) {
        const totalItems = campaigns.length;
        const totalPages = Math.max(
            1,
            Math.ceil(totalItems / pageSize),
        );
        currentPage = Math.max(
            1,
            Math.min(currentPage, totalPages),
        );
        const visibleCampaigns = campaigns.slice(
            (currentPage - 1) * pageSize,
            currentPage * pageSize,
        );

        return `
            <section class="campaign-table">
                ${pagination(totalItems)}
                <header class="campaign-table-head">
                    <span>Campaign</span>
                    <span>Progress</span>
                    <span>Status</span>
                    <span>Aksi</span>
                </header>
                <div class="campaign-table-body">
                    ${visibleCampaigns.map(row).join("")}
                </div>
                ${pagination(totalItems)}
            </section>
        `;
    }

    async function requestJson(url, options = {}) {
        const response = await fetch(url, {
            credentials: "same-origin",
            cache: "no-store",
            headers: {
                Accept: "application/json",
                ...(options.headers || {}),
            },
            ...options,
        });

        const text = await response.text();
        let payload = {};

        if (text) {
            try {
                payload = JSON.parse(text);
            } catch (_error) {
                payload = {detail: text};
            }
        }

        if (!response.ok) {
            const message = (
                payload?.detail
                || payload?.message
                || `HTTP ${response.status}`
            );
            const error = new Error(String(message));
            error.status = response.status;
            throw error;
        }

        return payload;
    }

    function renderCampaigns(campaigns) {
        const target = ensureTarget();

        if (!target) {
            return;
        }

        target.hidden = false;
        target.style.removeProperty("display");
        target.dataset.b18bLoaded = "1";
        target.dataset.b18bLoadedAt = new Date().toISOString();
        target.dataset.b18bCount = String(campaigns.length);

        latestCampaigns = campaigns;

        target.innerHTML = campaigns.length
            ? table(campaigns)
            : `
                <div class="empty">
                    Belum ada raw video catalog ads.
                </div>
            `;
    }

    function renderError(error) {
        const target = ensureTarget();

        if (!target) {
            return;
        }

        if (error?.status === 401 || error?.status === 403) {
            target.dataset.b18bAuthPending = "1";
            return;
        }

        target.hidden = false;
        target.style.removeProperty("display");
        target.innerHTML = `
            <div class="empty">
                Gagal memuat riwayat campaign:
                ${escapeHtml(error?.message || error)}
            </div>
        `;
    }

    async function refresh(force = false) {
        if (loading) {
            return;
        }

        const target = ensureTarget();

        if (!target) {
            return;
        }

        loading = true;

        try {
            const payload = await requestJson(ENDPOINT);
            const campaigns = Array.isArray(payload?.campaigns)
                ? payload.campaigns
                : [];

            hasActiveCampaign = campaigns.some(
                item => [
                    "queued",
                    "pending",
                    "rendering",
                    "processing",
                    "running",
                ].includes(
                    String(
                        item?.status || ""
                    ).toLowerCase()
                )
            );
            const signature = JSON.stringify(
                campaigns.map((item) => [
                    item?.id,
                    item?.status,
                    item?.completed_count,
                    item?.failed_count,
                    item?.variations,
                ]),
            );

            if (
                force
                || signature !== lastPayloadSignature
                || !target.dataset.b18bLoaded
                || target.children.length === 0
            ) {
                renderCampaigns(campaigns);
                lastPayloadSignature = signature;
            }
        } catch (error) {
            renderError(error);
        } finally {
            loading = false;
        }
    }

    async function showFallbackDetails(campaignId) {
        const target = document.getElementById(
            `campaignJobs-${campaignId}`,
        );

        if (!target) {
            return;
        }

        target.innerHTML = `
            <div class="render-item">
                Memuat hasil...
            </div>
        `;

        try {
            const payload = await requestJson(
                `/api/campaigns/${campaignId}`,
            );
            const campaign = payload?.campaign || {};
            const jobs = Array.isArray(campaign?.jobs)
                ? campaign.jobs
                : [];

            target.innerHTML = jobs.length
                ? jobs.map((job) => `
                    <div class="render-item">
                        <strong>
                            ${escapeHtml(job?.status || "unknown")}
                        </strong>
                        ${job?.output_url ? `
                            <a
                                class="mini-button"
                                href="${escapeHtml(job.output_url)}"
                                target="_blank"
                                rel="noopener"
                            >
                                Buka Video
                            </a>
                        ` : ""}
                        ${job?.error_message ? `
                            <small>${escapeHtml(job.error_message)}</small>
                        ` : ""}
                    </div>
                `).join("")
                : `
                    <div class="render-item">
                        Detail campaign berhasil dimuat.
                    </div>
                `;
        } catch (error) {
            target.innerHTML = `
                <div class="render-item">
                    Gagal memuat hasil:
                    ${escapeHtml(error?.message || error)}
                </div>
            `;
        }
    }

    async function handleClick(event) {
        const pageButton = event.target.closest(
            "[data-b18b-page]",
        );

        if (pageButton) {
            event.preventDefault();
            event.stopPropagation();

            const direction = pageButton.dataset.b18bPage;
            currentPage += direction === "next" ? 1 : -1;
            renderCampaigns(latestCampaigns);
            return;
        }

        const button = event.target.closest(
            "[data-b18b-action]",
        );

        if (!button) {
            return;
        }

        const action = button.dataset.b18bAction;
        const campaignId = numberValue(
            button.dataset.campaignId,
            0,
        );

        if (!campaignId) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        if (action === "view") {
            if (typeof window.viewCampaign === "function") {
                window.viewCampaign(campaignId, event);
            } else {
                await showFallbackDetails(campaignId);
            }
            return;
        }

        if (action === "retry") {
            if (typeof window.retryCampaign === "function") {
                window.retryCampaign(campaignId, event);
            }
            return;
        }

        if (action === "delete") {
            if (typeof window.deleteCampaign === "function") {
                window.deleteCampaign(campaignId, event);
            }
        }
    }

    function handleChange(event) {
        const select = event.target.closest(
            "[data-b18b-page-size]",
        );

        if (!select) {
            return;
        }

        const nextSize = numberValue(select.value, 5);
        pageSize = nextSize === 10 ? 10 : 5;
        currentPage = 1;
        renderCampaigns(latestCampaigns);
    }

    function schedule() {
        const scheduleNext = () => {
            if (pollTimer !== null) {
                clearTimeout(pollTimer);
            }

            pollTimer = null;

            if (document.hidden) {
                return;
            }

            const delay = hasActiveCampaign
                ? ACTIVE_POLL_MS
                : IDLE_POLL_MS;

            pollTimer = window.setTimeout(
                async () => {
                    await refresh(false);
                    scheduleNext();
                },
                delay,
            );
        };

        refresh(true).finally(
            scheduleNext
        );

        window.setTimeout(
            () => refresh(true),
            700,
        );

        window.B18FCampaignHistoryScheduleNext =
            scheduleNext;
    }

    document.addEventListener("click", handleClick, true);
    document.addEventListener("change", handleChange, true);

    document.addEventListener(
        "DOMContentLoaded",
        schedule,
        {once: true},
    );

    window.addEventListener(
        "pageshow",
        () => {
            refresh(true).finally(() => {
                window.B18FCampaignHistoryScheduleNext?.();
            });
        },
        {passive: true},
    );

    document.addEventListener(
        "visibilitychange",
        () => {
            if (document.hidden) {
                if (pollTimer !== null) {
                    clearTimeout(pollTimer);
                    pollTimer = null;
                }
                return;
            }

            refresh(true).finally(() => {
                window.B18FCampaignHistoryScheduleNext?.();
            });
        },
    );
window.B18FCampaignHistory = {
        version: VERSION,
        refresh: () => refresh(true),
        get active() {
            return hasActiveCampaign;
        },
    };

    window.B18BCampaignHistoryV3 = {
        version: VERSION,
        refresh: () => refresh(true),
    };

    if (document.readyState === "loading") {
        // DOMContentLoaded akan menjalankan schedule().
    } else {
        schedule();
    }
})();
