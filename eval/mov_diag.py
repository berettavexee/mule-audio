"""PEAQ basic MOVs of Opus 128 and MULE at the same rate, whole items (frame_diag.mule_at), to see
which model output separates them. TR (environment) set the transient detector's ratio in the
experiment of 19/11/2026 (a scratch build only; ignored otherwise).
    python eval/mov_diag.py item1,item2,..."""
import sys, os, re, tempfile, numpy as np, pandas as pd, soundfile as sf
sys.path[:0]=["eval","py"]
import frame_diag as F, metrics, refcodecs, corpus
from concurrent.futures import ProcessPoolExecutor
MOVS=["BandwidthRefB","BandwidthTestB","TotalNMRB","WinModDiff1B","ADBB","EHSB","AvgModDiff1B","AvgModDiff2B","RmsNoiseLoudB","MFPDB","RelDistFramesB"]
def movs(ref,deg,fs):
    with tempfile.TemporaryDirectory() as d:
        r,g=os.path.join(d,"r.wav"),os.path.join(d,"g.wav")
        metrics._to48k(ref,fs,r); metrics._to48k(deg,fs,g)
        env=dict(os.environ, PEAQ_MOVS="1"); peaq=metrics._PEAQ_DEFAULT
        env["GST_PLUGIN_PATH"]=os.path.join(os.path.dirname(os.path.dirname(peaq)),"lib","gstreamer-1.0")
        txt=metrics._run_retry([peaq,r,g],env=env)
    out={m:metrics._mov(txt,m) for m in MOVS}
    m=re.search(r"Objective Difference Grade:\s*([-\d.]+)",txt); out["odg"]=float(m.group(1))
    return out
def job(a):
    name,wav=a
    from mule import native
    if 'TR' in os.environ:
        native.lib.mule_tr_ratio_db=float(os.environ['TR'])
    x,fs=sf.read(wav,dtype="float64",always_2d=True)
    with tempfile.TemporaryDirectory() as work:
        od,_,ok=refcodecs.run("opus_128",wav,work)
        md,q,mk,_=F.mule_at(x,wav,ok,work); _=_.values
        ref0=metrics.subsonic(x,fs); rows=[]
        res={}
        res["short"]={"odg":float((_>0).mean())}
        for tag,p in (("opus",od),("mule",md)):
            y,fs2=metrics.load(p)
            if fs2!=fs:
                import soxr; y=soxr.resample(y,fs2,fs,quality="VHQ")
            r,y,lag=metrics.align(ref0,metrics.subsonic(y,fs))
            res[tag]=movs(r,y,fs)
        return [dict(item=name,codec=t,**v) for t,v in res.items()]
if __name__=="__main__":
    keep=sys.argv[1].split(",")
    items=[it for it in corpus.items("test") if it[0] in keep]
    with ProcessPoolExecutor(len(items)) as ex: rows=[r for rs in ex.map(job,items) for r in rs]
    d=pd.DataFrame(rows).set_index(["item","codec"])
    print(d.round(3).T.to_string())
