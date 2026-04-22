(function () {
  "use strict";

  if (window.__FNU_CHATBOT_LOADED__) return;
  window.__FNU_CHATBOT_LOADED__ = true;

  var scriptEl =
    document.currentScript ||
    (function () {
      var all = document.getElementsByTagName("script");
      return all[all.length - 1];
    })();

  var src = scriptEl && scriptEl.src ? scriptEl.src : window.location.href;
  var origin;
  try {
    origin = new URL(src).origin;
  } catch (e) {
    origin = window.location.origin;
  }

  var iframeUrl = origin + "/embed/chatbot";

  var launcher = document.createElement("button");
  launcher.type = "button";
  launcher.setAttribute("aria-label", "Open FNU chatbot");
  launcher.style.cssText = [
    "position:fixed",
    "bottom:24px",
    "right:24px",
    "width:56px",
    "height:56px",
    "border-radius:50%",
    "background:#003A70",
    "color:#fff",
    "border:none",
    "box-shadow:0 6px 16px rgba(0,0,0,0.2)",
    "cursor:pointer",
    "z-index:2147483000",
    "display:flex",
    "align-items:center",
    "justify-content:center",
  ].join(";");
  launcher.innerHTML =
    '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>';

  var frameWrap = document.createElement("div");
  frameWrap.style.cssText = [
    "position:fixed",
    "bottom:96px",
    "right:24px",
    "width:min(360px,calc(100vw - 32px))",
    "height:min(520px,calc(100vh - 128px))",
    "border-radius:12px",
    "overflow:hidden",
    "box-shadow:0 12px 32px rgba(0,0,0,0.25)",
    "z-index:2147483000",
    "display:none",
    "background:#fff",
  ].join(";");

  var iframe = document.createElement("iframe");
  iframe.src = iframeUrl;
  iframe.title = "FNU chatbot";
  iframe.setAttribute("loading", "lazy");
  iframe.style.cssText = "width:100%;height:100%;border:0";
  frameWrap.appendChild(iframe);

  var open = false;
  launcher.addEventListener("click", function () {
    open = !open;
    frameWrap.style.display = open ? "block" : "none";
    launcher.setAttribute(
      "aria-label",
      open ? "Close FNU chatbot" : "Open FNU chatbot",
    );
  });

  function mount() {
    document.body.appendChild(frameWrap);
    document.body.appendChild(launcher);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
