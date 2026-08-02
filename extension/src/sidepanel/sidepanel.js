const state = {
  extraction: null,
  analysis: null,
  activeCardIndex: 0,
  checkedCardIds: new Set(),
  analysisSessionId: null,
  dragStartX: null,
  dragDeltaX: 0,
  loadingTimer: null,
  activeController: null,
  restartRequested: false,
  runId: 0,
};

const SOURCE_PREVIEW_LIMIT = 50000;
const ANALYSIS_API_URL = "http://127.0.0.1:8000/api/analyze-reservation";
const ANALYSIS_SESSION_API_URL = "http://127.0.0.1:8000/api/analysis-sessions";
const WEB_DETAIL_URL = "http://127.0.0.1:8000/result";
const ANALYSIS_TIMEOUT_MS = 300000;
const SHORT_ANALYSIS_STEPS = [
  "예약 전에 확인할 조건을 찾고 있습니다.",
  "취소, 환불, 결제 조건을 살펴보고 있습니다.",
  "원문 근거가 있는 카드만 정리하고 있습니다.",
];
const LONG_ANALYSIS_STEPS = [
  "긴 원문이라 여러 조각으로 나누어 확인하고 있습니다.",
  "각 조각에서 예약 조건 후보를 찾고 있습니다.",
  "취소, 환불, 추가 비용, 책임 조건을 비교하고 있습니다.",
  "중복 내용을 합쳐 중요한 카드만 고르고 있습니다.",
  "긴 약관은 1~3분 정도 걸릴 수 있습니다.",
];
const LEVEL_META = {
  high: {
    label: "중요",
    tone: "high",
  },
  medium: {
    label: "확인",
    tone: "medium",
  },
  low: {
    label: "참고",
    tone: "low",
  },
};

const elements = {
  idlePanel: document.getElementById("idlePanel"),
  loadingPanel: document.getElementById("loadingPanel"),
  failurePanel: document.getElementById("failurePanel"),
  loadingTitle: document.getElementById("loadingTitle"),
  loadingStep: document.getElementById("loadingStep"),
  failureTitle: document.getElementById("failureTitle"),
  failureDetail: document.getElementById("failureDetail"),
  llmFailureDetails: document.getElementById("llmFailureDetails"),
  llmFailureResponse: document.getElementById("llmFailureResponse"),
  analyzePageButton: document.getElementById("analyzePageButton"),
  restartAnalysisButton: document.getElementById("restartAnalysisButton"),
  retryAnalysisButton: document.getElementById("retryAnalysisButton"),
  copyButton: document.getElementById("copyButton"),
  openWebButton: document.getElementById("openWebButton"),
  messageBox: document.getElementById("messageBox"),
  analysisPanel: document.getElementById("analysisPanel"),
  analysisSummary: document.getElementById("analysisSummary"),
  checkedCount: document.getElementById("checkedCount"),
  cardStack: document.getElementById("cardStack"),
  cardPosition: document.getElementById("cardPosition"),
  prevCardButton: document.getElementById("prevCardButton"),
  nextCardButton: document.getElementById("nextCardButton"),
  sourcePanel: document.getElementById("sourcePanel"),
  sourceText: document.getElementById("sourceText"),
  aiDisclaimer: document.getElementById("aiDisclaimer"),
};

function showIdleView() {
  stopLoadingCycle();
  elements.idlePanel.hidden = false;
  elements.loadingPanel.hidden = true;
  elements.failurePanel.hidden = true;
  elements.analysisPanel.hidden = true;
  elements.sourcePanel.hidden = true;
  elements.aiDisclaimer.hidden = true;
}

function showLoadingView(title, step) {
  elements.idlePanel.hidden = true;
  elements.loadingPanel.hidden = false;
  elements.failurePanel.hidden = true;
  elements.analysisPanel.hidden = true;
  elements.sourcePanel.hidden = true;
  elements.aiDisclaimer.hidden = true;
  elements.loadingTitle.textContent = title;
  elements.loadingStep.textContent = step;
}

