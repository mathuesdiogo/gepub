(function () {
  function addClasses(selector, classes) {
    document.querySelectorAll(selector).forEach(function (el) {
      classes.forEach(function (className) {
        el.classList.add(className);
      });
    });
  }

  function normalizeDesignSystemClasses() {
    // Tables
    addClasses("table", ["gp-table__native"]);
    addClasses(".table-shell", ["gp-table", "gp-table--responsive"]);
    addClasses(".table-shell__body", ["gp-table__body"]);

    // Filter bars
    addClasses("form.filter-bar, form.gp-table__filters", ["search-and-filters"]);

    // Forms
    addClasses("form.gp-form", ["form-shell"]);

    // Buttons and actions
    addClasses(".btn", ["gp-button"]);
    addClasses(".btn.btn-primary, .btn.primary", ["gp-button--primary"]);
    addClasses(".btn.btn-danger, .btn.danger", ["gp-button--danger"]);
    addClasses(".btn.btn-warning, .btn.warning", ["gp-button--warning"]);
    addClasses(".btn.btn-success, .btn.success", ["gp-button--success"]);
    addClasses(".btn.btn-default, .btn.default", ["gp-button--default"]);
    addClasses(".btn.btn-secondary, .btn.secondary", ["gp-button--secondary"]);
    addClasses(".btn.btn-outline, .btn.outline", ["gp-button--outline"]);
    addClasses(".btn.btn--ghost, .btn.btn-ghost", ["gp-button--ghost"]);

    // Data display and feedback
    addClasses(".card", ["gp-card"]);
    addClasses(".card__body", ["gp-card__body"]);
    addClasses(".badge", ["gp-badge"]);
    addClasses(".alert", ["gp-alert"]);

    // Navigation
    addClasses("ul.tabs", ["nav", "nav-tabs"]);
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
    normalizeDesignSystemClasses();
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
