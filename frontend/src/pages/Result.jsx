import React, { useEffect, useState } from "react";
import AnalysisChat from "../components/AnalysisChat";
import AnalysisResult from "../components/AnalysisResult";
import ReservationSourcePanel from "../components/ReservationSourcePanel";
import {
  mockReservationAnalysis,
  mockReservationText,
} from "../shared/mockReservationAnalysis";

function Result() {
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const analysisId = new URLSearchParams(window.location.search).get("analysisId");

  useEffect(() => {
    if (!analysisId) {
      setStatus("mock");
      return;
    }

    const controller = new AbortController();

    async function loadSession() {
      setStatus("loading");
      setError("");

      try {
        const response = await fetch(`/api/analysis-sessions/${analysisId}`, {
          signal: controller.signal,
        });
        const payload = await response.json().catch(() => ({}));

        if (!response.ok) {
          const detail = payload?.detail;
          throw new Error(
            typeof detail === "string"
              ? detail
              : "분석 결과를 불러오지 못했습니다.",
          );
        }

        setSession(payload);
        setStatus("ready");
      } catch (loadError) {
        if (loadError?.name === "AbortError") {
          return;
        }

        setError(loadError?.message || "분석 결과를 불러오지 못했습니다.");
        setStatus("error");
      }
    }

    loadSession();

    return () => controller.abort();
  }, [analysisId]);

  const isReady = status === "ready" && session;
  const analysis = isReady ? session.analysis : mockReservationAnalysis;
  const sourceText = isReady ? session.pageText : mockReservationText;
  const sourceTitle = isReady
    ? session.sourceMeta?.title || session.siteName || "예약 원문"
    : "부산 광안리 오션뷰 숙소";
  const shouldShowLayout = isReady || status === "mock";

  return (
    <main>
      <section className="app-hero" aria-labelledby="result-title">
        <p className="eyebrow">부비비 분석 결과</p>
        <h1 id="result-title">
          {isReady ? "저장된 예약 조건 확인" : "예약 조건 확인"}
        </h1>
        {isReady && session.url && (
          <p className="result-source-url">{session.url}</p>
        )}
      </section>

      {status === "loading" && (
        <section className="result-state" role="status">
          분석 결과를 불러오고 있습니다.
        </section>
      )}

      {status === "error" && (
        <section className="result-state result-state-error" role="alert">
          {error}
        </section>
      )}

      {shouldShowLayout && (
        <>
          <div className="demo-layout">
            <ReservationSourcePanel
              sourceText={sourceText}
              title={sourceTitle}
              eyebrow={isReady ? session.siteName || "예약 원문" : "예약 원문"}
            />
            <AnalysisResult
              analysis={analysis}
              eyebrow={isReady ? "AI 분석 결과" : "샘플 분석 결과"}
            />
          </div>

          {isReady && analysisId && (
            <AnalysisChat analysisId={analysisId} />
          )}
        </>
      )}
    </main>
  );
}

export default Result;
