const state = {
  extraction: null,
};

const SOURCE_PREVIEW_LIMIT = 50000;

const elements = {
  extractButton: document.getElementById("extractButton"),
  copyButton: document.getElementById("copyButton"),
  statusBadge: document.getElementById("statusBadge"),
  messageBox: document.getElementById("messageBox"),
  metaPanel: document.getElementById("metaPanel"),
  siteName: document.getElementById("siteName"),
  adapterName: document.getElementById("adapterName"),
  textLength: document.getElementById("textLength"),
  sourceText: document.getElementById("sourceText"),
};

function setStatus(text, tone = "idle") {
  elements.statusBadge.textContent = text;
  elements.statusBadge.dataset.tone = tone;
}

function setMessage(message, tone = "info") {
  elements.messageBox.textContent = message;
  elements.messageBox.dataset.tone = tone;
  elements.messageBox.hidden = !message;
}

function formatNumber(value) {
  return new Intl.NumberFormat("ko-KR").format(value || 0);
}

function renderExtraction(extraction) {
  state.extraction = extraction;
  const isPreview = extraction.pageText?.length > SOURCE_PREVIEW_LIMIT;
  const previewText = isPreview
    ? `${extraction.pageText.slice(0, SOURCE_PREVIEW_LIMIT)}\n\n[미리보기는 여기까지입니다. 분석/복사는 전체 원문을 사용합니다.]`
    : extraction.pageText;

  elements.metaPanel.hidden = false;
  elements.siteName.textContent = extraction.siteName || "알 수 없음";
  elements.adapterName.textContent = extraction.adapter || "generic";
  elements.textLength.textContent = `${formatNumber(extraction.textLength)}자`;
  elements.sourceText.textContent =
    previewText || "분석할 수 있는 텍스트를 찾지 못했습니다.";
  elements.copyButton.disabled = !extraction.pageText;
}

async function extractCurrentPage() {
  elements.extractButton.disabled = true;
  elements.copyButton.disabled = true;
  setStatus("추출 중", "loading");
  setMessage("");

  try {
    const response = await chrome.runtime.sendMessage({
      type: "GET_CURRENT_TAB_TEXT",
    });

    if (!response?.ok) {
      throw new Error(response?.error || "현재 페이지를 읽지 못했습니다.");
    }

    renderExtraction(response.result);
    setStatus("완료", "success");
    setMessage("현재 페이지의 예약 관련 텍스트를 가져왔습니다.", "success");
  } catch (error) {
    setStatus("실패", "error");
    setMessage(error?.message || "텍스트 추출에 실패했습니다.", "error");
  } finally {
    elements.extractButton.disabled = false;
  }
}

async function copyExtractedText() {
  if (!state.extraction?.pageText) {
    return;
  }

  await navigator.clipboard.writeText(state.extraction.pageText);
  setMessage("추출 원문을 복사했습니다.", "success");
}

elements.extractButton.addEventListener("click", extractCurrentPage);
elements.copyButton.addEventListener("click", copyExtractedText);
