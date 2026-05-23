from __future__ import annotations

import hashlib
import hmac
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any
from urllib.parse import quote, urlencode, urlparse

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


class BlobStoreError(RuntimeError):
    pass


@dataclass(slots=True)
class BlobObject:
    key: str
    size_bytes: int
    last_modified: str | None = None
    etag: str | None = None


def _ensure_scheme(endpoint: str) -> str:
    endpoint = endpoint.strip()
    if endpoint.startswith(("http://", "https://")):
        return endpoint
    return f"http://{endpoint}"


def _aws_quote(value: str) -> str:
    return quote(value, safe="-_.~/")


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _build_signing_key(secret_key: str, date_stamp: str, region: str, service: str = "s3") -> bytes:
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "aws4_request")


def _canonical_query_string(params: dict[str, str] | None) -> str:
    if not params:
        return ""

    items = []
    for key, value in sorted(params.items(), key=lambda item: item[0]):
        items.append((str(key), str(value)))
    return urlencode(items, quote_via=quote, safe="-_.~")


def _normalize_header_value(value: str) -> str:
    return " ".join(str(value).strip().split())


@dataclass(slots=True)
class MinioBlobStore:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    region: str = "us-east-1"
    session: requests.Session = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.endpoint = _ensure_scheme(self.endpoint).rstrip("/")
        self.session = requests.Session()
        self.session.trust_env = False

    @property
    def base_url(self) -> str:
        return self.endpoint

    @property
    def host(self) -> str:
        return urlparse(self.endpoint).netloc

    def _signed_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: bytes = b"",
        content_type: str | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> requests.Response:
        parsed = urlparse(self.endpoint)
        base_path = parsed.path.rstrip("/")
        encoded_path = _aws_quote(path.lstrip("/"))
        canonical_uri = f"{base_path}/{encoded_path}" if base_path else f"/{encoded_path}"
        query_string = _canonical_query_string(params)

        amz_date = _utc_amz_date()
        date_stamp = amz_date[:8]
        payload_hash = hashlib.sha256(body).hexdigest()

        headers: dict[str, str] = {
            "host": parsed.netloc,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        if content_type:
            headers["content-type"] = content_type
        if extra_headers:
            headers.update({key.lower(): value for key, value in extra_headers.items()})

        canonical_headers = "".join(
            f"{key}:{_normalize_header_value(value)}\n" for key, value in sorted(headers.items())
        )
        signed_headers = ";".join(sorted(headers))
        canonical_request = "\n".join(
            [
                method.upper(),
                canonical_uri,
                query_string,
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                f"{date_stamp}/{self.region}/s3/aws4_request",
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signing_key = _build_signing_key(self.secret_key, date_stamp, self.region)
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{date_stamp}/{self.region}/s3/aws4_request, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        request_headers = {
            "Authorization": authorization,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        if content_type:
            request_headers["Content-Type"] = content_type
        if extra_headers:
            request_headers.update(extra_headers)

        url = f"{self.base_url}{canonical_uri}"
        response = self.session.request(
            method.upper(),
            url,
            params=params,
            data=body,
            headers=request_headers,
            timeout=timeout,
        )
        return response

    def ensure_bucket(self) -> None:
        response = self._signed_request("PUT", f"/{self.bucket}", body=b"")
        if response.status_code in {200, 201, 204, 409}:
            return
        raise BlobStoreError(f"Failed to ensure bucket {self.bucket}: {response.status_code} {response.text}")

    def put_object(self, object_key: str, data: bytes, content_type: str | None = None) -> None:
        response = self._signed_request(
            "PUT",
            f"/{self.bucket}/{object_key.lstrip('/')}",
            body=data,
            content_type=content_type or "application/octet-stream",
        )
        if response.status_code not in {200, 201, 204}:
            raise BlobStoreError(
                f"Failed to upload object {object_key}: {response.status_code} {response.text}"
            )

    def get_object(self, object_key: str) -> bytes:
        response = self._signed_request("GET", f"/{self.bucket}/{object_key.lstrip('/')}")
        if response.status_code != 200:
            raise BlobStoreError(
                f"Failed to download object {object_key}: {response.status_code} {response.text}"
            )
        return response.content

    def delete_object(self, object_key: str) -> None:
        response = self._signed_request("DELETE", f"/{self.bucket}/{object_key.lstrip('/')}")
        if response.status_code not in {200, 204, 404}:
            raise BlobStoreError(
                f"Failed to delete object {object_key}: {response.status_code} {response.text}"
            )

    def list_objects(self, prefix: str = "", max_keys: int = 1000) -> list[BlobObject]:
        objects: list[BlobObject] = []
        continuation_token: str | None = None

        while True:
            params: dict[str, str] = {"list-type": "2"}
            if prefix:
                params["prefix"] = prefix.lstrip("/")
            if continuation_token:
                params["continuation-token"] = continuation_token
            if max_keys:
                params["max-keys"] = str(max_keys)

            response = self._signed_request("GET", f"/{self.bucket}", params=params)
            if response.status_code != 200:
                raise BlobStoreError(
                    f"Failed to list objects in bucket {self.bucket}: {response.status_code} {response.text}"
                )

            try:
                root = ET.fromstring(response.text)
            except ET.ParseError as exc:
                raise BlobStoreError(f"Failed to parse object listing for bucket {self.bucket}") from exc

            namespace = "{http://s3.amazonaws.com/doc/2006-03-01/}"
            for item in root.findall(f"{namespace}Contents"):
                key = (item.findtext(f"{namespace}Key") or "").strip()
                if not key:
                    continue
                size_text = item.findtext(f"{namespace}Size") or "0"
                try:
                    size_bytes = int(size_text)
                except ValueError:
                    size_bytes = 0
                objects.append(
                    BlobObject(
                        key=key,
                        size_bytes=size_bytes,
                        last_modified=(item.findtext(f"{namespace}LastModified") or None),
                        etag=(item.findtext(f"{namespace}ETag") or None),
                    )
                )

            is_truncated = (root.findtext(f"{namespace}IsTruncated") or "").strip().lower() == "true"
            continuation_token = root.findtext(f"{namespace}NextContinuationToken")
            if not is_truncated or not continuation_token:
                break

        return objects


def _utc_amz_date() -> str:
    from datetime import datetime, timezone

    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@lru_cache(maxsize=8)
def get_blob_store(bucket_name: str | None = None) -> MinioBlobStore:
    return MinioBlobStore(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=bucket_name or settings.minio_bucket,
        region=settings.minio_region,
    )
