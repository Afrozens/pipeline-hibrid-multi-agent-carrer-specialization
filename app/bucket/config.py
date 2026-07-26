import boto3
from app.core.config import get_settings

settings = get_settings()

extra_args = {}
if settings.S3_ENDPOINT_URL:
    extra_args["endpoint_url"] = settings.S3_ENDPOINT_URL

s3 = boto3.client(
    "s3",
    aws_access_key_id=settings.ACCESS_KEY_ID,
    aws_secret_access_key=settings.SECRET_ACCESS_KEY,
    **extra_args,
)

s3_resource = boto3.resource(
    "s3",
    aws_access_key_id=settings.ACCESS_KEY_ID,
    aws_secret_access_key=settings.SECRET_ACCESS_KEY,
    **extra_args,
)
