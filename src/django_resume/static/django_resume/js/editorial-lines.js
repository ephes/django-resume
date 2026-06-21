(() => {
  const ALL = ".editorial-sheet,.cv-header,.cv-header-aside,.cv-aside,.cv-rail-body,.timeline-entry";
  const DIVIDERS = ".cv-rail-body > section + section,.cv-aside > .cv-rail + .cv-rail .cv-rail-body > :first-child";
  const VERTICAL = ".editorial-sheet,.cv-header-aside,.cv-aside,.cv-rail-body";
  const OUTER = ".editorial-sheet";
  const TIMING = { innerDelay: 700, innerStep: 560, hPass: 0.45, hStep: 12, batch: 80 };
  const delays = new WeakMap();
  let batch = [];
  let batchTimer = null;

  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const clamp = (min, value, max) => Math.min(Math.max(value, min), max);
  const top = (node) => node.getBoundingClientRect().top + window.scrollY;
  const duration = (node) => parseInt(node.style.getPropertyValue("--line-draw-vertical-local"), 10) || 1600;
  const fail = (error) => {
    document.documentElement.classList.remove("js-lines");
    if (error) console.error(error);
  };

  window.cvLinesFail = fail;

  function draw(node, delay = 0) {
    node.classList.add("cv-line-scheduled");
    delays.set(node, delay);
    window.setTimeout(() => node.classList.add("cv-line-drawn"), delay);
  }

  function startX(node) {
    const rect = node.getBoundingClientRect();

    if (node.classList.contains("cv-rail-divider")) return rect.left;
    if (node.matches(".cv-header")) return (document.querySelector(".cv-header-aside") || node).getBoundingClientRect().left;
    return rect.right;
  }

  function groupsByTop(nodes) {
    return nodes.sort((a, b) => top(a) - top(b)).reduce((groups, node) => {
      const group = groups[groups.length - 1];

      if (!group || Math.abs(group.top - top(node)) > 36) groups.push({ top: top(node), nodes: [node] });
      else group.nodes.push(node);

      return groups;
    }, []);
  }

  function nearestVertical(node, plans) {
    const x = startX(node);
    const y = top(node);

    return plans.reduce((best, plan) => {
      if (plan.node.matches(OUTER)) return best;

      const rect = plan.node.getBoundingClientRect();
      const y1 = top(plan.node);
      const yGap = y < y1 ? y1 - y : Math.max(y - y1 - rect.height, 0);
      const score = Math.abs(rect.left - x) + yGap;

      return !best || score < best.score ? { score, ...plan } : best;
    }, null);
  }

  function schedule(nodes) {
    const pending = nodes.filter((node) => !node.classList.contains("cv-line-drawn") && !node.classList.contains("cv-line-scheduled"));
    const verticals = pending.filter((node) => node.matches(VERTICAL));
    const horizontals = pending.filter((node) => !node.matches(VERTICAL));

    pending.filter((node) => node.matches(OUTER)).forEach((node) => draw(node));
    groupsByTop(verticals.filter((node) => !node.matches(OUTER))).forEach((group, index) => {
      group.nodes.forEach((node) => draw(node, TIMING.innerDelay + index * TIMING.innerStep));
    });

    const plans = $$(VERTICAL).filter((node) => delays.has(node)).map((node) => ({ node, delay: delays.get(node) }));

    horizontals.sort((a, b) => top(a) - top(b)).forEach((node, index) => {
      const match = nearestVertical(node, plans);
      let delay = TIMING.innerDelay + index * TIMING.hStep;

      if (match) {
        const rect = match.node.getBoundingClientRect();
        const progress = clamp(0, (top(node) - top(match.node)) / Math.max(rect.height, 1), 1);
        delay = match.delay + Math.round(duration(match.node) * progress * TIMING.hPass) + index * TIMING.hStep;
      }

      draw(node, delay);
    });
  }

  function queue(node) {
    batch.push(node);

    if (batchTimer) return;

    batchTimer = window.setTimeout(() => {
      const nodes = batch;
      batch = [];
      batchTimer = null;
      schedule(nodes);
    }, TIMING.batch);
  }

  function init() {
    const nodes = [...$$(ALL), ...$$(DIVIDERS)];

    $$(DIVIDERS).forEach((node) => node.classList.add("cv-rail-divider"));
    nodes.filter((node) => node.matches(VERTICAL)).forEach((node) => {
      node.style.setProperty("--line-draw-vertical-local", `${clamp(1600, Math.round(node.getBoundingClientRect().height * 6), 12000)}ms`);
    });

    if ((window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) || !("IntersectionObserver" in window)) {
      nodes.forEach((node) => node.classList.add("cv-line-drawn"));
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        queue(entry.target);
        observer.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -10% 0px", threshold: 0.04 });

    nodes.forEach((node) => observer.observe(node));
  }

  function ready() {
    try {
      init();
    } catch (error) {
      fail(error);
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ready, { once: true });
  else ready();
})();
