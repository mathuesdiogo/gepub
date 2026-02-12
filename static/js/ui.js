document.addEventListener("DOMContentLoaded", function () {
  const btn = document.querySelector(".toggle-btn");
  const sidebar = document.querySelector(".sidebar");

  if (btn) {
    btn.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
    });
  }
});
