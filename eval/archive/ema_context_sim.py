"""M8 (docs/V3-IDEAS.md), simulation before the measure: conditional entropy of MDCT indices with
a |y_prev| context or a moving average, on a synthetic signal (held notes, vibrato). The real
measure on dev is ctx_lab.py m8 (eval/results/M-LOG.md: the gain did not hold). Runs on import:
no arguments."""
import numpy as np
rng=np.random.default_rng(1); fs=44100; N=1024; T=30
t=np.arange(fs*T)/fs
# signal synthétique : notes harmoniques qui changent toutes les ~1.5 s + vibrato léger + bruit
x=np.zeros_like(t)
for s in range(0,T*2,3):
    seg=(t>=s/2)&(t<s/2+1.5)
    f0=rng.choice([110,147,196,262,330])
    for h in range(1,12):
        x[seg]+= (0.6/h)*np.sin(2*np.pi*h*f0*t[seg]*(1+0.003*np.sin(2*np.pi*5*t[seg]))+rng.uniform(0,6.3))
x+=0.02*rng.standard_normal(len(x))
# MDCT (fenêtre sinus, saut N)
n=np.arange(2*N); w=np.sin(np.pi*(n+.5)/(2*N)); k=np.arange(N)
C=np.cos(np.pi/N*(n[:,None]+.5+N/2)*(k[None,:]+.5))
F=[(w*x[i:i+2*N])@C for i in range(0,len(x)-2*N,N)]
X=np.array(F); y=np.abs(np.round(X/np.percentile(np.abs(X),90)*4)).astype(int)  # index quantifiés
y=np.minimum(y,15)
def H_cond(y,pred,ncls=12):
    # classes de contexte : quantification log du prédicteur
    c=np.minimum((np.log2(1+pred)*3).astype(int),ncls-1)
    H=0;tot=y.size
    for ci in range(ncls):
        m=c==ci; n=m.sum()
        if n==0: continue
        p=np.bincount(y[m],minlength=16)/n; p=p[p>0]
        H+= n/tot*(-(p*np.log2(p)).sum())
    return H
yy=y[1:]; base=H_cond(yy,np.zeros_like(yy,dtype=float),1)
print(f"sans contexte : {base:.3f} bit/coef")
print(f"|y_prev|       : {H_cond(yy,y[:-1].astype(float)):.3f}")
for a in (0.3,0.5,0.7,0.85):
    e=np.zeros(N); preds=[]
    for f in range(len(y)-1):
        e=a*e+(1-a)*y[f]; preds.append(e.copy())
    preds=np.array(preds)/(1-a**np.arange(1,len(y))[:,None]).clip(1e-9)  # correction du démarrage
    print(f"EMA a={a:<5}: {H_cond(yy,preds):.3f}")
    if a==0.5:
        print(f"max(|y_prev|, EMA 0.5) : {H_cond(yy,np.maximum(y[:-1],preds)):.3f}")
