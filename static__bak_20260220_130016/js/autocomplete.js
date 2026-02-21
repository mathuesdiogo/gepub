(function () {
  function qs(el, sel) { return el.querySelector(sel); }

  function buildHref(template, item, query) {
    return template
      .replaceAll("{id}", encodeURIComponent(item.id ?? ""))
      .replaceAll("{q}", encodeURIComponent(query ?? ""))
      .replaceAll("{nome}", encodeURIComponent(item.nome ?? ""));
  }

  function attachAutocomplete(input) {
    const url = input.dataset.autocompleteUrl;
    if (!url) return;

    const min = parseInt(input.dataset.autocompleteMin || "2", 10);
    const delay = parseInt(input.dataset.autocompleteDelay || "250", 10);
    const hrefTpl = input.dataset.autocompleteHref || ""; // opcional
    const mode = input.dataset.autocompleteMode || "navigate"; // navigate | fill
    const fillTarget = input.dataset.autocompleteFillTarget || ""; // ex: "#id_aluno"

    // container overlay
    const wrap = document.createElement("div");
    wrap.style.position = "relative";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    const box = document.createElement("div");
    box.className = "suggest";
    box.style.display = "none";
    box.style.position = "absolute";
    box.style.top = "100%";
    box.style.left = "0";
    box.style.right = "0";
    box.style.zIndex = "60";
    box.style.marginTop = "6px";
    wrap.appendChild(box);

    let t = null;
    let last = "";
    let abort = null;

    function hide() {
      box.style.display = "none";
      box.innerHTML = "";
    }

    function show(items, query) {
      if (!items || !items.length) { hide(); return; }

      box.innerHTML = items.map(item => {
        const meta = item.meta || item.subtitle || "";
        const title = item.title || item.nome || item.text || "";
        const href = hrefTpl ? buildHref(hrefTpl, item, query) : "#";

        return `
          <a class="suggest__item" href="${href}" data-id="${item.id ?? ""}" data-title="${title.replaceAll('"', "&quot;")}">
            <div class="suggest__title">${title}</div>
            ${meta ? `<div class="suggest__meta">${meta}</div>` : ""}
          </a>
        `;
      }).join("");

      box.style.display = "block";
    }

    async function fetchSuggest(q) {
      if (abort) abort.abort();
      abort = new AbortController();
      const full = url + (url.includes("?") ? "&" : "?") + "q=" + encodeURIComponent(q);
      const res = await fetch(full, { signal: abort.signal, headers: { "X-Requested-With": "fetch" } });
      if (!res.ok) return [];
      const data = await res.json();
      return data.results || [];
    }

    input.addEventListener("input", () => {
      const q = (input.value || "").trim();
      if (q.length < min) { hide(); return; }
      if (q === last) return;
      last = q;

      clearTimeout(t);
      t = setTimeout(async () => {
        try {
          const items = await fetchSuggest(q);
          show(items, q);
        } catch (e) { /* abort */ }
      }, delay);
    });

    box.addEventListener("click", (e) => {
      const a = e.target.closest("a.suggest__item");
      if (!a) return;

      if (mode === "fill") {
        e.preventDefault();
        const id = a.getAttribute("data-id");
        const title = a.getAttribute("data-title");

        const target = fillTarget ? document.querySelector(fillTarget) : null;
        if (target) {
          target.value = id;
          target.dispatchEvent(new Event("change", { bubbles: true }));
        }

        // opcional: coloca o nome no input
        input.value = title || input.value;
        hide();
      }
    });

    document.addEventListener("click", (e) => {
      if (wrap.contains(e.target)) return;
      hide();
    });
  }

  function init() {
    document.querySelectorAll("input[data-autocomplete-url]").forEach(attachAutocomplete);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