function showFailureView(title, detail, llmResponse = "") {
  stopLoadingCycle();
  setMessage("");
  elements.idlePanel.hidden = true;
  elements.loadingPanel.hidden = true;
  elements.failurePanel.hidden = false;
  elements.analysisPanel.hidden = true;
  elements.sourcePanel.hidden = true;
  elements.aiDisclaimer.hidden = true;
  elements.failureTitle.textContent = title;
  elements.failureDetail.textContent = detail;
  elements.llmFailureResponse.textContent = llmResponse;
  elements.llmFailureDetails.hidden = !llmResponse;
  elements.llmFailureDetails.open = false;
}

function showResultView() {
  stopLoadingCycle();
  elements.idlePanel.hidden = true;
  elements.loadingPanel.hidden = true;
  elements.failurePanel.hidden = true;
  elements.analysisPanel.hidden = false;
  elements.sourcePanel.hidden = false;
  elements.aiDisclaimer.hidden = false;
}

function setLoadingStep(title, step) {
  elements.loadingTitle.textContent = title;
  elements.loadingStep.textContent = step;
}

function stopLoadingCycle() {
  if (state.loadingTimer) {
    clearInterval(state.loadingTimer);
    state.loadingTimer = null;
  }
}

function startLoadingCycle(title, steps) {
  stopLoadingCycle();

  let index = 0;
  setLoadingStep(title, steps[index]);

  state.loadingTimer = setInterval(() => {
    index = (index + 1) % steps.length;
    setLoadingStep(title, steps[index]);
  }, 4200);
}

function setMessage(message, tone = "info") {
  elements.messageBox.textContent = message;
  elements.messageBox.dataset.tone = tone;
  elements.messageBox.hidden = !message;
}

function getApiErrorInfo(payload, fallbackMessage) {
  const detail = payload?.detail;

  if (typeof detail === "string") {
    return {
      message: detail,
      llmResponse: "",
    };
  }

  if (!detail || typeof detail !== "object") {
    return {
      message: fallbackMessage,
      llmResponse: "",
    };
  }

  const message = detail.message
    || detail.repairError
    || detail.firstError
    || fallbackMessage;
  const llmResponse = detail.llmResponsePreview
    || detail.repairLlmResponsePreview
    || detail.firstLlmResponsePreview
    || "";

  return {
    message: typeof message === "string" ? message : fallbackMessage,
    llmResponse: typeof llmResponse === "string" ? llmResponse : "",
  };
}

function formatNumber(value) {
  return new Intl.NumberFormat("ko-KR").format(value || 0);
}

function normalizeLevel(level) {
  return Object.hasOwn(LEVEL_META, level) ? level : "medium";
}

function normalizeText(value, fallback = "") {
  if (typeof value !== "string") {
    return fallback;
  }

  const trimmed = value.trim();
  return trimmed || fallback;
}

function normalizeAnalysisResult(value) {
  const cards = Array.isArray(value?.cards)
    ? value.cards.map((card, index) => ({
        id: normalizeText(card?.id, `card-${index + 1}`),
        title: normalizeText(card?.title, "확인할 예약 조건"),
        level: normalizeLevel(card?.level),
        plain: normalizeText(
          card?.plain,
          "예약 전에 이 조건을 한 번 더 확인하면 좋습니다.",
        ),
        question: normalizeText(
          card?.question,
          "이 조건이 실제 예약에 어떻게 적용되는지 확인할 수 있을까요?",
        ),
        source: normalizeText(card?.source, "원문 근거를 찾지 못했습니다."),
      }))
    : [];

  return {
    summary: normalizeText(value?.summary, "예약 조건에서 확인할 내용을 찾았습니다."),
    cards,
  };
}

function clearElement(element) {
  while (element.firstChild) {
    element.removeChild(element.firstChild);
  }
}

function createTextElement(tagName, className, text) {
  const element = document.createElement(tagName);
  element.className = className;
  element.textContent = text;
  return element;
}

function updateCheckedCount() {
  const totalCards = state.analysis?.cards.length || 0;
  const checkedCards = state.checkedCardIds.size;
  elements.checkedCount.textContent = `${checkedCards}/${totalCards}개 확인`;
}

function markCardChecked(cardId) {
  if (!cardId || state.checkedCardIds.has(cardId)) {
    return;
  }

  state.checkedCardIds.add(cardId);

  const checkbox = Array.from(
    elements.cardStack.querySelectorAll("input[data-card-id]"),
  ).find((input) => input.dataset.cardId === cardId);

  if (checkbox) {
    checkbox.checked = true;
  }

  updateCheckedCount();
}

