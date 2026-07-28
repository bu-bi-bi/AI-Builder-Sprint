
// {
//   "summary": "서약서 전체가 무엇에 관한 것인지 1~2문장 요약",
//   "cards": [
//     {
//       "title": "항목 제목 (예: 사고 책임)",
//       "level": "high | medium | low",
//       "plain": "쉬운 말로 풀어쓴 설명 (2문장 이내)",
//       "question": "업체에 확인하면 좋을 질문 한 문장",
//       "source": "이 카드가 근거한 원문 문장을 그대로 발췌"
//     }
//   ]
// }

function ContractCard( { summary, card } ) {
    return (
        <div className="contract-card">
            <h3>요약</h3>
            <p>{summary}</p>
            <h3>분석 카드</h3>
            <div className="card">
                <h4>{card.title}</h4>
                <p>레벨: {card.level}</p>
                <p>{card.plain}</p>
                <p>질문: {card.question}</p>
                <p>출처: {card.source}</p>
            </div>
        </div>
    )
}