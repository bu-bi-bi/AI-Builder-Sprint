import React from "react";

function ReservationSourcePanel({
  sourceText,
  title = "예약 원문",
  eyebrow = "예약 원문",
}) {
  const paragraphs = String(sourceText || "")
    .trim()
    .split("\n")
    .filter(Boolean);

  return (
    <section className="source-panel" aria-labelledby="source-panel-title">
      <div className="source-panel-header">
        <p className="eyebrow">{eyebrow}</p>
        <h2 id="source-panel-title">{title}</h2>
      </div>

      <div className="source-document">
        {paragraphs.length > 0
          ? paragraphs.map((paragraph, index) => (
              <p key={`${index}-${paragraph.slice(0, 20)}`}>{paragraph}</p>
            ))
          : <p>표시할 원문이 없습니다.</p>}
      </div>
    </section>
  );
}

export default ReservationSourcePanel;
