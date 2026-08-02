import { useState } from "react";
import { LEVEL_META } from "../shared/analysisSchema";

function ContractCard({ card, checked = false, onCheckChange }) {
  const [sourceOpen, setSourceOpen] = useState(false);
  const levelMeta = LEVEL_META[card.level] ?? LEVEL_META.medium;

  return (
    <article className={`contract-card contract-card-${card.level}`}>
      <div className="contract-card-header">
        <div>
          <span className={`level-badge level-badge-${card.level}`}>
            {levelMeta.label}
          </span>
          <h3>{card.title}</h3>
        </div>

        <label className="check-control">
          <input
            type="checkbox"
            checked={checked}
            onChange={(event) => onCheckChange?.(event.target.checked)}
          />
          확인
        </label>
      </div>

      <p className="card-description">{levelMeta.description}</p>
      <p>{card.plain}</p>

      <div className="question-box">
        <strong>예약 전에 물어볼 질문</strong>
        <p>{card.question}</p>
      </div>

      <button
        className="source-toggle"
        type="button"
        onClick={() => setSourceOpen((current) => !current)}
      >
        {sourceOpen ? "원문 닫기" : "원문 보기"}
      </button>

      {sourceOpen && (
        <blockquote className="source-text">
          {card.source}
        </blockquote>
      )}
    </article>
  );
}

export default ContractCard;
