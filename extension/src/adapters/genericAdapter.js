(function attachGenericAdapter() {
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

  function extractReadableText(documentNode) {
    const bodyClone = documentNode.body?.cloneNode(true);

    if (!bodyClone) {
      return "";
    }

    removeNonTextNodes(bodyClone);

    return normalizeText(dedupeAdjacentLines(bodyClone.innerText || bodyClone.textContent));
  }

  function extract(documentNode, location) {
    const readableText = extractReadableText(documentNode);
    const redactedText = redactSensitiveText(readableText);

    return {
      adapter: "generic",
      url: location.href,
      siteName: location.hostname,
      title: normalizeText(documentNode.title),
      pageText: redactedText,
      textLength: redactedText.length,
      requiresChunking: redactedText.length > DIRECT_ANALYSIS_CHAR_LIMIT,
      capturedAt: new Date().toISOString(),
    };
  }

  window.ReservationGuardGenericAdapter = {
    extract,
  };
})();
