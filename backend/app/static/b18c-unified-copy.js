// B18C1_UNIFIED_AI_VARIANT_MATRIX_START
(() => {
    "use strict";

    const state = {
        configured: false,
        busy: false,
        model: "OpenAI",
    };

    const byId = id => document.getElementById(id);

    function detailMessage(data, fallback) {
        if (!data) return fallback;
        if (typeof data.detail === "string") return data.detail;
        if (data.detail) return JSON.stringify(data.detail);
        return data.message || fallback;
    }

    async function requestJson(url, options = {}) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 90000);

        try {
            const response = await fetch(url, {
                credentials: "same-origin",
                ...options,
                signal: controller.signal,
            });

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
                    detailMessage(data, `HTTP ${response.status}`)
                );
            }

            return data;
        } catch (error) {
            if (error?.name === "AbortError") {
                throw new Error("OpenAI timeout setelah 90 detik");
            }
            throw error;
        } finally {
            clearTimeout(timer);
        }
    }

    function setStatus(text, type = "pending") {
        const target = byId("b18c1OpenAIStatus");
        if (!target) return;
        target.textContent = text;
        target.className = `b18c1-status ${type}`;
    }

    function setMessage(text = "", error = false) {
        const target = byId("b18c1Message");
        if (!target) return;
        target.textContent = text;
        target.classList.toggle("error", Boolean(error));
    }

    function setBusy(busy) {
        state.busy = Boolean(busy);
        [
            "b18c1GenerateHookButton",
            "b18c1GenerateCtaButton",
            "b18c1GenerateBothButton",
        ].forEach(id => {
            const button = byId(id);
            if (button) button.disabled = state.busy || !state.configured;
        });
    }

    function selectedProductIds() {
        try {
            if (typeof window.selectedCatalogOrder === "function") {
                return window.selectedCatalogOrder()
                    .map(Number)
                    .filter(Boolean);
            }
            if (typeof selectedCatalogOrder === "function") {
                return selectedCatalogOrder()
                    .map(Number)
                    .filter(Boolean);
            }
        } catch (_) {}

        return [...document.querySelectorAll(".campaignProductCheckbox:checked")]
            .map(item => Number(item.value || item.dataset.productId))
            .filter(Boolean);
    }

    function firstLine(id) {
        return String(byId(id)?.value || "")
            .split(/\r?\n/)
            .map(value => value.trim())
            .find(Boolean) || null;
    }

    function payloadFor(mode) {
        return {
            product_ids: selectedProductIds(),
            mode,
            audience: byId("multiCampaignAudience")?.value || "retail_bulk",
            duration_seconds: Number(byId("multiCampaignDuration")?.value || 25),
            aspect_ratio: byId("multiCampaignAspect")?.value || "9:16",
            creative_template: byId("multiCampaignTemplate")?.value || "bundle_hemat",
            promo_enabled: Boolean(byId("multiCampaignPromoEnabled")?.checked),
            promo_min_amount: Number(byId("multiCampaignPromoMinAmount")?.value || 100000),
            promo_discount_percent: Number(byId("multiCampaignPromoDiscount")?.value || 10),
            promo_text: byId("multiCampaignPromoText")?.value.trim() || null,
            current_hook: firstLine("b13HookVariants"),
            current_cta: firstLine("b13CtaVariants"),
        };
    }

    function normalizeOptions(values) {
        return Array.isArray(values)
            ? [...new Set(values.map(value => String(value || "").trim()).filter(Boolean))]
            : [];
    }

    function applyLines(targetId, values, label) {
        const target = byId(targetId);
        if (!target || !values.length) return false;

        const next = values.join("\n");
        const current = target.value.trim();

        if (current && current !== next) {
            const replace = window.confirm(
                `${label} Variants sudah berisi teks. Ganti dengan 3 hasil OpenAI?`
            );
            if (!replace) return false;
        }

        target.value = next;
        target.dispatchEvent(new Event("input", {bubbles: true}));
        target.dispatchEvent(new Event("change", {bubbles: true}));
        return true;
    }

    function refreshMatrixPreview() {
        try {
            if (typeof window.renderB13VariantPreview === "function") {
                window.renderB13VariantPreview();
            }
        } catch (error) {
            setMessage(
                `Copy AI sudah masuk. Preview matrix perlu dibuat manual: ${error.message}`,
                false
            );
        }
    }

    async function loadStatus() {
        try {
            const data = await requestJson("/api/ai-copy/status");
            state.configured = Boolean(data.configured);
            state.model = data.model || "OpenAI";

            if (state.configured) {
                setStatus(`OpenAI aktif · ${state.model}`, "ready");
                setMessage("AI mengisi Hook/CTA Variants B13, satu opsi per baris.");
            } else {
                setStatus("OpenAI belum dikonfigurasi", "error");
                setMessage("OPENAI_API_KEY belum tersedia pada app container.", true);
            }
        } catch (error) {
            state.configured = false;
            setStatus("Status OpenAI gagal", "error");
            setMessage(error.message || "Tidak dapat memeriksa OpenAI", true);
        } finally {
            setBusy(false);
        }
    }

    async function generate(mode) {
        if (state.busy) return;
        if (!state.configured) {
            setMessage("OpenAI belum siap. Muat ulang halaman atau periksa API key.", true);
            return;
        }

        const payload = payloadFor(mode);
        if (payload.product_ids.length < 1) {
            setMessage("Pilih produk terlebih dahulu.", true);
            return;
        }

        state.busy = true;
        setBusy(true);
        setStatus("OpenAI sedang membuat copy...", "pending");
        setMessage("Menunggu tiga pilihan dari OpenAI. Jangan tutup halaman.");

        try {
            const data = await requestJson("/api/ai-copy/generate", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(payload),
            });

            const hooks = normalizeOptions(data.hooks);
            const ctas = normalizeOptions(data.ctas);
            let applied = 0;

            if (mode !== "cta" && hooks.length) {
                if (applyLines("b13HookVariants", hooks, "Hook")) applied += 1;
            }
            if (mode !== "hook" && ctas.length) {
                if (applyLines("b13CtaVariants", ctas, "CTA")) applied += 1;
            }

            if (!hooks.length && mode !== "cta") {
                throw new Error("OpenAI tidak mengembalikan Hook");
            }
            if (!ctas.length && mode !== "hook") {
                throw new Error("OpenAI tidak mengembalikan CTA");
            }

            state.model = data.model || state.model;
            setStatus(`OpenAI aktif · ${state.model}`, "ready");

            if (applied > 0) {
                setMessage(
                    "Hasil AI sudah masuk ke B13. Matrix preview diperbarui otomatis."
                );
                refreshMatrixPreview();
            } else {
                setMessage("Hasil AI tidak diterapkan karena penggantian dibatalkan.");
            }
        } catch (error) {
            setStatus("Generate OpenAI gagal", "error");
            setMessage(`Generate AI gagal: ${error.message}`, true);
        } finally {
            state.busy = false;
            setBusy(false);
        }
    }

    window.generateB18C1Copy = generate;
    window.reloadB18C1OpenAIStatus = loadStatus;

    function init() {
        const panel = byId("b18c1OpenAIStatus");
        if (!panel) return;
        setBusy(true);
        loadStatus();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init, {once: true});
    } else {
        init();
    }
})();
// B18C1_UNIFIED_AI_VARIANT_MATRIX_END
