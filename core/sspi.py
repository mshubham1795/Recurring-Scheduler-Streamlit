"""
Windows SSPI -- Kerberos/NTLM via secur32.dll (ctypes).
Direct port from sas_backend.py.
"""
import base64
import ctypes
import ctypes.wintypes
import platform
import logging

log = logging.getLogger("SASBackend")


class SecHandle(ctypes.Structure):
    _fields_ = [("dwLower", ctypes.POINTER(ctypes.c_ulong)),
                ("dwUpper", ctypes.POINTER(ctypes.c_ulong))]


class SecBuffer(ctypes.Structure):
    _fields_ = [("cbBuffer", ctypes.c_ulong),
                ("BufferType", ctypes.c_ulong),
                ("pvBuffer", ctypes.c_void_p)]


class SecBufferDesc(ctypes.Structure):
    _fields_ = [("ulVersion", ctypes.c_ulong),
                ("cBuffers", ctypes.c_ulong),
                ("pBuffers", ctypes.POINTER(SecBuffer))]


class TimeStamp(ctypes.Structure):
    _fields_ = [("LowPart", ctypes.wintypes.DWORD),
                ("HighPart", ctypes.wintypes.LONG)]


# SSPI constants
SECPKG_CRED_OUTBOUND = 0x00000002
ISC_REQ_DELEGATE = 0x00000001
ISC_REQ_MUTUAL_AUTH = 0x00000002
ISC_REQ_REPLAY_DETECT = 0x00000004
ISC_REQ_SEQUENCE_DETECT = 0x00000008
ISC_REQ_CONFIDENTIALITY = 0x00000010
ISC_REQ_CONNECTION = 0x00000800
ISC_REQ_INTEGRITY = 0x00010000
SECURITY_NATIVE_DREP = 0x00000010
SECBUFFER_TOKEN = 2
SECBUFFER_VERSION = 0
SEC_E_OK = 0x00000000
SEC_I_CONTINUE_NEEDED = 0x00090312

HAS_SSPI = platform.system() == "Windows"
secur32 = None
if HAS_SSPI:
    try:
        secur32 = ctypes.windll.secur32
    except Exception:
        HAS_SSPI = False


def sspi_get_negotiate_token(target_host, input_token=None):
    """Generate a Negotiate (Kerberos/NTLM) token using Windows SSPI.

    Args:
        target_host: hostname for SPN (e.g., "cluwe.am.lilly.com")
        input_token: base64-decoded server challenge (for multi-leg), or None

    Returns:
        base64-encoded token string, or None on failure
    """
    if not HAS_SSPI or not secur32:
        return None

    try:
        # Acquire credentials handle
        cred_handle = SecHandle()
        cred_handle.dwLower = ctypes.pointer(ctypes.c_ulong(0))
        cred_handle.dwUpper = ctypes.pointer(ctypes.c_ulong(0))
        lifetime = TimeStamp()

        status = secur32.AcquireCredentialsHandleW(
            None,
            ctypes.c_wchar_p("Negotiate"),
            ctypes.c_ulong(SECPKG_CRED_OUTBOUND),
            None, None, None, None,
            ctypes.byref(cred_handle),
            ctypes.byref(lifetime)
        )
        if status != SEC_E_OK:
            log.debug(f"[SSPI] AcquireCredentialsHandle failed: 0x{status:08X}")
            return None

        # Set up output buffer
        out_buf_size = 16384
        out_buf_data = ctypes.create_string_buffer(out_buf_size)
        out_buf = SecBuffer()
        out_buf.cbBuffer = out_buf_size
        out_buf.BufferType = SECBUFFER_TOKEN
        out_buf.pvBuffer = ctypes.cast(out_buf_data, ctypes.c_void_p)

        out_buf_desc = SecBufferDesc()
        out_buf_desc.ulVersion = SECBUFFER_VERSION
        out_buf_desc.cBuffers = 1
        out_buf_desc.pBuffers = ctypes.pointer(out_buf)

        # Set up input buffer (if server sent a challenge)
        in_buf_desc_ptr = None
        if input_token:
            in_buf_data = ctypes.create_string_buffer(input_token)
            in_buf = SecBuffer()
            in_buf.cbBuffer = len(input_token)
            in_buf.BufferType = SECBUFFER_TOKEN
            in_buf.pvBuffer = ctypes.cast(in_buf_data, ctypes.c_void_p)

            in_buf_desc = SecBufferDesc()
            in_buf_desc.ulVersion = SECBUFFER_VERSION
            in_buf_desc.cBuffers = 1
            in_buf_desc.pBuffers = ctypes.pointer(in_buf)
            in_buf_desc_ptr = ctypes.byref(in_buf_desc)

        # Initialize security context
        ctx_handle = SecHandle()
        ctx_handle.dwLower = ctypes.pointer(ctypes.c_ulong(0))
        ctx_handle.dwUpper = ctypes.pointer(ctypes.c_ulong(0))
        ctx_attrs = ctypes.c_ulong(0)
        ctx_lifetime = TimeStamp()
        spn = f"HTTP/{target_host}"

        isc_flags = (ISC_REQ_DELEGATE | ISC_REQ_MUTUAL_AUTH |
                     ISC_REQ_REPLAY_DETECT | ISC_REQ_SEQUENCE_DETECT |
                     ISC_REQ_CONFIDENTIALITY | ISC_REQ_CONNECTION)

        status = secur32.InitializeSecurityContextW(
            ctypes.byref(cred_handle),
            None if not input_token else ctypes.byref(ctx_handle),
            ctypes.c_wchar_p(spn),
            ctypes.c_ulong(isc_flags),
            ctypes.c_ulong(0),
            ctypes.c_ulong(SECURITY_NATIVE_DREP),
            in_buf_desc_ptr,
            ctypes.c_ulong(0),
            ctypes.byref(ctx_handle),
            ctypes.byref(out_buf_desc),
            ctypes.byref(ctx_attrs),
            ctypes.byref(ctx_lifetime)
        )

        if status not in (SEC_E_OK, SEC_I_CONTINUE_NEEDED):
            log.debug(f"[SSPI] InitializeSecurityContext failed: 0x{status:08X}")
            secur32.FreeCredentialsHandle(ctypes.byref(cred_handle))
            return None

        # Extract token from output buffer
        token_size = out_buf.cbBuffer
        if token_size > 0:
            token_bytes = ctypes.string_at(out_buf.pvBuffer, token_size)
            token_b64 = base64.b64encode(token_bytes).decode("ascii")
            secur32.DeleteSecurityContext(ctypes.byref(ctx_handle))
            secur32.FreeCredentialsHandle(ctypes.byref(cred_handle))
            return token_b64

        secur32.FreeCredentialsHandle(ctypes.byref(cred_handle))
        return None

    except Exception as e:
        log.debug(f"[SSPI] Exception: {e}")
        return None
