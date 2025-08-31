# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Iterable

def _mod11_sri(digits: Iterable[int]) -> int:
    weights = (2,3,4,5,6,7)
    total = 0
    i = 0
    for d in reversed(list(digits)):
        w = weights[i % len(weights)]
        total += int(d) * w
        i += 1
    dv_raw = 11 - (total % 11)
    if dv_raw == 11:
        return 0
    if dv_raw == 10:
        return 1
    return dv_raw

def _only_digits(s: str) -> str:
    return ''.join(ch for ch in (s or '') if ch.isdigit())

def _zpad(s: str, n: int) -> str:
    s = (s or '').strip()
    return s.zfill(n)[-n:]

def generate_access_key(*,
    fecha_emision_ddmmyyyy: str,
    cod_doc: str,
    ruc: str,
    ambiente: str,
    estab: str,
    pto_emi: str,
    secuencial_9d: str,
    codigo_numerico_8d: str,
    tipo_emision: str) -> str:
    f = _only_digits(fecha_emision_ddmmyyyy)
    if len(f) != 8:
        raise ValueError("fecha_emision_ddmmyyyy must be 8 digits ddmmaaaa")
    cdoc = _zpad(_only_digits(cod_doc), 2)
    r = _zpad(_only_digits(ruc), 13)
    amb = _zpad(_only_digits(ambiente), 1)
    e = _zpad(_only_digits(estab), 3)
    p = _zpad(_only_digits(pto_emi), 3)
    seq = _zpad(_only_digits(secuencial_9d), 9)
    cn = _zpad(_only_digits(codigo_numerico_8d), 8)
    te = _zpad(_only_digits(tipo_emision), 1)
    base48 = f + cdoc + r + amb + e + p + seq + cn + te
    if len(base48) != 48:
        raise ValueError("Clave base must be 48 digits, got %d" % len(base48))
    dv = _mod11_sri(int(ch) for ch in base48)
    return base48 + str(dv)
