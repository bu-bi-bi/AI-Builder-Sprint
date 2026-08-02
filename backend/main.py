import base64
import json
import os
import requests
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
UPSTAGE_BASE_URL = "https://api.upstage.ai/v1"
UPSTAGE_MODEL = "solar-pro3"
DIRECT_ANALYSIS_CHAR_LIMIT = 50_000
CHUNK_CHAR_LIMIT = 45_000
CHUNK_ANALYSIS_CONCURRENCY = 3
MAX_TOTAL_INPUT_CHARS = 300_000
MAX_ANALYSIS_SESSIONS = 50
LLM_ERROR_PREVIEW_CHARS = 4_000
CHAT_CONTEXT_CHAR_LIMIT = 60_000
CHAT_HISTORY_LIMIT = 8
MODUSIGN_API_BASE_URL = os.getenv("MODUSIGN_API_BASE_URL", "https://api.modusign.co.kr")
MODUSIGN_REQUEST_TIMEOUT = 20
ANALYSIS_SESSIONS: dict[str, dict[str, Any]] = {}


def load_env_file() -> None:
    env_file = PROJECT_ROOT / ".env"

    if not env_file.exists():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()


class ReservationSourceMeta(BaseModel):
    url: str | None = None
    siteName: str | None = None
    title: str | None = None


class AnalyzeReservationRequest(BaseModel):
    pageText: str = Field(..., min_length=1)
    url: str | None = None
    siteName: str | None = None
    sourceMeta: ReservationSourceMeta | None = None


class AnalysisCard(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)
    level: Literal["high", "medium", "low"]
    plain: str = Field(..., min_length=1, max_length=260)
    question: str = Field(..., min_length=1, max_length=180)
    source: str = Field(..., min_length=1, max_length=500)


class ReservationAnalysis(BaseModel):
    summary: str = Field(..., min_length=1, max_length=280)
    cards: list[AnalysisCard] = Field(..., min_length=1, max_length=6)


class ChunkReservationAnalysis(BaseModel):
    summary: str = Field(..., min_length=1, max_length=280)
    cards: list[AnalysisCard] = Field(default_factory=list, max_length=3)


class AnalysisSessionCreate(BaseModel):
    analysis: ReservationAnalysis
    pageText: str = Field(..., min_length=1, max_length=MAX_TOTAL_INPUT_CHARS)
    url: str | None = None
    siteName: str | None = None
    sourceMeta: ReservationSourceMeta | None = None


class AnalysisSessionResponse(BaseModel):
    analysisId: str
    analysis: ReservationAnalysis
    pageText: str
    url: str | None = None
    siteName: str | None = None
    sourceMeta: ReservationSourceMeta | None = None
    createdAt: str


class AnalysisChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class AnalysisChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    history: list[AnalysisChatMessage] = Field(default_factory=list, max_length=CHAT_HISTORY_LIMIT)


class AnalysisChatResponse(BaseModel):
    answer: str = Field(..., min_length=1)
    sourceQuotes: list[str] = Field(default_factory=list, max_length=4)
    followUpQuestions: list[str] = Field(default_factory=list, max_length=3)
    disclaimer: str = Field(..., min_length=1)


class ModusignSigningRequest(BaseModel):
    signerName: str = Field(..., min_length=2, max_length=30)
    signerContact: str = Field(..., min_length=3, max_length=100)
    signingMethod: Literal["EMAIL", "KAKAO", "SECURE_LINK"] = "EMAIL"
    requesterMessage: str | None = Field(default=None, max_length=1000)


class ModusignSigningResponse(BaseModel):
    mode: Literal["live", "demo"]
    documentId: str
    title: str
    status: str
    signingUrl: str | None = None
    embeddedUrl: str | None = None
    message: str
    createdAt: str


app = FastAPI(title="Busan Reservation Guard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {
        "ok": True,
        "service": "Busan Reservation Guard API",
        "frontendDist": FRONTEND_DIST.exists(),
        "upstageConfigured": bool(os.getenv("UPSTAGE_API_KEY")),
        "directAnalysisCharLimit": DIRECT_ANALYSIS_CHAR_LIMIT,
        "chunkCharLimit": CHUNK_CHAR_LIMIT,
        "chunkAnalysisConcurrency": CHUNK_ANALYSIS_CONCURRENCY,
        "maxTotalInputChars": MAX_TOTAL_INPUT_CHARS,
        "modusignConfigured": is_modusign_configured(),
        "modusignTemplateConfigured": bool(os.getenv("MODUSIGN_TEMPLATE_ID")),
    }


@app.post("/contractsParsing")
async def contracts_parsing_legacy():
    return JSONResponse(
        status_code=410,
        content={
            "message": "파일 업로드/OCR 기반 계약 파싱은 현재 제품 방향에서 제외되었습니다.",
            "nextEndpoint": "/api/analyze-reservation",
        },
    )


@app.post("/contractsParsingOCR")
async def contracts_parsing_ocr_legacy():
    return JSONResponse(
        status_code=410,
        content={
            "message": "OCR 기반 계약 파싱은 현재 제품 방향에서 제외되었습니다.",
            "nextEndpoint": "/api/analyze-reservation",
        },
    )


