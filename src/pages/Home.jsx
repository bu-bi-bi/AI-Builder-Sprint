import UploadForm from "../components/UploadForm";

function Home() {
  return (
    <main>
      <h1>해양 레저 계약 분석 서비스</h1>

      <p>
        URL 또는 계약서를 업로드하면
        불공평한 계약 조항을 분석합니다.
      </p>

      <UploadForm />
    </main>
  );
}

export default Home;