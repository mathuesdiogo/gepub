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

  function slugify(value) {
    return (value || "")
      .toString()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function bindGeneratedTabs() {
    var parents = [];
    var seen = new Set();

    qsa(".tab-pane[data-title], .tab-pane[data-title-tab]").forEach(function (pane) {
      var parent = pane.parentElement;
      if (!parent || seen.has(parent)) return;
      seen.add(parent);
      parents.push(parent);
    });

    parents.forEach(function (parent, parentIndex) {
      var panes = Array.from(parent.children).filter(function (child) {
        return (
          child.classList &&
          child.classList.contains("tab-pane") &&
          (child.hasAttribute("data-title") || child.hasAttribute("data-title-tab"))
        );
      });
      if (!panes.length) return;
      if (parent.querySelector(".nav.nav-tabs[data-gp-generated-tabs='true']")) return;

      var nav = document.createElement("ul");
      nav.className = "nav nav-tabs";
      nav.setAttribute("data-gp-generated-tabs", "true");
      nav.setAttribute("aria-label", parent.getAttribute("data-tabs-aria-label") || "Abas da seção");

      var hash = (window.location.hash || "").replace("#", "");
      var activePaneId = "";
      var paneEntries = [];

      panes.forEach(function (pane, paneIndex) {
        var title = pane.getAttribute("data-title") || pane.getAttribute("data-title-tab") || ("Aba " + (paneIndex + 1));
        var tabSlug = pane.getAttribute("data-tab") || slugify(title) || ("aba-" + (paneIndex + 1));
        var paneId = pane.id || ("gp-tab-pane-" + parentIndex + "-" + tabSlug);
        pane.id = paneId;

        var counterRaw = pane.getAttribute("data-counter");
        var hideOnZero = String(pane.getAttribute("data-hide-tab-on-counter-zero") || "").toLowerCase() === "true";
        if (hideOnZero && counterRaw !== null && Number(counterRaw) === 0) {
          pane.hidden = true;
          return;
        }

        var li = document.createElement("li");
        var link = document.createElement("a");
        link.href = "#" + paneId;
        link.className = "tabs__item";
        link.setAttribute("data-gp-tab-target", paneId);

        var label = document.createElement("span");
        label.className = "tabs__label";
        label.textContent = title;
        link.appendChild(label);

        if (counterRaw !== null && counterRaw !== "") {
          var badge = document.createElement("span");
          badge.className = "tabs__badge";
          badge.textContent = String(counterRaw);
          link.appendChild(badge);
        }

        var checked = (pane.getAttribute("data-checked") || "").toLowerCase();
        if (checked === "true" || checked === "false") {
          var check = document.createElement("span");
          check.className = "tabs__check " + (checked === "true" ? "is-ok" : "is-ko");
          check.setAttribute("aria-hidden", "true");
          link.appendChild(check);
        }

        li.appendChild(link);
        nav.appendChild(li);

        paneEntries.push({ pane: pane, li: li, link: link });
        if (!activePaneId) {
          activePaneId = paneId;
        }
        if (pane.getAttribute("data-default-tab") === "true") {
          activePaneId = paneId;
        }
      });

      if (!paneEntries.length) return;
      if (hash && paneEntries.some(function (entry) { return entry.pane.id === hash; })) {
        activePaneId = hash;
      }

      function activate(paneId) {
        paneEntries.forEach(function (entry) {
          var isActive = entry.pane.id === paneId;
          entry.pane.hidden = !isActive;
          entry.li.classList.toggle("active", isActive);
          entry.link.classList.toggle("is-active", isActive);
          if (isActive) {
            entry.link.setAttribute("aria-current", "page");
          } else {
            entry.link.removeAttribute("aria-current");
          }
        });
      }

      nav.addEventListener("click", function (event) {
        var link = event.target.closest("[data-gp-tab-target]");
        if (!link) return;
        event.preventDefault();
        var paneId = link.getAttribute("data-gp-tab-target");
        activate(paneId);
      });

      parent.insertBefore(nav, panes[0]);
      activate(activePaneId);
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

    qsa(".markall-container input[type='checkbox']").forEach(function (master) {
      master.addEventListener("change", function () {
        var targetSelector = (master.getAttribute("data-markall-target") || "").trim();
        if (targetSelector) {
          qsa(targetSelector).forEach(function (item) {
            if (item !== master) item.checked = master.checked;
          });
          return;
        }

        var scope = master.closest("table, .table-shell, form, .gp-card, .card");
        if (!scope) scope = document;
        var checkboxes = qsa("tbody input[type='checkbox'], input[type='checkbox']", scope).filter(function (item) {
          return item !== master;
        });
        checkboxes.forEach(function (item) {
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

  function bindLegacyButtonBehaviors() {
    qsa(".disable_on_click[data-href]").forEach(function (el) {
      el.addEventListener("click", function (event) {
        if (el.classList.contains("disabled")) {
          event.preventDefault();
          return;
        }
        event.preventDefault();
        el.classList.add("disabled");
        el.setAttribute("aria-disabled", "true");
        if (el.tagName === "BUTTON") {
          el.disabled = true;
        }
        var targetHref = (el.getAttribute("data-href") || "").trim();
        if (targetHref) {
          window.location.assign(targetHref);
        }
      });
    });

    qsa(".confirm[data-confirm]").forEach(function (el) {
      el.addEventListener("click", function (event) {
        var message = (el.getAttribute("data-confirm") || "").trim();
        if (!message) return;
        if (!window.confirm(message)) {
          event.preventDefault();
        }
      });
    });

    qsa(".popup[href]").forEach(function (el) {
      el.addEventListener("click", function (event) {
        var href = (el.getAttribute("href") || "").trim();
        if (!href || href === "#" || href.toLowerCase().indexOf("javascript:") === 0) return;
        var popup = window.open(
          href,
          "_blank",
          "popup=yes,width=1200,height=760,resizable=yes,scrollbars=yes"
        );
        if (popup) {
          event.preventDefault();
          popup.focus();
        }
      });
    });
  }

  function boot() {
    bindThemeSwitcher();
    bindGeneratedTabs();
    bindDropdownButtons();
    bindSortableTables();
    bindSelectAllCheckbox();
    bindIntegratedSearch();
    bindAlertDismiss();
    bindSmartForms();
    bindLegacyButtonBehaviors();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
