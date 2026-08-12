from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote


@dataclass(frozen=True, slots=True)
class StoredObjectMetadata:
    size: int
    content_type: str


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    url: str
    fields: dict[str, str]


class PrivateObjectStorage(Protocol):
    def create_upload(
        self, *, bucket: str, key: str, content_type: str, max_bytes: int
    ) -> PresignedUpload: ...

    def head(self, *, bucket: str, key: str) -> StoredObjectMetadata: ...

    def read(self, *, bucket: str, key: str, max_bytes: int) -> bytes: ...

    def create_download(
        self, *, bucket: str, key: str, filename: str, expires_seconds: int
    ) -> str: ...

    def delete(self, *, bucket: str, key: str) -> None: ...

    def promote(self, *, bucket: str, source_key: str, destination_key: str) -> None: ...

    def write(self, *, bucket: str, key: str, content: bytes, content_type: str) -> None: ...


class S3PrivateObjectStorage:
    def __init__(self) -> None:
        import boto3

        self.client = boto3.client("s3")

    def create_upload(
        self, *, bucket: str, key: str, content_type: str, max_bytes: int
    ) -> PresignedUpload:
        result = self.client.generate_presigned_post(
            Bucket=bucket,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, max_bytes],
            ],
            ExpiresIn=300,
        )
        return PresignedUpload(
            url=str(result["url"]),
            fields={str(key): str(value) for key, value in result["fields"].items()},
        )

    def head(self, *, bucket: str, key: str) -> StoredObjectMetadata:
        result = self.client.head_object(Bucket=bucket, Key=key)
        return StoredObjectMetadata(
            size=int(result["ContentLength"]),
            content_type=str(result.get("ContentType", "application/octet-stream")),
        )

    def read(self, *, bucket: str, key: str, max_bytes: int) -> bytes:
        result = self.client.get_object(Bucket=bucket, Key=key, Range=f"bytes=0-{max_bytes}")
        content = result["Body"].read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValueError("private object exceeds its permitted size")
        return bytes(content)

    def create_download(self, *, bucket: str, key: str, filename: str, expires_seconds: int) -> str:
        disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
        return str(
            self.client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": bucket,
                    "Key": key,
                    "ResponseContentDisposition": disposition,
                },
                ExpiresIn=expires_seconds,
                HttpMethod="GET",
            )
        )

    def delete(self, *, bucket: str, key: str) -> None:
        self.client.delete_object(Bucket=bucket, Key=key)

    def promote(self, *, bucket: str, source_key: str, destination_key: str) -> None:
        self.client.copy_object(
            Bucket=bucket,
            Key=destination_key,
            CopySource={"Bucket": bucket, "Key": source_key},
            MetadataDirective="COPY",
        )

    def write(self, *, bucket: str, key: str, content: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )


def get_private_storage() -> PrivateObjectStorage:
    return S3PrivateObjectStorage()
