import ctypes
import ctypes.util
import sys

_FC_MATCH = b"family"


def _library():
    name = ctypes.util.find_library("fontconfig") or "libfontconfig.so.1"
    try:
        lib = ctypes.CDLL(name)
    except OSError:
        return None
    lib.FcConfigGetCurrent.restype = ctypes.c_void_p
    lib.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.FcConfigAppFontAddFile.restype = ctypes.c_int
    lib.FcFreeTypeQuery.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    lib.FcFreeTypeQuery.restype = ctypes.c_void_p
    lib.FcPatternGetString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int,
                                       ctypes.POINTER(ctypes.c_char_p)]
    lib.FcPatternGetString.restype = ctypes.c_int
    lib.FcPatternDestroy.argtypes = [ctypes.c_void_p]
    return lib


def _family(lib, path):
    count = ctypes.c_int(0)
    pattern = lib.FcFreeTypeQuery(path, 0, None, ctypes.byref(count))
    if not pattern:
        return None
    try:
        value = ctypes.c_char_p()
        if lib.FcPatternGetString(pattern, _FC_MATCH, 0, ctypes.byref(value)) == 0 and value.value:
            return value.value.decode("utf-8", "replace")
        return None
    finally:
        lib.FcPatternDestroy(pattern)


def register(paths):
    if not paths:
        return []
    lib = _library()
    if lib is None:
        print("leech: libfontconfig не найдена, шрифты из конфига не подключены", file=sys.stderr)
        return []
    config = lib.FcConfigGetCurrent()
    families = []
    for path in paths:
        encoded = str(path).encode()
        family = _family(lib, encoded)
        if family is None:
            print(f"leech: {path} не похож на файл шрифта", file=sys.stderr)
            continue
        if not lib.FcConfigAppFontAddFile(config, encoded):
            print(f"leech: fontconfig не принял {path}", file=sys.stderr)
            continue
        if family not in families:
            families.append(family)
    return families


def css_family_list(families):
    return ", ".join('"' + f.replace("\\", "\\\\").replace('"', '\\"') + '"' for f in families)


def font_css(text_families, icon_families, fallback_family):
    families = list(text_families) or ([fallback_family] if fallback_family else [])
    families += [f for f in icon_families if f not in families]
    if not families:
        return ""
    return f"* {{ font-family: {css_family_list(families)}; }}"
