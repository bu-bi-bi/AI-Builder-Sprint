import React from "react";
import AnalysisResult from "../components/AnalysisResult";
import ReservationSourcePanel from "../components/ReservationSourcePanel";
import {
  mockReservationAnalysis,
  mockReservationText,
} from "../shared/mockReservationAnalysis";

function Home() {
  return (
    <main>
      <section className="app-hero" aria-labelledby="app-title">
        <p className="eyebrow">부산 여행 예약 조건</p>
        <h1 id="app-title">예약 전에 확인할 주의사항</h1>
        <p>
          취소, 환불, 책임, 이용 조건을 원문 근거와 함께 카드로 확인합니다.
        </p>
      </section>

      <div className="demo-layout">
        <ReservationSourcePanel sourceText={mockReservationText} />
        <AnalysisResult analysis={mockReservationAnalysis} />
      </div>
    </main>
  );
}

export default Home;
