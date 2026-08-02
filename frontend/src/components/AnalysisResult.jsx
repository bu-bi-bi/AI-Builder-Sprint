import React, { useEffect, useMemo, useState } from "react";
import { EffectCards } from "swiper/modules";
import { Swiper, SwiperSlide } from "swiper/react";
import "swiper/css";
import "swiper/css/effect-cards";
import { normalizeAnalysisResult } from "../shared/analysisSchema";
import ContractCard from "./ContractCard";

function AnalysisResult({
  analysis,
  eyebrow = "샘플 분석 결과",
  title = "예약 전에 확인할 내용",
}) {
  const { result, issues } = useMemo(
    () => normalizeAnalysisResult(analysis),
    [analysis],
  );
  const [checkedCards, setCheckedCards] = useState({});
  const [activeCardIndex, setActiveCardIndex] = useState(0);

  const checkedCount = result.cards.filter((card) => checkedCards[card.id]).length;
  const allChecked = result.cards.length > 0 && checkedCount === result.cards.length;

  useEffect(() => {
    setCheckedCards({});
    setActiveCardIndex(0);
  }, [analysis]);

  const handleCheckChange = (cardId, checked) => {
    setCheckedCards((current) => ({
      ...current,
      [cardId]: checked,
    }));
  };

  return (
    <section className="analysis-result" aria-labelledby="analysis-title">
      <div className="analysis-summary">
        <p className="eyebrow">{eyebrow}</p>
        <h2 id="analysis-title">{title}</h2>
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

      <div className="analysis-card-deck" aria-label="예약 주의사항 카드">
        {activeCardIndex === 0 && result.cards.length > 1 && (
          <div className="swipe-hint" aria-hidden="true">
            <span className="swipe-arrow">←</span>
            <span>왼쪽으로 밀어 다음 카드 보기</span>
          </div>
        )}

        <Swiper
          effect="cards"
          grabCursor
          modules={[EffectCards]}
          className="reservation-card-swiper"
          onSlideChange={(swiper) => setActiveCardIndex(swiper.activeIndex)}
          cardsEffect={{
            perSlideOffset: 12,
            perSlideRotate: 3,
            rotate: true,
            slideShadows: false,
          }}
        >
          {result.cards.map((card) => (
            <SwiperSlide key={card.id}>
              <ContractCard
                card={card}
                checked={Boolean(checkedCards[card.id])}
                onCheckChange={(checked) => handleCheckChange(card.id, checked)}
              />
            </SwiperSlide>
          ))}
        </Swiper>
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
