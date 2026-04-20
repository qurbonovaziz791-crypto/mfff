/**
 * Hayriyalar ro‘yxati: filtr checkbox holati (karta fonidagi ajratish).
 */
(function () {
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }
  ready(function () {
    document.querySelectorAll(".hy-charity-filters__check-row").forEach(function (row) {
      var cb = row.querySelector(".hy-charity-filters__checkbox");
      if (!cb) return;
      function upd() {
        row.classList.toggle("is-checked", cb.checked);
      }
      cb.addEventListener("change", upd);
      upd();
    });
  });
})();
