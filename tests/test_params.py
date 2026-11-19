"""The Python settings (py/mule/params.py) and the C encoder's (core/mule_enc.h) agree: the
defaults are the same, and every field of mule_enc_params is set from Python."""
from mule import native, params as E


def _fields(p):
    return {f: getattr(p, f) for f, _ in native.ffi.typeof("mule_enc_params").fields}


def test_python_defaults_are_the_c_defaults():
    """Params() gives exactly mule_enc_defaults (a default changed on one side only shows here)"""
    c = native.ffi.new("mule_enc_params *")
    native.lib.mule_enc_defaults(c)
    assert _fields(native.c_params(E.Params())) == _fields(c)


def test_every_c_field_is_set_from_python():
    """c_params writes every field of mule_enc_params (a new C setting needs its Python twin)"""
    names = [f for f, _ in native.ffi.typeof("mule_enc_params").fields]
    src = open(native.__file__).read()
    missing = [f for f in names if f"p.{f} = " not in src]
    assert not missing, f"mule_enc_params fields not set by c_params: {missing}"
