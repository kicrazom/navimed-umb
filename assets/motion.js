/* NaviMed-UMB — tasteful scroll-reveal. Self-hosted, no deps.
   Reduced-motion safe (bails out) and no-JS safe (nothing is hidden unless
   this script runs and adds .js-motion to <html> before first paint). */
(function () {
  var root = document.documentElement;

  // Honour prefers-reduced-motion: no reveal at all, content stays visible.
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  // Runs in <head> (synchronous) so the hide rule applies from first paint → no flash.
  root.classList.add('js-motion');

  function init() {
    var nodes = document.querySelectorAll('main .wrap > *');
    var targets = [];
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (el.classList.contains('results-wide')) continue; // uses transform for layout
      targets.push(el);
    }
    // No IntersectionObserver → give up hiding, show everything.
    if (!('IntersectionObserver' in window) || !targets.length) {
      root.classList.remove('js-motion');
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      for (var k = 0; k < entries.length; k++) {
        if (entries[k].isIntersecting) {
          entries[k].target.classList.add('is-visible');
          io.unobserve(entries[k].target);
        }
      }
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    for (var j = 0; j < targets.length; j++) io.observe(targets[j]);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
