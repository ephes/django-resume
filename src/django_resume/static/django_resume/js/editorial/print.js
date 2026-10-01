// Print buttons of the editorial theme: revealed only when this script runs,
// so visitors without JavaScript never see a button that does nothing.
(function () {
  "use strict";
  function init() {
    var buttons = document.querySelectorAll("[data-editorial-print]");
    buttons.forEach(function (button) {
      var container = button.closest("[data-editorial-print-container]");
      while (container) {
        container.hidden = false;
        container = container.parentElement.closest("[data-editorial-print-container]");
      }
      button.addEventListener("click", function () { window.print(); });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
