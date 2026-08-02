const CONTENT_SCRIPT_FILES = [
  "src/adapters/genericAdapter.js",
  "src/adapters/targetSiteAdapter.js",
  "src/contentScript.js",
];

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab?.id) {
    return;
  }

  await chrome.sidePanel.open({ tabId: tab.id });
});

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({
    active: true,
    currentWindow: true,
  });

  return tab;
}

async function injectContentScripts(tabId) {
  await chrome.scripting.executeScript({
    target: { tabId },
    files: CONTENT_SCRIPT_FILES,
  });
}

async function requestPageExtraction(tab) {
  try {
    return await chrome.tabs.sendMessage(tab.id, {
      type: "EXTRACT_RESERVATION_TEXT",
    });
  } catch (error) {
    await injectContentScripts(tab.id);
    return chrome.tabs.sendMessage(tab.id, {
      type: "EXTRACT_RESERVATION_TEXT",
    });
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "GET_CURRENT_TAB_TEXT") {
    return false;
  }

  getActiveTab()
    .then((tab) => {
      if (!tab?.id || !tab.url || tab.url.startsWith("chrome://")) {
        throw new Error("현재 페이지에서는 텍스트를 가져올 수 없습니다.");
      }

      return requestPageExtraction(tab);
    })
    .then((result) => {
      sendResponse({ ok: true, result });
    })
    .catch((error) => {
      sendResponse({
        ok: false,
        error: error?.message || "페이지 텍스트 추출에 실패했습니다.",
      });
    });

  return true;
});
