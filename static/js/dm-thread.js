/**
 * DM suhbat: qalqib menyu, emoji, ovozli xabar, polling pitnachkalar.
 */
(function () {
  "use strict";

  var EMOJIS = Array.from(
    "😀😃😄😁😅😂🤣😊😍🥰😘😉🙂😎😢😭😤🙏👍👎👏💪🔥❤️✨🎉💯✅❌💬📝👋🤝✌️👌🙌💋🌹🎂🎁⭐🌈☀️🌙😳🥺🤔😴😇🤗🤩😐😬😱😨🤯💀👻🤖💩🦄🐶🐱📷🎤🎵📎💡❓🆗🇺🇿🫶🤍💔🥳🙈👀💅🧠🍀🎯🏆😡🤬😮🫠🤒🤧👽🎮🕺💃🧋☕🍕🥐🍰🤝🫡🥶🥵🪄✍️👉👈☝️🤙💼🕐📍🔔🤓🧐🤤😵🥱🤮🙃😦😧😨🤐💜🖤🧡💚💙⚠️🎊🌸🤳🫠"
  );

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function resetPopoverPosition(pop) {
    if (!pop) return;
    pop.style.position = "";
    pop.style.right = "";
    pop.style.bottom = "";
    pop.style.left = "";
    pop.style.top = "";
    pop.style.zIndex = "";
  }

  function closeAllPopovers(except) {
    document.querySelectorAll(".hy-dm-msg__popover").forEach(function (p) {
      if (p !== except) {
        p.hidden = true;
        resetPopoverPosition(p);
        var m = p.closest(".hy-dm-msg__toolbar");
        if (m) {
          var b = m.querySelector(".hy-dm-msg__more");
          if (b) b.setAttribute("aria-expanded", "false");
        }
      }
    });
  }

  function updateTicks(peerReadId) {
    if (typeof peerReadId !== "number" && typeof peerReadId !== "string") return;
    var pr = parseInt(peerReadId, 10);
    if (isNaN(pr)) return;
    document.querySelectorAll(".hy-dm-msg--out[data-dm-msg-id]").forEach(function (row) {
      var id = parseInt(row.getAttribute("data-dm-msg-id"), 10);
      var ticks = row.querySelector(".hy-dm-msg__ticks");
      if (!ticks || isNaN(id)) return;
      var read = id <= pr;
      ticks.classList.toggle("hy-dm-msg__ticks--read", read);
      ticks.classList.toggle("hy-dm-msg__ticks--delivered", !read);
      ticks.setAttribute("title", read ? "O‘qilgan" : "Yetkazildi");
      ticks.setAttribute("aria-label", read ? "O‘qilgan" : "Yetkazildi");
      var second = ticks.querySelector(".hy-dm-msg__tick--2");
      if (second) second.hidden = !read;
    });
  }

  function initEmojiPanel() {
    var panel = $("#hy-dm-emoji-panel");
    var grid = $("#hy-dm-emoji-grid");
    var ta = $("#hy-dm-body");
    var toggle = $("#hy-dm-emoji-toggle");
    if (!panel || !grid || !ta) return;

    EMOJIS.forEach(function (ch) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "hy-dm-emoji-cell";
      btn.textContent = ch;
      btn.addEventListener("click", function () {
        var start = ta.selectionStart;
        var end = ta.selectionEnd;
        var v = ta.value || "";
        ta.value = v.slice(0, start) + ch + v.slice(end);
        ta.selectionStart = ta.selectionEnd = start + ch.length;
        ta.focus();
        panel.hidden = true;
      });
      grid.appendChild(btn);
    });

    if (toggle) {
      toggle.addEventListener("click", function (e) {
        e.stopPropagation();
        panel.hidden = !panel.hidden;
        closeAllPopovers();
      });
    }

    document.addEventListener("click", function () {
      panel.hidden = true;
    });
    panel.addEventListener("click", function (e) {
      e.stopPropagation();
    });
  }

  function initPopovers() {
    document.addEventListener("click", function (e) {
      var t = e.target;
      var more = t.closest && t.closest(".hy-dm-msg__more");
      var insidePop = t.closest && t.closest(".hy-dm-msg__popover");
      if (more) {
        e.preventDefault();
        e.stopPropagation();
        var toolbar = more.closest(".hy-dm-msg__toolbar");
        var pop = toolbar && toolbar.querySelector(".hy-dm-msg__popover");
        if (!pop) return;
        var open = pop.hidden;
        closeAllPopovers(open ? pop : null);
        var emoji = $("#hy-dm-emoji-panel");
        if (emoji) emoji.hidden = true;
        if (open) {
          pop.hidden = false;
          var r = more.getBoundingClientRect();
          pop.style.position = "fixed";
          pop.style.left = "auto";
          pop.style.top = "auto";
          pop.style.right = Math.max(8, window.innerWidth - r.right) + "px";
          pop.style.bottom = window.innerHeight - r.top + 8 + "px";
          pop.style.zIndex = "200";
          more.setAttribute("aria-expanded", "true");
        } else {
          pop.hidden = true;
          resetPopoverPosition(pop);
          more.setAttribute("aria-expanded", "false");
        }
        return;
      }
      if (insidePop) {
        e.stopPropagation();
        return;
      }
      closeAllPopovers();
    });
  }

  function initConfirmDeletes() {
    document.addEventListener("submit", function (e) {
      var f = e.target;
      if (f && f.matches && f.matches("form[data-dm-delete-scope]")) {
        var scopeIn = f.querySelector(".hy-dm-msg__delete-scope");
        var isOwn = false;
        var row = f.closest && f.closest(".hy-dm-msg");
        if (row && row.classList) isOwn = row.classList.contains("hy-dm-msg--out");
        var msg = isOwn
          ? "Xabar hamma uchun o‘chirilsinmi?\nOK = hamma uchun, Cancel = faqat siz uchun."
          : "Bu xabar faqat siz uchun yashiriladi. Davom etilsinmi?";
        if (isOwn) {
          var all = window.confirm(msg);
          if (scopeIn) scopeIn.value = all ? "all" : "me";
        } else {
          if (!window.confirm(msg)) {
            e.preventDefault();
            return;
          }
          if (scopeIn) scopeIn.value = "me";
        }
      }
    });
  }

  function initVoice() {
    var btn = $("#hy-dm-voice-btn");
    var form = $("#hy-dm-compose-form");
    var voiceIn = $("#hy-dm-voice-file");
    var voiceFlag = $("#hy-dm-voice-flag");
    var fileIn = $("#hy-dm-file");
    var hint = $("#hy-dm-file-hint");
    if (!btn || !form || !voiceIn) return;

    var recorder = null;
    var chunks = [];

    function clearVoiceUi() {
      btn.classList.remove("is-recording");
      recorder = null;
      chunks = [];
    }

    if (fileIn) {
      fileIn.addEventListener("change", function () {
        if (fileIn.files && fileIn.files[0]) {
          voiceIn.value = "";
          if (voiceFlag) voiceFlag.value = "0";
        }
      });
    }

    btn.addEventListener("click", function () {
      if (!navigator.mediaDevices || !window.MediaRecorder) {
        window.alert("Brauzeringiz ovozli xabarni qo‘llab-quvvatlamaydi.");
        return;
      }
      if (recorder && recorder.state === "recording") {
        recorder.stop();
        return;
      }
      navigator.mediaDevices
        .getUserMedia({ audio: true })
        .then(function (stream) {
          chunks = [];
          var mime = "audio/webm";
          if (!MediaRecorder.isTypeSupported(mime)) mime = "";
          recorder = mime
            ? new MediaRecorder(stream, { mimeType: mime })
            : new MediaRecorder(stream);
          recorder.ondataavailable = function (ev) {
            if (ev.data && ev.data.size) chunks.push(ev.data);
          };
          recorder.onstop = function () {
            stream.getTracks().forEach(function (tr) {
              tr.stop();
            });
            var blob = new Blob(chunks, {
              type: recorder.mimeType || "audio/webm",
            });
            if (!blob.size) {
              clearVoiceUi();
              return;
            }
            var name = "voice-" + Date.now() + ".webm";
            var file = new File([blob], name, { type: blob.type });
            var dt = new DataTransfer();
            dt.items.add(file);
            voiceIn.files = dt.files;
            if (voiceFlag) voiceFlag.value = "1";
            if (fileIn) fileIn.value = "";
            if (hint) {
              hint.hidden = false;
              hint.textContent = "Ovozli xabar yuborilmoqda…";
            }
            if (typeof form.requestSubmit === "function") form.requestSubmit();
            else form.submit();
            clearVoiceUi();
          };
          btn.classList.add("is-recording");
          recorder.start();
        })
        .catch(function () {
          window.alert("Mikrofonga ruxsat berilmadi.");
          clearVoiceUi();
        });
    });
  }

  function initReplyBar() {
    var hid = $("#hy-dm-reply-to");
    var bar = $("#hy-dm-reply-bar");
    var whoEl = $("#hy-dm-reply-bar-who");
    var snipEl = $("#hy-dm-reply-bar-snip");
    var cancel = $("#hy-dm-reply-cancel");
    var ta = $("#hy-dm-body");
    if (!hid || !bar) return;

    function clearReply() {
      hid.value = "";
      bar.hidden = true;
      if (whoEl) whoEl.textContent = "";
      if (snipEl) snipEl.textContent = "";
    }

    // Self-heal: agar hidden id bo‘sh bo‘lsa, panel ko‘rinmasin
    if (!String(hid.value || "").trim()) {
      bar.hidden = true;
    }

    document.addEventListener("click", function (e) {
      var b = e.target && e.target.closest && e.target.closest("[data-dm-reply]");
      if (!b) return;
      e.preventDefault();
      e.stopPropagation();
      var id = b.getAttribute("data-dm-reply") || "";
      var author = b.getAttribute("data-dm-reply-author") || "";
      var snip = b.getAttribute("data-dm-reply-snippet") || "";
      hid.value = id;
      if (whoEl) whoEl.textContent = author;
      if (snipEl) snipEl.textContent = snip;
      bar.hidden = !id;
      closeAllPopovers();
      var emoji = $("#hy-dm-emoji-panel");
      if (emoji) emoji.hidden = true;
      if (ta) ta.focus();
    });

    if (cancel) {
      cancel.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        clearReply();
        if (ta) ta.focus();
      });
    }

    // Xabar yuborilganda reply qotib qolmasin
    var form = $("#hy-dm-compose-form");
    if (form) {
      form.addEventListener("submit", function () {
        clearReply();
      });
    }
  }

  function initForward() {
    document.addEventListener("click", function (e) {
      var b = e.target && e.target.closest && e.target.closest("[data-dm-forward]");
      if (!b) return;
      e.preventDefault();
      e.stopPropagation();
      var id = b.getAttribute("data-dm-forward") || "";
      if (!id) return;
      var uname = window.prompt("Kimga yuboramiz? (username)");
      if (!uname) return;
      uname = String(uname || "").trim().replace(/^@+/, "");
      if (!uname) return;
      var row = b.closest(".hy-dm-msg");
      var pop = b.closest(".hy-dm-msg__popover");
      closeAllPopovers();
      if (!row) return;

      // POST (same thread): action=forward, message_id, to_username
      var form = document.createElement("form");
      form.method = "post";
      form.action = window.location.href;
      form.style.display = "none";

      var csrf = document.querySelector("input[name=csrfmiddlewaretoken]");
      if (csrf) {
        var ci = document.createElement("input");
        ci.type = "hidden";
        ci.name = "csrfmiddlewaretoken";
        ci.value = csrf.value;
        form.appendChild(ci);
      }

      function add(name, val) {
        var i = document.createElement("input");
        i.type = "hidden";
        i.name = name;
        i.value = val;
        form.appendChild(i);
      }
      add("action", "forward");
      add("message_id", id);
      add("to_username", uname);
      document.body.appendChild(form);
      form.submit();
    });
  }

  function initCompose() {
    var form = $("#hy-dm-compose-form");
    var ta = $("#hy-dm-body");
    var fileIn = $("#hy-dm-file");
    var voiceIn = $("#hy-dm-voice-file");
    if (!form || !ta) return;
    form.addEventListener("submit", function (e) {
      var f = fileIn && fileIn.files && fileIn.files[0];
      var v = voiceIn && voiceIn.files && voiceIn.files[0];
      if (!String(ta.value || "").trim() && !f && !v) {
        e.preventDefault();
        ta.focus();
      }
    });
  }

  function initPoll() {
    var box = $("#hy-dm-bubbles");
    if (!box || !window.HY_DM_POLL_URL) return;
    var lastId = parseInt(window.HY_DM_LAST_ID || "0", 10) || 0;

    function poll() {
      if (lastId <= 0) return;
      fetch(
        window.HY_DM_POLL_URL +
          "?after=" +
          encodeURIComponent(String(lastId)),
        {
          headers: { "X-Requested-With": "XMLHttpRequest" },
          credentials: "same-origin",
        }
      )
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (!data || !data.ok) return;
          if (typeof data.peer_read_id === "number") {
            updateTicks(data.peer_read_id);
          }
          if (data.fragments && data.fragments.length) {
            data.fragments.forEach(function (html) {
              box.insertAdjacentHTML("beforeend", html);
            });
          }
          if (typeof data.last_id === "number" && data.last_id > lastId) {
            lastId = data.last_id;
          }
          box.scrollTop = box.scrollHeight;
        })
        .catch(function () {});
    }

    setInterval(poll, 10000);
  }

  function initScroll() {
    var box = $("#hy-dm-bubbles");
    if (!box) return;
    function toBottom() {
      box.scrollTop = box.scrollHeight;
    }
    toBottom();
    requestAnimationFrame(function () {
      requestAnimationFrame(toBottom);
    });
    setTimeout(toBottom, 180);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initScroll();
    initEmojiPanel();
    initPopovers();
    initReplyBar();
    initConfirmDeletes();
    initForward();
    initVoice();
    initCompose();
    initPoll();
  });

  // BFCache / back-forward: DOMContentLoaded qayta ishlamasligi mumkin
  window.addEventListener("pageshow", function () {
    initScroll();
  });
})();
