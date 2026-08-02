(function attachTargetSiteAdapter() {
  const DIRECT_ANALYSIS_CHAR_LIMIT = 50000;
  const NON_TEXT_SELECTOR = [
    "script",
    "style",
    "noscript",
    "svg",
    "canvas",
    "img",
    "picture",
    "video",
    "audio",
    "iframe",
    "source",
    "template",
    "[hidden]",
  ].join(",");

  function normalizeText(value) {
    return String(value || "")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function matches(location) {
    return /(^|\.)airbnb\./i.test(location.hostname);
  }

  function redactSensitiveText(text) {
    return text
      .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[이메일 숨김]")
      .replace(/\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b/g, "[긴 숫자 숨김]")
      .replace(/\b\d{6}[- ]?\d{7}\b/g, "[긴 숫자 숨김]")
      .replace(/\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b/g, "[전화번호 숨김]");
  }

  function removeNonTextNodes(root) {
    root.querySelectorAll(NON_TEXT_SELECTOR).forEach((element) => {
      element.remove();
    });
  }

  function dedupeAdjacentLines(text) {
    const lines = text
      .split("\n")
      .map((line) => normalizeText(line))
      .filter(Boolean);
    const deduped = [];

    lines.forEach((line) => {
      if (deduped[deduped.length - 1] !== line) {
        deduped.push(line);
      }
    });

    return deduped.join("\n");
  }

  function detectAirbnbPageKind(pathname) {
    if (/\/rooms\//i.test(pathname)) {
      return "listing";
    }

    if (/\/book\//i.test(pathname) || /\/payments\//i.test(pathname)) {
      return "checkout";
    }

    if (/terms|help|policies|cancellation/i.test(pathname)) {
      return "policy";
    }

    return "airbnb";
  }

  function extractReadableText(documentNode) {
    const bodyClone = documentNode.body?.cloneNode(true);

    if (!bodyClone) {
      return "";
    }

    removeNonTextNodes(bodyClone);

    return normalizeText(dedupeAdjacentLines(bodyClone.innerText || bodyClone.textContent));
  }

  function extract(documentNode, location) {
    const pageText = extractReadableText(documentNode);
    const redactedText = redactSensitiveText(pageText);
    const pageKind = detectAirbnbPageKind(location.pathname);

    return {
      adapter: "airbnb",
      url: location.href,
      siteName: "Airbnb",
      title: normalizeText(documentNode.title),
      pageText: redactedText,
      textLength: redactedText.length,
      pageKind,
      requiresChunking: redactedText.length > DIRECT_ANALYSIS_CHAR_LIMIT,
      capturedAt: new Date().toISOString(),
    };
  }

  window.ReservationGuardTargetAdapter = {
    matches,
    extract,
  };
})();
