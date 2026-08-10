(function () {
  function ready(fn) {
    if (document.readyState !== "loading") {
      fn();
    } else {
      document.addEventListener("DOMContentLoaded", fn);
    }
  }

  ready(function () {
    var org = document.getElementById("id_organization");
    var agent = document.getElementById("id_agent");
    if (!org || !agent) {
      return;
    }

    var allOptions = Array.from(agent.options).map(function (opt) {
      return {
        value: opt.value,
        text: opt.text,
        orgId: opt.getAttribute("data-organization-id") || "",
      };
    });

    function rebuild() {
      var orgId = org.value || "";
      var prev = agent.value;
      var keepPrev =
        !prev ||
        !orgId ||
        allOptions.some(function (o) {
          return o.value === prev && o.orgId === orgId;
        });

      agent.innerHTML = "";
      allOptions.forEach(function (o) {
        if (o.value && orgId && o.orgId !== orgId) {
          return;
        }
        var opt = document.createElement("option");
        opt.value = o.value;
        opt.textContent = o.text;
        if (o.orgId) {
          opt.setAttribute("data-organization-id", o.orgId);
        }
        if (o.value === prev && keepPrev) {
          opt.selected = true;
        }
        agent.appendChild(opt);
      });

      if (prev && !keepPrev) {
        agent.value = "";
      }

      if (window.django && django.jQuery) {
        django.jQuery(agent).trigger("change");
      }
    }

    org.addEventListener("change", rebuild);
    if (window.django && django.jQuery) {
      django.jQuery(org).on("change select2:select select2:clear", rebuild);
    }
    rebuild();
  });
})();
