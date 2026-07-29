import os
import time
from typing import Any

import requests
from fastapi import HTTPException

MODUSIGN_BASE_URL = os.getenv("MODUSIGN_BASE_URL", "https://api.modusign.co.kr")
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1.0


class ModusignClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = MODUSIGN_BASE_URL.rstrip("/")

    def _auth_headers(self, content_type: str | None = "application/json") -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _handle_response(self, response: requests.Response) -> Any:
        if response.ok:
            if response.status_code == 204 or not response.content:
                return {}
            return response.json()

        detail: Any
        try:
            detail = response.json()
        except ValueError:
            detail = response.text or response.reason

        raise HTTPException(status_code=response.status_code, detail=detail)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        content_type: str | None = "application/json",
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers = self._auth_headers(content_type=None if files else content_type)

        last_response: requests.Response | None = None
        for attempt in range(MAX_RETRIES):
            response = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                files=files,
                data=data,
                timeout=60,
            )
            last_response = response

            if response.status_code != 429:
                return self._handle_response(response)

            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))

        return self._handle_response(last_response)  # type: ignore[arg-type]

    def request_with_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/documents/request-with-template", json=payload)

    def create_embedded_draft_with_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/embedded-drafts/create-with-template", json=payload)

    def get_document(self, document_id: str) -> dict[str, Any]:
        return self._request("GET", f"/documents/{document_id}")

    def list_documents(
        self,
        *,
        offset: int = 0,
        limit: int = 10,
        filter_query: str | None = None,
        order_by: str | None = None,
        metadatas: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"offset": offset, "limit": limit}
        if filter_query:
            params["filter"] = filter_query
        if order_by:
            params["orderBy"] = order_by
        if metadatas:
            params["metadatas"] = metadatas
        return self._request("GET", "/documents", params=params)

    def get_embedded_participant_view(
        self,
        document_id: str,
        participant_id: str,
        *,
        redirect_url: str | None = None,
    ) -> dict[str, Any]:
        params = {"redirectUrl": redirect_url} if redirect_url else None
        return self._request(
            "GET",
            f"/documents/{document_id}/participants/{participant_id}/embedded-view",
            params=params,
        )

    def get_embedded_document_view(
        self,
        document_id: str,
        *,
        redirect_url: str | None = None,
    ) -> dict[str, Any]:
        params = {"redirectUrl": redirect_url} if redirect_url else None
        return self._request("GET", f"/documents/{document_id}/embedded-view", params=params)

    def cancel_document(self, document_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/documents/{document_id}/cancel",
            json=payload or {},
        )

    def upload_file(
        self,
        *,
        file_type: str,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/files",
            params={"type": file_type},
            files={"file": (filename, content, content_type)},
        )
