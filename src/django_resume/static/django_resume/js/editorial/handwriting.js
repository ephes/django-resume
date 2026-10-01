// Self-writing handwriting labels of the editorial theme.
(function () {
  "use strict";
  var root = document.documentElement;
  var failed = false, io;

  function failOpen() {
    failed = true;
    root.classList.remove("js-hw");
    if (io) io.disconnect();
  }

  function guarded(callback) {
    return function () {
      if (failed) return;
      try { return callback.apply(this, arguments); }
      catch (error) { failOpen(); }
    };
  }

  try {
    var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !("IntersectionObserver" in window)) return;

    // Brisk but not racing. The clamp makes LONG labels write at a higher pace
    // (their time is capped) and SHORT labels a touch slower (min time), so long
    // words don't drag relative to short ones.
    var SPEED = 4800;   // units/second for mid-length labels (lower = slower)
    var CAP = 1.7;      // max seconds for one label (long words -> higher pace)
    var MINW = 0.55;    // min seconds for one label (short words -> calmer)
    var OVER = 0.82;    // stroke overlap within a label
    var GAP = 0.08;     // pause between labels (seconds)
    var replayCooldown = parseInt(root.getAttribute("data-hw-replay-cooldown"), 10);
    if (!isFinite(replayCooldown) || replayCooldown < 0) replayCooldown = 30000;

    var svgs = [].slice.call(document.querySelectorAll(".hw-svg"));
    svgs.forEach(function (svg, i) {
      svg.querySelectorAll(".hw-pen").forEach(function (p) {
        var length = p.getTotalLength();
        if (!isFinite(length) || length < 0) throw new Error("Invalid handwriting stroke length");
        p.style.setProperty("--L", length);
      });
      svg.classList.add("hw-armed");                  // hidden until written
      svg._idx = i;                                   // DOM order
      svg._rail = !!svg.closest(".cv-rail-label");     // rail labels go after the lead
    });

    function schedule(svg) {
      // distribute durations over the label's pens; return total time to written.
      var pens = [].slice.call(svg.querySelectorAll(".hw-pen"));
      var lens = pens.map(function (p) { return parseFloat(p.style.getPropertyValue("--L")) || 0; });
      var total = lens.reduce(function (a, b) { return a + b; }, 0) || 1;
      var target = Math.min(CAP, Math.max(MINW, total / SPEED));
      var off = 0, end = 0;
      pens.forEach(function (p, i) {
        // Single-point skeletons have no length to reveal. Keep their final
        // state without delaying or disabling the remaining real strokes.
        if (lens[i] === 0) {
          p.style.animation = "none";
          return;
        }
        var d = (lens[i] / total) * target / OVER;
        p.style.animationDuration = d + "s";
        p.style.animationDelay = off + "s";
        end = off + d;
        off += d * OVER;
      });
      return end;
    }

    // lead (non-rail) labels first, then rail labels; ties by DOM order.
    function order(list) {
      return list.slice().sort(function (a, b) {
        return ((a._rail ? 1 : 0) - (b._rail ? 1 : 0)) || (a._idx - b._idx);
      });
    }

    var queue = [], playing = false, run = 0, lastRunAt = Date.now();

    function pump() {
      if (playing || !queue.length) return;
      playing = true;
      var token = run;
      var svg = queue.shift();
      lastRunAt = Date.now();
      svg.classList.remove("hw-go");        // restart even if it already wrote
      svg.querySelectorAll(".hw-pen").forEach(function (p) { p.style.animation = "none"; });
      svg.getBoundingClientRect();          // force reflow (SVG has no offsetWidth)
      svg.querySelectorAll(".hw-pen").forEach(function (p) { p.style.animation = ""; });
      var t = schedule(svg);
      svg.classList.add("hw-go");
      setTimeout(guarded(function () {
        if (token !== run) return;     // a replay superseded this sequence
        playing = false;
        pump();
      }), (t + GAP) * 1000);
    }

    // First viewing: animate each label once as it scrolls into view.
    var seen = new Set();
    io = new IntersectionObserver(guarded(function (entries) {
      var batch = entries.filter(function (e) { return e.isIntersecting && !seen.has(e.target); });
      if (!batch.length) return;
      batch.forEach(function (e) { seen.add(e.target); io.unobserve(e.target); });
      order(batch.map(function (e) { return e.target; })).forEach(function (s) { queue.push(s); });
      pump();
    }), { threshold: 0.5 });
    svgs.forEach(function (s) { io.observe(s); });

    function inView(svg) {
      var r = svg.getBoundingClientRect();
      var vh = window.innerHeight || document.documentElement.clientHeight;
      return r.bottom > 0 && r.top < vh;
    }

    function replayVisible() {
      if (Date.now() - lastRunAt < replayCooldown) return false;

      var visible = order(svgs.filter(inView));
      if (!visible.length) return false;

      run++;                              // cancel any in-flight sequence
      playing = false;
      queue = visible;
      visible.forEach(function (s) { s.classList.remove("hw-go"); });
      pump();
      return true;
    }

    var armedForTopReplay = false;
    addEventListener("scroll", guarded(function () {
      var y = window.scrollY || document.documentElement.scrollTop || 0;
      var vh = window.innerHeight || document.documentElement.clientHeight || 800;

      if (y > vh * 0.6) {
        armedForTopReplay = true;
      } else if (y <= 4 && armedForTopReplay) {
        armedForTopReplay = false;
        replayVisible();
      }
    }), { passive: true });

    var wasHidden = false;
    document.addEventListener("visibilitychange", guarded(function () {
      if (document.visibilityState === "hidden") {
        wasHidden = true;
      } else if (document.visibilityState === "visible" && wasHidden) {
        wasHidden = false;
        replayVisible();
      }
    }));
    // Keep the default written state until measurement and all setup succeeded.
    // A missing/blocked script never hides labels; runtime failures restore ink.
    root.classList.add("js-hw");
  } catch (error) {
    failOpen();
  }
})();
