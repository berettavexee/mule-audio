"""cffi binding to core/ (build/libmule.so, rebuilt by `make` when the C sources are newer)."""
import fcntl
import os
import subprocess

import numpy as np
from cffi import FFI

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILD = os.environ.get("MULE_BUILD", "build")      # a separate build dir for experiments
LIB = os.path.join(ROOT, BUILD, "libmule.so")

ffi = FFI()


def _params_cdef():
    """mule_enc_params as core/mule_enc.h declares it (one definition: a field forgotten here
    would shift the others silently)"""
    import re
    h = open(os.path.join(ROOT, "core", "mule_enc.h")).read()
    return re.search(r"typedef struct \{.*?\} mule_enc_params;", h, re.S).group(0)


ffi.cdef("""
double mule_stream_cost(int nsyms, int nctx, const int32_t *ctx, const int32_t *sym, int64_t len,
                        const int64_t *resets, int64_t nresets);
double mule_stream_cost_each(int nsyms, int nctx, const int32_t *ctx, const int32_t *sym,
                             int64_t len, const int64_t *resets, int64_t nresets,
                             const uint16_t *init, double *each);
double mule_stream_cost_init(int nsyms, int nctx, const int32_t *ctx, const int32_t *sym,
                             int64_t len, const int64_t *resets, int64_t nresets,
                             const uint16_t *init);
typedef struct mule_models mule_models;
mule_models *mule_models_alloc(void);
void mule_models_free(mule_models *ms);
void mule_models_copy(mule_models *dst, const mule_models *src);
void mule_models_reset(mule_models *ms);
int mule_rans_encode(mule_models *ms, const int32_t *model, const uint32_t *val, int64_t n,
                     uint8_t *out, int cap);
typedef struct mule_dec mule_dec;
mule_dec *mule_dec_new(const uint8_t *head, int len);
void mule_dec_free(mule_dec *d);
int mule_dec_packet(mule_dec *d, const uint8_t *p, int len, int16_t *pcm, int max_samples);
void mule_dec_seek(mule_dec *d);
void mule_dec_set_fft(int (*fft)(int32_t *re, int32_t *im, int bits));
int mule_dec_pre_skip(const mule_dec *d);
size_t mule_dec_size(void);
%MULE_ENC_PARAMS%
void mule_enc_defaults(mule_enc_params *p);
int mule_encode(const double *pcm, int64_t L, const mule_enc_params *p,
                const char *const *tags, int ntags, uint8_t **out, size_t *out_len,
                size_t *audio_bytes);
void mule_free(void *p);
int mule_encode_trace(const double *pcm, int64_t L, const mule_enc_params *p, int32_t **model,
                      uint32_t **val, int64_t *n, int64_t **frame_start, int *frames,
                      int32_t **trace, int64_t *ntrace);
int mule_encode_ops(const double *pcm, int64_t L, const mule_enc_params *p, int32_t **model,
                    uint32_t **val, int64_t *n, int64_t **frame_start, int *frames);
""".replace("%MULE_ENC_PARAMS%", _params_cdef()))


