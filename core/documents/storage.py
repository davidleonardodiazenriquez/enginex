"""Private, immutable PDF snapshots in the configured storage container."""

import hashlib
import io
from pathlib import Path

from azure.core.exceptions import AzureError, ResourceExistsError
from azure.storage.blob import BlobServiceClient, ContentSettings
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from pypdf import PdfReader


class DocumentError(Exception):
    pass


def configured():
    return bool(settings.AZURE_STORAGE_ACCOUNT_NAME and settings.AZURE_STORAGE_ACCOUNT_KEY)


def container_client():
    if not configured():
        raise DocumentError("Azure storage is not configured. Local uploads remain available in development.")
    return BlobServiceClient(
        account_url=f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net",
        credential=settings.AZURE_STORAGE_ACCOUNT_KEY.strip(),
        connection_timeout=10, read_timeout=30, retry_total=1,
    ).get_container_client(settings.AZURE_STORAGE_CONTAINER)


def inspect_pdf(data):
    if not data or len(data) > settings.CONTRACT_MAX_BYTES:
        raise DocumentError("Choose a PDF no larger than 64 MB.")
    if not data.startswith(b"%PDF-"):
        raise DocumentError("The file is not a PDF.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise DocumentError("Upload an unencrypted PDF so it can be reviewed and extracted.")
        count = len(reader.pages)
        if not 1 <= count <= settings.CONTRACT_MAX_PAGES:
            raise DocumentError("PDFs must contain between 1 and 80 pages.")
        return count
    except DocumentError:
        raise
    except Exception:
        raise DocumentError("The PDF could not be read. Check the file and upload it again.") from None


def store_pdf(data, digest):
    key = f"enginex/contracts/{digest}.pdf"
    if configured():
        try:
            container_client().upload_blob(key, data, overwrite=False, content_settings=ContentSettings(content_type="application/pdf"))
        except ResourceExistsError:
            # Reuse only the identical snapshot, never a changed file under the same key.
            existing = container_client().download_blob(key, max_concurrency=1).readall()
            if hashlib.sha256(existing).hexdigest() != digest:
                raise DocumentError("The stored PDF snapshot failed its integrity check.")
        except AzureError:
            raise DocumentError("The PDF could not be saved to Azure Storage. Please retry.") from None
        return "azure:" + key
    if not settings.DEBUG:
        raise DocumentError("Configure Azure Storage before uploading contracts.")
    storage = FileSystemStorage(location=settings.MEDIA_ROOT)
    if not storage.exists(key):
        storage.save(key, ContentFile(data))
    return "local:" + key


def read_pdf(document):
    backend, key = document.storage_key.split(":", 1)
    if key != f"enginex/contracts/{document.sha256}.pdf":
        raise DocumentError("Invalid PDF snapshot reference.")
    try:
        if backend == "azure":
            blob = container_client().get_blob_client(key)
            if blob.get_blob_properties().size > settings.CONTRACT_MAX_BYTES:
                raise DocumentError("The PDF exceeds the supported size.")
            data = blob.download_blob(max_concurrency=1).readall()
        elif backend == "local":
            data = (Path(settings.MEDIA_ROOT) / key).read_bytes()
        else:
            raise DocumentError("Unknown PDF storage backend.")
    except (AzureError, OSError):
        raise DocumentError("The source PDF is temporarily unavailable.") from None
    if hashlib.sha256(data).hexdigest() != document.sha256:
        raise DocumentError("The source PDF has changed. Its integrity check failed.")
    return data


def available_blobs(marker=None):
    try:
        pages = container_client().list_blobs(results_per_page=100).by_page(continuation_token=marker)
        page = next(pages, [])
        items = [{"name": b.name, "size": b.size} for b in page if b.name.lower().endswith(".pdf") and not b.name.startswith("enginex/contracts/")]
        return items, pages.continuation_token
    except (AzureError, ValueError):
        raise DocumentError("The storage file list could not be loaded. Retry or upload a local PDF.") from None


def read_blob(name):
    if not isinstance(name, str) or not name.lower().endswith(".pdf") or len(name) > 1024:
        raise DocumentError("Choose a PDF from the storage container.")
    try:
        blob = container_client().get_blob_client(name)
        properties = blob.get_blob_properties()
        if properties.size > settings.CONTRACT_MAX_BYTES:
            raise DocumentError("Choose a PDF no larger than 64 MB.")
        return blob.download_blob(max_concurrency=1).readall()
    except AzureError:
        raise DocumentError("The selected storage PDF could not be read.") from None
