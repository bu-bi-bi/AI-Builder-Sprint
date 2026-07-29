import requests
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from modusign.router import router as modusign_router

app = FastAPI(title="서약돋보기 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(modusign_router)

# todo: adding api key to api call does not fuking make sense, needs to find better ways to handle api key. -> maybe .env? idk

# todo : add error handling for the requests.post calls and validate the inputs (url, upstreamApiKey, modusignApiKey, file) before making the API calls.
# todo : add url support for instead of just file upload, so that the user can provide a url to the document instead of uploading it.
@app.post("/contractsParsing")
async def contracts_parsing(
    url: str | None = Form(None),
    upstreamApiKey: str | None = Form(None),
    modusignApiKey: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    contents = await file.read()

    ApiURL = "https://api.upstage.ai/v1/document-digitization"
    headers = {"Authorization": f"Bearer {upstreamApiKey}"}
    files = {
        "document": (file.filename, contents, file.content_type)
    }
    data = {"ocr": "force", "base64_encoding": "['table']", "model": "document-parse"}
    response = requests.post(ApiURL, headers=headers, files=files, data=data)
    return response.json()

# todo : add error handling for the requests.post calls and validate the inputs (url, upstreamApiKey, modusignApiKey, file) before making the API calls.
# todo : add url support for instead of just file upload, so that the user can provide a url to the document instead of uploading it.
@app.post("/contractsParsingOCR")
async def contracts_parsing_ocr(
    url: str | None = Form(None),
    upstreamApiKey: str | None = Form(None),
    modusignApiKey: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    contents = await file.read()

    ApiURL = "https://api.upstage.ai/v1/document-digitization"
    headers = {"Authorization": f"Bearer {upstreamApiKey}"}
    files = {
        "document": (file.filename, contents, file.content_type)
    }
    data = {"model": "ocr"}
    response = requests.post(url, headers=headers, files=files, data=data)
    return response.json()


# test feature for simple AI response using solar-pro2 model, this is a test feature and will be removed in future.
@app.post("/simpleAIResponse")
async def simple_ai_response(
    upstreamApiKey: str | None = Form(None),
    model: str | None = Form("solar-pro2"),
    prompt: str | None = Form(None),
    role: str | None = Form("user")
):
    client = OpenAI(
        api_key=upstreamApiKey,
        base_url="https://api.upstage.ai/v1",
    )
    stream = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": role,
                "content": prompt
            }
        ],
        stream=False,
    )
    return {"content": stream.choices[0].message.content}