def _load():
    import glob
    src = glob.glob(os.path.join(ROOT, "core", "*.[ch]")) + [os.path.join(ROOT, "Makefile")]
    os.makedirs(os.path.dirname(LIB), exist_ok=True)
    # one rebuild at a time: the workers of an evaluation import this together (a race once
    # left a truncated library, "file too short")
    with open(LIB + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        if not os.path.exists(LIB) or os.path.getmtime(LIB) < max(map(os.path.getmtime, src)):
            subprocess.run(["make", "-s", "-C", ROOT, f"BUILD={BUILD}", f"{BUILD}/libmule.so"],
                           check=True)
        return ffi.dlopen(LIB)


lib = _load()


def stream_cost(nsyms, nctx, ctx, sym, resets=(), init=None):
    """Bits to code sym[i] with adaptive model ctx[i] (all models reset at the given positions,
    to uniform or to the trained CDFs init[nctx, nsyms + 1])."""
    ctx = np.ascontiguousarray(ctx, dtype=np.int32)
    sym = np.ascontiguousarray(sym, dtype=np.int32)
    assert ctx.shape == sym.shape
    if not len(sym):
        return 0.0
    assert 0 <= ctx.min() and ctx.max() < nctx and 0 <= sym.min() and sym.max() < nsyms
    res = np.ascontiguousarray(sorted(resets), dtype=np.int64)
    if init is not None:
        init = np.ascontiguousarray(init, dtype=np.uint16)
        assert init.shape == (nctx, nsyms + 1)
    return lib.mule_stream_cost_init(nsyms, nctx, ffi.from_buffer("int32_t[]", ctx),
                                     ffi.from_buffer("int32_t[]", sym), len(sym),
                                     ffi.from_buffer("int64_t[]", res), len(res),
                                     ffi.from_buffer("uint16_t[]", init) if init is not None
                                     else ffi.NULL)


def stream_cost_each(nsyms, nctx, ctx, sym, resets=(), init=None):
    """stream_cost, as each symbol's bits (float64 array)."""
    ctx = np.ascontiguousarray(ctx, dtype=np.int32)
    sym = np.ascontiguousarray(sym, dtype=np.int32)
    out = np.zeros(len(sym))
    if not len(sym):
        return out
    assert 0 <= ctx.min() and ctx.max() < nctx and 0 <= sym.min() and sym.max() < nsyms
    res = np.ascontiguousarray(sorted(resets), dtype=np.int64)
    if init is not None:
        init = np.ascontiguousarray(init, dtype=np.uint16)
        assert init.shape == (nctx, nsyms + 1)
    lib.mule_stream_cost_each(nsyms, nctx, ffi.from_buffer("int32_t[]", ctx),
                              ffi.from_buffer("int32_t[]", sym), len(sym),
                              ffi.from_buffer("int64_t[]", res), len(res),
                              ffi.from_buffer("uint16_t[]", init) if init is not None else ffi.NULL,
                              ffi.from_buffer("double[]", out))
    return out


def counts_to_cdf(counts, prior=0.5):
    """Trained initial CDFs (15 bits) from symbol counts [nctx, nsyms]: add-`prior` smoothing,
    unseen contexts uniform."""
    counts = np.asarray(counts, float) + prior
    p = counts / counts.sum(axis=1, keepdims=True)
    cdf = np.zeros((counts.shape[0], counts.shape[1] + 1))
    cdf[:, 1:] = np.cumsum(p, axis=1)
    cdf = np.round(cdf * 32768).astype(np.int64)
    cdf[:, -1] = 32768
    return np.maximum.accumulate(cdf, axis=1).astype(np.uint16)


def bits_table(cdf):
    """Cost in bits of each symbol under CDFs [nctx, nsyms + 1], as core/model.c codes them
    (MULE_MIN_FREQ floor): [nctx, nsyms]."""
    cdf = np.asarray(cdf, np.int64)
    n = cdf.shape[1] - 1
    span = 32768 - n * 4
    start = (cdf * span >> 15) + np.arange(n + 1) * 4
    start[:, -1] = 32768
    return 15 - np.log2(np.diff(start, axis=1))


class Models:
    """Adaptive models state of the rANS encoder (core/rans.c), persistent across packets."""

    def __init__(self):
        self.p = ffi.gc(lib.mule_models_alloc(), lib.mule_models_free)

    def reset(self):
        """Back to the initial models (the trained tables), as at a key packet."""
        lib.mule_models_reset(self.p)

    def copy(self):
        """An independent copy of these models (their adaptation state included)."""
        o = Models()
        lib.mule_models_copy(o.p, self.p)
        return o

    def encode(self, model, val, cap=8192):
        """rANS payload of one packet's operations (models adapted), or None if > cap bytes."""
        model = np.ascontiguousarray(model, np.int32)
        val = np.ascontiguousarray(val, np.uint32)
        out = ffi.new("uint8_t[]", cap)
        n = lib.mule_rans_encode(self.p, ffi.from_buffer("int32_t[]", model),
                                 ffi.from_buffer("uint32_t[]", val), len(model), out, cap)
        return None if n < 0 else bytes(ffi.buffer(out, n))


class Decoder:
    """core/dec.c, the reference decoder (integers only, int16 output: the player's samples)."""

    def __init__(self, head):
        self.p = lib.mule_dec_new(head, len(head))
        if self.p == ffi.NULL:
            raise ValueError("invalid MULEHead")
        self.p = ffi.gc(self.p, lib.mule_dec_free)
        self.pre_skip = lib.mule_dec_pre_skip(self.p)

    def packet(self, data):
        """Decoded samples (n, 2) int16 of one audio packet (n = 0 while skipping to a key)."""
        out = np.zeros((8 * 1024, 2), np.int16)
        n = lib.mule_dec_packet(self.p, data, len(data), ffi.from_buffer("int16_t[]", out), 8 * 1024)
        if n < 0:
            raise ValueError(f"packet decoding failed ({n})")
        return out[:n]

    def seek(self):
        """After a jump: packets dropped until a key packet, then its first frame."""
        lib.mule_dec_seek(self.p)


def c_params(params):
    """params.Params -> mule_enc_params (core/mule_enc.h)."""
    p = ffi.new("mule_enc_params *")
    lib.mule_enc_defaults(p)
    p.q_db = params.q_db
    p.keyframe = params.keyframe
    p.groups = {"adaptive": 0, "8": 8, "1": 1}[params.groups]
    p.group_db = params.group_db
    p.stereo = {"auto": 0, "lr": 1, "ms": 2}[params.stereo]
    p.ath_db = params.ath_db
    p.tonal_all = int(params.tonal == "all")
    p.low_db = params.low_db
    p.mid_db = params.mid_db
    p.mid_hi = params.mid_hi
    p.ton_scale = params.ton_scale
    p.tcap_db = params.tcap_db if params.tcap_db is not None else 0.0
    p.alloc_auto = int(params.alloc_mode == "auto")
    p.alloc_hyst = params.alloc_hyst
    p.fft_tonal = int(params.fft_tonal)
    p.fft_noise_db = params.fft_noise_db
    p.rd_lambda = params.rd_lambda
    p.tcq_lam = params.tcq_lam
    p.tcq_rd = params.tcq_rd
    p.tcq_rdl = params.tcq_rdl
    p.fine_p = params.fine_p
    p.fine_w = params.fine_w
    p.fine_nb = params.fine_nb
    p.pre_db = params.pre_db
    p.nf_bias = params.nf_bias
    p.tg = params.tg
    p.tg_db = params.tg_db
    p.tg_ton = params.tg_ton
    p.tg_a = params.tg_a
    p.tg_band = params.tg_band
    p.nf_top = params.nf_top
    p.eg = params.eg
    p.eg_band = params.eg_band
    p.eg_db = params.eg_db
    p.eg_a = params.eg_a
    p.tr_hf = params.tr_hf
    p.tr_hf_fc = params.tr_hf_fc
    p.tr_hf_db = params.tr_hf_db
    p.tr_decay_db = params.tr_decay_db
    p.tr_hf_ton = params.tr_hf_ton
    p.nf_off_db = params.nf_off_db
    p.spread_mode = params.spread_mode
    p.sp_dz = params.sp_dz
    p.dyn_a = params.dyn_a
    p.tr_db = params.tr_db
    p.group_mode = params.group_mode
    p.short_db = params.short_db
    p.tcq_states = params.tcq_states
    p.tcq_chain = params.tcq_chain
    p.coef_a8 = params.coef_a8
    p.tcq_rd_states = params.tcq_rd_states
    return p


def c_encode(x, params, tags=None):
    """C encoder: x (L, 2) float -> (Ogg file bytes, audio packet bytes)."""
    x = np.ascontiguousarray(x, np.float64)
    assert x.ndim == 2 and x.shape[1] == 2
    p = c_params(params)
    pairs = tags.items() if isinstance(tags, dict) else (tags or [])   # a dict, or (key, value)s
    items = [ffi.new("char[]", f"{k.upper()}={v}".encode()) for k, v in pairs]
    tarr = ffi.new("char *[]", items) if items else ffi.NULL
    out = ffi.new("uint8_t **")
    n = ffi.new("size_t *")
    ab = ffi.new("size_t *")
    rc = lib.mule_encode(ffi.from_buffer("double[]", x), len(x), p, tarr, len(items), out, n, ab)
    if rc:
        raise RuntimeError(f"mule_encode failed ({rc})")
    data = bytes(ffi.buffer(out[0], n[0]))
    lib.mule_free(out[0])
    return data, ab[0]


def c_ops(x, params):
    """C encoder's coding operations: (model, val, frame_start) numpy arrays."""
    x = np.ascontiguousarray(x, np.float64)
    p = c_params(params)
    m, v, fs = ffi.new("int32_t **"), ffi.new("uint32_t **"), ffi.new("int64_t **")
    n, T = ffi.new("int64_t *"), ffi.new("int *")
    if lib.mule_encode_ops(ffi.from_buffer("double[]", x), len(x), p, m, v, n, fs, T):
        raise RuntimeError("mule_encode_ops failed")
    out = (np.frombuffer(ffi.buffer(m[0], 4 * n[0]), np.int32).copy(),
           np.frombuffer(ffi.buffer(v[0], 4 * n[0]), np.uint32).copy(),
           np.frombuffer(ffi.buffer(fs[0], 8 * (T[0] + 1)), np.int64).copy())
    for q in (m[0], v[0], fs[0]):
        lib.mule_free(q)
    return out


TRACE_FIELDS = {
    "coef": ["kind", "op", "frame", "ch", "type", "band", "line", "ac", "tail1", "tail2", "inter", "e",
             "yprev", "mag", "ctx", "pm", "level", "x256", "lam1e4", "tstate"],
    "energy": ["kind", "op", "frame", "ch", "type", "band", "q", "pred", "r", "ctx", "alpha", "group",
               "key", "qprev", "ms", "_1", "_2", "_3", "_4", "_5"],
    "band": ["kind", "op", "frame", "ch", "type", "band", "a", "ms", "group", "mask_mdb", "pow_mdb", "q",
             "k0", "k1", "flat_cdb", "peak_mdb", "_3", "_4", "_5", "_6"],
}


def c_trace(x, params):
    """C encoder's coding operations and its measurement trace (mule_encode_trace, mule_enc.h):
    (model, val, frame_start, trace) with trace an (n, 20) int32 array, fields TRACE_FIELDS."""
    x = np.ascontiguousarray(x, np.float64)
    p = c_params(params)
    m, v, fs = ffi.new("int32_t **"), ffi.new("uint32_t **"), ffi.new("int64_t **")
    tr, n, nt, T = ffi.new("int32_t **"), ffi.new("int64_t *"), ffi.new("int64_t *"), ffi.new("int *")
    if lib.mule_encode_trace(ffi.from_buffer("double[]", x), len(x), p, m, v, n, fs, T, tr, nt):
        raise RuntimeError("mule_encode_trace failed")
    out = (np.frombuffer(ffi.buffer(m[0], 4 * n[0]), np.int32).copy(),
           np.frombuffer(ffi.buffer(v[0], 4 * n[0]), np.uint32).copy(),
           np.frombuffer(ffi.buffer(fs[0], 8 * (T[0] + 1)), np.int64).copy(),
           np.frombuffer(ffi.buffer(tr[0], 80 * nt[0]), np.int32).reshape(-1, 20).copy())
    for q in (m[0], v[0], fs[0], tr[0]):
        lib.mule_free(q)
    return out
