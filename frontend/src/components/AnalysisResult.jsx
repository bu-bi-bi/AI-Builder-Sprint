import { useMemo, useState } from "react";
import { normalizeAnalysisResult } from "../shared/analysisSchema";
import ContractCard from "./ContractCard";

function AnalysisResult({ analysis }) {
  const { result, issues } = useMemo(
    () => normalizeAnalysisResult(analysis),
    [analysis],
  );
  const [checkedCards, setCheckedCards] = useState({});

  const checkedCount = result.cards.filter((card) => checkedCards[card.id]).length;
  const allChecked = result.cards.length > 0 && checkedCount === result.cards.length;

  const handleCheckChange = (cardId, checked) => {
    setCheckedCards((current) => ({
      ...current,
      [cardId]: checked,
    }));
  };

  return (
    <section className="analysis-result" aria-labelledby="analysis-title">
      <div className="analysis-summary">
        <p className="eyebrow">샘플 분석 결과</p>
        <h2 id="analysis-title">예약 전에 확인할 내용</h2>
        <p>{result.summary}</p>
      </div>

      {issues.length > 0 && (
        <div className="analysis-warning" role="status">
          <strong>스키마 확인 필요</strong>
          <ul>
            {issues.map((issue) => (
              <li key={`${issue.path}-${issue.message}`}>
                {issue.path}: {issue.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="analysis-card-list">
        {result.cards.map((card) => (
          <ContractCard
            key={card.id}
            card={card}
            checked={Boolean(checkedCards[card.id])}
            onCheckChange={(checked) => handleCheckChange(card.id, checked)}
          />
        ))}
      </div>

      <div className="analysis-confirmation">
        <span>
          {checkedCount}/{result.cards.length}개 확인
        </span>
        <strong>{allChecked ? "모든 주의사항을 확인했습니다." : "카드를 하나씩 확인해 주세요."}</strong>
      </div>
    </section>
  );
}

export default AnalysisResult;
