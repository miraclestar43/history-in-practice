"""Text normalisation shared by checks and the registry.

OpenCC (opencc-python-reimplemented, pure Python) is required for 繁简
normalisation; install it in the project venv. Without it, t2s is identity and
`doctor` reports the degraded state instead of silently passing."""
try:
    from opencc import OpenCC
    _cc = OpenCC("t2s")
    t2s = _cc.convert
    HAVE_OPENCC = True
except Exception:  # pragma: no cover
    def t2s(s):
        return s
    HAVE_OPENCC = False