def get_upstage_client() -> OpenAI:
    api_key = os.getenv("UPSTAGE_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="UPSTAGE_API_KEY 환경변수가 필요합니다.",
        )

    return OpenAI(
        api_key=api_key,
        base_url=UPSTAGE_BASE_URL,
        timeout=30,
    )


def build_reservation_analysis_schema(
    min_cards: int = 1,
    max_cards: int = 6,
) -> dict[str, Any]:
    return {
        "name": "reservation_analysis",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "예약 조건 전체가 무엇에 관한 것인지 1~2문장으로 요약",
                },
                "cards": {
                    "type": "array",
                    "description": f"예약 전에 확인하면 좋은 핵심 조건 카드. {min_cards}~{max_cards}개.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "항목 제목",
                            },
                            "level": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "주의 수준",
                            },
                            "plain": {
                                "type": "string",
                                "description": "쉬운 한국어 설명. 2문장 이내.",
                            },
                            "question": {
                                "type": "string",
                                "description": "예약 전에 업체에 확인하면 좋은 질문 1문장",
                            },
                            "source": {
                                "type": "string",
                                "description": "카드의 근거가 되는 원문 구절. 1~2문장만 그대로 발췌.",
                            },
                        },
                        "required": [
                            "title",
                            "level",
                            "plain",
                            "question",
                            "source",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["summary", "cards"],
            "additionalProperties": False,
        },
    }


def build_analysis_chat_schema() -> dict[str, Any]:
    return {
        "name": "analysis_chat_answer",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "사용자 질문에 대한 쉬운 한국어 답변",
                },
                "sourceQuotes": {
                    "type": "array",
                    "description": "답변 근거가 되는 원문 구절. 원문에 없으면 빈 배열.",
                    "items": {"type": "string"},
                    "maxItems": 4,
                },
                "followUpQuestions": {
                    "type": "array",
                    "description": "사용자가 이어서 물어볼 만한 질문",
                    "items": {"type": "string"},
                    "maxItems": 3,
                },
                "disclaimer": {
                    "type": "string",
                    "description": "AI 답변 한계에 대한 짧은 고지",
                },
            },
            "required": [
                "answer",
                "sourceQuotes",
                "followUpQuestions",
                "disclaimer",
            ],
            "additionalProperties": False,
        },
    }


def build_analysis_messages(request: AnalyzeReservationRequest) -> list[dict[str, str]]:
    source_label = request.siteName
    source_url = request.url

    if request.sourceMeta:
        source_label = source_label or request.sourceMeta.siteName
        source_url = source_url or request.sourceMeta.url

    context_lines = []

    if source_label:
        context_lines.append(f"예약 사이트/출처: {source_label}")

    if source_url:
        context_lines.append(f"예약 URL: {source_url}")

    context = "\n".join(context_lines) if context_lines else "예약 사이트/출처: 알 수 없음"

    system_prompt = """
너는 부산 여행객이 온라인 예약 조건을 이해하도록 돕는 AI다.
법률 판단, 유불리 단정, 업체 비난을 하지 않는다.
원문에 없는 내용을 추가하지 않는다.
사용자가 예약 전에 확인해야 할 조건을 쉬운 한국어 카드로 정리한다.
각 카드는 반드시 근거 원문을 source에 그대로 발췌한다.
source는 가능한 한 입력 원문에 실제로 존재하는 문장 또는 연속 구절이어야 한다.
source는 1~2문장만 사용하고, 긴 조항 전체를 붙이지 않는다.
중요 카드만 선별하고 cards는 최대 6개로 제한한다.
plain은 2문장 이내로 작성한다.
question은 업체나 예약처에 확인할 수 있는 자연스러운 질문 1문장으로 작성한다.
level 기준:
- high: 환불 불가, 취소 수수료, 노쇼, 추가 결제, 사고/분실 책임, 이용 제한처럼 예약 결정에 큰 영향을 줄 수 있는 항목
- medium: 체크인/이용 시간, 변경 조건, 준비물, 보험/보증금, 현장 결제처럼 확인이 필요한 항목
- low: 일반 안내, 위치, 문의 방법, 기본 준비 안내처럼 참고용 항목
""".strip()

    user_prompt = f"""
다음 온라인 예약 페이지 텍스트를 분석해 JSON 스키마에 맞게 응답해줘.

{context}

[예약 페이지 원문]
{request.pageText.strip()}
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_chunk_analysis_messages(
    request: AnalyzeReservationRequest,
    chunk: str,
    chunk_index: int,
    total_chunks: int,
) -> list[dict[str, str]]:
    source_label = request.siteName
    source_url = request.url

    if request.sourceMeta:
        source_label = source_label or request.sourceMeta.siteName
        source_url = source_url or request.sourceMeta.url

    context_lines = [
        f"예약 사이트/출처: {source_label or '알 수 없음'}",
        f"전체 chunk: {total_chunks}개 중 {chunk_index + 1}번째",
    ]

    if source_url:
        context_lines.append(f"예약 URL: {source_url}")

    system_prompt = """
