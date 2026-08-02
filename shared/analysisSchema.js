export const ANALYSIS_LEVELS = ["high", "medium", "low"];

export const DEFAULT_ANALYSIS_LEVEL = "medium";

export const LEVEL_META = {
  high: {
    label: "중요",
    tone: "red",
    description: "예약 결정에 큰 영향을 줄 수 있는 항목",
  },
  medium: {
    label: "확인",
    tone: "yellow",
    description: "예약 전에 한 번 더 확인하면 좋은 항목",
  },
  low: {
    label: "참고",
    tone: "green",
    description: "기본 안내 또는 참고용 항목",
  },
};

const REQUIRED_CARD_FIELDS = ["title", "level", "plain", "question", "source"];

export function isAnalysisLevel(level) {
  return ANALYSIS_LEVELS.includes(level);
}

export function normalizeLevel(level) {
  return isAnalysisLevel(level) ? level : DEFAULT_ANALYSIS_LEVEL;
}

export function normalizeText(value, fallback = "") {
  if (typeof value !== "string") {
    return fallback;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : fallback;
}

export function createEmptyAnalysisResult() {
  return {
    summary: "",
    cards: [],
  };
}

export function validateAnalysisResult(value) {
  const issues = [];

  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return [
      {
        path: "root",
        message: "분석 결과는 객체여야 합니다.",
      },
    ];
  }

  if (typeof value.summary !== "string" || value.summary.trim().length === 0) {
    issues.push({
      path: "summary",
      message: "summary는 비어 있지 않은 문자열이어야 합니다.",
    });
  }

  if (!Array.isArray(value.cards)) {
    issues.push({
      path: "cards",
      message: "cards는 배열이어야 합니다.",
    });

    return issues;
  }

  if (value.cards.length === 0) {
    issues.push({
      path: "cards",
      message: "최소 1개 이상의 카드가 필요합니다.",
    });
  }

  value.cards.forEach((card, index) => {
    if (!card || typeof card !== "object" || Array.isArray(card)) {
      issues.push({
        path: `cards.${index}`,
        message: "카드는 객체여야 합니다.",
      });
      return;
    }

    REQUIRED_CARD_FIELDS.forEach((field) => {
      if (typeof card[field] !== "string" || card[field].trim().length === 0) {
        issues.push({
          path: `cards.${index}.${field}`,
          message: `${field}는 비어 있지 않은 문자열이어야 합니다.`,
        });
      }
    });

    if (typeof card.level === "string" && !isAnalysisLevel(card.level)) {
      issues.push({
        path: `cards.${index}.level`,
        message: `level은 ${ANALYSIS_LEVELS.join(", ")} 중 하나여야 합니다.`,
      });
    }
  });

  return issues;
}

export function normalizeAnalysisResult(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {
      result: createEmptyAnalysisResult(),
      issues: validateAnalysisResult(value),
    };
  }

  const cards = Array.isArray(value.cards)
    ? value.cards.map((card, index) => ({
        id: normalizeText(card?.id, `card-${index + 1}`),
        title: normalizeText(card?.title, "확인할 예약 조건"),
        level: normalizeLevel(card?.level),
        plain: normalizeText(
          card?.plain,
          "이 항목은 예약 전에 내용을 한 번 더 확인하는 것이 좋습니다.",
        ),
        question: normalizeText(
          card?.question,
          "예약 전에 이 조건이 어떻게 적용되는지 확인할 수 있을까요?",
        ),
        source: normalizeText(
          card?.source,
          "원문 근거를 찾지 못했습니다.",
        ),
      }))
    : [];

  return {
    result: {
      summary: normalizeText(
        value.summary,
        "예약 조건에서 확인할 내용을 찾았습니다.",
      ),
      cards,
    },
    issues: validateAnalysisResult(value),
  };
}
