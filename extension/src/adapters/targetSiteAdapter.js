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
    return getSiteMeta(location) !== null;
  }

  function getSiteMeta(location) {
    if (/(^|\.)airbnb\./i.test(location.hostname)) {
      return {
        adapter: "airbnb",
        siteName: "Airbnb",
        pageKind: detectAirbnbPageKind(location.pathname),
      };
    }

    if (/(^|\.)trip\.com$/i.test(location.hostname)) {
      return {
        adapter: "trip",
        siteName: "Trip.com",
        pageKind: detectGenericBookingPageKind(location.pathname),
      };
    }

    if (
      /(^|\.)booking\.naver\.com$/i.test(location.hostname)
      || /(^|\.)smartplace\.naver\.com$/i.test(location.hostname)
      || /(^|\.)new\.smartplace\.naver\.com$/i.test(location.hostname)
    ) {
      return {
        adapter: "naver-booking",
        siteName: "네이버 예약",
        pageKind: detectGenericBookingPageKind(location.pathname),
      };
    }

    return null;
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

  function detectGenericBookingPageKind(pathname) {
    if (/terms|policy|policies|agreement|notice|cancel|refund/i.test(pathname)) {
      return "policy";
    }

    if (/book|booking|reservation|checkout|order|payment/i.test(pathname)) {
      return "checkout";
    }

    return "booking";
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
    const siteMeta = getSiteMeta(location) || {
      adapter: "target",
      siteName: location.hostname,
      pageKind: "booking",
    };

    return {
      adapter: siteMeta.adapter,
      url: location.href,
      siteName: siteMeta.siteName,
      title: normalizeText(documentNode.title),
      pageText: redactedText,
      textLength: redactedText.length,
      pageKind: siteMeta.pageKind,
      requiresChunking: redactedText.length > DIRECT_ANALYSIS_CHAR_LIMIT,
      capturedAt: new Date().toISOString(),
    };
  }

  window.ReservationGuardTargetAdapter = {
    matches,
    extract,
  };
})();
