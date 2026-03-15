(function () {
  const STORAGE_KEY = "gepub_cookie_consent_v1";
  const COOKIE_KEY = "gepub_cookie_consent";
  const CONSENT_VERSION = "2026.03";
  const COOKIE_MAX_AGE = 60 * 60 * 24 * 180;

  const defaultPreferences = {
    necessary: true,
    analytics: false,
    functional: false,
    marketing: false,
  };

  const root = document.querySelector("[data-cookie-consent]");
  if (!root) return;

  const banner = root.querySelector("[data-cookie-banner]");
  const modal = root.querySelector("[data-cookie-modal]");
  const backdrop = root.querySelector("[data-cookie-modal-backdrop]");
  const reopenTriggers = Array.from(document.querySelectorAll("[data-cookie-open-preferences]"));
  const prefInputs = {
    analytics: root.querySelector('[data-cookie-pref="analytics"]'),
    functional: root.querySelector('[data-cookie-pref="functional"]'),
    marketing: root.querySelector('[data-cookie-pref="marketing"]'),
  };

  function safeJsonParse(raw) {
    try {
      return JSON.parse(raw);
    } catch (error) {
      return null;
    }
  }

  function readCookie(name) {
    const encodedName = `${name}=`;
    const parts = document.cookie.split(";");
    for (let i = 0; i < parts.length; i += 1) {
      const value = parts[i].trim();
      if (!value.startsWith(encodedName)) continue;
      return decodeURIComponent(value.slice(encodedName.length));
    }
    return null;
  }

  function writeCookie(name, value) {
    const secure = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax${secure}`;
  }

  function buildConsent(preferences, source) {
    return {
      version: CONSENT_VERSION,
      updated_at: new Date().toISOString(),
      source: source || "banner",
      preferences: {
        ...defaultPreferences,
        ...preferences,
        necessary: true,
      },
    };
  }

  function isValidConsent(value) {
    return Boolean(
      value &&
        typeof value === "object" &&
        value.preferences &&
        typeof value.preferences === "object" &&
        typeof value.preferences.analytics === "boolean" &&
        typeof value.preferences.functional === "boolean" &&
        typeof value.preferences.marketing === "boolean"
    );
  }

  function getStoredConsent() {
    const local = safeJsonParse(window.localStorage.getItem(STORAGE_KEY) || "null");
    if (isValidConsent(local)) return local;

    const cookie = safeJsonParse(readCookie(COOKIE_KEY) || "null");
    if (isValidConsent(cookie)) return cookie;

    return null;
  }

  function persistConsent(consent) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(consent));
    writeCookie(COOKIE_KEY, JSON.stringify(consent));
  }

  function setModalPreferences(preferences) {
    prefInputs.analytics.checked = Boolean(preferences.analytics);
    prefInputs.functional.checked = Boolean(preferences.functional);
    prefInputs.marketing.checked = Boolean(preferences.marketing);
  }

  function getModalPreferences() {
    return {
      necessary: true,
      analytics: Boolean(prefInputs.analytics.checked),
      functional: Boolean(prefInputs.functional.checked),
      marketing: Boolean(prefInputs.marketing.checked),
    };
  }

  function dispatchConsent(consent) {
    window.GEPUBCookieConsent = consent;
    window.dispatchEvent(
      new CustomEvent("gepub:cookie-consent-updated", {
        detail: consent,
      })
    );
  }

  window.GEPUBConsent = {
    get: function () {
      return window.GEPUBCookieConsent || getStoredConsent();
    },
    has: function (category) {
      const current = window.GEPUBCookieConsent || getStoredConsent();
      if (!current || !current.preferences) return category === "necessary";
      return Boolean(current.preferences[category]);
    },
    openPreferences: openModal,
  };

  function applyConsent(consent) {
    persistConsent(consent);
    setModalPreferences(consent.preferences);
    dispatchConsent(consent);
    hideBanner();
  }

  function showBanner() {
    banner.hidden = false;
  }

  function hideBanner() {
    banner.hidden = true;
  }

  function openModal() {
    modal.hidden = false;
    backdrop.hidden = false;
    document.body.classList.add("cc-modal-open");
  }

  function closeModal() {
    modal.hidden = true;
    backdrop.hidden = true;
    document.body.classList.remove("cc-modal-open");
  }

  function acceptAll(source) {
    applyConsent(
      buildConsent(
        { necessary: true, analytics: true, functional: true, marketing: true },
        source || "accept_all"
      )
    );
    closeModal();
  }

  function rejectOptional(source) {
    applyConsent(
      buildConsent(
        { necessary: true, analytics: false, functional: false, marketing: false },
        source || "reject_optional"
      )
    );
    closeModal();
  }

  function savePreferences(source) {
    applyConsent(buildConsent(getModalPreferences(), source || "save_preferences"));
    closeModal();
  }

  const existing = getStoredConsent();
  if (existing) {
    setModalPreferences(existing.preferences);
    dispatchConsent(existing);
    hideBanner();
  } else {
    setModalPreferences(defaultPreferences);
    showBanner();
  }

  root.querySelector("[data-cookie-accept-all]").addEventListener("click", function () {
    acceptAll("banner_accept_all");
  });
  root.querySelector("[data-cookie-reject-all]").addEventListener("click", function () {
    rejectOptional("banner_reject_optional");
  });
  root.querySelector("[data-cookie-open-modal]").addEventListener("click", openModal);

  root.querySelector("[data-cookie-close-modal]").addEventListener("click", closeModal);
  backdrop.addEventListener("click", closeModal);
  reopenTriggers.forEach(function (trigger) {
    trigger.addEventListener("click", openModal);
  });

  root.querySelector("[data-cookie-save-prefs]").addEventListener("click", function () {
    savePreferences("modal_save");
  });
  root.querySelector("[data-cookie-accept-all-modal]").addEventListener("click", function () {
    acceptAll("modal_accept_all");
  });
  root.querySelector("[data-cookie-reject-all-modal]").addEventListener("click", function () {
    rejectOptional("modal_reject_optional");
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !modal.hidden) {
      closeModal();
    }
  });
})();