너는 긴 온라인 예약 조건 원문을 chunk 단위로 1차 검토하는 AI다.
이 단계에서는 최종 결론을 만들지 말고, 현재 chunk 안에서만 예약 전에 확인할 만한 후보 카드를 추출한다.
원문에 없는 내용을 추가하지 않는다.
법률 판단, 유불리 단정, 업체 비난을 하지 않는다.
source는 반드시 현재 chunk 안에 실제로 존재하는 짧은 문장 또는 연속 구절을 그대로 발췌한다.
source는 1~2문장만 사용하고, 긴 조항 전체를 붙이지 않는다.
cards는 최대 3개만 반환한다. 중요 후보가 없으면 빈 배열을 반환한다.
plain은 2문장 이내로 작성한다.
level 기준:
- high: 환불 불가, 취소 수수료, 노쇼, 추가 결제, 사고/분실 책임, 이용 제한처럼 예약 결정에 큰 영향을 줄 수 있는 항목
- medium: 체크인/이용 시간, 변경 조건, 준비물, 보험/보증금, 현장 결제처럼 확인이 필요한 항목
- low: 일반 안내, 위치, 문의 방법, 기본 준비 안내처럼 참고용 항목
""".strip()

    user_prompt = f"""
다음은 긴 예약/약관 원문의 일부입니다. 현재 chunk 안에서만 후보 카드를 JSON 스키마에 맞게 추출해줘.

{chr(10).join(context_lines)}

[예약 페이지 원문 chunk]
{chunk}
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_final_merge_messages(
    request: AnalyzeReservationRequest,
    chunk_results: list[ChunkReservationAnalysis],
) -> list[dict[str, str]]:
    source_label = request.siteName
    source_url = request.url

    if request.sourceMeta:
        source_label = source_label or request.sourceMeta.siteName
        source_url = source_url or request.sourceMeta.url

    candidates = []

    for result_index, result in enumerate(chunk_results):
        for card in result.cards:
            candidates.append(
                {
                    "chunk": result_index + 1,
                    "title": card.title,
                    "level": card.level,
                    "plain": card.plain,
                    "question": card.question,
                    "source": card.source,
                }
            )

    system_prompt = """
너는 chunk별로 추출된 예약 조건 후보를 최종 사용자 카드로 병합하는 AI다.
중복 후보를 합치고, 예약 결정에 중요한 항목을 우선해 최대 6개의 카드를 만든다.
원문에 없는 내용을 추가하지 않는다.
법률 판단, 유불리 단정, 업체 비난을 하지 않는다.
source는 후보 카드의 source 문구 중 하나를 그대로 사용하거나, 서로 인접한 같은 원문 근거만 짧게 합쳐서 사용한다.
source는 1~2문장만 사용하고, 긴 조항 전체를 붙이지 않는다.
부산 여행객이 예약 전에 확인할 수 있는 쉬운 한국어로 작성한다.
plain은 2문장 이내로 작성한다.
""".strip()

    user_prompt = f"""
다음은 긴 예약/약관 원문을 chunk별로 분석한 후보 카드 목록입니다.
최종 결과 JSON 스키마에 맞춰 summary와 cards를 만들어줘.

예약 사이트/출처: {source_label or '알 수 없음'}
예약 URL: {source_url or '알 수 없음'}

[후보 카드 JSON]
{json.dumps(candidates, ensure_ascii=False)}
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_analysis_chat_messages(
    session: dict[str, Any],
    request: AnalysisChatRequest,
) -> list[dict[str, str]]:
    source_text = (session.get("pageText") or "").strip()
    source_excerpt = source_text[:CHAT_CONTEXT_CHAR_LIMIT]
    truncated_note = (
        "\n[안내: 원문이 길어 앞부분 일부만 채팅 컨텍스트에 포함되었습니다.]"
        if len(source_text) > CHAT_CONTEXT_CHAR_LIMIT
        else ""
    )
    history = [
        message.model_dump()
        for message in request.history[-CHAT_HISTORY_LIMIT:]
    ]

    system_prompt = """
너는 부비비의 예약 조건 후속 질문 AI다.
부산 여행객이 이미 확인한 예약 조건 카드에 대해 더 자세히 이해하도록 돕는다.
법률 자문, 법적 판단, 승소 가능성, 업체 비난, 유불리 단정을 하지 않는다.
제공된 분석 카드와 원문 안에서 확인되는 내용만 근거로 답한다.
원문에서 확인할 수 없는 정보는 추측하지 말고 "제공된 원문만으로는 확인하기 어렵다"고 말한다.
답변은 쉬운 한국어로 작성하고, 사용자가 예약처에 확인할 수 있는 행동을 제안한다.
sourceQuotes에는 제공된 원문 또는 카드 source에 실제로 있는 구절만 넣는다.
설명, 마크다운, 코드블록 없이 JSON 객체만 출력한다.
""".strip()

    user_prompt = f"""
다음 분석 세션을 바탕으로 사용자의 후속 질문에 답해줘.

[출처]
사이트: {session.get("siteName") or "알 수 없음"}
URL: {session.get("url") or "알 수 없음"}
제목: {(session.get("sourceMeta") or {}).get("title") or "알 수 없음"}

[분석 카드 JSON]
{json.dumps(session.get("analysis"), ensure_ascii=False)}

[예약 원문 일부]
{source_excerpt}{truncated_note}

[이전 대화 JSON]
{json.dumps(history, ensure_ascii=False)}

