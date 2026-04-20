/**
 * Hayriya batafsil: to‘lov (plastik karta + nusxa), telefon, shikoyat, Google xarita.
 */
(function () {
  var DETAIL_CB = "hyCharityDetailMapInit";

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function toast(msg) {
    var el = document.getElementById("hy-charity-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "hy-charity-toast";
      el.className = "hy-charity-toast";
      el.setAttribute("role", "status");
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add("hy-charity-toast--show");
    clearTimeout(el._hyT);
    el._hyT = setTimeout(function () {
      el.classList.remove("hy-charity-toast--show");
    }, 2200);
  }

  function copyText(text) {
    text = (text || "").trim();
    if (!text) return Promise.reject();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
        document.body.removeChild(ta);
        resolve();
      } catch (e) {
        document.body.removeChild(ta);
        reject(e);
      }
    });
  }

  function maskDigits(d) {
    if (d.length <= 8) return d;
    return d.slice(0, 4) + " **** **** " + d.slice(-4);
  }

  function findCardLikeDigitSequences(text) {
    var results = [];
    var seen = new Set();
    if (!text) return results;
    var re = /\b\d{4}(?:[\s\u00a0\-]?\d{4}){2,5}\b|\b\d{13,19}\b/g;
    var m;
    while ((m = re.exec(text)) !== null) {
      var digits = m[0].replace(/\D/g, "");
      if (digits.length >= 12 && digits.length <= 19 && !seen.has(digits)) {
        seen.add(digits);
        results.push({ digits: digits, label: maskDigits(digits) });
      }
    }
    return results;
  }

  function formatPanGroups(digits) {
    var parts = [];
    for (var i = 0; i < digits.length; i += 4) {
      parts.push(digits.slice(i, i + 4));
    }
    return parts.join(" ");
  }

  var PLASTIC_BRANDS = [
    "visa",
    "mastercard",
    "uzcard",
    "humo",
    "mir",
    "unionpay",
    "generic",
  ];

  function detectCardBrand(digits) {
    if (!digits || digits.length < 4) return "generic";
    if (digits.indexOf("9860") === 0) return "humo";
    if (digits.indexOf("8600") === 0 || digits.indexOf("5614") === 0) return "uzcard";
    var f4 = parseInt(digits.slice(0, 4), 10);
    if (!isNaN(f4) && f4 >= 2200 && f4 <= 2204) return "mir";
    if (digits.charAt(0) === "4") return "visa";
    var t2 = parseInt(digits.slice(0, 2), 10);
    if (!isNaN(t2) && t2 >= 51 && t2 <= 55) return "mastercard";
    var six = parseInt(digits.slice(0, 6), 10);
    if (
      digits.charAt(0) === "2" &&
      !isNaN(six) &&
      six >= 222100 &&
      six <= 272099
    ) {
      return "mastercard";
    }
    if (digits.slice(0, 2) === "62") return "unionpay";
    return "generic";
  }

  function applyPlasticBrand(cardEl, digits) {
    if (!cardEl) return;
    var brand = digits ? detectCardBrand(digits) : "generic";
    PLASTIC_BRANDS.forEach(function (b) {
      cardEl.classList.remove("hy-plastic-card--" + b);
    });
    cardEl.classList.add("hy-plastic-card--" + brand);
  }

  function initPlasticCard() {
    var cardEl = document.getElementById("hy-plastic-card");
    var rawEl = document.getElementById("hy-payment-raw");
    var panEl = document.getElementById("hy-plastic-pan");
    var metaEl = document.getElementById("hy-plastic-meta");
    if (!rawEl || !panEl || !metaEl) return;

    var text = rawEl.value || "";
    var found = findCardLikeDigitSequences(text);
    var lines = text
      .split(/\r?\n/)
      .map(function (s) {
        return s.trim();
      })
      .filter(Boolean);

    function appendMetaLine(s) {
      var p = document.createElement("div");
      p.className = "hy-plastic-card__line";
      p.textContent = s;
      metaEl.appendChild(p);
    }

    metaEl.textContent = "";

    var copyPanBtn = document.getElementById("hy-copy-pan-digits");
    if (copyPanBtn) copyPanBtn.hidden = true;

    if (found.length > 0) {
      panEl.textContent = formatPanGroups(found[0].digits);
      var d0 = found[0].digits;
      var rest = lines.filter(function (ln) {
        var onlyDigits = ln.replace(/\D/g, "");
        if (onlyDigits === d0 && onlyDigits.length >= 12) return false;
        return true;
      });
      rest.forEach(appendMetaLine);
      if (rest.length === 0 && found.length > 1) {
        appendMetaLine("Yana " + (found.length - 1) + " ta karta (pastda)");
      }
      if (copyPanBtn) {
        copyPanBtn.hidden = false;
        copyPanBtn.addEventListener("click", function () {
          copyText(d0)
            .then(function () {
              toast("Nusxalandi");
            })
            .catch(function () {
              toast("Nusxalab bo‘lmadi");
            });
        });
      }
    } else {
      panEl.textContent = "•••• •••• •••• ••••";
      if (lines.length) {
        lines.forEach(appendMetaLine);
      } else if (text.trim()) {
        appendMetaLine(text.trim());
      } else {
        appendMetaLine("—");
      }
    }

    applyPlasticBrand(cardEl, found.length > 0 ? found[0].digits : null);
  }

  function initPaymentCopy() {
    var root = document.getElementById("hy-charity-payment");
    if (!root) return;
    var rawEl = document.getElementById("hy-payment-raw");
    var text = rawEl ? rawEl.value : "";
    var digitsWrap = document.getElementById("hy-payment-digits");

    var btnAll = document.getElementById("hy-copy-payment-all");
    if (btnAll && text) {
      btnAll.addEventListener("click", function () {
        copyText(text)
          .then(function () {
            toast("Nusxalandi");
          })
          .catch(function () {
            toast("Nusxalab bo‘lmadi");
          });
      });
    }

    if (digitsWrap && text) {
      var found = findCardLikeDigitSequences(text);
      found.forEach(function (item, i) {
        if (i === 0) return;
        var row = document.createElement("div");
        row.className = "hy-copy-row";
        var lab = document.createElement("span");
        lab.className = "hy-copy-row__label";
        lab.textContent = "Karta " + (i + 1) + ": " + item.label;
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "hy-copy-btn";
        btn.textContent = "Karta nusxasi";
        btn.addEventListener("click", function () {
          copyText(item.digits)
            .then(function () {
              toast("Nusxalandi");
            })
            .catch(function () {
              toast("Nusxalab bo‘lmadi");
            });
        });
        row.appendChild(lab);
        row.appendChild(btn);
        digitsWrap.appendChild(row);
      });
    }
  }

  function initPhoneCopy() {
    var btn = document.getElementById("hy-copy-phone");
    if (!btn) return;
    var phone = btn.getAttribute("data-phone") || "";
    btn.addEventListener("click", function () {
      var digits = phone.replace(/\D/g, "");
      var toCopy = digits.length >= 9 ? digits : phone;
      copyText(toCopy)
        .then(function () {
          toast("Nusxalandi");
        })
        .catch(function () {
          toast("Nusxalab bo‘lmadi");
        });
    });
  }

  function initComplaintCounter() {
    var ta = document.getElementById("id_complaint_message");
    var out = document.getElementById("hy-complaint-len");
    if (!ta || !out) return;
    function sync() {
      out.textContent = String(ta.value.length);
    }
    ta.addEventListener("input", sync);
    sync();
  }

  function initCharityShare() {
    var btn = document.getElementById("hy-charity-copy-link");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var url = (btn.getAttribute("data-url") || "").trim();
      if (!url) return;
      copyText(url)
        .then(function () {
          toast("Havola nusxalandi");
        })
        .catch(function () {
          toast("Nusxalab bo‘lmadi");
        });
    });
  }

  function initDetailMap() {
    var el = document.getElementById("hy-charity-detail-map");
    if (!el) return;
    // Google Maps JS offline/google-bloklangan tarmoqda ishlamaydi.
    // Xaritani majburlamaymiz: linklar orqali ochish yetarli.
    el.style.display = "none";
    var lat = parseFloat(el.getAttribute("data-lat"));
    var lng = parseFloat(el.getAttribute("data-lng"));
    if (isNaN(lat) || isNaN(lng)) return;
  }

  ready(function () {
    initPlasticCard();
    initPaymentCopy();
    initPhoneCopy();
    initCharityShare();
    initComplaintCounter();
    initDetailMap();
  });
})();
