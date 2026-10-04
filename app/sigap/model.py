"""Model kondisi timbunan: z = a + b*(KBDI/150)^g + c*cuaca7, dikalibrasi Nelder-Mead."""
from __future__ import annotations
import json
import numpy as np, pandas as pd
from scipy.optimize import minimize
from scipy.stats import spearmanr
from .config import PARAMS_FILE, JENDELA_API_HARI
from .index import FITUR
from .satellite import _di_luar_kejadian


def _huber(r, delta=1.0):
    a = np.abs(r)
    return np.where(a <= delta, 0.5 * r ** 2, delta * (a - 0.5 * delta))


def pasangkan(fitur, landsat, kejadian=None, ketat=True):
    s = landsat.copy(); s["tanggal"] = s.date.dt.normalize()
    m = s.merge(fitur[["tanggal"] + FITUR], on="tanggal", how="inner")
    m = m[_di_luar_kejadian(m.tanggal, kejadian)]
    if ketat and "qc_ketat" in m:
        m = m[m.qc_ketat]
    return m.dropna(subset=["z_hot"] + FITUR)


class ModelTimbunan:
    def __init__(self, par=None, a=None):
        self.par, self.a = par, a

    def _f(self, p, X):
        g = float(np.clip(abs(p[2]), 0.3, 4.0))
        return p[0] * np.power(np.clip(X.kbdi_n.values, 1e-6, None), g) + p[1] * X.cuaca7.values

    def latih(self, data: list[pd.DataFrame]):
        allm = pd.concat(data)
        def obj(p):
            r = allm.z_hot.values - self._f(p, allm)
            return _huber(r - np.median(r)).mean()
        terbaik = None
        for b in (0.5, 1.5, 3.0):
            for c in (-1, 0, 1):
                for g in (0.5, 1, 2):
                    r = minimize(obj, [b, c, g], method="Nelder-Mead",
                                 options={"maxiter": 3000, "xatol": 1e-4, "fatol": 1e-6})
                    if terbaik is None or r.fun < terbaik.fun:
                        terbaik = r
        self.par = terbaik.x.tolist()
        self.a = float(np.median(allm.z_hot.values - self._f(terbaik.x, allm)))
        return self

    def prediksi(self, X):
        return self.a + self._f(np.array(self.par), X)

    def uraian(self):
        g = float(np.clip(abs(self.par[2]), 0.3, 4.0))
        return f"z = {self.a:.2f} + {self.par[0]:.2f}·(KBDI/150)^{g:.2f} + {self.par[1]:.2f}·cuaca7"

    def simpan(self, path=PARAMS_FILE):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"par": self.par, "a": self.a}, indent=2))
        return path

    @classmethod
    def muat(cls, path=PARAMS_FILE):
        if not path.exists():
            return None
        d = json.loads(path.read_text())
        return cls(par=d["par"], a=d["a"])


def evaluasi(model: ModelTimbunan, fitur, landsat, kejadian=None) -> dict:
    m = pasangkan(fitur, landsat, kejadian)
    pred, y = model.prediksi(m), m.z_hot.values
    rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
    return {"n": len(m), "RMSE": round(rmse, 3),
            "perbaikan_%": round(100 * (1 - rmse / float(np.sqrt(np.mean(y ** 2)))), 1),
            "rho": round(float(spearmanr(pred, y).correlation), 3)}
