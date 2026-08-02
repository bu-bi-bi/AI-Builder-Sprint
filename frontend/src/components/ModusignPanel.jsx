import React, { useMemo, useState } from "react";

const contactPlaceholders = {
  EMAIL: "name@example.com",
  KAKAO: "01012345678",
  SECURE_LINK: "name@example.com",
};

function ModusignPanel({ analysisId, confirmation }) {
  const [form, setForm] = useState({
    signerName: "",
    signerContact: "",
    signingMethod: "EMAIL",
  });
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [errorDetail, setErrorDetail] = useState(null);

  const canRequest = Boolean(
    analysisId
      && confirmation?.allChecked
      && form.signerName.trim()
      && form.signerContact.trim(),
  );
  const progressLabel = useMemo(() => {
    const checked = confirmation?.checkedCount || 0;
    const total = confirmation?.totalCount || 0;

    return `${checked}/${total}개 확인`;
  }, [confirmation]);

  const updateForm = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  };

  const submitSigningRequest = async (event) => {
    event.preventDefault();

    if (!canRequest) {
      return;
    }

    setStatus("loading");
    setError("");
    setErrorDetail(null);
    setResult(null);

    try {
      const response = await fetch(
        `/api/analysis-sessions/${analysisId}/modusign-signing-request`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            signerName: form.signerName.trim(),
            signerContact: form.signerContact.trim(),
            signingMethod: form.signingMethod,
          }),
        },
      );
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        const detail = payload?.detail;
        const message = typeof detail === "string"
          ? detail
          : detail?.message || "모두싸인 요청을 만들지 못했습니다.";
        setErrorDetail(typeof detail === "object" ? detail : null);
        throw new Error(message);
      }

      setResult(payload);
      setStatus("ready");
    } catch (submitError) {
      setError(submitError?.message || "모두싸인 요청을 만들지 못했습니다.");
      setStatus("error");
    }
  };

  return (
    <section className="modusign-panel" aria-labelledby="modusign-title">
      <div className="modusign-header">
        <p className="eyebrow">모두싸인 확인서</p>
        <h2 id="modusign-title">확인한 예약 조건을 남겨두기</h2>
        <p>
          카드를 모두 확인하면 부비비 분석 결과와 출처를 바탕으로 확인서 서명 요청을 만들 수 있습니다.
        </p>
      </div>

      <div className="modusign-status">
        <span>{progressLabel}</span>
        <strong>
          {confirmation?.allChecked
            ? "서명 요청을 만들 수 있습니다."
            : "모든 카드를 먼저 확인해 주세요."}
        </strong>
      </div>

      <form className="modusign-form" onSubmit={submitSigningRequest}>
        <div>
          <label htmlFor="signerName">이름</label>
          <input
            id="signerName"
            name="signerName"
            value={form.signerName}
            onChange={updateForm}
            placeholder="홍길동"
            autoComplete="name"
          />
        </div>

        <div>
          <label htmlFor="signingMethod">서명 방식</label>
          <select
            id="signingMethod"
            name="signingMethod"
            value={form.signingMethod}
            onChange={updateForm}
          >
            <option value="EMAIL">이메일</option>
            <option value="KAKAO">카카오</option>
            <option value="SECURE_LINK">보안 링크</option>
          </select>
        </div>

        <div>
          <label htmlFor="signerContact">연락처</label>
          <input
            id="signerContact"
            name="signerContact"
            value={form.signerContact}
            onChange={updateForm}
            placeholder={contactPlaceholders[form.signingMethod]}
            autoComplete="email"
          />
        </div>

        <button type="submit" disabled={!canRequest || status === "loading"}>
          {status === "loading" ? "요청 생성 중" : "모두싸인 확인서 만들기"}
        </button>
      </form>

      {status === "error" && (
        <div className="modusign-error" role="alert">
          <p>{error}</p>
          {errorDetail && (
            <details>
              <summary>오류 상세 보기</summary>
              <pre>
                {JSON.stringify(
                  {
                    requestPath: errorDetail.requestPath,
                    statusCode: errorDetail.statusCode,
                    responsePreview: errorDetail.responsePreview,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
          )}
        </div>
      )}

      {result && (
        <div className="modusign-result" role="status">
          <div>
            <strong>{result.title}</strong>
            <span>
              {result.mode === "demo" ? "데모 모드" : "실제 요청"} · {result.status}
            </span>
          </div>
          <p>{result.message}</p>
          {(result.embeddedUrl || result.signingUrl) && (
            <a
              href={result.embeddedUrl || result.signingUrl}
              target="_blank"
              rel="noreferrer"
            >
              모두싸인에서 열기
            </a>
          )}
        </div>
      )}
    </section>
  );
}

export default ModusignPanel;
