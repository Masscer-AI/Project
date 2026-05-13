/**
 * Organization Management billing: wallet recharge confirmation dialog,
 * manual subscription panel toggle, end date from billing interval.
 */
(function () {
  "use strict";

  function utcToday() {
    var now = new Date();
    return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  }

  function formatYmdUTC(d) {
    var y = d.getUTCFullYear();
    var m = String(d.getUTCMonth() + 1).padStart(2, "0");
    var day = String(d.getUTCDate()).padStart(2, "0");
    return y + "-" + m + "-" + day;
  }

  /** Add whole calendar months in UTC; clamps to last day of target month when needed. */
  function addCalendarMonthsUTC(base, months) {
    var y = base.getUTCFullYear();
    var mo = base.getUTCMonth();
    var day = base.getUTCDate();
    var cand = new Date(Date.UTC(y, mo + months, day));
    if (cand.getUTCDate() !== day) {
      cand = new Date(Date.UTC(y, mo + months + 1, 0));
    }
    return cand;
  }

  function endDateFromInterval(interval) {
    var start = utcToday();
    switch (interval) {
      case "monthly":
        return addCalendarMonthsUTC(start, 1);
      case "quarterly":
        return addCalendarMonthsUTC(start, 3);
      case "yearly":
        return addCalendarMonthsUTC(start, 12);
      case "one_time":
        return addCalendarMonthsUTC(start, 1);
      case "custom":
        return addCalendarMonthsUTC(start, 1);
      default:
        return addCalendarMonthsUTC(start, 1);
    }
  }

  function initEndDateFromBillingInterval() {
    var endInput = document.getElementById("id_end_date");
    var intervalSelect = document.getElementById("id_billing_interval");
    var btn = document.getElementById("org-mgmt-calc-end-from-now");
    if (!endInput || !intervalSelect || !btn) return;

    btn.addEventListener("click", function () {
      var interval = intervalSelect.value || "monthly";
      endInput.value = formatYmdUTC(endDateFromInterval(interval));
    });
  }

  function parseDecimal(s) {
    if (!s || typeof s !== "string") return null;
    var t = s.trim().replace(",", ".");
    if (!t) return null;
    var n = Number(t);
    if (!Number.isFinite(n) || n <= 0) return null;
    return n;
  }

  function fmtNum(n, decimals) {
    if (!Number.isFinite(n)) return "—";
    var d = decimals != null ? decimals : 4;
    return n.toLocaleString(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: d,
    });
  }

  function initWalletDialog() {
    var form = document.getElementById("org-mgmt-wallet-form");
    var dialog = document.getElementById("org-mgmt-wallet-dialog");
    var openBtn = document.getElementById("org-mgmt-wallet-open");
    var confirmBtn = document.getElementById("org-mgmt-wallet-confirm");
    var cancelBtn = document.getElementById("org-mgmt-wallet-cancel");
    var summary = document.getElementById("org-mgmt-wallet-modal-summary");
    var amountInput = document.getElementById("id_amount_usd");
    var registerPayment = document.getElementById("id_register_wallet_recharge_payment");
    var paymentNoteRow = document.getElementById("org-mgmt-wallet-payment-note-row");
    var paymentNote = document.getElementById("id_wallet_recharge_payment_note");
    if (!form || !dialog || !openBtn || !confirmBtn || !summary || !amountInput) return;

    if (form.getAttribute("data-org-mgmt-wallet-disabled") === "1") {
      return;
    }

    var oneUsdIs = parseDecimal(form.getAttribute("data-one-usd-is") || "");
    var balanceBefore = parseDecimal(form.getAttribute("data-balance-cu") || "0");
    if (balanceBefore === null) balanceBefore = 0;
    var unitName = form.getAttribute("data-unit-name") || "Compute Unit";

    function buildSummary(amountUsd) {
      var lines = [];
      if (!oneUsdIs || oneUsdIs <= 0) {
        lines.push(
          document.getElementById("org-mgmt-wallet-msg-no-rate")
            ? document.getElementById("org-mgmt-wallet-msg-no-rate").textContent
            : "Preview unavailable."
        );
        return lines.join("\n\n");
      }
      var addCu = amountUsd * oneUsdIs;
      var afterCu = balanceBefore + addCu;
      var usdBefore = balanceBefore / oneUsdIs;
      var usdAfter = afterCu / oneUsdIs;
      var beforeLabel = document.getElementById("org-mgmt-wallet-lbl-before");
      var afterLabel = document.getElementById("org-mgmt-wallet-lbl-after");
      var addLabel = document.getElementById("org-mgmt-wallet-lbl-add");
      var usdLabel = document.getElementById("org-mgmt-wallet-lbl-usd");
      lines.push(
        (beforeLabel ? beforeLabel.textContent : "Before") +
          ":\n  " +
          fmtNum(balanceBefore, 6) +
          " " +
          unitName +
          (Number.isFinite(usdBefore)
            ? "\n  (~" + fmtNum(usdBefore, 4) + " USD)"
            : "")
      );
      lines.push(
        (addLabel ? addLabel.textContent : "Credit") +
          ":\n  +" +
          fmtNum(addCu, 6) +
          " " +
          unitName +
          "\n  (" +
          fmtNum(amountUsd, 2) +
          " USD)"
      );
      lines.push(
        (afterLabel ? afterLabel.textContent : "After") +
          ":\n  " +
          fmtNum(afterCu, 6) +
          " " +
          unitName +
          (Number.isFinite(usdAfter)
            ? "\n  (~" + fmtNum(usdAfter, 4) + " USD)"
            : "")
      );
      if (usdLabel && Number.isFinite(usdAfter) && Number.isFinite(usdBefore)) {
        lines.push(
          usdLabel.textContent +
            ": " +
            fmtNum(usdBefore, 4) +
            " → " +
            fmtNum(usdAfter, 4) +
            " USD"
        );
      }
      return lines.join("\n\n");
    }

    function syncPaymentNote() {
      if (!registerPayment || !paymentNoteRow || !paymentNote) return;
      var enabled = registerPayment.checked && !registerPayment.disabled;
      if (enabled) {
        paymentNoteRow.removeAttribute("hidden");
        paymentNote.setAttribute("required", "required");
        paymentNote.removeAttribute("disabled");
      } else {
        paymentNoteRow.setAttribute("hidden", "hidden");
        paymentNote.removeAttribute("required");
        paymentNote.setAttribute("disabled", "disabled");
      }
    }

    syncPaymentNote();
    if (registerPayment) {
      registerPayment.addEventListener("change", syncPaymentNote);
    }

    openBtn.addEventListener("click", function () {
      var amountUsd = parseDecimal(amountInput.value);
      if (!amountUsd) {
        window.alert(
          document.getElementById("org-mgmt-wallet-msg-invalid-amount")
            ? document.getElementById("org-mgmt-wallet-msg-invalid-amount").textContent
            : "Enter a valid positive USD amount."
        );
        return;
      }
      if (registerPayment && registerPayment.checked && paymentNote && !paymentNote.value.trim()) {
        paymentNote.reportValidity();
        return;
      }
      summary.textContent = buildSummary(amountUsd);
      if (typeof dialog.showModal === "function") {
        dialog.showModal();
      } else {
        if (window.confirm(summary.textContent)) {
          form.submit();
        }
      }
    });

    confirmBtn.addEventListener("click", function () {
      dialog.close();
      form.submit();
    });

    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () {
        dialog.close();
      });
    }
  }

  function initStripeCancelConfirm() {
    document.querySelectorAll("form[data-org-mgmt-stripe-confirm]").forEach(function (form) {
      var msg = form.getAttribute("data-org-mgmt-stripe-confirm");
      if (!msg) return;
      form.addEventListener("submit", function (e) {
        if (!window.confirm(msg)) {
          e.preventDefault();
        }
      });
    });
  }

  function initManualPanel() {
    var btn = document.getElementById("org-mgmt-open-manual-subscription");
    var panel = document.getElementById("org-mgmt-manual-subscription-panel");
    if (!btn || !panel) return;
    btn.addEventListener("click", function () {
      var hidden = panel.hasAttribute("hidden");
      if (hidden) {
        panel.removeAttribute("hidden");
        btn.setAttribute("aria-expanded", "true");
      } else {
        panel.setAttribute("hidden", "hidden");
        btn.setAttribute("aria-expanded", "false");
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initWalletDialog();
      initManualPanel();
      initStripeCancelConfirm();
      initEndDateFromBillingInterval();
    });
  } else {
    initWalletDialog();
    initManualPanel();
    initStripeCancelConfirm();
    initEndDateFromBillingInterval();
  }
})();