[사용자 질문]
{request.question.strip()}
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def split_text_into_chunks(text: str, max_chars: int = CHUNK_CHAR_LIMIT) -> list[str]:
    lines = [line.strip() for line in text.splitlines()]
    chunks: list[str] = []
    current_lines: list[str] = []
    current_length = 0

    def flush_current() -> None:
        nonlocal current_lines, current_length

        if current_lines:
            chunks.append("\n".join(current_lines).strip())
            current_lines = []
            current_length = 0

    for line in lines:
        if not line:
            continue

        if len(line) > max_chars:
            flush_current()

            for start in range(0, len(line), max_chars):
                chunks.append(line[start : start + max_chars])

            continue

        next_length = current_length + len(line) + 1

        if current_lines and next_length > max_chars:
            flush_current()

        current_lines.append(line)
        current_length += len(line) + 1

    flush_current()

    return [chunk for chunk in chunks if chunk]


def validate_analysis_result(
    raw_result: Any,
    allow_empty_cards: bool = False,
) -> ReservationAnalysis | ChunkReservationAnalysis:
    normalized_result = normalize_analysis_payload(
        raw_result,
        max_cards=3 if allow_empty_cards else 6,
    )

    try:
        model = ChunkReservationAnalysis if allow_empty_cards else ReservationAnalysis
        analysis = model.model_validate(normalized_result)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "LLM 응답이 분석 스키마와 맞지 않습니다.",
                "errors": exc.errors(),
            },
        ) from exc

    if not allow_empty_cards and not analysis.cards:
        raise HTTPException(
            status_code=502,
            detail="LLM 응답에 카드가 없습니다.",
        )

    return analysis


def clamp_text(value: Any, max_length: int) -> Any:
    if not isinstance(value, str):
        return value

    text = " ".join(value.split()).strip()

    if len(text) <= max_length:
        return text

    clipped = text[:max_length].rstrip()
    sentence_end = max(
        clipped.rfind("."),
        clipped.rfind("?"),
        clipped.rfind("!"),
        clipped.rfind("。"),
        clipped.rfind("다."),
        clipped.rfind("요."),
    )

    if sentence_end >= max_length * 0.45:
        clipped = clipped[: sentence_end + 1].rstrip()

    return clipped


def normalize_analysis_payload(raw_result: Any, max_cards: int) -> Any:
    if not isinstance(raw_result, dict):
        return raw_result

    normalized = {
        **raw_result,
        "summary": clamp_text(raw_result.get("summary"), 280),
    }
    raw_cards = raw_result.get("cards")

    if not isinstance(raw_cards, list):
        return normalized

    cards = []

    for card in raw_cards[:max_cards]:
        if not isinstance(card, dict):
            cards.append(card)
            continue

        cards.append(
            {
                **card,
                "title": clamp_text(card.get("title"), 80),
                "plain": clamp_text(card.get("plain"), 260),
                "question": clamp_text(card.get("question"), 180),
                "source": clamp_text(card.get("source"), 500),
            }
        )

    normalized["cards"] = cards
    return normalized


def parse_json_content(content: str | None) -> Any:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM 응답이 비어 있습니다.")

    stripped = content.strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()

    for start, character in enumerate(stripped):
        if character not in "{[":
            continue

        try:
            raw_result, _ = decoder.raw_decode(stripped[start:])
            return raw_result
        except json.JSONDecodeError:
            continue

    raise ValueError("LLM 응답에서 JSON 객체를 찾지 못했습니다.")


def parse_and_validate_analysis_content(
    content: str | None,
    allow_empty_cards: bool = False,
) -> ReservationAnalysis | ChunkReservationAnalysis:
    preview = (content or "")[:LLM_ERROR_PREVIEW_CHARS]

    try:
        raw_result = parse_json_content(content)
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "LLM 응답을 JSON으로 파싱할 수 없습니다.",
                "llmResponsePreview": preview,
            },
        ) from exc

    try:
        return validate_analysis_result(
            raw_result,
            allow_empty_cards=allow_empty_cards,
        )
    except HTTPException as exc:
        detail = exc.detail

        if isinstance(detail, dict):
            detail = {
                **detail,
                "llmResponsePreview": preview,
            }

        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


def parse_and_validate_chat_content(content: str | None) -> AnalysisChatResponse:
    preview = (content or "")[:LLM_ERROR_PREVIEW_CHARS]

    try:
        raw_result = parse_json_content(content)
        return AnalysisChatResponse.model_validate(raw_result)
    except (ValueError, ValidationError) as exc:
        detail: dict[str, Any] = {
            "message": "LLM 채팅 응답을 JSON 스키마로 파싱할 수 없습니다.",
            "llmResponsePreview": preview,
        }

        if isinstance(exc, ValidationError):
            detail["errors"] = exc.errors()

        raise HTTPException(status_code=502, detail=detail) from exc


def create_structured_completion(
    client: OpenAI,
    messages: list[dict[str, str]],
    max_tokens: int = 1800,
    json_schema: dict[str, Any] | None = None,
) -> str | None:
    schema = json_schema or build_reservation_analysis_schema()

    try:
        response = client.chat.completions.create(
            model=UPSTAGE_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
            reasoning_effort="low",
            response_format={
                "type": "json_schema",
                "json_schema": schema,
            },
        )
    except OpenAIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Upstage Solar LLM 호출에 실패했습니다: {exc}",
        ) from exc

    return response.choices[0].message.content


