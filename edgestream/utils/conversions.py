def bytes_to_human_readable(size, decimals=2, binary_system=True):
    units = (
        ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB"]
        if binary_system
        else ["B", "kB", "MB", "GB", "TB", "PB", "EB", "ZB"]
    )
    step = 1024 if binary_system else 1000
    for unit in units:
        if size < step:
            break
        size /= step
    return f"{size:.{decimals}f}{unit}"
