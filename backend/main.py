from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

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


@app.post("/api/analyze-reservation")
async def analyze_reservation(payload: dict):
    page_text = str(payload.get("pageText", "")).strip()

    if not page_text:
        return JSONResponse(
            status_code=400,
            content={"message": "pageText가 필요합니다."},
        )

    return {
        "summary": "예약 조건에서 확인할 수 있는 주요 주의사항을 찾았습니다.",
        "cards": [
            {
                "title": "AI 분석 API 준비 중",
                "level": "medium",
                "plain": "현재 엔드포인트는 FastAPI 연결 확인용 mock 응답을 반환합니다.",
                "question": "실제 Upstage Solar LLM 연결은 다음 단계에서 진행할까요?",
                "source": page_text[:240],
            }
        ],
    }


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

    from openai import OpenAI

    client = OpenAI(
        api_key=upstream_api_key,
        base_url="https://api.upstage.ai/v1",
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
