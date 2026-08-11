from __future__ import annotations

import os
import psutil
from typing import Any, Dict, List

from edgestream.utils.conversions import bytes_to_human_readable
from edgestream.core.config import Logger

# Filesystem types that provide no informative value for system health monitoring
_IGNORE_FSTYPES = {
    "proc", "sysfs", "devtmpfs", "devfs", "tmpfs", "overlay", "squashfs", "autofs",
    "mqueue", "bpf", "ramfs", "debugfs", "tracefs", "fusectl", "fuse.portal", "fuse.lxcfs",
    "cgroup", "cgroup2", "pstore", "configfs", "securityfs", "selinuxfs", "efivarfs",
}

# Mount paths for container runtimes or virtualized subsystems to ignore
_IGNORE_PREFIXES = (
    "/proc", "/sys", "/run", "/snap", "/var/snap", "/var/lib/docker",
    "/var/lib/containers", "/dev",
)


def get_partition_usage() -> List[Dict[str, Any]]:
    """
    Scans physical disk partitions and returns usage metrics.
    Filters out virtual, container-internal, and read-only snap filesystems.
    """
    partitions: List[Dict[str, Any]] = []
    seen_dev_ids: set[int] = set()

    for p in psutil.disk_partitions(all=False):
        if p.fstype.lower() in _IGNORE_FSTYPES:
            continue

        if any(p.mountpoint.startswith(pref) for pref in _IGNORE_PREFIXES):
            continue

        is_physical = p.device.startswith("/dev/")
        is_standard_fs = p.fstype.lower() in {"ext4", "ext3", "ext2", "xfs", "btrfs", "zfs"}

        if not (is_physical or is_standard_fs):
            continue

        try:
            stat_info = os.stat(p.mountpoint)
            dev_id = stat_info.st_dev

            if dev_id in seen_dev_ids:
                continue

            seen_dev_ids.add(dev_id)
            usage = psutil.disk_usage(p.mountpoint)

        except (PermissionError, FileNotFoundError) as e:
            Logger.logger.debug(f"Skipping partition {p.mountpoint}: {e}")
            continue
        except Exception as e:
            Logger.logger.warning(f"Unexpected error checking partition {p.mountpoint}: {e}")
            continue

        partitions.append({
            "mount_point": p.mountpoint,
            "fs_type": p.fstype,
            "device": p.device,
            "disk_total_bytes": usage.total,
            "disk_total_human_readable": bytes_to_human_readable(usage.total, 2, False),
            "disk_used_bytes": usage.used,
            "disk_used_human_readable": bytes_to_human_readable(usage.used, 2, False),
            "disk_free_bytes": usage.free,
            "disk_free_human_readable": bytes_to_human_readable(usage.free, 2, False),
            "disk_usage_percent": round(usage.percent, 1),
        })

    # Sort logic: Root (/) always first, then alphabetical by mount path
    partitions.sort(key=lambda x: (x["mount_point"] != "/", x["mount_point"]))

    return partitions
