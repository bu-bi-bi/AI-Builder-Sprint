import React from "react";
import AnalysisResult from "../components/AnalysisResult";
import ReservationSourcePanel from "../components/ReservationSourcePanel";
import {
  mockReservationAnalysis,
  mockReservationText,
} from "../shared/mockReservationAnalysis";

function Result() {
  return (
    <main>
      <section className="app-hero" aria-labelledby="result-title">
        <p className="eyebrow">분석 결과</p>
        <h1 id="result-title">예약 조건 확인</h1>
      </section>

      <div className="demo-layout">
        <ReservationSourcePanel sourceText={mockReservationText} />
        <AnalysisResult analysis={mockReservationAnalysis} />
      </div>
    </main>
  );
}

export default Result;
