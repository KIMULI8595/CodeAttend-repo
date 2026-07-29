"use strict";

document.addEventListener("DOMContentLoaded", () => {
    initialiseMobileMenu();
    initialiseIdleLogout();
});

function initialiseMobileMenu() {
    const button = document.getElementById("mobile-menu-button");
    const menu = document.getElementById("header-content");
    if (!button || !menu) return;

    const mobileQuery = window.matchMedia("(max-width: 800px)");

    const setOpen = (open) => {
        menu.classList.toggle("is-open", open);
        button.setAttribute("aria-expanded", String(open));
        button.setAttribute("aria-label", open ? "Close navigation menu" : "Open navigation menu");
        document.body.classList.toggle("mobile-menu-open", open);
    };

    button.addEventListener("click", () => setOpen(button.getAttribute("aria-expanded") !== "true"));

    menu.addEventListener("click", (event) => {
        if (mobileQuery.matches && event.target.closest("a")) setOpen(false);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && button.getAttribute("aria-expanded") === "true") {
            setOpen(false);
            button.focus();
        }
    });

    mobileQuery.addEventListener?.("change", (event) => {
        if (!event.matches) setOpen(false);
    });
}

function initialiseIdleLogout() {
    const body = document.body;
    if (body.dataset.authenticated !== "true") return;

    const logoutForm = document.getElementById("logout-form");
    const warningDialog = document.getElementById("session-warning");
    const countdown = document.getElementById("session-countdown");
    const staySignedIn = document.getElementById("stay-signed-in");
    const logoutNow = document.getElementById("logout-now");
    if (!logoutForm || !warningDialog || !countdown || !staySignedIn || !logoutNow) return;

    const timeoutMs = Math.max(Number(body.dataset.sessionTimeoutMs) || 1_800_000, 60_000);
    const warningMs = Math.min(Math.max(Number(body.dataset.sessionWarningMs) || 60_000, 10_000), timeoutMs - 1_000);
    const storageKey = body.dataset.activityStorageKey || "codeattend-last-activity";
    const activityEvents = ["pointerdown", "keydown", "touchstart", "scroll"];

    let warningTimer = 0;
    let logoutTimer = 0;
    let countdownTimer = 0;
    let deadline = 0;
    let lastActivityWrite = 0;
    let isLoggingOut = false;

    const clearTimers = () => {
        window.clearTimeout(warningTimer);
        window.clearTimeout(logoutTimer);
        window.clearInterval(countdownTimer);
    };

    const hideWarning = () => {
        warningDialog.hidden = true;
        body.classList.remove("session-warning-open");
        window.clearInterval(countdownTimer);
    };

    const submitLogout = () => {
        if (isLoggingOut) return;
        isLoggingOut = true;
        clearTimers();
        if (typeof logoutForm.requestSubmit === "function") logoutForm.requestSubmit();
        else logoutForm.submit();
    };

    const updateCountdown = () => {
        const seconds = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
        countdown.textContent = String(seconds);
        if (seconds <= 0) submitLogout();
    };

    const showWarning = () => {
        warningDialog.hidden = false;
        body.classList.add("session-warning-open");
        updateCountdown();
        countdownTimer = window.setInterval(updateCountdown, 1000);
        staySignedIn.focus();
    };

    const scheduleFrom = (lastActivity) => {
        clearTimers();
        hideWarning();
        deadline = lastActivity + timeoutMs;
        const now = Date.now();
        const untilLogout = deadline - now;
        const untilWarning = untilLogout - warningMs;

        if (untilLogout <= 0) {
            submitLogout();
            return;
        }

        if (untilWarning <= 0) showWarning();
        else warningTimer = window.setTimeout(showWarning, untilWarning);

        logoutTimer = window.setTimeout(submitLogout, untilLogout);
    };

    const registerActivity = (force = false) => {
        const now = Date.now();
        if (!force && now - lastActivityWrite < 1000) return;
        lastActivityWrite = now;
        try { localStorage.setItem(storageKey, String(now)); } catch (_) { /* storage may be unavailable */ }
        scheduleFrom(now);
    };

    activityEvents.forEach((eventName) => {
        document.addEventListener(eventName, () => registerActivity(false), { passive: true });
    });

    staySignedIn.addEventListener("click", () => registerActivity(true));
    logoutNow.addEventListener("click", submitLogout);

    window.addEventListener("storage", (event) => {
        if (event.key !== storageKey || !event.newValue) return;
        const timestamp = Number(event.newValue);
        if (Number.isFinite(timestamp)) scheduleFrom(timestamp);
    });

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            let lastActivity = Date.now();
            try { lastActivity = Number(localStorage.getItem(storageKey)) || lastActivity; } catch (_) { /* ignore */ }
            scheduleFrom(lastActivity);
        }
    });

    let initialActivity = Date.now();
    try {
        const stored = Number(localStorage.getItem(storageKey));
        if (Number.isFinite(stored) && stored > 0) initialActivity = stored;
        else localStorage.setItem(storageKey, String(initialActivity));
    } catch (_) { /* ignore */ }
    scheduleFrom(initialActivity);
}
