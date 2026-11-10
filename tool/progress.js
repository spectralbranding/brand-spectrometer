/* Scroll-progress line for meter.spectralbranding.com — self-contained: injects its
   own style + element, then tracks scroll. Include once per page:
   <script src="/progress.js" defer></script> */
(function () {
  var css =
    '.scroll-progress{position:fixed;left:0;bottom:0;height:3px;width:0;' +
    'background:linear-gradient(90deg,#e64a3b,#e8842b,#e8c531,#7bc043,#2fb3a8,#3a8dde,#7a5cd0,#c44fa8);' +
    'z-index:100;opacity:.9;transition:width .15s ease-out;pointer-events:none}';
  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  var bar = document.createElement('div');
  bar.className = 'scroll-progress';
  bar.setAttribute('aria-hidden', 'true');
  document.body.appendChild(bar);

  function update() {
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%';
  }
  document.addEventListener('scroll', update, { passive: true });
  window.addEventListener('resize', update, { passive: true });
  update();
})();
