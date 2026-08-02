import UploadForm from "../components/UploadForm";
import AnalysisResult from "../components/AnalysisResult";
import { mockReservationAnalysis } from "../shared/mockReservationAnalysis";

function Home() {
  return (
    <main>
      <h1>부산 여행 예약 조건 분석 서비스</h1>

      <p>
        온라인 예약 페이지의 취소, 환불, 책임, 이용 조건을
        쉬운 주의사항 카드로 정리합니다.
      </p>

      <UploadForm />

      <AnalysisResult analysis={mockReservationAnalysis} />
    </main>
  );
}

export default Home;
