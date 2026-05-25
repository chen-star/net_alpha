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
    // Pin to en-US so the animated digits match the server-rendered text
    // (Python "{:,.2f}"); `undefined` uses the browser locale and could
    // diverge on a non-US browser (e.g. "1.234,56").
    return value.toLocaleString("en-US", {
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

  // The Overview dashboard lazy-loads #portfolio-body once on page load (its
  // hx-trigger="load") and then RE-swaps that same target on every toolbar
  // (period/account) change. Replaying the 0→value count-up and the staggered
  // reveal on a mere filter change is visually noisy, so we only animate the
  // INITIAL entrance. The moment the user touches the Overview toolbar we latch
  // `body.na-overview-filtered`, which (a) makes CSS suppress the row reveal
  // re-entrance and (b) makes the htmx:afterSwap handler below skip the
  // count-up scan so the spans just show their final server-rendered text.
  //
  // We key off the user's `change` event rather than counting swaps for two
  // reasons: a single body load fires htmx:afterSwap twice (main swap + an
  // out-of-band #portfolio-subline swap), and the new #overview-rows is not
  // reliably present in #portfolio-body at afterSwap time (htmx settle / the
  // fragment cache materialize it slightly later) — so neither a swap counter
  // nor a DOM strip at afterSwap is dependable. A body class set BEFORE the
  // swap is, because CSS is re-evaluated whenever the rows are finally styled.
  document.body.addEventListener("change", function (evt) {
    var t = evt.target;
    if (t && t.closest && t.closest('form[hx-target="#portfolio-body"]')) {
      document.body.classList.add("na-overview-filtered");
    }
  }, true);

  document.body.addEventListener("htmx:afterSwap", function (evt) {
    var target = evt.detail && evt.detail.target;
    if (!target) return;
    if (target.id === "portfolio-body" &&
        document.body.classList.contains("na-overview-filtered")) {
      return;
    }
    scan(target);
  });
})();
