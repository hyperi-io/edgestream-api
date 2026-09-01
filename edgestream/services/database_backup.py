"""
Project:   edgestream-api
File:      edgestream/services/database_backup.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations

import os
import tempfile
import asyncio
import pyminizip
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from google.cloud import storage
from aiobotocore.session import get_session

from edgestream.core.config import Logger


# -----------------------------------------------------------------------------
# Utility Helpers
# -----------------------------------------------------------------------------

def parse_retention(retention: str) -> timedelta:
    """
    Parses retention strings like '12h' or '30d' into timedelta objects.
    """
    try:
        unit = retention[-1].lower()
        value = int(retention[:-1])
        if unit == 'h':
            return timedelta(hours=value)
        elif unit == 'd':
            return timedelta(days=value)
    except (IndexError, ValueError):
        pass

    raise ValueError("Invalid retention format. Use '12h' for hours or '30d' for days.")


def _get_timestamp_str() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def zip_file(source_path: str, dest_dir: str, zip_password: str) -> str:
    """
    Compresses a file into a password-protected ZIP.
    Compression level set to 5 (balanced).
    """
    zip_file_name = f"config_backup_{_get_timestamp_str()}.zip"
    zip_file_path = os.path.join(dest_dir, zip_file_name)

    # pyminizip params: source, prefix, output, password, compress_level
    pyminizip.compress(source_path, None, zip_file_path, zip_password, 5)
    return zip_file_path


# -----------------------------------------------------------------------------
# Local File Backup
# -----------------------------------------------------------------------------

def cleanup_file_backups(backup_dir: str, retention_period: timedelta):
    """Enforces retention on local filesystem backups."""
    now = datetime.now()
    if not os.path.exists(backup_dir):
        return

    for file in os.listdir(backup_dir):
        file_path = os.path.join(backup_dir, file)
        if os.path.isfile(file_path) and file.startswith("config_backup_"):
            creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
            if now - creation_time > retention_period:
                try:
                    os.remove(file_path)
                    Logger.logger.info(f"Purged expired local backup: {file}")
                except Exception as e:
                    Logger.logger.error(f"Failed to delete local backup {file}: {e}")


def backup_to_file(file_path: str, retention: str, backup_dir: str, password: str):
    """Saves a compressed backup to a local directory."""
    os.makedirs(backup_dir, exist_ok=True)

    zip_path = zip_file(file_path, backup_dir, password)
    retention_period = parse_retention(retention)

    cleanup_file_backups(backup_dir, retention_period)
    Logger.logger.info(f"Local backup completed: {zip_path}")
    return zip_path


# -----------------------------------------------------------------------------
# GCS (Google Cloud Storage)
# -----------------------------------------------------------------------------

async def cleanup_gcs_backups(bucket_name: str, path_prefix: str, retention_period: timedelta, credentials_path: str):
    """Removes expired backups from Google Cloud Storage."""
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    now = datetime.now(timezone.utc)

    try:
        blobs = bucket.list_blobs(prefix=path_prefix)
        for blob in blobs:
            if blob.time_created and (now - blob.time_created > retention_period):
                Logger.logger.info(f"Deleting expired GCS backup: {blob.name}")
                blob.delete()
    except Exception as e:
        Logger.logger.error(f"GCS cleanup failed: {e}")


async def upload_to_gcs(file_path: str, bucket_name: str, gcs_path: str, credentials_path: str):
    """Uploads a backup file to GCS."""
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    blob_name = os.path.join(gcs_path, os.path.basename(file_path))
    blob = bucket.blob(blob_name)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, blob.upload_from_filename, file_path)
    Logger.logger.info(f"Uploaded to GCS: {bucket_name}/{blob_name}")


# -----------------------------------------------------------------------------
# S3 (Amazon / S3-Compatible)
# -----------------------------------------------------------------------------

async def cleanup_s3_backups(bucket_name: str, path_prefix: str, retention_period: timedelta, access_key: str,
                             secret_key: str):
    """Removes expired backups from S3."""
    session = get_session()
    now = datetime.now(timezone.utc)

    async with session.create_client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_key) as s3:
        paginator = s3.get_paginator('list_objects_v2')
        async for page in paginator.paginate(Bucket=bucket_name, Prefix=path_prefix):
            if 'Contents' in page:
                for obj in page['Contents']:
                    if now - obj['LastModified'] > retention_period:
                        Logger.logger.info(f"Deleting expired S3 backup: {obj['Key']}")
                        await s3.delete_object(Bucket=bucket_name, Key=obj['Key'])


async def upload_to_s3(file_path: str, bucket_name: str, s3_path: str, access_key: str, secret_key: str):
    """Uploads a backup file to S3."""
    session = get_session()
    async with session.create_client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_key) as s3:
        s3_key = os.path.join(s3_path, os.path.basename(file_path))
        with open(file_path, 'rb') as f:
            await s3.put_object(Bucket=bucket_name, Key=s3_key, Body=f)
        Logger.logger.info(f"Uploaded to S3: {bucket_name}/{s3_key}")


# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------

async def backup_config(provider: str, file_path: str, retention: str, password: str, **kwargs):
    """
    Orchestrates the backup process for a given provider.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Configuration file {file_path} not found.")

    # Always use a temporary directory for the initial zip
    tmp_dir = tempfile.gettempdir()
    retention_period = parse_retention(retention)

    try:
        if provider == 'file':
            backup_to_file(file_path, retention, kwargs.get('path', '/var/backups/edgestream'), password)

        elif provider == 'gcs':
            zip_path = zip_file(file_path, tmp_dir, password)
            try:
                await asyncio.gather(
                    upload_to_gcs(zip_path, kwargs['bucket_name'], kwargs.get('path', ''), kwargs['credentials_path']),
                    cleanup_gcs_backups(kwargs['bucket_name'], kwargs.get('path', ''), retention_period,
                                        kwargs['credentials_path'])
                )
            finally:
                if os.path.exists(zip_path): os.remove(zip_path)

        elif provider == 's3':
            zip_path = zip_file(file_path, tmp_dir, password)
            try:
                await asyncio.gather(
                    upload_to_s3(zip_path, kwargs['bucket_name'], kwargs.get('path', ''), kwargs['access_key_id'],
                                 kwargs['secret_access_key']),
                    cleanup_s3_backups(kwargs['bucket_name'], kwargs.get('path', ''), retention_period,
                                       kwargs['access_key_id'], kwargs['secret_access_key'])
                )
            finally:
                if os.path.exists(zip_path): os.remove(zip_path)
        else:
            raise ValueError(f"Unsupported backup provider: {provider}")

    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing required backup parameter: {str(e)}")
    except Exception as e:
        Logger.logger.error(f"Backup job failed: {e}", exc_info=True)
        raise
