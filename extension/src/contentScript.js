(function attachReservationGuardContentScript() {
  if (window.__reservationGuardContentScriptAttached) {
    return;
  }

  window.__reservationGuardContentScriptAttached = true;
  const SUPPORTED_SITE_CONFIGS = [
    {
      id: "airbnb",
      name: "Airbnb",
      matches: (location) => /(^|\.)airbnb\./i.test(location.hostname),
      termsUrl: "https://www.airbnb.com/help/article/2908",
      termsPagePattern: /\/help\/article\/(2877|2857)|terms|legal/i,
    },
    {
      id: "trip",
      name: "Trip.com",
      matches: (location) => /(^|\.)trip\.com$/i.test(location.hostname),
      termsUrl: "https://kr.trip.com/contents/service-guideline/terms.html",
      termsPagePattern: /\/contents\/service-guideline\/terms\.html|terms/i,
    },
    {
      id: "naver-booking",
      name: "네이버 예약",
      matches: (location) =>
        /(^|\.)booking\.naver\.com$/i.test(location.hostname)
        || /(^|\.)smartplace\.naver\.com$/i.test(location.hostname)
        || /(^|\.)new\.smartplace\.naver\.com$/i.test(location.hostname),
      termsUrl: "https://new.smartplace.naver.com/help/policy?menu=term&tab=booking",
      termsPagePattern: /\/help\/policy/i,
    },
  ];

  function getSupportedSite(location) {
    return SUPPORTED_SITE_CONFIGS.find((site) => site.matches(location)) || null;
  }

  function openSidePanel() {
    chrome.runtime.sendMessage({ type: "OPEN_BUBIBI_SIDE_PANEL" });
  }

  function isTermsPage(site, location) {
    return site.termsPagePattern?.test(`${location.pathname}${location.search}`) || false;
  }

  function goToTermsPage(site) {
    window.location.assign(site.termsUrl);
  }

  function dismissPrompt(hostname) {
    sessionStorage.setItem(`bubibiPromptDismissed:${hostname}`, "true");
    document.getElementById("bubibi-site-prompt")?.remove();
  }

  function createPromptStyles() {
    const style = document.createElement("style");
    style.textContent = `
      :host {
        all: initial;
        color-scheme: light;
        font-family: Inter, Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }

      .prompt {
        position: fixed;
        right: 18px;
        bottom: 18px;
        z-index: 2147483647;
        width: min(330px, calc(100vw - 36px));
        border: 1px solid #d8e2dc;
        border-radius: 8px;
        background: #ffffff;
        box-shadow: 0 18px 45px rgb(15 23 42 / 18%);
        padding: 16px;
        color: #161a1d;
      }

      .header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
      }

      .kicker {
        margin: 0 0 4px;
        color: #006d77;
        font-size: 12px;
        font-weight: 900;
        line-height: 1.3;
      }

      .title {
        margin: 0;
        color: #111719;
        font-size: 18px;
        font-weight: 950;
        line-height: 1.25;
      }

      .close {
        display: inline-grid;
        width: 30px;
        height: 30px;
        place-items: center;
        border: 1px solid #d8e2dc;
        border-radius: 999px;
        background: #ffffff;
        color: #4f5d5f;
        cursor: pointer;
        font: inherit;
        font-size: 17px;
        font-weight: 900;
        line-height: 1;
      }

      .body {
        margin: 12px 0 14px;
        color: #4f5d5f;
        font-size: 13px;
        font-weight: 750;
        line-height: 1.55;
      }

      .actions {
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 8px;
      }

      .primary,
      .secondary {
        min-height: 40px;
        border-radius: 8px;
        cursor: pointer;
        font: inherit;
        font-size: 13px;
        font-weight: 900;
      }

      .primary {
        border: 0;
        background: #006d77;
        color: #ffffff;
        padding: 0 14px;
      }

      .secondary {
        border: 1px solid #cfd8dc;
        background: #ffffff;
        color: #2f3e46;
        padding: 0 12px;
      }

      @media (max-width: 480px) {
        .prompt {
          right: 12px;
          bottom: 12px;
          width: calc(100vw - 24px);
        }
      }
    `;
    return style;
  }

  function showSitePrompt() {
    const site = getSupportedSite(window.location);

    if (!site || document.getElementById("bubibi-site-prompt")) {
      return;
    }

    const dismissKey = `bubibiPromptDismissed:${window.location.hostname}`;

    if (sessionStorage.getItem(dismissKey) === "true") {
      return;
    }

    const host = document.createElement("div");
    host.id = "bubibi-site-prompt";
    const shadow = host.attachShadow({ mode: "open" });
    const wrapper = document.createElement("section");
    const onTermsPage = isTermsPage(site, window.location);
    const title = onTermsPage
      ? "이 약관을 부비비로 분석할 수 있어요"
      : `${site.name} 약관을 먼저 확인해 볼까요?`;
    const body = onTermsPage
      ? "현재 약관 페이지에서 취소·환불 조건, 추가 비용, 책임 범위를 카드로 정리할 수 있습니다."
      : "예약 약관, 취소·환불 조건, 추가 비용을 확인하려면 먼저 해당 사이트의 약관 페이지로 이동해 주세요.";
    const primaryLabel = onTermsPage ? "부비비 열기" : "약관 페이지로 이동";
    wrapper.className = "prompt";
    wrapper.setAttribute("aria-label", "부비비 약관 확인 안내");
    wrapper.innerHTML = `
      <div class="header">
        <div>
          <p class="kicker">부비비</p>
          <p class="title">${title}</p>
        </div>
        <button class="close" type="button" aria-label="닫기">×</button>
      </div>
      <p class="body">${body}</p>
      <div class="actions">
        <button class="primary" type="button">${primaryLabel}</button>
        <button class="secondary" type="button">나중에</button>
      </div>
    `;

    shadow.append(createPromptStyles(), wrapper);
    document.documentElement.appendChild(host);

    shadow.querySelector(".primary").addEventListener("click", () => {
      if (onTermsPage) {
        openSidePanel();
        return;
      }

      goToTermsPage(site);
    });
    shadow.querySelector(".secondary").addEventListener(
      "click",
      () => dismissPrompt(window.location.hostname),
    );
    shadow.querySelector(".close").addEventListener(
      "click",
      () => dismissPrompt(window.location.hostname),
    );
  }

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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showSitePrompt, { once: true });
  } else {
    showSitePrompt();
  }
})();