def build_json_repair_messages(
    invalid_content: str | None,
    error_detail: Any,
    max_cards: int = 6,
) -> list[dict[str, str]]:
    content_preview = (invalid_content or "")[:12_000]

    system_prompt = """
너는 JSON 복구기다.
설명, 사과, 마크다운, 코드블록 없이 JSON 객체만 출력한다.
출력은 반드시 summary와 cards만 가진 객체여야 한다.
cards의 각 항목은 title, level, plain, question, source만 가진다.
cards는 반드시 허용 개수 이하로 줄인다.
level은 high, medium, low 중 하나만 사용한다.
source는 1~2문장, 500자 이하로 짧게 줄인다.
원문 근거가 불확실하면 새 내용을 만들지 말고 기존 응답 안의 근거 문구를 사용한다.
""".strip()

    user_prompt = f"""
아래 응답은 예약 조건 분석 결과였지만 JSON 파싱 또는 스키마 검증에 실패했다.
동일한 의미를 유지하면서 유효한 JSON 객체 하나로만 다시 작성해줘.
cards는 최대 {max_cards}개만 남겨줘. 중요도가 높은 항목을 우선하고 나머지는 버려.
summary는 280자 이하, title은 80자 이하, plain은 260자 이하, question은 180자 이하, source는 500자 이하로 작성해줘.

[검증 오류]
{json.dumps(error_detail, ensure_ascii=False, default=str)}

[이전 응답]
{content_preview}
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_chat_json_repair_messages(
    invalid_content: str | None,
    error_detail: Any,
) -> list[dict[str, str]]:
    content_preview = (invalid_content or "")[:12_000]

    system_prompt = """
너는 부비비 채팅 응답 JSON 복구기다.
설명, 사과, 마크다운, 코드블록 없이 JSON 객체만 출력한다.
출력은 반드시 answer, sourceQuotes, followUpQuestions, disclaimer만 가진 객체여야 한다.
sourceQuotes와 followUpQuestions는 문자열 배열이다.
""".strip()

    user_prompt = f"""
아래 응답은 채팅 답변이었지만 JSON 파싱 또는 스키마 검증에 실패했다.
동일한 의미를 유지하면서 유효한 JSON 객체 하나로만 다시 작성해줘.

[검증 오류]
{json.dumps(error_detail, ensure_ascii=False, default=str)}

[이전 응답]
{content_preview}
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def request_structured_analysis(
    client: OpenAI,
    messages: list[dict[str, str]],
    max_tokens: int = 1800,
    allow_empty_cards: bool = False,
) -> ReservationAnalysis | ChunkReservationAnalysis:
    max_cards = 3 if allow_empty_cards else 6
    analysis_schema = build_reservation_analysis_schema(
        min_cards=0 if allow_empty_cards else 1,
        max_cards=max_cards,
    )
    content = create_structured_completion(
        client=client,
        messages=messages,
        max_tokens=max_tokens,
        json_schema=analysis_schema,
    )

    try:
        return parse_and_validate_analysis_content(
            content,
            allow_empty_cards=allow_empty_cards,
        )
    except HTTPException as first_error:
        repair_content = create_structured_completion(
            client=client,
            messages=build_json_repair_messages(
                content,
                first_error.detail,
                max_cards=max_cards,
            ),
            max_tokens=max_tokens,
            json_schema=analysis_schema,
        )

        try:
            return parse_and_validate_analysis_content(
                repair_content,
                allow_empty_cards=allow_empty_cards,
            )
        except HTTPException as repair_error:
            repair_detail = repair_error.detail
            first_detail = first_error.detail
            first_preview = None
            repair_preview = None

            if isinstance(repair_detail, dict):
                repair_preview = repair_detail.get("llmResponsePreview")
                repair_detail = repair_detail.get("message", repair_detail)

            if isinstance(first_detail, dict):
                first_preview = first_detail.get("llmResponsePreview")
                first_detail = first_detail.get("message", first_detail)

            raise HTTPException(
                status_code=502,
                detail={
                    "message": "LLM 응답을 JSON 스키마로 복구하지 못했습니다.",
                    "firstError": first_detail,
                    "repairError": repair_detail,
                    "llmResponsePreview": repair_preview or first_preview,
                    "firstLlmResponsePreview": first_preview,
                    "repairLlmResponsePreview": repair_preview,
                },
            ) from repair_error


def request_analysis_chat(
    client: OpenAI,
    session: dict[str, Any],
    request: AnalysisChatRequest,
) -> AnalysisChatResponse:
    messages = build_analysis_chat_messages(session, request)
    content = create_structured_completion(
        client=client,
        messages=messages,
        max_tokens=1200,
        json_schema=build_analysis_chat_schema(),
    )

    try:
        return parse_and_validate_chat_content(content)
    except HTTPException as first_error:
        repair_content = create_structured_completion(
            client=client,
            messages=build_chat_json_repair_messages(content, first_error.detail),
            max_tokens=1200,
            json_schema=build_analysis_chat_schema(),
        )

        try:
            return parse_and_validate_chat_content(repair_content)
        except HTTPException as repair_error:
            repair_detail = repair_error.detail
            first_detail = first_error.detail
            first_preview = None
            repair_preview = None

            if isinstance(repair_detail, dict):
                repair_preview = repair_detail.get("llmResponsePreview")
                repair_detail = repair_detail.get("message", repair_detail)

            if isinstance(first_detail, dict):
                first_preview = first_detail.get("llmResponsePreview")
                first_detail = first_detail.get("message", first_detail)

            raise HTTPException(
                status_code=502,
                detail={
                    "message": "LLM 채팅 응답을 JSON 스키마로 복구하지 못했습니다.",
                    "firstError": first_detail,
                    "repairError": repair_detail,
                    "llmResponsePreview": repair_preview or first_preview,
                },
            ) from repair_error


