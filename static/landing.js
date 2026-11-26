/**
 * HemoSlab Landing Page Controller
 * Handles Sign In modal, demo credential helper, Guest navigation, and Escape key handling.
 */

(function () {
  "use strict";

  const signInModal = document.getElementById("signInModal");
  const signInForm = document.getElementById("signInForm");
  const operatorIdInput = document.getElementById("operatorIdInput");
  const facilitySelect = document.getElementById("facilitySelect");
  const passcodeInput = document.getElementById("passcodeInput");
  const signInError = document.getElementById("signInError");

  const openTriggers = [
    document.getElementById("headerSignInBtn"),
    document.getElementById("heroSignInBtn"),
  ];
  const guestTriggers = [
    document.getElementById("headerGuestBtn"),
    document.getElementById("heroGuestBtn"),
    document.getElementById("modalGuestBtn"),
  ];
  const closeBtn = document.getElementById("closeSignInModal");
  const fillDemoBtn = document.getElementById("fillDemoCredsBtn");

  function openModal() {
    if (!signInModal) return;
    signInModal.classList.remove("is-hidden");
    if (signInError) {
      signInError.classList.add("is-hidden");
      signInError.textContent = "";
    }
    if (operatorIdInput) {
      operatorIdInput.focus();
    }
  }

  function closeModal() {
    if (!signInModal) return;
    signInModal.classList.add("is-hidden");
  }

  function enterAsGuest() {
    try {
      sessionStorage.setItem(
        "hemoslab_session",
        JSON.stringify({
          mode: "guest",
          operator: "Guest Observer",
          facility: "ALL",
          signedInAt: new Date().toISOString(),
        })
      );
    } catch (_err) {
      // Ignore storage errors in restricted environments
    }
    window.location.href = "/dashboard?mode=guest";
  }

  openTriggers.forEach((btn) => {
    if (btn) btn.addEventListener("click", openModal);
  });

  guestTriggers.forEach((btn) => {
    if (btn) btn.addEventListener("click", enterAsGuest);
  });

  if (closeBtn) {
    closeBtn.addEventListener("click", closeModal);
  }

  if (signInModal) {
    signInModal.addEventListener("click", (event) => {
      if (event.target === signInModal) {
        closeModal();
      }
    });
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && signInModal && !signInModal.classList.contains("is-hidden")) {
      closeModal();
    }
  });

  if (fillDemoBtn) {
    fillDemoBtn.addEventListener("click", () => {
      if (operatorIdInput) operatorIdInput.value = "cmd.officer@rims.hemoslab.in";
      if (facilitySelect) facilitySelect.value = "ALL";
      if (passcodeInput) passcodeInput.value = "hemoslab-fefo-2026";
      if (signInError) {
        signInError.classList.add("is-hidden");
        signInError.textContent = "";
      }
    });
  }

  if (signInForm) {
    signInForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const operatorId = (operatorIdInput?.value || "").trim();
      const passcode = (passcodeInput?.value || "").trim();
      const facility = facilitySelect?.value || "ALL";

      if (!operatorId || !passcode) {
        if (signInError) {
          signInError.textContent = "Please enter both an Operator ID and Command Passcode (or click Fill Demo Operator).";
          signInError.classList.remove("is-hidden");
        }
        return;
      }

      try {
        sessionStorage.setItem(
          "hemoslab_session",
          JSON.stringify({
            mode: "operator",
            operator: operatorId,
            facility: facility,
            signedInAt: new Date().toISOString(),
          })
        );
      } catch (_err) {
        // Ignore storage errors in restricted environments
      }

      const params = new URLSearchParams({
        mode: "operator",
        facility: facility,
      });
      window.location.href = `/dashboard?${params.toString()}`;
    });
  }
})();
