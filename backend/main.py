import requests
from fastapi import FastAPI, File, Form, UploadFile

app = FastAPI()

app.frontend("/", directory="../dist")

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