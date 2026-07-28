import requests
from fastapi import FastAPI

app = FastAPI()

app.frontend("/", directory="../dist")


@app.post("/contractsAnalyze")
async def contracts_analyze():
    formData = await requests.request.form()
    print ("Received form data:", formData)
    return {"message": "Form data received successfully"}