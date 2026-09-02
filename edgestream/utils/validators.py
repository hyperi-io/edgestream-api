"""
Project:   edgestream-api
File:      edgestream/utils/validators.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import re
import ipaddress
import bleach
from OpenSSL import crypto
from datetime import datetime
from fastapi import HTTPException

from edgestream.core.config import Logger


def is_valid_fqdn(hostname):
    return re.match(r"^(?!.{255}|.{253} .])(a-z0-9?.)*a-z0-9?[.]?$", hostname, re.IGNORECASE)

def validate_ip(address):
    try:
        ipaddress.ip_address(address)
        return True
    except ipaddress.AddressValueError:
        return False

def validate_ip_or_fqdn(address):
    return is_valid_fqdn(address) or validate_ip(address)

def validate_port(port):
    if isinstance(port, int):
        return 0 < int(port) <= 65535
    else:
        return str(port).isdigit() and 0 < int(port) <= 65535

def validate_network(cidr: str) -> bool:
    """
    True only if cidr is a valid network with no host bits (strict).
    Never raises.
    """
    try:
        ipaddress.ip_network(cidr, strict=True)
        return True
    except ValueError:
        return False

def normalize_network(cidr: str) -> str | None:
    """
    Return the normalized network (network address + original prefix)
    even if the input had host bits. Returns None if totally invalid.
    """
    try:
        net = ipaddress.ip_network(cidr, strict=False)
        return f"{net.network_address}/{net.prefixlen}"
    except ValueError:
        return None

def is_ipv4_mask(ip_mask):
    if not validate_ip(ip_mask):
        return False
    ip_mask_binary = "".join([bin(int(octet))[2:].zfill(8) for octet in ip_mask.split(".")])
    is_bit_zero = ip_mask[0] == "0"
    for bit in ip_mask_binary[1:]:
        if bit == "1" and is_bit_zero:
            return False
        if bit == "0":
            is_bit_zero = True
    return True

def validate_path(file_path):
    import os
    fpath = os.path.normpath(file_path)
    banned_locations = {
        "/etc/", "/bin/", "/boot/", "/cdrom/", "/dev/", "/lib/", "/lib32/", "/lib64/", "/libx32/", "/opt/",
        "/proc/", "/root/", "/run/", "/sbin/", "/snap/", "/srv/", "/sys/", "/usr/", "/var/",
    }
    if any(fpath.startswith(location) for location in banned_locations):
        raise HTTPException(
            status_code=400,
            detail="File path starts with a banned location.",
        )

def clean_var(var):
    try:
        cleaned_var = bleach.clean(var)
        return cleaned_var
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Error cleansing input.")

def validate_certificate(contents):
    try:
        crypto.load_certificate(crypto.FILETYPE_PEM, contents)
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Invalid certificate file.")

def validate_privatekey(contents):
    try:
        crypto.load_privatekey(crypto.FILETYPE_PEM, contents)
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Invalid private key.")


def parse_certificate_metadata(contents: bytes) -> dict:
    """
    Extracts common_name, issuer, and expiration date from a PEM or ASN1 certificate.
    Returns default values if parsing fails or if it's a private key.
    """
    data = contents.encode("utf-8") if isinstance(contents, str) else contents

    try:
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, data)
    except Exception:
        try:
            cert = crypto.load_certificate(crypto.FILETYPE_ASN1, data)
        except Exception:
            return {"not_after": None, "common_name": None, "issuer": None}

    Logger.logger.info(f"not_after: {cert}")

    not_after = None
    try:
        # Returns bytes like b'20281231235959Z'
        exp_str = cert.get_notAfter()
        if exp_str:
            exp_clean = exp_str.decode("utf-8").rstrip('Z')
            not_after = datetime.strptime(exp_clean, "%Y%m%d%H%M%S")
    except Exception:
        pass

    common_name = None
    try:
        subject = cert.get_subject()
        common_name = subject.CN
    except Exception:
        pass

    issuer = None
    try:
        iss = cert.get_issuer()
        issuer = iss.CN
    except Exception:
        pass

    return {
        "not_after": not_after,
        "common_name": common_name,
        "issuer": issuer,
    }

def certificate_thumbprint(contents: str | bytes, algo: str = "sha1") -> str:
    """
    Return the certificate fingerprint (thumbprint) as uppercase hex (no colons).
    Supports PEM or DER. Returns "" on any failure.

    Note: This returns the *certificate's* own thumbprint.
    """
    if contents is None:
        return ""

    # Ensure bytes
    data = contents.encode("utf-8") if isinstance(contents, str) else contents

    # Try PEM first, then DER (ASN.1)
    try:
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, data)
    except Exception:
        try:
            cert = crypto.load_certificate(crypto.FILETYPE_ASN1, data)
        except Exception:
            return ""

    try:
        d = cert.digest(algo)  # e.g., "AA:BB:CC:..."
        if isinstance(d, bytes):
            d = d.decode()
        return d.replace(":", "").upper()
    except Exception:
        return ""
