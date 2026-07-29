import os

from fastapi import Form, Header, HTTPException


def resolve_modusign_api_key(
    *,
    header_key: str | None = None,
    form_key: str | None = None,
) -> str:
    api_key = header_key or form_key or os.getenv("MODUSIGN_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Modusign API key가 필요합니다. X-Modusign-Api-Key 헤더, modusignApiKey 필드, 또는 MODUSIGN_API_KEY 환경변수를 설정하세요.",
        )
    return api_key


def get_modusign_api_key_from_header(
    x_modusign_api_key: str | None = Header(default=None, alias="X-Modusign-Api-Key"),
) -> str:
    return resolve_modusign_api_key(header_key=x_modusign_api_key)


def get_modusign_api_key_from_form(
    modusignApiKey: str | None = Form(default=None),
    x_modusign_api_key: str | None = Header(default=None, alias="X-Modusign-Api-Key"),
) -> str:
    return resolve_modusign_api_key(header_key=x_modusign_api_key, form_key=modusignApiKey)
