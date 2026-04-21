/**
 * MYFEEL shell: HTMX top progress, optional focus trap for modals.
 */
(function () {
  "use strict";

  var root = document.documentElement;
  var progressEl = document.getElementById("mf-htmx-progress");
  var progressResetTimer;

  function setProgress(scale, opacity) {
    if (!progressEl) return;
    progressEl.style.transform = "scaleX(" + scale + ")";
    if (typeof opacity === "number") progressEl.style.opacity = String(opacity);
  }

  function onBeforeRequest() {
    root.classList.add("mf-htmx-loading");
    clearTimeout(progressResetTimer);
    setProgress(0.06, 1);
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        setProgress(0.42, 1);
      });
    });
  }

  function onAfterRequest() {
    setProgress(1, 1);
    root.classList.remove("mf-htmx-loading");
    progressResetTimer = setTimeout(function () {
      setProgress(0, 0);
    }, 280);
  }

  document.body.addEventListener("htmx:beforeRequest", onBeforeRequest);
  document.body.addEventListener("htmx:afterRequest", onAfterRequest);
  document.body.addEventListener("htmx:error", onAfterRequest);

  // Logout confirmation (covers all logout links)
  document.addEventListener("click", function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a) return;
    if (a.getAttribute("href") !== "/logout/" && a.getAttribute("href") !== "logout" && !/\/logout\/?$/.test(a.getAttribute("href") || "")) {
      return;
    }
    var ok = window.confirm("Chiqishni xohlaysizmi?");
    if (!ok) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, { capture: true });

  /**
   * Call when opening a modal: MYFEEL.trapFocus(modalElement)
   * Returns disposer function to remove listeners and restore focus.
   */
  var MYFEEL = window.MYFEEL || {};
  MYFEEL.trapFocus = function trapFocus(container) {
    if (!container || !container.querySelector) {
      return function () {};
    }
    var previous = document.activeElement;
    var sel =
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
    function getFocusable() {
      return Array.prototype.slice.call(container.querySelectorAll(sel)).filter(function (el) {
        return el.offsetWidth > 0 || el.offsetHeight > 0 || el === document.activeElement;
      });
    }
    function onKeydown(e) {
      if (e.key !== "Tab") return;
      var nodes = getFocusable();
      if (nodes.length === 0) return;
      var first = nodes[0];
      var last = nodes[nodes.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first || !container.contains(document.activeElement)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last || !container.contains(document.activeElement)) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    container.addEventListener("keydown", onKeydown);
    var toFocus = getFocusable()[0];
    if (toFocus) toFocus.focus();
    return function dispose() {
      container.removeEventListener("keydown", onKeydown);
      if (previous && typeof previous.focus === "function") {
        try {
          previous.focus();
        } catch (_) {}
      }
    };
  };
  window.MYFEEL = MYFEEL;

  document.addEventListener("alpine:init", function () {
    if (typeof Alpine === "undefined" || !Alpine.data) return;
    Alpine.data("mfModal", function (initialOpen) {
      return {
        open: !!initialOpen,
        _untrap: null,
        init: function () {
          var self = this;
          this.$watch("open", function (isOpen) {
            if (self._untrap) {
              self._untrap();
              self._untrap = null;
            }
            if (!isOpen) return;
            requestAnimationFrame(function () {
              var el = self.$refs.mfModalRoot;
              if (el && window.MYFEEL && window.MYFEEL.trapFocus) {
                self._untrap = window.MYFEEL.trapFocus(el);
              }
            });
          });
        },
        toggle: function () {
          this.open = !this.open;
        },
        show: function () {
          this.open = true;
        },
        hide: function () {
          this.open = false;
        },
      };
    });
  });
})();
