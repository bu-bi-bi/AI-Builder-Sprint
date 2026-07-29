from typing import Any, Literal

from pydantic import BaseModel, Field


class SigningMethod(BaseModel):
    type: Literal["EMAIL", "KAKAO", "SECURE_LINK"]
    value: str = Field(..., description="이메일 또는 휴대전화번호")


class ParticipantInput(BaseModel):
    role: str = Field(..., description="템플릿에 설정된 참여자 역할")
    name: str = Field(..., min_length=2, max_length=30)
    signingMethod: SigningMethod
    requesterMessage: str | None = None
    signingDuration: int | None = Field(default=20160, ge=60, le=525600)


class SignRequestBody(BaseModel):
    templateId: str
    title: str = Field(..., min_length=1, max_length=100)
    participants: list[ParticipantInput] = Field(..., min_length=1, max_length=30)
    requesterInputMappings: list[dict[str, Any]] | None = None
    metadatas: list[dict[str, str]] | None = None
    labelIds: list[str] | None = None


class EmbeddedSignRequestBody(SignRequestBody):
    redirectUrl: str | None = None


class TemplateSignRequestBody(BaseModel):
    templateId: str
    document: dict[str, Any]
    brandId: str | None = None


class EmbeddedDraftRequestBody(BaseModel):
    templateId: str
    document: dict[str, Any] | None = None
    redirectUrl: str | None = None
    brandId: str | None = None