def analyze_chunked_reservation(
    client: OpenAI,
    request: AnalyzeReservationRequest,
) -> ReservationAnalysis:
    chunks = split_text_into_chunks(request.pageText)

    if not chunks:
        raise HTTPException(status_code=400, detail="pageText가 필요합니다.")

    def analyze_single_chunk(index: int, chunk: str) -> tuple[int, ChunkReservationAnalysis]:
        analysis = request_structured_analysis(
            client=client,
            messages=build_chunk_analysis_messages(
                request=request,
                chunk=chunk,
                chunk_index=index,
                total_chunks=len(chunks),
            ),
            max_tokens=1800,
            allow_empty_cards=True,
        )

        return index, analysis

    indexed_results: list[tuple[int, ChunkReservationAnalysis]] = []
    max_workers = min(CHUNK_ANALYSIS_CONCURRENCY, len(chunks))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(analyze_single_chunk, index, chunk)
            for index, chunk in enumerate(chunks)
        ]

        for future in as_completed(futures):
            indexed_results.append(future.result())

    indexed_results.sort(key=lambda item: item[0])
    chunk_results = [result for _, result in indexed_results if result.cards]

    if not chunk_results:
        raise HTTPException(
            status_code=502,
            detail="긴 원문에서 분석할 예약 조건 후보를 찾지 못했습니다.",
        )

    return request_structured_analysis(
        client=client,
        messages=build_final_merge_messages(request, chunk_results),
        max_tokens=1800,
    )


def prune_analysis_sessions() -> None:
    overflow = len(ANALYSIS_SESSIONS) - MAX_ANALYSIS_SESSIONS

    if overflow <= 0:
        return

    oldest_ids = sorted(
        ANALYSIS_SESSIONS,
        key=lambda analysis_id: ANALYSIS_SESSIONS[analysis_id]["createdAt"],
    )[:overflow]

    for analysis_id in oldest_ids:
        ANALYSIS_SESSIONS.pop(analysis_id, None)


def is_modusign_configured() -> bool:
    return bool(
        os.getenv("MODUSIGN_TEMPLATE_ID")
        and (
            os.getenv("MODUSIGN_BASIC_AUTH")
            or os.getenv("MODUSIGN_AUTH_HEADER")
            or os.getenv("MODUSIGN_ACCESS_TOKEN")
        )
    )


def get_modusign_headers() -> dict[str, str]:
    auth_header = os.getenv("MODUSIGN_AUTH_HEADER")

    if os.getenv("MODUSIGN_BASIC_AUTH"):
        basic_auth = os.getenv("MODUSIGN_BASIC_AUTH", "").strip()

        if ":" in basic_auth:
            basic_auth = base64.b64encode(basic_auth.encode("utf-8")).decode("ascii")

        authorization = f"Basic {basic_auth}"
    elif auth_header:
        authorization = auth_header.strip()

        if not authorization.lower().startswith(("bearer ", "basic ")):
            authorization = f"Bearer {authorization}"
    elif os.getenv("MODUSIGN_ACCESS_TOKEN"):
        authorization = f"Bearer {os.getenv('MODUSIGN_ACCESS_TOKEN')}"
    else:
        raise HTTPException(
            status_code=503,
            detail="모두싸인 인증 환경변수가 필요합니다.",
        )

    return {
        "Authorization": authorization,
        "Content-Type": "application/json",
    }


def compact_checked_cards(analysis: dict[str, Any]) -> str:
    cards = analysis.get("cards") if isinstance(analysis, dict) else []

    if not isinstance(cards, list):
        return ""

    lines = []

    for index, card in enumerate(cards[:6], start=1):
        if not isinstance(card, dict):
            continue

        title = clamp_text(card.get("title"), 80) or "주의사항"
        level = card.get("level") or "medium"
        plain = clamp_text(card.get("plain"), 180) or ""
        question = clamp_text(card.get("question"), 140) or ""
        lines.append(f"{index}. [{level}] {title} - {plain} 확인 질문: {question}")

    return "\n".join(lines)[:1000]


