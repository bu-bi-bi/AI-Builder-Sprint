(function attachReservationGuardContentScript() {
  if (window.__reservationGuardContentScriptAttached) {
    return;
  }

  window.__reservationGuardContentScriptAttached = true;

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type !== "EXTRACT_RESERVATION_TEXT") {
      return false;
    }

    const targetAdapter = window.ReservationGuardTargetAdapter;
    const genericAdapter = window.ReservationGuardGenericAdapter;
    const adapter = targetAdapter?.matches?.(window.location)
      ? targetAdapter
      : genericAdapter;

    const extraction = adapter.extract(document, window.location);
    sendResponse(extraction);

    return false;
  });
})();
