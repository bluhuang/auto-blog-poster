(function () {
  "use strict";

  var root = document.querySelector("[data-home-redesign]");
  if (!root) return;

  document.body.classList.add("home-redesign-active");

  var revealItems = [].slice.call(root.querySelectorAll("[data-home-reveal]"));
  var reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (reducedMotion || !("IntersectionObserver" in window)) {
    revealItems.forEach(function (item) { item.classList.add("is-visible"); });
  } else {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -10%", threshold: 0.08 });

    revealItems.forEach(function (item) { observer.observe(item); });
  }

  var portrait = root.querySelector(".home-portrait");
  var hero = root.querySelector(".home-hero");
  if (portrait && hero && !reducedMotion && window.matchMedia("(pointer: fine)").matches) {
    hero.addEventListener("pointermove", function (event) {
      var rect = hero.getBoundingClientRect();
      var x = (event.clientX - rect.left) / rect.width - 0.5;
      var y = (event.clientY - rect.top) / rect.height - 0.5;
      portrait.style.setProperty("--portrait-x", (x * 5).toFixed(2) + "px");
      portrait.style.setProperty("--portrait-y", (y * 5).toFixed(2) + "px");
      portrait.style.setProperty("--portrait-rotate", (x * 1.8).toFixed(2) + "deg");
    });
    hero.addEventListener("pointerleave", function () {
      portrait.style.removeProperty("--portrait-x");
      portrait.style.removeProperty("--portrait-y");
      portrait.style.removeProperty("--portrait-rotate");
    });
  }
})();
