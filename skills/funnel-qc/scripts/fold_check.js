/* Above-the-fold measurement — paste this whole expression into the browser tool that
   evaluates JS on the page (Claude_Browser javascript_tool, chrome-devtools
   evaluate_script, playwright browser_evaluate). It returns a JSON verdict you can drop
   straight into the QA packet.

   Run it once per page per viewport, AFTER setting the viewport and loading the page
   fresh. It does not modify anything permanently — the reveal-forcing it does is undone
   by the next page load.

   Validated 2026-07-27 against Scalability vsl-funnel: reproduced the A page's 58px CTA
   cut at 390x664 and confirmed the B fix (63px spare), while correctly ignoring the
   display:none desktop CTA. */

(() => {
  // A zero-sized viewport means the page never laid out. Every rect would read 0 and the
  // whole run would report a cheerful, meaningless PASS — so refuse to measure instead.
  if (!innerWidth || !innerHeight) return { error: `bad viewport ${innerWidth}x${innerHeight}` };

  // Scroll-reveal elements start at opacity:0 behind an IntersectionObserver. Anything
  // below the fold never gets observed, so it can measure at the wrong height (or read as
  // hidden). Force them in before measuring. Class names cover the variants these
  // templates have shipped.
  document.querySelectorAll('.reveal, .io').forEach(el => {
    el.classList.add('in', 'is-visible', 'visible');
    el.style.opacity = '1';
    el.style.transform = 'none';
  });

  // These templates ship BOTH a desktop `.hero-copy .cta-block` and a separate
  // `.cta-mobile`, with one display:none per breakpoint. Measuring the hidden one is the
  // classic false pass: it reports bottom 0, i.e. "comfortably above the fold."
  const shown = el => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return false;
    const cs = getComputedStyle(el);
    return cs.display !== 'none' && cs.visibility !== 'hidden';
  };
  const pick = sel => [...document.querySelectorAll(sel)].find(shown) || null;

  // Severity drives the verdict: only the primary CTA blocks. Widen a selector list if a
  // client's hero uses different class names — but keep the CTA list ordered
  // mobile-variant-first so the visible one is found before any fallback.
  const targets = [
    ['headline',    'high',     '.hero-wrap h1, .hero-copy h1, h1'],
    ['video/form',  'high',     '.hero-media, .video-shell, .hero-form, form'],
    ['primary CTA', 'BLOCKING', '.cta-mobile .cf-cta, .hero-copy .cta-block .cf-cta, .hero-wrap .cf-cta, .hero-wrap a.btn'],
    ['trust strip', 'cosmetic', '.logo-strip, .logos, .trust'],
  ];

  // Booking pages have no hero CTA button — the calendar/application embed IS the CTA.
  // For an embed the meaningful check is not "bottom above fold" (a tall calendar never
  // is) but "does it visibly START above the fold": at least 80px of it in view.
  const EMBED_FALLBACK = '#cal-widget, .calendly-inline-widget, .cal-typeform, .cal-embed, .form-shell';

  const rows = targets.map(([element, severity, sel]) => {
    let el = pick(sel);
    let embedMode = false;
    if (!el && severity === 'BLOCKING') { el = pick(EMBED_FALLBACK); embedMode = !!el; }
    if (!el) return { element, severity, status: 'ABSENT at this viewport', selector: null };
    const rect = el.getBoundingClientRect();
    if (embedMode) {
      const visible = Math.round(innerHeight - rect.top);
      return {
        element: element + ' (booking embed)', severity,
        status: visible >= 80 ? `PASS (embed starts ${visible}px above fold)`
                              : `FAIL (embed starts ${visible < 0 ? Math.abs(visible) + 'px below' : 'only ' + visible + 'px above'} fold)`,
        bottom: Math.round(rect.top), fold: innerHeight,
        selector: el.className || el.tagName,
      };
    }
    const bottom = Math.round(rect.bottom);
    const spare = innerHeight - bottom;
    return {
      element, severity,
      status: spare >= 0 ? `PASS (${spare}px spare)` : `FAIL (cut by ${-spare}px)`,
      bottom, fold: innerHeight,
      selector: el.className || el.tagName,
    };
  });

  // Pass only on an explicit PASS. An ABSENT CTA is not a pass — either the selector list
  // is wrong for this client or the hero has no CTA, and both need a human to look.
  const cta = rows.find(r => r.severity === 'BLOCKING');
  const pass = cta && cta.status.startsWith('PASS');
  return {
    viewport: `${innerWidth}x${innerHeight}`,
    url: location.pathname,
    gate: pass ? 'PASS' : `FAIL — blocking (${cta ? cta.status : 'no CTA row'})`,
    rows,
  };
})()
