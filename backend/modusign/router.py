from typing import Any

from fastapi import APIRouter, Depends, File, Query, UploadFile

from modusign.client import ModusignClient
from modusign.dependencies import get_modusign_api_key_from_form, get_modusign_api_key_from_header
from modusign.schemas import (
    EmbeddedDraftRequestBody,
    EmbeddedSignRequestBody,
    SignRequestBody,
    TemplateSignRequestBody,
)

router = APIRouter(prefix="/modusign", tags=["modusign"])


def _client(api_key: str = Depends(get_modusign_api_key_from_header)) -> ModusignClient:
    return ModusignClient(api_key)


def _build_document_payload(body: SignRequestBody) -> dict[str, Any]:
    document: dict[str, Any] = {
        "title": body.title,
        "participantMappings": [
            {
                "role": participant.role,
                "name": participant.name,
                "signingMethod": participant.signingMethod.model_dump(),
                **(
                    {"requesterMessage": participant.requesterMessage}
                    if participant.requesterMessage
                    else {}
                ),
                **(
                    {"signingDuration": participant.signingDuration}
                    if participant.signingDuration is not None
                    else {}
                ),
            }
            for participant in body.participants
        ],
    }

    if body.requesterInputMappings:
        document["requesterInputMappings"] = body.requesterInputMappings
    if body.metadatas:
        document["metadatas"] = body.metadatas
    if body.labelIds:
        document["labelIds"] = body.labelIds

    return document


@router.post("/sign/request")
def create_sign_request(
    body: SignRequestBody,
    client: ModusignClient = Depends(_client),
) -> dict[str, Any]:
    """템플릿 기반 서명 요청 (여행객 → 업체 순차 서명용)."""
    payload = {
        "templateId": body.templateId,
        "document": _build_document_payload(body),
    }
    return client.request_with_template(payload)


@router.post("/sign/embedded")
def create_embedded_sign_request(
    body: EmbeddedSignRequestBody,
    client: ModusignClient = Depends(_client),
) -> dict[str, Any]:
    """템플릿 기반 임베디드 서명 초안 생성 (웹앱 내 서명 화면)."""
    payload: dict[str, Any] = {
        "templateId": body.templateId,
        "document": _build_document_payload(body),
    }
    if body.redirectUrl:
        payload["redirectUrl"] = body.redirectUrl
    return client.create_embedded_draft_with_template(payload)


@router.post("/documents/request-with-template")
def request_with_template(
    body: TemplateSignRequestBody,
    client: ModusignClient = Depends(_client),
) -> dict[str, Any]:
    """모두싸인 API: POST /documents/request-with-template 프록시."""
    payload = body.model_dump(exclude_none=True)
    return client.request_with_template(payload)


@router.post("/embedded-drafts/create-with-template")
def create_embedded_draft_with_template(
    body: EmbeddedDraftRequestBody,
    client: ModusignClient = Depends(_client),
) -> dict[str, Any]:
    """모두싸인 API: POST /embedded-drafts/create-with-template 프록시."""
    payload = body.model_dump(exclude_none=True)
    return client.create_embedded_draft_with_template(payload)


@router.get("/documents")
def list_documents(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    filter: str | None = Query(default=None, alias="filter"),
    orderBy: str | None = Query(default=None),
    metadatas: str | None = Query(default=None),
    client: ModusignClient = Depends(_client),
) -> dict[str, Any]:
    """모두싸인 API: GET /documents 프록시."""
    return client.list_documents(
        offset=offset,
        limit=limit,
        filter_query=filter,
        order_by=orderBy,
        metadatas=metadatas,
    )


@router.get("/documents/{document_id}")
def get_document(
    document_id: str,
    client: ModusignClient = Depends(_client),
) -> dict[str, Any]:
    """모두싸인 API: GET /documents/{documentId} 프록시."""
    return client.get_document(document_id)


@router.get("/documents/{document_id}/participants/{participant_id}/embedded-view")
def get_embedded_participant_view(
    document_id: str,
    participant_id: str,
    redirectUrl: str | None = Query(default=None),
    client: ModusignClient = Depends(_client),
) -> dict[str, Any]:
    """모두싸인 API: 임베디드 서명자 보안 링크 조회."""
    return client.get_embedded_participant_view(
        document_id,
        participant_id,
        redirect_url=redirectUrl,
    )


@router.get("/documents/{document_id}/embedded-view")
def get_embedded_document_view(
    document_id: str,
    redirectUrl: str | None = Query(default=None),
    client: ModusignClient = Depends(_client),
) -> dict[str, Any]:
    """모두싸인 API: 임베디드 문서 보기 URL 조회."""
    return client.get_embedded_document_view(document_id, redirect_url=redirectUrl)


@router.post("/documents/{document_id}/cancel")
def cancel_document(
    document_id: str,
    body: dict[str, Any] | None = None,
    client: ModusignClient = Depends(_client),
) -> dict[str, Any]:
    """모두싸인 API: POST /documents/{documentId}/cancel 프록시."""
    return client.cancel_document(document_id, body)


@router.post("/files")
async def upload_file(
    type: str = Query(..., pattern="^(document|attachment)$"),
    file: UploadFile = File(...),
    api_key: str = Depends(get_modusign_api_key_from_form),
) -> dict[str, Any]:
    """모두싸인 API: POST /files 프록시 (문서/첨부파일 사전 업로드)."""
    client = ModusignClient(api_key)
    contents = await file.read()
    return client.upload_file(
        file_type=type,
        filename=file.filename or "upload.bin",
        content=contents,
        content_type=file.content_type or "application/octet-stream",
    )