def build_modusign_prefill_fields(
    session: dict[str, Any],
    confirmed_at: str,
) -> list[dict[str, Any]]:
    field_map = {
        "MODUSIGN_FIELD_ANALYSIS_SUMMARY": {
            "defaultLabel": "분석요약",
            "value": clamp_text(session.get("analysis", {}).get("summary"), 900),
        },
        "MODUSIGN_FIELD_SOURCE_URL": {
            "defaultLabel": "예약URL",
            "value": clamp_text(session.get("url") or "알 수 없음", 900),
        },
        "MODUSIGN_FIELD_SOURCE_TITLE": {
            "defaultLabel": "예약출처",
            "value": clamp_text(
                (session.get("sourceMeta") or {}).get("title")
                or session.get("siteName")
                or "예약 원문",
                900,
            ),
        },
        "MODUSIGN_FIELD_CHECKED_CARDS": {
            "defaultLabel": "확인카드",
            "value": compact_checked_cards(session.get("analysis", {})),
        },
        "MODUSIGN_FIELD_CONFIRMED_AT": {
            "defaultLabel": "확인시각",
            "value": confirmed_at,
        },
        "MODUSIGN_FIELD_NOTICE": {
            "defaultLabel": "AI고지",
            "value": (
                "AI를 통해 생성된 카드들입니다. 위 내용은 AI를 통해 불리할 수 있는 "
                "내용들을 요약한 것이며 AI가 찾지 못한 정보 또한 존재할 수 있습니다."
            ),
        },
    }
    requester_inputs = []

    for env_key, field in field_map.items():
        data_label = os.getenv(env_key) or field["defaultLabel"]
        value = field["value"]

        if data_label and value:
            requester_inputs.append(
                {
                    "dataLabel": data_label,
                    "value": str(value)[:1000],
                }
            )

    return requester_inputs


def build_modusign_requester_inputs(
    session: dict[str, Any],
    confirmed_at: str,
) -> list[dict[str, Any]]:
    return build_modusign_prefill_fields(session, confirmed_at)


def build_modusign_participant_field_mappings(
    session: dict[str, Any],
    confirmed_at: str,
) -> list[dict[str, Any]]:
    return [
        {
            "dataLabel": field["dataLabel"],
            "excluded": False,
            "prefilledValue": field["value"],
        }
        for field in build_modusign_prefill_fields(session, confirmed_at)
    ]


def build_modusign_document_payload(
    session: dict[str, Any],
    payload: ModusignSigningRequest,
    confirmed_at: str,
) -> dict[str, Any]:
    template_id = os.getenv("MODUSIGN_TEMPLATE_ID")

    if not template_id:
        raise HTTPException(
            status_code=503,
            detail="MODUSIGN_TEMPLATE_ID 환경변수가 필요합니다.",
        )

    title = clamp_text(
        f"부비비 예약 조건 확인서 - {session.get('siteName') or '예약'}",
        100,
    )
    participant_role = os.getenv("MODUSIGN_PARTICIPANT_ROLE", "여행객")
    field_mapping_target = os.getenv(
        "MODUSIGN_FIELD_MAPPING_TARGET",
        "participant",
    ).strip().lower()
    participant_mapping = {
        "role": participant_role,
        "name": payload.signerName,
        "signingMethod": {
            "type": payload.signingMethod,
            "value": payload.signerContact,
        },
        "signingDuration": int(os.getenv("MODUSIGN_SIGNING_DURATION", "20160")),
        "requesterMessage": payload.requesterMessage
        or "부비비에서 확인한 예약 조건 확인서입니다.",
        "locale": "ko",
    }

    if field_mapping_target != "requester":
        participant_mapping["fieldMappings"] = build_modusign_participant_field_mappings(
            session=session,
            confirmed_at=confirmed_at,
        )

    document = {
        "templateId": template_id,
        "document": {
            "title": title,
            "participantMappings": [participant_mapping],
            "auditTrail": {"locales": ["ko"]},
            "metadatas": [
                {"key": "service", "value": "bubibi"},
                {"key": "analysisId", "value": session["analysisId"][:80]},
                {"key": "siteName", "value": (session.get("siteName") or "unknown")[:80]},
                {"key": "confirmedAt", "value": confirmed_at[:80]},
            ],
            "seal": {
                "integritySeal": {
                    "enabled": True,
                    "position": "TOP_RIGHT",
                }
            },
        },
    }

    if field_mapping_target == "requester":
        document["document"]["requesterInputMappings"] = build_modusign_requester_inputs(
            session=session,
            confirmed_at=confirmed_at,
        )

    return document


def modusign_request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_url = os.getenv("MODUSIGN_API_BASE_URL", MODUSIGN_API_BASE_URL).rstrip("/")
    url = f"{base_url}{path}"

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=get_modusign_headers(),
            json=json_body,
            params=params,
            timeout=MODUSIGN_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"모두싸인 API 호출에 실패했습니다: {exc}",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "모두싸인 API가 오류를 반환했습니다.",
                "requestPath": path,
                "statusCode": response.status_code,
                "responsePreview": response.text[:1000],
            },
        )

    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="모두싸인 API 응답을 JSON으로 읽지 못했습니다.",
        ) from exc


def create_demo_modusign_response(
    session: dict[str, Any],
    payload: ModusignSigningRequest,
    confirmed_at: str,
) -> ModusignSigningResponse:
    document_id = f"demo-{session['analysisId'][:12]}"

    return ModusignSigningResponse(
        mode="demo",
        documentId=document_id,
        title=f"부비비 예약 조건 확인서 - {session.get('siteName') or '예약'}",
        status="READY",
        signingUrl=None,
        embeddedUrl=None,
        createdAt=confirmed_at,
        message=(
            f"{payload.signerName}님의 확인서 흐름을 준비했습니다. "
            "MODUSIGN_TEMPLATE_ID와 인증 환경변수를 설정하면 실제 모두싸인 요청으로 전환됩니다."
        ),
    )


