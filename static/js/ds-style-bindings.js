(function () {
  function qsa(selector, scope) {
    return Array.from((scope || document).querySelectorAll(selector));
  }

  function addClasses(selector, classes) {
    qsa(selector).forEach(function (el) {
      classes.forEach(function (className) {
        el.classList.add(className);
      });
    });
  }

  function addClassByState(el, mapping) {
    Object.keys(mapping).some(function (stateClass) {
      if (!el.classList.contains(stateClass)) return false;
      el.classList.add(mapping[stateClass]);
      return true;
    });
  }

  function normalizeTables() {
    addClasses("table", ["gp-table__native"]);
    addClasses(".table-shell", ["gp-table", "gp-table--responsive"]);
    addClasses(".table-shell__body", ["gp-table__body"]);
    addClasses(".table-responsive", ["gp-table", "gp-table--responsive"]);
    addClasses(".table-responsive > table", ["gp-table__native"]);
  }

  function normalizeForms() {
    addClasses("form.filter-bar, form.gp-table__filters", ["search-and-filters"]);
    addClasses(".filter-bar", ["search-and-filters"]);
    addClasses("form.gp-form", ["form-shell"]);

    // Bridge: forms legados recebem shell automaticamente quando possuem campos visíveis.
    qsa("form").forEach(function (form) {
      if (
        form.classList.contains("form-shell") ||
        form.classList.contains("u-inline-form") ||
        form.classList.contains("gp-inline-form") ||
        form.classList.contains("gauth-inline-form") ||
        form.classList.contains("topbar-search")
      ) {
        return;
      }

      var hasVisibleFields = !!form.querySelector(
        "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='reset']), select, textarea"
      );
      if (!hasVisibleFields) {
        return;
      }

      form.classList.add("form-shell");

      var classBlob = Array.from(form.classList).join(" ").toLowerCase();
      var looksLikeFilter =
        classBlob.indexOf("filter") >= 0 ||
        classBlob.indexOf("search") >= 0 ||
        !!form.querySelector("input[type='search']");
      if (
        looksLikeFilter &&
        !form.classList.contains("search-and-filters") &&
        !form.classList.contains("topbar-search")
      ) {
        form.classList.add("search-and-filters");
      }
    });
  }

  function normalizeButtonsAndActions() {
    addClasses(".btn", ["gp-button"]);
    addClasses(".btn.btn-primary, .btn.primary", ["gp-button--primary"]);
    addClasses(".btn.btn-danger, .btn.danger", ["gp-button--danger"]);
    addClasses(".btn.btn-warning, .btn.warning", ["gp-button--warning"]);
    addClasses(".btn.btn-success, .btn.success", ["gp-button--success"]);
    addClasses(".btn.btn-default, .btn.default", ["gp-button--default"]);
    addClasses(".btn.btn-secondary, .btn.secondary", ["gp-button--secondary"]);
    addClasses(".btn.btn-outline, .btn.outline", ["gp-button--outline"]);
    addClasses(".btn.btn--ghost, .btn.btn-ghost", ["gp-button--ghost"]);
    addClasses(".action-bar", ["gp-action-bar"]);
  }

  function normalizeDataDisplay() {
    addClasses(".card", ["gp-card"]);
    addClasses(".card__body", ["gp-card__body"]);
    addClasses(".card__head, .card__header", ["gp-card__header"]);
    addClasses(".box", ["gp-card"]);
    addClasses(".box > .content, .box > .body", ["gp-card__body"]);
    addClasses(".board", ["gp-card"]);
    addClasses(".board > .content, .board > .body", ["gp-card__body"]);
    addClasses(".general-box", ["gp-card"]);
    addClasses(".general-box .primary-info", ["gp-card__body"]);
    addClasses(".total-container > a, .total-container > div", ["gp-card", "gp-card__body"]);
    addClasses(".gallery > .gallery-item", ["gp-card", "gp-card__body"]);
    addClasses(".flex-container", ["gp-grid"]);
  }

  function normalizeNavigation() {
    addClasses("ul.tabs", ["nav", "nav-tabs"]);
    qsa("ul.nav.nav-tabs li.active > a, ul.pills li.active > a").forEach(function (a) {
      a.classList.add("is-active");
      a.setAttribute("aria-current", "page");
    });
  }

  function normalizeFeedback() {
    addClasses(".badge", ["gp-badge"]);
    addClasses(".alert", ["gp-alert"]);
    addClasses(".flash", ["alert", "gp-alert"]);

    qsa(".alert, .flash").forEach(function (el) {
      addClassByState(el, {
        success: "gp-alert--success",
        warning: "gp-alert--warning",
        alert: "gp-alert--warning",
        danger: "gp-alert--error",
        error: "gp-alert--error",
        info: "gp-alert--info",
        light: "gp-alert--info",
      });
    });

    qsa(".status").forEach(function (el) {
      el.classList.add("gp-badge");
      addClassByState(el, {
        success: "gp-badge--success",
        concluido: "gp-badge--success",
        finalizado: "gp-badge--success",
        warning: "gp-badge--warning",
        alert: "gp-badge--warning",
        danger: "gp-badge--danger",
        error: "gp-badge--danger",
        cancelado: "gp-badge--danger",
        info: "gp-badge--primary",
      });
    });
  }

  function normalizeIndicators() {
    addClasses(".progressbar", ["progress"]);
    addClasses(".progressbar .bar", ["progress-bar"]);
    addClasses(".progressbar > div", ["progress-bar"]);
    addClasses(".progressbar-value", ["progress-description"]);
    addClasses(".stats, .stats-list, .counter-list", ["gp-grid"]);
    addClasses(".stats > li, .stats-list > li, .counter-list > li", ["gp-card", "gp-card__body"]);
  }

  function clampPercent(value) {
    var parsed = Number.parseFloat(String(value || "").replace("%", "").replace(",", "."));
    if (!Number.isFinite(parsed)) return null;
    if (parsed < 0) return 0;
    if (parsed > 100) return 100;
    return parsed;
  }

  function applyDimensionFromData(selector, cssProp) {
    document.querySelectorAll(selector).forEach(function (el) {
      var raw = el.getAttribute(selector === "[data-style-width-pct]" ? "data-style-width-pct" : "data-style-height-pct");
      var pct = clampPercent(raw);
      if (pct === null) return;
      el.style[cssProp] = pct + "%";
    });
  }

  function applyBackgrounds() {
    document.querySelectorAll("[data-style-bg]").forEach(function (el) {
      var bg = el.getAttribute("data-style-bg");
      if (!bg) return;
      el.style.background = bg;
    });
  }

  function applyCssVars() {
    document.querySelectorAll("[data-style-var-root], [data-style-var-v], [data-style-var-pct], [data-style-var-gp-progress], [data-style-var-bar], [data-style-var-slide-image], [data-style-var-card-image], [data-style-var-turismo-image], [data-style-var-portal-primary], [data-style-var-portal-secondary]").forEach(function (el) {
      Array.from(el.attributes).forEach(function (attr) {
        if (!attr.name.startsWith("data-style-var-")) return;
        var varName = "--" + attr.name.replace("data-style-var-", "");
        if (!attr.value) return;
        el.style.setProperty(varName, attr.value);
      });
    });
  }

  function boot() {
    normalizeTables();
    normalizeForms();
    normalizeButtonsAndActions();
    normalizeDataDisplay();
    normalizeNavigation();
    normalizeFeedback();
    normalizeIndicators();
    applyDimensionFromData("[data-style-width-pct]", "width");
    applyDimensionFromData("[data-style-height-pct]", "height");
    applyBackgrounds();
    applyCssVars();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
