import os
import uuid
import boto3
from botocore.client import Config


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("AWS_S3_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_S3_REGION_NAME"),
        config=Config(signature_version="s3v4"),
    )


def upload_file_to_s3(file_obj, project_id):
    s3 = get_s3_client()
    bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")

    extension = ""
    if "." in file_obj.name:
        extension = "." + file_obj.name.split(".")[-1]

    key = f"projects/{project_id}/{uuid.uuid4()}{extension}"

    s3.upload_fileobj(file_obj, bucket_name, key)

    return key


def upload_bytes_to_s3(data: bytes, key: str, content_type: str | None = None) -> str:
    s3 = get_s3_client()
    bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
    kwargs = {"Bucket": bucket_name, "Key": key, "Body": data}
    if content_type:
        kwargs["ContentType"] = content_type
    s3.put_object(**kwargs)
    return key


def download_file_from_s3(s3_key: str) -> bytes:
    s3 = get_s3_client()
    bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
    response = s3.get_object(Bucket=bucket_name, Key=s3_key)
    return response["Body"].read()


def delete_file_from_s3(s3_key: str) -> None:
    s3 = get_s3_client()
    s3.delete_object(Bucket=os.getenv("AWS_STORAGE_BUCKET_NAME"), Key=s3_key)


def generate_presigned_url(s3_key: str, expires: int = 3600) -> str:
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": os.getenv("AWS_STORAGE_BUCKET_NAME"), "Key": s3_key},
        ExpiresIn=expires,
    )


def get_s3_object_metadata(s3_key: str) -> dict:
    s3 = get_s3_client()
    response = s3.head_object(
        Bucket=os.getenv("AWS_STORAGE_BUCKET_NAME"),
        Key=s3_key,
    )
    return {
        "size": response.get("ContentLength"),
        "last_modified": response.get("LastModified"),
        "content_type": response.get("ContentType"),
    }
