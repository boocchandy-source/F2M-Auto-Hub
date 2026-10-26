/* F2M Auto-Hub — small, dependency-free UI behaviours. */
(function () {
  "use strict";

  var body = document.body;
  var sidebar = document.getElementById("sidebar");
  var backdrop = document.querySelector("[data-sidebar-close]");
  var toggleButtons = document.querySelectorAll("[data-sidebar-toggle]");

  function setSidebar(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("is-open", open);
    body.classList.toggle("sidebar-open", open);
    if (backdrop) backdrop.hidden = !open;
    toggleButtons.forEach(function (button) {
      button.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  toggleButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      setSidebar(!sidebar.classList.contains("is-open"));
    });
  });

  if (backdrop) {
    backdrop.addEventListener("click", function () {
      setSidebar(false);
    });
  }

  if (sidebar) {
    sidebar.querySelectorAll("a.nav-link").forEach(function (link) {
      link.addEventListener("click", function () {
        if (window.matchMedia("(max-width: 940px)").matches) setSidebar(false);
      });
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && sidebar && sidebar.classList.contains("is-open")) {
      setSidebar(false);
    }
  });

  window.addEventListener("resize", function () {
    if (window.matchMedia("(min-width: 941px)").matches) setSidebar(false);
  });

  /* Dismissible flash messages. */
  document.querySelectorAll("[data-dismiss]").forEach(function (button) {
    button.addEventListener("click", function () {
      var alert = button.closest("[data-flash]");
      if (!alert) return;
      alert.classList.add("flash-hiding");
      window.setTimeout(function () {
        alert.remove();
      }, 180);
    });
  });

  window.setTimeout(function () {
    document.querySelectorAll("[data-flash]").forEach(function (alert) {
      alert.classList.add("flash-hiding");
      window.setTimeout(function () {
        alert.remove();
      }, 320);
    });
  }, 9000);

  /* Confirmation prompts for destructive forms. */
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    var message = form.getAttribute("data-confirm");
    if (message && !window.confirm(message)) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  });

  /* Search filters that submit as soon as a value changes. */
  document.querySelectorAll("[data-autosubmit]").forEach(function (field) {
    field.addEventListener("change", function () {
      if (field.form) field.form.submit();
    });
  });

  /* Show / hide the login password. */
  document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
    var field = document.getElementById("password");
    if (!field) return;
    button.addEventListener("click", function () {
      var showing = field.type === "text";
      field.type = showing ? "password" : "text";
      button.textContent = showing ? "Show" : "Hide";
      button.setAttribute("aria-label", showing ? "Show password" : "Hide password");
      field.focus();
    });
  });

  document.querySelectorAll("[data-print]").forEach(function (button) {
    button.addEventListener("click", function () {
      window.print();
    });
  });

  document.querySelectorAll("[data-back]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (window.history.length > 1) {
        window.history.back();
      } else {
        window.location.href = "/";
      }
    });
  });
})();
