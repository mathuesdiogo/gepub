(function () {
  "use strict";

  function closeAlert(el) {
    el.classList.add("alert--closing");
    setTimeout(() => el.remove(), 220);
  }

  document.addEventListener("DOMContentLoaded", function () {

    // Alerts
    document.querySelectorAll(".alert").forEach((alert) => {
      const closeBtn = alert.querySelector(".alert__close");
      if (closeBtn) {
        closeBtn.addEventListener("click", () => closeAlert(alert));
      }

      const delay = parseInt(alert.dataset.autoclose || "4000", 10);
      if (delay > 0) {
        setTimeout(() => {
          if (document.body.contains(alert)) closeAlert(alert);
        }, delay);
      }
    });

    // Dropdown
    document.querySelectorAll("[data-dropdown-toggle]").forEach((btn) => {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();

        const root = btn.closest(".dropdown");
        if (!root) return;

        document.querySelectorAll(".dropdown.is-open").forEach(d => {
          if (d !== root) d.classList.remove("is-open");
        });

        root.classList.toggle("is-open");
      });
    });

    document.addEventListener("click", function () {
      document.querySelectorAll(".dropdown.is-open")
        .forEach(d => d.classList.remove("is-open"));
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        document.querySelectorAll(".dropdown.is-open")
          .forEach(d => d.classList.remove("is-open"));
      }
    });

  });
})();
