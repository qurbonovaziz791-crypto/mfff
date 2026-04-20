/**
 * Hayriya formasi: manzil.
 *
 * Offline / Google-bloklangan tarmoqlarda maps.googleapis.com ishlamaydi.
 * Shuning uchun interaktiv xaritani majburlamaymiz: foydalanuvchi lat/lng ni qo‘lda kiritadi,
 * yoki koordinatani clipboard’dan qo‘yadi.
 */
(function () {
  var DEFAULT_CENTER = { lat: 41.311151, lng: 69.279737 };
  var DEFAULT_ZOOM = 12;

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function toast(msg) {
    var el = document.getElementById("hy-charity-form-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "hy-charity-form-toast";
      el.className = "hy-charity-toast";
      el.setAttribute("role", "status");
      var anchor = document.querySelector(".hy-form-page");
      if (anchor) anchor.appendChild(el);
      else document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add("hy-charity-toast--show");
    clearTimeout(el._hyT);
    el._hyT = setTimeout(function () {
      el.classList.remove("hy-charity-toast--show");
    }, 2600);
  }

  function setInputs(lat, lng) {
    var la = document.getElementById("id_latitude");
    var lo = document.getElementById("id_longitude");
    if (la) la.value = lat.toFixed(6);
    if (lo) lo.value = lng.toFixed(6);
  }

  function readInputs() {
    var la = document.getElementById("id_latitude");
    var lo = document.getElementById("id_longitude");
    var lat = la && la.value ? parseFloat(la.value) : NaN;
    var lng = lo && lo.value ? parseFloat(lo.value) : NaN;
    if (!isNaN(lat) && !isNaN(lng)) return { lat: lat, lng: lng };
    return null;
  }

  function disableGoogleMapUi() {
    var mapEl = document.getElementById("hy-charity-form-map");
    if (mapEl) {
      mapEl.style.display = "none";
    }
    var fill = document.getElementById("hy-map-fill-address");
    if (fill) fill.disabled = true;
  }

  ready(function () {
    var mapEl = document.getElementById("hy-charity-form-map");
    if (!mapEl) return;
    // Xarita blocklangan tarmoqda layout buzmasin
    disableGoogleMapUi();

    // Geolocation: foydalanuvchi lat/lng ni tez to‘ldirsin
    var btnGeo = document.getElementById("hy-map-my-location");
    if (btnGeo) {
      btnGeo.addEventListener("click", function () {
        if (!navigator.geolocation) {
          toast("Brauzer joylashuvni qo‘llab-quvvatlamaydi");
          return;
        }
        btnGeo.disabled = true;
        navigator.geolocation.getCurrentPosition(
          function (pos) {
            setInputs(pos.coords.latitude, pos.coords.longitude);
            btnGeo.disabled = false;
            toast("Joylashuv qo‘yildi (lat/lng)");
          },
          function () {
            btnGeo.disabled = false;
            toast("Joylashuv rad etildi yoki topilmadi");
          },
          { enableHighAccuracy: true, timeout: 12000 }
        );
      });
    }
  });
})();
