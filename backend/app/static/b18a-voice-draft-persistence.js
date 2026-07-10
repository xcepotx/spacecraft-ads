// B18F_VOICE_DRAFT_CONTROLLER_START
(() => {
    "use strict";

    const VERSION = "B18F-1.0";

    const previous =
        window.B18FVoiceDraftController;

    if (
        previous
        && typeof previous.destroy === "function"
    ) {
        previous.destroy();
    }

    const abortController =
        new AbortController();

    const signal =
        abortController.signal;

    const ids = {
        checkbox:
            "multiCampaignVoiceoverEnabled",
        voice:
            "multiCampaignVoiceId",
        controls:
            "multiVoiceoverControls",
        mode:
            "multiCampaignVoiceMode",
        wrap:
            "multiCustomVoiceTextWrap",
        textarea:
            "multiCampaignVoiceText",
    };

    let queued = false;
    let lastState = null;
    let settleTimer = null;

    const byId = id =>
        document.getElementById(id);

    function desiredState() {
        const checkbox =
            byId(ids.checkbox);

        const voice =
            byId(ids.voice);

        return Boolean(
            checkbox
            && checkbox.checked
            && !checkbox.disabled
            && voice
            && !voice.disabled
            && String(
                voice.value || ""
            ).trim()
        );
    }

    function sync(reason = "sync") {
        queued = false;

        const checkbox =
            byId(ids.checkbox);

        const voice =
            byId(ids.voice);

        const controls =
            byId(ids.controls);

        const mode =
            byId(ids.mode);

        const wrap =
            byId(ids.wrap);

        const textarea =
            byId(ids.textarea);

        if (
            !checkbox
            || !voice
            || !controls
            || !mode
            || !wrap
        ) {
            return false;
        }

        const visible =
            desiredState();

        if (mode.value !== "custom") {
            mode.value = "custom";
        }

        if (!mode.disabled) {
            mode.disabled = true;
        }

        controls.classList.toggle(
            "voiceover-disabled",
            !visible
        );

        if (
            wrap.classList.contains("hidden")
            === visible
        ) {
            wrap.classList.toggle(
                "hidden",
                !visible
            );
        }

        const expectedAria =
            visible ? "false" : "true";

        if (
            wrap.getAttribute("aria-hidden")
            !== expectedAria
        ) {
            wrap.setAttribute(
                "aria-hidden",
                expectedAria
            );
        }

        if (
            visible
            && wrap.hasAttribute("hidden")
        ) {
            wrap.removeAttribute("hidden");
        }

        if (
            textarea
            && textarea.disabled === visible
        ) {
            textarea.disabled = !visible;
        }

        wrap.dataset.b18fVisible =
            visible ? "1" : "0";

        wrap.dataset.b18fReason =
            reason;

        if (lastState !== visible) {
            lastState = visible;

            console.info(
                `[${VERSION}] Voice panel `
                + `${visible ? "shown" : "hidden"}`
            );
        }

        return true;
    }

    function queueSync(
        reason = "event",
        settle = true
    ) {
        if (!queued) {
            queued = true;

            queueMicrotask(
                () => sync(reason)
            );
        }

        if (!settle) {
            return;
        }

        if (settleTimer !== null) {
            clearTimeout(settleTimer);
        }

        settleTimer = window.setTimeout(
            () => sync(
                `${reason}-settled`
            ),
            80
        );
    }

    function relevantTarget(target) {
        return Boolean(
            target
            && [
                ids.checkbox,
                ids.voice,
                ids.mode,
            ].includes(target.id)
        );
    }

    document.addEventListener(
        "change",
        event => {
            if (
                relevantTarget(event.target)
            ) {
                queueSync(
                    `change:${event.target.id}`
                );
            }
        },
        {
            capture: true,
            signal,
        }
    );

    window.addEventListener(
        "pageshow",
        () => queueSync("pageshow"),
        {
            passive: true,
            signal,
        }
    );

    document.addEventListener(
        "visibilitychange",
        () => {
            if (!document.hidden) {
                queueSync(
                    "visibilitychange"
                );
            }
        },
        {signal}
    );

    function wrapLegacy(name) {
        const original =
            window[name];

        if (
            typeof original !== "function"
            || original.__b18fWrapped
        ) {
            return;
        }

        const wrapped =
            function (...args) {
                const result =
                    original.apply(
                        this,
                        args
                    );

                queueSync(
                    `legacy:${name}`
                );

                return result;
            };

        wrapped.__b18fWrapped = true;
        wrapped.__b18fOriginal =
            original;

        window[name] = wrapped;
    }

    function boot() {
        wrapLegacy(
            "toggleMultiVoiceoverControls"
        );

        wrapLegacy(
            "toggleMultiCustomVoiceText"
        );

        sync("boot");

        window.setTimeout(
            () => sync("boot-settled"),
            250
        );
    }

    if (
        document.readyState
        === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            boot,
            {
                once: true,
                signal,
            }
        );
    } else {
        boot();
    }

    window.syncB18AVoiceDraftPanelPersistent =
        () => queueSync("manual");

    window.B18FVoiceDraftController = {
        version: VERSION,
        sync: () => sync("api"),
        destroy() {
            abortController.abort();

            if (settleTimer !== null) {
                clearTimeout(
                    settleTimer
                );
            }

            settleTimer = null;
        },
    };
})();
// B18F_VOICE_DRAFT_CONTROLLER_END
