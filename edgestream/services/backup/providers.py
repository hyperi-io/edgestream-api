# edgestream/core/system/backup/providers.py

from __future__ import annotations
import io, json, datetime as dt, os
from typing import Protocol, Iterable, List, Tuple

from edgestream.core.config import Logger

def _parse_retention(ret: str) -> dt.timedelta:
    import re
    m = re.fullmatch(r"(\d+)([dhm])", (ret or "").strip())
    if not m:
        return dt.timedelta(days=30)
    n, u = int(m.group(1)), m.group(2)
    return dt.timedelta(days=n) if u == "d" else dt.timedelta(hours=n) if u == "h" else dt.timedelta(minutes=n)

class BackupProvider(Protocol):
    def put(self, *, bytes_data: bytes, bucket: str, key: str) -> None: ...
    def list_objects(self, *, bucket: str, prefix: str) -> List[Tuple[str, dt.datetime]]: ...
    def delete_many(self, *, bucket: str, keys: Iterable[str]) -> None: ...

# ---------- Local ----------
class LocalProvider:
    def put(self, *, bytes_data: bytes, bucket: str, key: str) -> None:
        # `key` may contain directories (prefixes). Create them and write.
        path = key if os.path.isabs(key) else os.path.join("/", key).lstrip("/")  # keep relative OK too
        dirpath = os.path.dirname(path) or "."
        os.makedirs(dirpath, exist_ok=True)
        with open(path, "wb") as f:
            f.write(bytes_data)

    def list_objects(self, *, bucket: str, prefix: str) -> List[Tuple[str, dt.datetime]]:
        base = prefix.rstrip("/")
        if not base:
            base = "."
        res: List[Tuple[str, dt.datetime]] = []
        if os.path.isdir(base):
            for root, _, files in os.walk(base):
                for fn in files:
                    p = os.path.join(root, fn)
                    try:
                        lm = dt.datetime.utcfromtimestamp(os.path.getmtime(p))
                        res.append((p, lm))
                    except FileNotFoundError:
                        pass
        else:
            if os.path.exists(base):
                lm = dt.datetime.utcfromtimestamp(os.path.getmtime(base))
                res.append((base, lm))
        return res

    def delete_many(self, *, bucket: str, keys: Iterable[str]) -> None:
        for k in keys:
            try: os.remove(k)
            except FileNotFoundError: pass

# ---------- S3 ----------
class S3Provider:
    def __init__(self, access_key_id: str, secret_access_key: str, region: str, endpoint_url: str | None = None):
        import boto3
        self._s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
            region_name=region or None,
            endpoint_url=endpoint_url or None,
        )

    def put(self, *, bytes_data: bytes, bucket: str, key: str) -> None:
        self._s3.put_object(Bucket=bucket, Key=key, Body=bytes_data, ContentType="application/x-yaml")

    def list_objects(self, *, bucket: str, prefix: str) -> List[Tuple[str, dt.datetime]]:
        out: List[Tuple[str, dt.datetime]] = []
        kwargs = {"Bucket": bucket, "Prefix": prefix or ""}
        while True:
            resp = self._s3.list_objects_v2(**kwargs)
            for o in resp.get("Contents", []) or []:
                out.append((o["Key"], o["LastModified"].replace(tzinfo=None)))
            if resp.get("IsTruncated"):
                kwargs["ContinuationToken"] = resp.get("NextContinuationToken")
            else:
                break
        return out

    def delete_many(self, *, bucket: str, keys: Iterable[str]) -> None:
        ks = list(keys)
        if not ks: return
        for i in range(0, len(ks), 1000):
            chunk = ks[i:i+1000]
            self._s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in chunk]})

# ---------- GCS ----------
class GCSProvider:
    def __init__(self, credentials_json: str):
        from google.cloud import storage
        from google.oauth2 import service_account
        if credentials_json.strip().startswith("{"):
            creds = service_account.Credentials.from_service_account_info(json.loads(credentials_json))
        else:
            creds = service_account.Credentials.from_service_account_file(credentials_json)
        self._client = storage.Client(credentials=creds)

    def put(self, *, bytes_data: bytes, bucket: str, key: str) -> None:
        b = self._client.bucket(bucket)
        blob = b.blob(key)
        blob.upload_from_file(io.BytesIO(bytes_data), content_type="application/x-yaml")

    def list_objects(self, *, bucket: str, prefix: str) -> List[Tuple[str, dt.datetime]]:
        out: List[Tuple[str, dt.datetime]] = []
        b = self._client.bucket(bucket)
        for blob in self._client.list_blobs(b, prefix=prefix or ""):
            lm = blob.updated
            out.append((blob.name, lm.replace(tzinfo=None)))
        return out

    def delete_many(self, *, bucket: str, keys: Iterable[str]) -> None:
        b = self._client.bucket(bucket)
        for k in keys:
            b.blob(k).delete(if_generation_match=None)

# ---------- Factory & pruning ----------
def build_provider(cfg) -> BackupProvider:
    prov = (getattr(cfg, "provider", "file") or "file").lower()
    if prov == "file":
        return LocalProvider()
    if prov == "s3":
        return S3Provider(
            getattr(cfg, "access_key_id", "") or "",
            getattr(cfg, "secret_access_key", "") or "",
            getattr(cfg, "region", "") or "",
            getattr(cfg, "endpoint_url", None) or None,  # tolerate missing attr
        )
    if prov == "gcs":
        return GCSProvider(getattr(cfg, "gcs_credentials_json", "") or "")
    raise ValueError(f"Unsupported provider: {getattr(cfg, 'provider', None)}")

def prune_old(provider: BackupProvider, *, bucket: str, prefix: str, retention: str) -> int:
    ttl = _parse_retention(retention or "30d")
    cutoff = dt.datetime.utcnow() - ttl
    objs = provider.list_objects(bucket=bucket, prefix=prefix or "")
    to_delete = [k for (k, lm) in objs if lm < cutoff]
    provider.delete_many(bucket=bucket, keys=to_delete)
    return len(to_delete)
