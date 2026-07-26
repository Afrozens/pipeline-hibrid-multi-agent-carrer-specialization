import logging
from app.bucket.config import s3, s3_resource

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class S3Service:
    def __init__(self):
        self.s3_client = s3
        self.s3_resource = s3_resource

    async def upload_file(self, file, bucket_name, folder_name, file_name):
        """
        Uploads a file to an S3-compatible bucket.
        - `file`: The file object to upload.
        - `bucket_name`: The name of the bucket.
        - `folder_name`: The folder in the bucket where the file will be stored.
        - `file_name`: The name of the file in the bucket.
        Returns `True` if successful, otherwise `False`.
        """
        try:
            key = f"{folder_name}/{file_name}"
            self.s3_client.upload_fileobj(file, bucket_name, key)
            return True
        except Exception as ex:
            logger.error(f"Unexpected Error: {ex}")
            return False

    async def get_all_files(self, bucket_name):
        """
        Retrieves a list of all files in a bucket.
        - `bucket_name`: The name of the bucket.
        Returns the list of files if successful, otherwise `False`.
        """
        try:
            files = self.s3_client.list_objects_v2(Bucket=bucket_name)
            return files
        except Exception as ex:
            logger.error(f"Unexpected Error: {str(ex)}")
            return False

    def download_file(self, file_name: str, bucket_name: str):
        """
        Generates a pre-signed URL to download a file from a bucket.
        - `file_name`: The key (path) of the file in the bucket.
        - `bucket_name`: The name of the bucket.
        Returns the pre-signed URL if successful, otherwise raises an exception.
        """
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket_name, "Key": file_name},
                ExpiresIn=3600,
            )
            return url
        except Exception as ex:
            logger.error(f"Unexpected Error: {ex}")
            raise False

    async def delete_file(self, bucket_name: str, file_key: str):
        """
        Deletes a file from a bucket.
        - `bucket_name`: The name of the bucket.
        - `file_key`: The key (path) of the file to delete.
        Returns `True` if successful, otherwise `False`.
        """
        try:
            self.s3_client.delete_object(Bucket=bucket_name, Key=file_key)
            logger.info(f"File {file_key} deleted successfully from bucket {bucket_name}.")
            return True
        except Exception as ex:
            logger.error(f"Error deleting file {file_key} from bucket {bucket_name}: {ex}")
            return False
