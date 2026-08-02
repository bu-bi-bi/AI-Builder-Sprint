import json
import os
from pathlib import Path
from typing import Any, Literal

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
    title: str = Field(..., min_length=1)
    level: Literal["high", "medium", "low"]
    plain: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)


class ReservationAnalysis(BaseModel):
    summary: str = Field(..., min_length=1)
    cards: list[AnalysisCard] = Field(..., min_length=1, max_length=6)

app = FastAPI(title="Busan Reservation Guard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
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


def build_reservation_analysis_schema() -> dict[str, Any]:
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
                    "description": "예약 전에 확인하면 좋은 핵심 조건 카드. 최대 6개.",
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
                                "description": "카드의 근거가 되는 원문 문장 그대로 발췌",
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


def validate_analysis_result(raw_result: Any) -> ReservationAnalysis:
    try:
        analysis = ReservationAnalysis.model_validate(raw_result)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "LLM 응답이 분석 스키마와 맞지 않습니다.",
                "errors": exc.errors(),
            },
        ) from exc

    if not analysis.cards:
        raise HTTPException(
            status_code=502,
            detail="LLM 응답에 카드가 없습니다.",
        )

    return analysis


@app.post("/api/analyze-reservation")
async def analyze_reservation(payload: AnalyzeReservationRequest):
    request = payload.model_copy(update={"pageText": payload.pageText.strip()})

    if not request.pageText:
        raise HTTPException(status_code=400, detail="pageText가 필요합니다.")

    client = get_upstage_client()

    try:
        response = client.chat.completions.create(
            model=UPSTAGE_MODEL,
            messages=build_analysis_messages(request),
            temperature=0.2,
            max_tokens=1800,
            reasoning_effort="low",
            response_format={
                "type": "json_schema",
                "json_schema": build_reservation_analysis_schema(),
            },
        )
    except OpenAIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Upstage Solar LLM 호출에 실패했습니다: {exc}",
        ) from exc

    content = response.choices[0].message.content

    try:
        raw_result = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "LLM 응답을 JSON으로 파싱할 수 없습니다.",
                "content": content,
            },
        ) from exc

    analysis = validate_analysis_result(raw_result)
    return analysis.model_dump()


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