function updateCardControls() {
  const totalCards = state.analysis?.cards.length || 0;
  elements.cardPosition.textContent = totalCards > 0
    ? `${state.activeCardIndex + 1} / ${totalCards}`
    : "0 / 0";
  elements.prevCardButton.disabled = totalCards <= 1;
  elements.nextCardButton.disabled = totalCards <= 1;
}

function updateCardStack() {
  const cards = Array.from(elements.cardStack.querySelectorAll(".analysis-card"));
  const totalCards = cards.length;

  cards.forEach((card, index) => {
    const offset = index - state.activeCardIndex;
    const isActive = offset === 0;
    const absOffset = Math.abs(offset);
    const visibleOffset = Math.min(absOffset, 3);
    const direction = offset < 0 ? -1 : 1;
    const translateX = isActive ? state.dragDeltaX : direction * visibleOffset * 13;
    const translateY = isActive ? 0 : visibleOffset * 9;
    const rotate = isActive ? state.dragDeltaX * 0.035 : direction * visibleOffset * 2.3;
    const scale = isActive ? 1 : 1 - visibleOffset * 0.045;

    card.style.zIndex = String(totalCards - absOffset);
    card.style.opacity = absOffset > 3 ? "0" : "1";
    card.style.pointerEvents = isActive ? "auto" : "none";
    card.style.transform = `translateX(${translateX}px) translateY(${translateY}px) rotate(${rotate}deg) scale(${scale})`;
    card.dataset.active = String(isActive);
  });

  updateCardControls();
}

function goToCard(nextIndex) {
  const totalCards = state.analysis?.cards.length || 0;

  if (totalCards === 0) {
    return;
  }

  state.activeCardIndex = (nextIndex + totalCards) % totalCards;
  state.dragDeltaX = 0;
  updateCardStack();
}

function goToPreviousCard() {
  goToCard(state.activeCardIndex - 1);
}

function goToNextCard() {
  goToCard(state.activeCardIndex + 1);
}

function createCardElement(card, index) {
  const article = document.createElement("article");
  article.className = "analysis-card";
  article.dataset.level = card.level;

  const header = document.createElement("div");
  header.className = "card-header";

  const title = createTextElement("h3", "card-title", card.title);
  const level = normalizeLevel(card.level);
  const badge = createTextElement("span", "level-badge", LEVEL_META[level].label);
  badge.dataset.tone = LEVEL_META[level].tone;

  header.append(title, badge);

  const plain = createTextElement("p", "card-plain", card.plain);
  const question = createTextElement("p", "card-question", card.question);

  const sourceDetails = document.createElement("details");
  sourceDetails.className = "source-details";
  const summary = createTextElement("summary", "", "원문 보기");
  const source = createTextElement("p", "card-source", card.source);
  sourceDetails.append(summary, source);

  const checkLabel = document.createElement("label");
  checkLabel.className = "check-row";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.dataset.cardId = card.id;
  checkbox.checked = state.checkedCardIds.has(card.id);
  checkbox.addEventListener("change", () => {
    if (checkbox.checked) {
      state.checkedCardIds.add(card.id);
    } else {
      state.checkedCardIds.delete(card.id);
    }

    updateCheckedCount();
  });
  const checkText = document.createElement("span");
  checkText.textContent = "확인했습니다";
  checkLabel.append(checkbox, checkText);

  article.append(header, plain, question, sourceDetails, checkLabel);
  return article;
}

function renderCardStack(cards) {
  clearElement(elements.cardStack);

  cards.forEach((card, index) => {
    elements.cardStack.appendChild(createCardElement(card, index));
  });

  updateCardStack();
}

function renderAnalysis(rawAnalysis) {
  const analysis = normalizeAnalysisResult(rawAnalysis);

  state.analysis = analysis;
  state.activeCardIndex = 0;
  state.checkedCardIds = new Set();
  elements.analysisPanel.hidden = false;
  elements.analysisSummary.textContent = analysis.summary;
  elements.openWebButton.disabled = !state.analysisSessionId;
  renderCardStack(analysis.cards);

  updateCheckedCount();
  showResultView();
}

