import os
import time

from modules import config


def prune(directory, max_bytes, max_age_s, now=None):
    now = time.time() if now is None else now
    try:
        names = os.listdir(directory)
    except OSError:
        return 0
    entries = []
    for name in names:
        path = os.path.join(directory, name)
        try:
            info = os.stat(path)
        except OSError:
            continue
        entries.append((info.st_mtime, info.st_size, path))
    removed = 0
    kept = []
    for mtime, size, path in entries:
        if now - mtime > max_age_s and _remove(path):
            removed += 1
        else:
            kept.append((mtime, size, path))
    total = sum(size for _, size, _ in kept)
    for mtime, size, path in sorted(kept):
        if total <= max_bytes:
            break
        if _remove(path):
            total -= size
            removed += 1
    return removed


def touch(path):
    try:
        os.utime(path)
    except OSError:
        pass


def prune_default():
    return prune(config.CACHE_DIR / "thumbs", config.THUMB_DISK_MAX_BYTES, config.THUMB_DISK_MAX_AGE_DAYS * 86400)


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        return False
    return True
