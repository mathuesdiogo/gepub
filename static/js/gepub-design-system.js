(function () {
  function qs(sel, scope) {
    return (scope || document).querySelector(sel);
  }

  function qsa(sel, scope) {
    return Array.from((scope || document).querySelectorAll(sel));
  }

  function bindThemeSwitcher() {
    qsa("[data-gp-theme-switch]").forEach(function (el) {
      el.addEventListener("change", function () {
        var value = (el.value || "").trim().toLowerCase();
        if (!value) return;
        document.documentElement.setAttribute("data-theme", value);
      });
    });
  }

  function bindDropdownButtons() {
    qsa(".gp-button-dropdown [data-gp-dropdown-toggle]").forEach(function (btn) {
      btn.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        var root = btn.closest(".gp-button-dropdown");
        if (!root) return;
        root.classList.toggle("is-open");
      });
    });

    document.addEventListener("click", function () {
      qsa(".gp-button-dropdown.is-open").forEach(function (item) {
        item.classList.remove("is-open");
      });
    });
  }

  function bindSortableTables() {
    qsa(".gp-table--sortable").forEach(function (table) {
      var body = table.tBodies[0];
      if (!body) return;
      qsa("thead th", table).forEach(function (th, idx) {
        if (th.dataset.sortable === "false") return;
        th.setAttribute("aria-sort", "none");
        th.addEventListener("click", function () {
          var asc = th.getAttribute("aria-sort") !== "ascending";
          qsa("thead th", table).forEach(function (head) {
            head.setAttribute("aria-sort", "none");
          });
          th.setAttribute("aria-sort", asc ? "ascending" : "descending");
          var rows = Array.from(body.querySelectorAll("tr"));
          rows.sort(function (a, b) {
            var av = ((a.children[idx] || {}).textContent || "").trim().toLowerCase();
            var bv = ((b.children[idx] || {}).textContent || "").trim().toLowerCase();
            if (av < bv) return asc ? -1 : 1;
            if (av > bv) return asc ? 1 : -1;
            return 0;
          });
          rows.forEach(function (row) {
            body.appendChild(row);
          });
        });
      });
    });
  }

  function bindSelectAllCheckbox() {
    qsa("[data-gp-select-all]").forEach(function (master) {
      master.addEventListener("change", function () {
        var target = master.getAttribute("data-gp-select-all");
        qsa("[data-gp-select='" + target + "']").forEach(function (item) {
          item.checked = master.checked;
        });
      });
    });
  }

  function bindIntegratedSearch() {
    qsa("[data-gp-table-search]").forEach(function (input) {
      var tableId = input.getAttribute("data-gp-table-search");
      var table = qs("#" + tableId);
      if (!table || !table.tBodies[0]) return;
      input.addEventListener("input", function () {
        var val = (input.value || "").trim().toLowerCase();
        Array.from(table.tBodies[0].rows).forEach(function (row) {
          var text = (row.textContent || "").toLowerCase();
          row.hidden = val && text.indexOf(val) < 0;
        });
      });
    });
  }

  function bindAlertDismiss() {
    qsa(".gp-alert--dismissible .alert__close, .alert .alert__close").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var alert = btn.closest(".gp-alert, .alert");
        if (alert) {
          alert.remove();
        }
      });
    });
  }

  function bindSmartForms() {
    qsa("form.gp-form").forEach(function (form) {
      if (form.classList.contains("gp-form--stacked")) return;
      if (form.querySelector(".form-shell__fields")) return;

      var directRows = Array.from(form.children).filter(function (child) {
        if (child.tagName !== "P") return false;
        return !!child.querySelector("input, select, textarea");
      });

      if (directRows.length < 2) return;
      form.classList.add("gp-form--smart");
    });
  }

  function boot() {
    bindThemeSwitcher();
    bindDropdownButtons();
    bindSortableTables();
    bindSelectAllCheckbox();
    bindIntegratedSearch();
    bindAlertDismiss();
    bindSmartForms();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