function renderExtraction(extraction) {
  state.extraction = extraction;
  state.analysis = null;
  state.checkedCardIds = new Set();
  const isPreview = extraction.pageText?.length > SOURCE_PREVIEW_LIMIT;
  const previewText = isPreview
    ? `${extraction.pageText.slice(0, SOURCE_PREVIEW_LIMIT)}\n\n[미리보기는 여기까지입니다. 분석/복사는 전체 원문을 사용합니다.]`
    : extraction.pageText;

  elements.sourceText.textContent =
    previewText || "분석할 수 있는 텍스트를 찾지 못했습니다.";
  elements.copyButton.disabled = !extraction.pageText;
  elements.openWebButton.disabled = true;
  clearElement(elements.cardStack);
  updateCardControls();
}

function resetExtractionState() {
  state.extraction = null;
  state.analysis = null;
  state.analysisSessionId = null;
  state.activeCardIndex = 0;
  state.checkedCardIds = new Set();
  elements.copyButton.disabled = true;
  elements.openWebButton.disabled = true;
  elements.sourceText.textContent = "";
  elements.sourcePanel.open = false;
  clearElement(elements.cardStack);
  updateCardControls();
}

async function saveAnalysisSession(analysis) {
  const response = await fetch(ANALYSIS_SESSION_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      analysis,
      pageText: state.extraction.pageText,
      url: state.extraction.url,
      siteName: state.extraction.siteName,
      sourceMeta: {
        url: state.extraction.url,
        siteName: state.extraction.siteName,
        title: state.extraction.title,
      },
    }),
  });

    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      const { message } = getApiErrorInfo(payload, "분석 결과 저장에 실패했습니다.");
      throw new Error(message);
    }

  return payload.analysisId;
}

function restartAnalysisFlow() {
  state.restartRequested = true;
  state.runId += 1;

  if (state.activeController) {
    state.activeController.abort();
    state.activeController = null;
  }

  stopLoadingCycle();
  resetExtractionState();
  setMessage("");
  elements.analyzePageButton.disabled = false;
  showIdleView();
}

async function extractCurrentPage(runId) {
  elements.copyButton.disabled = true;
  setMessage("");
  setLoadingStep("페이지 읽는 중", "현재 탭에서 예약 조건 원문을 가져오고 있습니다.");

  try {
    const response = await chrome.runtime.sendMessage({
      type: "GET_CURRENT_TAB_TEXT",
    });

    if (!response?.ok) {
      throw new Error(response?.error || "현재 페이지를 읽지 못했습니다.");
    }

    if (runId !== state.runId) {
      return;
    }

    if (!normalizeText(response.result?.pageText)) {
      throw new Error("현재 페이지에서 읽을 수 있는 예약 조건 텍스트를 찾지 못했습니다.");
    }

    renderExtraction(response.result);
  } catch (error) {
    if (runId !== state.runId) {
      return;
    }

    resetExtractionState();
    showFailureView(
      "페이지를 읽지 못했습니다",
      error?.message || "텍스트 추출에 실패했습니다.",
    );
  } finally {
  }
}

async function analyzeCurrentExtraction() {
  if (!state.extraction?.pageText) {
    setMessage("먼저 현재 페이지를 가져와야 합니다.", "error");
    return;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), ANALYSIS_TIMEOUT_MS);
  const runId = state.runId;

  state.activeController = controller;
  state.restartRequested = false;
  elements.analyzePageButton.disabled = true;
  startLoadingCycle(
    "AI 분석 중",
    state.extraction.requiresChunking
      ? LONG_ANALYSIS_STEPS
      : SHORT_ANALYSIS_STEPS,
  );

  try {
    const response = await fetch(ANALYSIS_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        pageText: state.extraction.pageText,
        url: state.extraction.url,
        siteName: state.extraction.siteName,
        sourceMeta: {
          url: state.extraction.url,
          siteName: state.extraction.siteName,
          title: state.extraction.title,
        },
      }),
      signal: controller.signal,
    });

    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      const { message, llmResponse } = getApiErrorInfo(
        payload,
        "분석 API 호출에 실패했습니다.",
      );
      const apiError = new Error(message);
      apiError.llmResponse = llmResponse;
      throw apiError;
    }

    if (runId !== state.runId) {
      return;
    }

    stopLoadingCycle();
    setLoadingStep("카드 정리 중", "분석 결과를 웹에서도 볼 수 있게 저장하고 있습니다.");
    state.analysisSessionId = await saveAnalysisSession(payload);
    renderAnalysis(payload);
    setMessage("");
  } catch (error) {
    if (state.restartRequested || runId !== state.runId) {
      return;
    }

    const message = error?.name === "AbortError"
      ? "분석 시간이 너무 오래 걸려 중단했습니다."
      : error?.message || "분석에 실패했습니다.";
    showFailureView("분석하지 못했습니다", message, error?.llmResponse || "");
  } finally {
    state.activeController = null;
    stopLoadingCycle();
    clearTimeout(timeoutId);
    elements.analyzePageButton.disabled = false;
  }
}

