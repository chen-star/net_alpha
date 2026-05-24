/**
 * net-alpha count-up helper (premium refresh).
 *
 * Animates the numeric digits inside any `<span class="js-countup-num">` from
 * 0 to a target on initial load and after HTMX swaps. The span's server-rendered
 * text is the final formatted value, so no-JS and reduced-motion users see the
 * correct number immediately — this only ever animates UP to that value.
 *
 * Markup contract:
 *   <span class="js-countup-num" data-to="1234.56" data-decimals="2">1,234.56</span>
 * Sign ("+"/"−"), currency symbol, and color stay on the OUTER element so this
 * helper only rewrites the digit run and never clobbers a `.text-neg` wrapper.
 */
(function () {
  function reduced() {
    try {
      return window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch (e) {
      return false;
    }
  }

  function fmt(value, decimals) {
    return value.toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }

  function animateEl(el) {
    var to = parseFloat(el.dataset.to);
    if (isNaN(to)) return;
    var decimals = parseInt(el.dataset.decimals || "0", 10);
    if (reduced()) {
      el.textContent = fmt(to, decimals);
      return;
    }
    var duration = 600;
    var start = null;
    function frame(ts) {
      if (start === null) start = ts;
      var t = Math.min((ts - start) / duration, 1);
      // easeOutCubic
      var eased = 1 - Math.pow(1 - t, 3);
      el.textContent = fmt(to * eased, decimals);
      if (t < 1) requestAnimationFrame(frame);
      else el.textContent = fmt(to, decimals);
    }
    requestAnimationFrame(frame);
  }

  function scan(root) {
    var nodes = (root || document).querySelectorAll(".js-countup-num");
    for (var i = 0; i < nodes.length; i++) animateEl(nodes[i]);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { scan(document); });
  } else {
    scan(document);
  }

  // Re-fire after an HTMX swap (e.g. the /portfolio/kpis fragment).
  document.body.addEventListener("htmx:afterSwap", function (evt) {
    if (evt.detail && evt.detail.target) scan(evt.detail.target);
  });
})();
