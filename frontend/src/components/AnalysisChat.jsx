import React, { useMemo, useState } from "react";

const STARTER_QUESTIONS = [
  "가장 조심해야 할 조건이 뭐야?",
  "환불이나 취소에서 더 확인할 게 있어?",
  "업체에 어떤 질문을 하면 좋을까?",
];

function getApiErrorMessage(payload, fallback) {
  const detail = payload?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (detail && typeof detail === "object") {
    return detail.message || detail.repairError || detail.firstError || fallback;
  }

  return fallback;
}

function AnalysisChat({ analysisId }) {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  const apiHistory = useMemo(
    () =>
      messages
        .filter((message) => message.role === "user" || message.role === "assistant")
        .map((message) => ({
          role: message.role,
          content: message.content,
        })),
    [messages],
  );

  async function sendQuestion(nextQuestion = question) {
    const trimmedQuestion = nextQuestion.trim();

    if (!trimmedQuestion || status === "loading") {
      return;
    }

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmedQuestion,
    };

    setMessages((current) => [...current, userMessage]);
    setQuestion("");
    setStatus("loading");
    setError("");

    try {
      const response = await fetch(`/api/analysis-sessions/${analysisId}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: trimmedQuestion,
          history: apiHistory.slice(-8),
        }),
      });
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(getApiErrorMessage(payload, "채팅 답변을 만들지 못했습니다."));
      }

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: payload.answer,
          sourceQuotes: payload.sourceQuotes || [],
          followUpQuestions: payload.followUpQuestions || [],
          disclaimer: payload.disclaimer,
        },
      ]);
      setStatus("idle");
    } catch (sendError) {
      setError(sendError?.message || "채팅 답변을 만들지 못했습니다.");
      setStatus("error");
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    sendQuestion();
  }

  return (
    <section className="analysis-chat" aria-labelledby="analysis-chat-title">
      <div className="analysis-chat-header">
        <p className="eyebrow">후속 질문</p>
        <h2 id="analysis-chat-title">위험을 더 자세히 물어보기</h2>
        <p>
          저장된 분석 카드와 원문을 바탕으로, 이해가 안 되는 조건을 더 물어볼 수 있습니다.
        </p>
      </div>

      {messages.length === 0 && (
        <div className="chat-starters" aria-label="추천 질문">
          {STARTER_QUESTIONS.map((starter) => (
            <button
              key={starter}
              type="button"
              onClick={() => sendQuestion(starter)}
              disabled={status === "loading"}
            >
              {starter}
            </button>
          ))}
        </div>
      )}

      <div className="chat-thread" aria-live="polite">
        {messages.map((message) => (
          <article
            key={message.id}
            className={`chat-message chat-message-${message.role}`}
          >
            <p>{message.content}</p>

            {message.sourceQuotes?.length > 0 && (
              <details className="chat-sources">
                <summary>근거 원문</summary>
                {message.sourceQuotes.map((quote, index) => (
                  <blockquote key={`${index}-${quote.slice(0, 16)}`}>
                    {quote}
                  </blockquote>
                ))}
              </details>
            )}

            {message.disclaimer && (
              <p className="chat-disclaimer">{message.disclaimer}</p>
            )}

            {message.followUpQuestions?.length > 0 && (
              <div className="chat-followups">
                {message.followUpQuestions.map((followUp) => (
                  <button
                    key={followUp}
                    type="button"
                    onClick={() => sendQuestion(followUp)}
                    disabled={status === "loading"}
                  >
                    {followUp}
                  </button>
                ))}
              </div>
            )}
          </article>
        ))}

        {status === "loading" && (
          <article className="chat-message chat-message-assistant">
            <p>원문과 분석 카드를 다시 확인하고 있습니다.</p>
          </article>
        )}
      </div>

      {error && (
        <p className="chat-error" role="alert">
          {error}
        </p>
      )}

      <form className="chat-form" onSubmit={handleSubmit}>
        <label htmlFor="analysisChatInput">질문</label>
        <div>
          <input
            id="analysisChatInput"
            type="text"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="예: 이 취소 조건이 왜 위험해?"
            disabled={status === "loading"}
          />
          <button type="submit" disabled={status === "loading" || !question.trim()}>
            보내기
          </button>
        </div>
      </form>
    </section>
  );
}

export default AnalysisChat;