def create_live_modusign_response(
    session: dict[str, Any],
    payload: ModusignSigningRequest,
    confirmed_at: str,
) -> ModusignSigningResponse:
    document_payload = build_modusign_document_payload(
        session=session,
        payload=payload,
        confirmed_at=confirmed_at,
    )
    document = modusign_request(
        "POST",
        "/documents/request-with-template",
        json_body=document_payload,
    )
    document_id = document.get("id")

    if not document_id:
        raise HTTPException(
            status_code=502,
            detail="모두싸인 문서 ID를 응답에서 찾지 못했습니다.",
        )

    embedded_url = None
    participants = document.get("participants")

    if payload.signingMethod == "SECURE_LINK" and isinstance(participants, list) and participants:
        participant_id = participants[0].get("id")

        if participant_id:
            redirect_url = os.getenv("MODUSIGN_REDIRECT_URL")
            participant_view = modusign_request(
                "GET",
                f"/documents/{document_id}/participants/{participant_id}/embedded-view",
                params={"redirectUrl": redirect_url} if redirect_url else None,
            )
            embedded_url = participant_view.get("embeddedUrl")

    return ModusignSigningResponse(
        mode="live",
        documentId=document_id,
        title=document.get("title") or document_payload["document"]["title"],
        status=document.get("status") or "ON_GOING",
        signingUrl=embedded_url,
        embeddedUrl=embedded_url,
        createdAt=confirmed_at,
        message=(
            "모두싸인 서명 요청을 만들었습니다."
            if embedded_url
            else "모두싸인 서명 요청을 만들었습니다. 이메일/카카오 방식은 모두싸인 알림으로 서명이 진행됩니다."
        ),
    )


@app.post("/api/analyze-reservation")
def analyze_reservation(payload: AnalyzeReservationRequest):
    request = payload.model_copy(update={"pageText": payload.pageText.strip()})

    if not request.pageText:
        raise HTTPException(status_code=400, detail="pageText가 필요합니다.")

    if len(request.pageText) > MAX_TOTAL_INPUT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=(
                f"pageText는 최대 {MAX_TOTAL_INPUT_CHARS:,}자까지 분석할 수 있습니다. "
                "더 긴 페이지는 원문을 나누어 요청해야 합니다."
            ),
        )

    client = get_upstage_client()

    if len(request.pageText) <= DIRECT_ANALYSIS_CHAR_LIMIT:
        analysis = request_structured_analysis(
            client=client,
            messages=build_analysis_messages(request),
        )
    else:
        analysis = analyze_chunked_reservation(client, request)

    return analysis.model_dump()


@app.post("/api/analysis-sessions", response_model=AnalysisSessionResponse)
def create_analysis_session(payload: AnalysisSessionCreate):
    analysis_id = uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    session = {
        "analysisId": analysis_id,
        "analysis": payload.analysis.model_dump(),
        "pageText": payload.pageText.strip(),
        "url": payload.url,
        "siteName": payload.siteName,
        "sourceMeta": payload.sourceMeta.model_dump() if payload.sourceMeta else None,
        "createdAt": created_at,
    }

    ANALYSIS_SESSIONS[analysis_id] = session
    prune_analysis_sessions()

    return session


@app.get("/api/analysis-sessions/{analysis_id}", response_model=AnalysisSessionResponse)
def get_analysis_session(analysis_id: str):
    session = ANALYSIS_SESSIONS.get(analysis_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="분석 세션을 찾을 수 없습니다.",
        )

    return session


@app.post(
    "/api/analysis-sessions/{analysis_id}/chat",
    response_model=AnalysisChatResponse,
)
def chat_with_analysis_session(analysis_id: str, payload: AnalysisChatRequest):
    session = ANALYSIS_SESSIONS.get(analysis_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="분석 세션을 찾을 수 없습니다.",
        )

    client = get_upstage_client()
    return request_analysis_chat(client, session, payload)


@app.post(
    "/api/analysis-sessions/{analysis_id}/modusign-signing-request",
    response_model=ModusignSigningResponse,
)
def create_modusign_signing_request(
    analysis_id: str,
    payload: ModusignSigningRequest,
):
    session = ANALYSIS_SESSIONS.get(analysis_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="분석 세션을 찾을 수 없습니다.",
        )

    confirmed_at = datetime.now(timezone.utc).isoformat()

    if not is_modusign_configured():
        return create_demo_modusign_response(
            session=session,
            payload=payload,
            confirmed_at=confirmed_at,
        )

    return create_live_modusign_response(
        session=session,
        payload=payload,
        confirmed_at=confirmed_at,
    )


@app.post("/simpleAIResponse")
async def simple_ai_response(payload: dict):
    upstream_api_key = payload.get("upstreamApiKey")
    model = payload.get("model", "solar-pro2")
    prompt = payload.get("prompt")
    role = payload.get("role", "user")

    if not upstream_api_key or not prompt:
        return JSONResponse(
            status_code=400,
            content={"message": "upstreamApiKey와 prompt가 필요합니다."},
        )

    client = OpenAI(
        api_key=upstream_api_key,
        base_url=UPSTAGE_BASE_URL,
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": role, "content": prompt}],
        stream=False,
    )
    return {"content": response.choices[0].message.content}


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{path:path}")
async def serve_frontend(path: str):
    index_file = FRONTEND_DIST / "index.html"

    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse(
        status_code=503,
        content={
            "message": "frontend/dist가 없습니다. frontend에서 npm.cmd run build를 먼저 실행하세요.",
        },
    )