async function analyzeCurrentPage() {
  elements.analyzePageButton.disabled = true;
  stopLoadingCycle();
  resetExtractionState();
  const runId = state.runId + 1;
  state.runId = runId;
  showLoadingView("분석 시작", "현재 페이지를 읽을 준비를 하고 있습니다.");

  try {
    await extractCurrentPage(runId);

    if (runId !== state.runId) {
      return;
    }

    if (!state.extraction?.pageText) {
      showFailureView(
        "분석할 원문이 없습니다",
        "현재 페이지에서 읽을 수 있는 예약 조건 텍스트를 찾지 못했습니다.",
      );
      return;
    }

    await analyzeCurrentExtraction();
  } finally {
    elements.analyzePageButton.disabled = false;
  }
}

async function copyExtractedText(event) {
  event?.preventDefault();
  event?.stopPropagation();

  if (!state.extraction?.pageText) {
    return;
  }

  await navigator.clipboard.writeText(state.extraction.pageText);
  setMessage("추출 원문을 복사했습니다.", "success");
}

function openWebDetail() {
  if (!state.analysisSessionId) {
    setMessage("웹에서 볼 분석 결과가 아직 저장되지 않았습니다.", "error");
    return;
  }

  const url = `${WEB_DETAIL_URL}?analysisId=${encodeURIComponent(state.analysisSessionId)}`;
  chrome.tabs.create({ url });
}

function getClientX(event) {
  return event.touches?.[0]?.clientX ?? event.changedTouches?.[0]?.clientX ?? event.clientX;
}

function startCardDrag(event) {
  if (!state.analysis?.cards.length) {
    return;
  }

  if (event.target.closest("summary, input, label, button")) {
    return;
  }

  state.dragStartX = getClientX(event);
  state.dragDeltaX = 0;
  elements.cardStack.dataset.dragging = "true";
}

function moveCardDrag(event) {
  if (state.dragStartX === null) {
    return;
  }

  state.dragDeltaX = getClientX(event) - state.dragStartX;
  updateCardStack();
}

function endCardDrag() {
  if (state.dragStartX === null) {
    return;
  }

  const shouldMove = Math.abs(state.dragDeltaX) > 55;
  const direction = state.dragDeltaX < 0 ? 1 : -1;

  state.dragStartX = null;
  elements.cardStack.dataset.dragging = "false";

  if (shouldMove) {
    const currentCard = state.analysis?.cards[state.activeCardIndex];
    markCardChecked(currentCard?.id);
    goToCard(state.activeCardIndex + direction);
  } else {
    state.dragDeltaX = 0;
    updateCardStack();
  }
}

elements.analyzePageButton.addEventListener("click", analyzeCurrentPage);
elements.restartAnalysisButton.addEventListener("click", restartAnalysisFlow);
elements.retryAnalysisButton.addEventListener("click", analyzeCurrentPage);
elements.copyButton.addEventListener("click", copyExtractedText);
elements.openWebButton.addEventListener("click", openWebDetail);
elements.prevCardButton.addEventListener("click", goToPreviousCard);
elements.nextCardButton.addEventListener("click", goToNextCard);
elements.cardStack.addEventListener("mousedown", startCardDrag);
elements.cardStack.addEventListener("mousemove", moveCardDrag);
elements.cardStack.addEventListener("mouseup", endCardDrag);
elements.cardStack.addEventListener("mouseleave", endCardDrag);
elements.cardStack.addEventListener("touchstart", startCardDrag, { passive: true });
elements.cardStack.addEventListener("touchmove", moveCardDrag, { passive: true });
elements.cardStack.addEventListener("touchend", endCardDrag);

showIdleView();
