def report():
    values = {}
    with open("/proc/self/status", encoding="utf-8") as f:
        for line in f:
            key, _, rest = line.partition(":")
            if key in ("VmRSS", "RssAnon", "RssFile", "RssShmem", "Threads"):
                values[key] = int(rest.split()[0])

    def mb(key):
        return values.get(key, 0) / 1024

    return (f"RSS {mb('VmRSS'):.0f} МБ = своя память {mb('RssAnon'):.0f} МБ "
            f"+ разделяемые библиотеки {mb('RssFile'):.0f} МБ (+ shm {mb('RssShmem'):.0f} МБ), "
            f"потоков: {values.get('Threads', 0)}")
