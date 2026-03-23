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