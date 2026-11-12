import ctypes
import locale

RENDER_PARAM_INVALID = 0
RENDER_PARAM_API_TYPE = 1
RENDER_PARAM_OPENGL_INIT_PARAMS = 2
RENDER_PARAM_OPENGL_FBO = 3
RENDER_PARAM_FLIP_Y = 4
RENDER_PARAM_WL_DISPLAY = 9
RENDER_UPDATE_FRAME = 1

GET_PROC_ADDRESS = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)
UPDATE_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_void_p)


class RenderParam(ctypes.Structure):
    _fields_ = (("type", ctypes.c_int), ("data", ctypes.c_void_p))


class OpenGLInitParams(ctypes.Structure):
    _fields_ = (("get_proc_address", GET_PROC_ADDRESS), ("get_proc_address_ctx", ctypes.c_void_p))


class OpenGLFbo(ctypes.Structure):
    _fields_ = (("fbo", ctypes.c_int), ("w", ctypes.c_int), ("h", ctypes.c_int), ("internal_format", ctypes.c_int))


def _library():
    for name in ("libmpv.so.2", "libmpv.so.1", "libmpv.so"):
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    raise OSError("libmpv не найден")


def _egl_get_proc_address():
    egl = ctypes.CDLL("libEGL.so.1")
    egl.eglGetProcAddress.restype = ctypes.c_void_p
    egl.eglGetProcAddress.argtypes = (ctypes.c_char_p,)
    return egl.eglGetProcAddress


def available():
    try:
        _library()
        return True
    except OSError:
        return False


def _params(*pairs):
    array = (RenderParam * (len(pairs) + 1))()
    for index, (kind, data) in enumerate(pairs):
        array[index].type = kind
        array[index].data = ctypes.cast(data, ctypes.c_void_p)
    array[len(pairs)].type = RENDER_PARAM_INVALID
    return array


class Player:
    def __init__(self, options):
        lib = self._lib = _library()
        lib.mpv_create.restype = ctypes.c_void_p
        lib.mpv_set_option_string.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p)
        lib.mpv_set_property_string.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p)
        lib.mpv_initialize.argtypes = (ctypes.c_void_p,)
        lib.mpv_command.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p))
        lib.mpv_terminate_destroy.argtypes = (ctypes.c_void_p,)
        lib.mpv_error_string.restype = ctypes.c_char_p
        lib.mpv_render_context_create.argtypes = (ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
                                                  ctypes.POINTER(RenderParam))
        lib.mpv_render_context_render.argtypes = (ctypes.c_void_p, ctypes.POINTER(RenderParam))
        lib.mpv_render_context_set_update_callback.argtypes = (ctypes.c_void_p, UPDATE_CALLBACK, ctypes.c_void_p)
        lib.mpv_render_context_update.argtypes = (ctypes.c_void_p,)
        lib.mpv_render_context_update.restype = ctypes.c_uint64
        lib.mpv_render_context_free.argtypes = (ctypes.c_void_p,)

        locale.setlocale(locale.LC_NUMERIC, "C")
        self._handle = lib.mpv_create()
        if not self._handle:
            raise OSError("mpv_create не удался")
        self._render = ctypes.c_void_p()
        self._keep = []
        for name, value in options.items():
            self._check(lib.mpv_set_option_string(self._handle, name.encode(), value.encode()), name)
        self._check(lib.mpv_initialize(self._handle), "initialize")

    def _check(self, code, what):
        if code < 0:
            raise OSError(f"mpv {what}: {self._lib.mpv_error_string(code).decode()}")

    def attach_gl(self, on_update, wl_display=None):
        proc = _egl_get_proc_address()
        get_proc = GET_PROC_ADDRESS(lambda _ctx, name: proc(name))
        init = OpenGLInitParams(get_proc, None)
        api = ctypes.c_char_p(b"opengl")
        pairs = [(RENDER_PARAM_API_TYPE, api), (RENDER_PARAM_OPENGL_INIT_PARAMS, ctypes.pointer(init))]
        if wl_display:
            pairs.append((RENDER_PARAM_WL_DISPLAY, ctypes.c_void_p(wl_display)))
        params = _params(*pairs)
        self._check(self._lib.mpv_render_context_create(ctypes.byref(self._render), self._handle, params),
                    "render context")
        callback = UPDATE_CALLBACK(lambda _ctx: on_update())
        self._keep += [get_proc, init, api, callback]
        self._lib.mpv_render_context_set_update_callback(self._render, callback, None)

    def load(self, path):
        self.command("loadfile", path)

    def command(self, *args):
        array = (ctypes.c_char_p * (len(args) + 1))(*(arg.encode() for arg in args), None)
        self._check(self._lib.mpv_command(self._handle, array), args[0])

    def set_property(self, name, value):
        self._check(self._lib.mpv_set_property_string(self._handle, name.encode(), value.encode()), name)

    def render(self, fbo, width, height):
        if not self._render:
            return
        self._lib.mpv_render_context_update(self._render)
        target = OpenGLFbo(fbo, width, height, 0)
        flip = ctypes.c_int(1)
        params = _params((RENDER_PARAM_OPENGL_FBO, ctypes.pointer(target)), (RENDER_PARAM_FLIP_Y, ctypes.pointer(flip)))
        self._lib.mpv_render_context_render(self._render, params)

    def close(self):
        if self._render:
            self._lib.mpv_render_context_free(self._render)
            self._render = ctypes.c_void_p()
        if self._handle:
            self._lib.mpv_terminate_destroy(self._handle)
            self._handle = None
