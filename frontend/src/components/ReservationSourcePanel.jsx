import React from "react";

function ReservationSourcePanel({ sourceText }) {
  const paragraphs = sourceText
    .trim()
    .split("\n")
    .filter(Boolean);

  return (
    <section className="source-panel" aria-labelledby="source-panel-title">
      <div className="source-panel-header">
        <p className="eyebrow">예약 원문</p>
        <h2 id="source-panel-title">부산 광안리 오션뷰 숙소</h2>
      </div>

      <div className="source-document">
        {paragraphs.map((paragraph) => (
          <p key={paragraph}>{paragraph}</p>
        ))}
      </div>
    </section>
  );
}

export default ReservationSourcePanel;
