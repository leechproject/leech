def clock(microseconds):
    seconds = max(0, int(microseconds // 1_000_000))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def progress(position, length):
    position = max(0, min(position, length)) if length > 0 else max(0, position)
    return f"{clock(position)}/{clock(max(0, length - position))}"


def stopwatch(seconds):
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"
