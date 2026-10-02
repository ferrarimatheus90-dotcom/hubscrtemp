#!/usr/bin/env python3
"""Desenho técnico paramétrico da vasilha (tigela) de aço inox.

Folha A3 paisagem, 1º diedro (ABNT), escala 1:1:
  - vista frontal em meio corte (metade esquerda em vista, metade direita em corte)
  - vista superior
  - detalhe A (aba / borda enrolada) 5:1 e detalhe B (fundo) 2:1

Uso:
    python3 vasilha.py medidas.json

Cotas que não estiverem no JSON usam o valor estimado pelas fotos e saem no
desenho marcadas com asterisco (*).
"""
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Arc as MArc
from matplotlib.patches import Circle as MCircle
from matplotlib.patches import Polygon as MPoly
from shapely.geometry import LineString, MultiPolygon, Point

AQUI = os.path.dirname(os.path.abspath(__file__))

# Cotas da peça (mm / graus). Estimativas tiradas das fotos, usadas quando a
# medida com paquímetro não foi informada.
ESTIMADAS = {
    "A": 134.0,   # Ø externo total (borda enrolada)
    "B": 109.0,   # Ø externo da parede no início da curva da aba
    "C": 88.4,    # Ø externo do fundo (canto vivo virtual parede/fundo)
    "D": 48.0,    # Ø do rebaixo central do fundo
    "P": 48.2,    # profundidade interna (topo da borda até o centro do fundo)
    "e": 0.5,     # espessura da chapa
    "b": 1.6,     # espessura da borda enrolada
    "R1": 6.0,    # raio da curva parede/aba (face externa)
    "R2": 5.0,    # raio externo do fundo
    "p": 1.0,     # altura do rebaixo central
    "beta": 40.0, # inclinação da aba em relação à horizontal (graus)
}

MM = 72.0 / 25.4            # pontos por mm
GROSSA = 0.6 * MM           # linha de contorno visível
FINA = 0.25 * MM            # cota, extensão, linha de centro
TXT = 3.0                   # altura de texto das cotas (mm)


def fonte(h_mm):
    """Altura de maiúscula em mm -> tamanho de fonte em pt."""
    return h_mm / 0.73 * MM


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def fmt(v):
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")


# --------------------------------------------------------------------------- geometria

def arco_canto(p_ant, p, p_prox, r, n=40):
    """Arredonda o canto p (entre p_ant->p e p->p_prox) com raio r."""
    p_ant, p, p_prox = (np.asarray(q, float) for q in (p_ant, p, p_prox))
    v1, v2 = unit(p_ant - p), unit(p_prox - p)
    ang = math.acos(np.clip(np.dot(v1, v2), -1, 1))
    t = r / math.tan(ang / 2)
    t1, t2 = p + v1 * t, p + v2 * t
    c = p + unit(v1 + v2) * r / math.sin(ang / 2)
    a1 = math.atan2(*(t1 - c)[::-1])
    a2 = math.atan2(*(t2 - c)[::-1])
    d = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
    pts = [c + r * np.array([math.cos(a1 + d * s), math.sin(a1 + d * s)])
           for s in np.linspace(0, 1, n)]
    return pts, c


def arco_horario(c, r, a_ini, a_fim, n=40):
    return [c + r * np.array([math.cos(a), math.sin(a)]) for a in np.linspace(a_ini, a_fim, n)]


class Perfil:
    """Perfil de revolução (metade direita, eixo em x = 0, mesa em y = 0).

    `pele` é a face externa da chapa (fundo por baixo, parede e aba por fora);
    a chapa de espessura e fica à esquerda do sentido de percurso.
    Incógnitas resolvidas numericamente: altura do início da curva da aba (yT)
    e comprimento reto da aba (Lf), para fechar Ø A e a altura total.
    """

    VARREDURA_BORDA = 230  # graus da borda enrolada

    def __init__(self, m):
        self.m = m
        self.H = m["P"] + m["p"] + m["e"]
        self.yT = self.H - 10
        self.Lf = 8.0
        for _ in range(80):
            self._construir()
            xmax, ymax = self.banda.bounds[2], self.banda.bounds[3]
            self.Lf += (m["A"] / 2 - xmax) / math.cos(math.radians(m["beta"]))
            self.yT += self.H - ymax
        self._construir()

    def _construir(self):
        m = self.m
        e, p = m["e"], m["p"]
        beta = math.radians(m["beta"])
        rc = m["D"] / 2
        w = max(1.5 * p, 1.0)
        self.rc, self.w = rc, w
        P0, P1, P2 = (0.0, p), (rc - w, p), (rc, 0.0)
        Q0 = np.array([m["C"] / 2, 0.0])
        T1 = np.array([m["B"] / 2, self.yT])
        self.T1 = T1
        uw = unit(T1 - Q0)
        self.theta = math.atan2(uw[0], uw[1])  # inclinação da parede em relação à vertical
        # concordância do fundo: canto virtual Q0 entre fundo e parede
        arco0, self.c0 = arco_canto(P2, Q0, T1, m["R2"])
        # curva da aba: começa tangente à parede em T1, gira no sentido horário até beta
        c1 = T1 + m["R1"] * np.array([uw[1], -uw[0]])
        a_ini = math.atan2(*(T1 - c1)[::-1])
        a_fim = beta + math.pi / 2
        arco1 = arco_horario(c1, m["R1"], a_ini, a_fim)
        self.c1 = c1
        F0 = arco1[-1]
        d = np.array([math.cos(beta), math.sin(beta)])
        E = F0 + d * self.Lf
        self.F0, self.E = F0, E
        # borda enrolada para fora/baixo, diâmetro externo b
        rb = max(m["b"] / 2 - e, 0.05)
        cb = E + rb * np.array([math.sin(beta), -math.cos(beta)])
        a0 = beta + math.pi / 2
        borda = arco_horario(cb, rb, a0, a0 - math.radians(self.VARREDURA_BORDA))
        self.cb = cb
        self.arco0 = arco0
        pts = [P0, P1, P2] + arco0[:-1] + arco1 + [E] + borda[1:]
        self.pele = np.array(pts, float)
        linha = LineString(self.pele)
        self.banda = linha.buffer(e, single_sided=True, cap_style="flat", join_style="round")
        ext = np.array(self.banda.exterior.coords)
        j = np.argmax(ext[:, 1])
        self.x_topo = ext[j, 0]  # topo da borda (y = H)
        mask = ext[:, 0] > m["A"] / 2 - m["b"] - 0.3
        i = np.argmin(np.where(mask, ext[:, 1], np.inf))
        self.y_borda, self.x_borda = ext[i, 1], ext[i, 0]

    def raio_max(self, y):
        """Maior raio da peça na altura y (silhueta da vista externa)."""
        corte = self.banda.intersection(LineString([(0, y), (1e3, y)]))
        if corte.is_empty:
            return None
        return corte.bounds[2]

    def silhueta(self, passo=0.02):
        H = self.H
        pts = [(0.0, 0.0)]
        for y in np.arange(passo / 2, H, passo):
            r = self.raio_max(y)
            if r is not None:
                pts.append((r, y))
        pts.append((self.x_topo, H))
        pts.append((0.0, H))
        return np.array(pts)

    def corte_normal(self, ponto, n):
        """Interseção da chapa com a reta por `ponto` na direção n -> (p_menor, p_maior)."""
        ponto, n = np.asarray(ponto, float), unit(n)
        seg = LineString([ponto - 5 * n, ponto + 5 * n])
        g = self.banda.intersection(seg)
        xy = np.array(g.coords) if g.geom_type == "LineString" else np.array(
            [c for gg in g.geoms for c in gg.coords])
        s = (xy - ponto) @ n
        return ponto + n * s.min(), ponto + n * s.max()


# --------------------------------------------------------------------------- folha

class Folha:
    def __init__(self):
        self.fig = plt.figure(figsize=(420 / 25.4, 297 / 25.4))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, 420)
        self.ax.set_ylim(0, 297)
        self.ax.set_aspect("equal")
        self.ax.axis("off")

    def linha(self, pts, lw=GROSSA, cor="k", z=3, ls="-"):
        pts = np.asarray(pts, float)
        self.ax.plot(pts[:, 0], pts[:, 1], color=cor, lw=lw, ls=ls,
                     solid_capstyle="butt", solid_joinstyle="round", zorder=z)

    def centro(self, p1, p2):
        seq = [8, 1.5, 0.5, 1.5]
        dash = tuple(s * MM / FINA for s in seq)
        self.linha([p1, p2], lw=FINA, ls=(0, dash), z=2)

    def circulo(self, c, r, lw=GROSSA, cor="k"):
        self.ax.add_patch(MCircle(c, r, fill=False, lw=lw, ec=cor, zorder=3))

    def texto(self, p, s, h=TXT, cor="k", **kw):
        kw.setdefault("ha", "center")
        kw.setdefault("va", "bottom")
        self.ax.text(p[0], p[1], s, fontsize=fonte(h), color=cor,
                     family="DejaVu Sans", zorder=6, **kw)

    def seta(self, ponta, d, L=2.6, larg=0.95):
        d = unit(d)
        n = np.array([-d[1], d[0]])
        ponta = np.asarray(ponta, float)
        base = ponta - d * L
        self.ax.add_patch(MPoly([ponta, base + n * larg / 2, base - n * larg / 2],
                                closed=True, fc="k", ec="k", lw=0, zorder=5))

    def preencher(self, geom, desloc, esc):
        polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
        for g in polys:
            if g.is_empty:
                continue
            xy = np.array(g.exterior.coords) * esc + desloc
            self.ax.add_patch(MPoly(xy, closed=True, fc="k", ec="k", lw=FINA, zorder=3))

    # ---- cotas
    def cota_h(self, xa, xb, ya, yb, yd, txt, fora=False, folga=1.0):
        for x, y in ((xa, ya), (xb, yb)):
            s = 1 if yd > y else -1
            self.linha([(x, y + s * folga), (x, yd + s * 2)], lw=FINA)
        if fora:
            self.linha([(xa - 7, yd), (xb + 7, yd)], lw=FINA)
            self.seta((xa, yd), (1, 0))
            self.seta((xb, yd), (-1, 0))
        else:
            self.linha([(xa, yd), (xb, yd)], lw=FINA)
            self.seta((xa, yd), (-1, 0))
            self.seta((xb, yd), (1, 0))
        self.texto(((xa + xb) / 2, yd + 0.8), txt)

    def cota_v(self, ya, yb, xa, xb, xd, txt, fora=False, folga=1.0, txt_lado=-1,
               extensao=True):
        if extensao:
            for y, x in ((ya, xa), (yb, xb)):
                s = 1 if xd > x else -1
                self.linha([(x + s * folga, y), (xd + s * 2, y)], lw=FINA)
        if fora:
            self.linha([(xd, ya - 7), (xd, yb + 7)], lw=FINA)
            self.seta((xd, ya), (0, 1))
            self.seta((xd, yb), (0, -1))
        else:
            self.linha([(xd, ya), (xd, yb)], lw=FINA)
            self.seta((xd, ya), (0, -1))
            self.seta((xd, yb), (0, 1))
        ha = "right" if txt_lado < 0 else "left"
        self.texto((xd + 0.8 * txt_lado, (ya + yb) / 2), txt,
                   rotation=90, ha=ha, va="center")

    def cota_meia(self, x_eixo, xb, yb, yd, txt):
        """Cota de diâmetro em meio corte: uma seta só, linha passa do eixo."""
        s = 1 if yd > yb else -1
        self.linha([(xb, yb + s * 1.0), (xb, yd + s * 2)], lw=FINA)
        self.linha([(x_eixo - 9, yd), (xb, yd)], lw=FINA)
        self.seta((xb, yd), (1, 0))
        self.texto(((x_eixo + xb) / 2, yd + 0.8), txt)

    def cota_raio(self, c, R, ang, txt, comp=9, de_fora=True, ombro=7):
        """Cota de raio: seta tocando o arco, vinda de fora (apontando para o
        centro) ou saindo do centro."""
        u = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
        c = np.asarray(c, float)
        p_arco = c + R * u
        if de_fora:
            p_fim = p_arco + comp * u
            self.seta(p_arco, -u)
        else:
            p_fim = c - comp * u
            self.seta(p_arco, u)
        self.linha([p_arco, p_fim], lw=FINA)
        self.ombro(p_fim, txt, 1 if p_fim[0] >= p_arco[0] else -1, ombro)

    def ombro(self, p_fim, txt, lado, comp=7):
        p_ombro = p_fim + np.array([lado * comp, 0])
        self.linha([p_fim, p_ombro], lw=FINA)
        self.texto(((p_fim[0] + p_ombro[0]) / 2, p_fim[1] + 0.8), txt)

    def chamada(self, ponta, p_fim, txt, lado=1, comp=12):
        """Linha de chamada com seta tocando a peça."""
        ponta, p_fim = np.asarray(ponta, float), np.asarray(p_fim, float)
        self.linha([ponta, p_fim], lw=FINA)
        self.seta(ponta, ponta - p_fim)
        self.ombro(p_fim, txt, lado, comp)

    def cota_angulo(self, v, r, a0, a1, txt):
        a0d, a1d = math.degrees(a0), math.degrees(a1)
        self.ax.add_patch(MArc(v, 2 * r, 2 * r, theta1=a0d, theta2=a1d,
                               lw=FINA, ec="k", zorder=4))
        for a, s in ((a0, -1), (a1, 1)):
            p = np.asarray(v) + r * np.array([math.cos(a), math.sin(a)])
            tang = np.array([-math.sin(a), math.cos(a)]) * s
            self.seta(p, tang, L=2.2, larg=0.8)
        am = (a0 + a1) / 2
        pt = np.asarray(v) + (r + 1.5) * np.array([math.cos(am), math.sin(am)])
        self.texto(pt, txt, ha="left", va="center")


# --------------------------------------------------------------------------- desenho

def desenhar(medidas, saida_base):
    m = {k: float(medidas[k]) if medidas.get(k) is not None else v for k, v in ESTIMADAS.items()}
    estimadas = [k for k in ESTIMADAS if medidas.get(k) is None]

    def rot(k, prefixo="", sufixo=""):
        return prefixo + fmt(m[k]) + sufixo + ("*" if k in estimadas else "")

    perf = Perfil(m)
    A, B, C, D, e = (m[k] for k in "ABCDe")
    H = perf.H
    f = Folha()

    # ---- moldura (NBR 10068: margem esquerda 25, demais 10 para A3)
    f.linha([(25, 10), (410, 10), (410, 287), (25, 287), (25, 10)], lw=0.7 * MM)

    # ================= VISTA FRONTAL (meio corte) — escala 1:1
    X0, Y0 = 125.0, 196.0
    o = np.array([X0, Y0])

    f.linha(perf.silhueta() * [-1, 1] + o)
    # contorno inferior da borda enrolada, à frente da aba
    f.linha([(X0 - perf.x_borda, Y0 + perf.y_borda), (X0, Y0 + perf.y_borda)])
    # metade em corte: chapa enegrecida + topo da borda ao fundo
    f.preencher(perf.banda, o, 1.0)
    f.linha([(X0, Y0 + H), (X0 + perf.x_topo, Y0 + H)])
    f.centro((X0, Y0 - 6), (X0, Y0 + H + 6))

    # círculos indicadores dos detalhes
    cA = np.array([(perf.T1[0] + A / 2) / 2 + 0.3, (perf.T1[1] + H) / 2 + 0.3])
    rA = 9.5
    f.circulo(o + cA, rA, lw=FINA)
    f.texto(o + cA + [rA * 0.75, rA * 0.75], "A", h=4, ha="left", va="bottom")
    cB = np.array([(perf.rc - perf.w + C / 2) / 2, 3.0])
    rB = (C / 2 - perf.rc + perf.w) / 2 + 1.5
    f.circulo(o + cB, rB, lw=FINA)
    f.texto(o + cB + [rB * 0.72, rB * 0.72], "B", h=4, ha="left", va="bottom")

    # Ø total (acima)
    f.cota_h(X0 - A / 2, X0 + A / 2, Y0 + perf.cb[1], Y0 + perf.cb[1], Y0 + H + 10, rot("A", "Ø"))
    # diâmetros abaixo: D (meia cota), C (canto vivo virtual), B (início da curva da aba)
    f.cota_meia(X0, X0 + D / 2, Y0, Y0 - 15, rot("D", "Ø"))
    t_fundo, t_parede = perf.arco0[0], perf.arco0[-1]
    for s in (-1, 1):
        f.linha([o + [s * t_fundo[0], 0], o + [s * C / 2, 0]], lw=FINA)
        f.linha([o + [s * t_parede[0], t_parede[1]], o + [s * C / 2, 0]], lw=FINA)
    f.cota_h(X0 - C / 2, X0 + C / 2, Y0, Y0, Y0 - 23, rot("C", "Ø"), folga=0.0)
    yT = perf.T1[1]
    f.cota_h(X0 - B / 2, X0 + B / 2, Y0 + yT, Y0 + yT, Y0 - 31, rot("B", "Ø"))
    # altura total (cota auxiliar) e profundidade interna (medida)
    f.cota_v(Y0, Y0 + H, X0 - t_fundo[0], X0 - perf.x_topo, X0 - A / 2 - 10,
             "(" + fmt(round(H, 1)) + ")")
    f.cota_v(Y0 + m["p"] + e, Y0 + H, None, None, X0 + 12, rot("P"),
             extensao=False, txt_lado=1)

    # ================= VISTA SUPERIOR — escala 1:1 (abaixo da frontal, 1º diedro)
    Xs, Ys = X0, 83.0
    cs = (Xs, Ys)
    f.circulo(cs, A / 2)                                   # borda enrolada (externo)
    f.circulo(cs, perf.E[0] - e, lw=FINA)                  # tangência aba/borda
    f.circulo(cs, perf.F0[0] - e * math.sin(math.radians(m["beta"])), lw=FINA)  # aba/curva
    f.circulo(cs, B / 2 - e, lw=FINA)                      # curva/parede
    f.circulo(cs, perf.arco0[0][0], lw=FINA)               # parede/fundo
    f.circulo(cs, perf.rc)                                 # rebaixo central (arestas)
    f.circulo(cs, perf.rc - perf.w)
    f.centro((Xs - A / 2 - 5, Ys), (Xs + A / 2 + 5, Ys))
    f.centro((Xs, Ys - A / 2 - 4), (Xs, Ys + A / 2 + 4))

    # ================= DETALHES
    def detalhe(cr, rr, esc, centro_folha, letra):
        clip = Point(cr).buffer(rr, 128)
        desloc = np.asarray(centro_folha) - np.asarray(cr) * esc
        f.preencher(perf.banda.intersection(clip), desloc, esc)
        f.circulo(centro_folha, rr * esc, lw=FINA)
        f.texto((centro_folha[0], centro_folha[1] - rr * esc - 4),
                f"DETALHE {letra}  ESCALA {esc}:1", h=3.5, va="top")
        return lambda p: np.asarray(p, float) * esc + desloc

    # ---- DETALHE A — aba, escala 5:1
    escA = 5
    TA = detalhe(cA, rA, escA, (318.0, 230.0), "A")
    beta = math.radians(m["beta"])
    dflange = np.array([math.cos(beta), math.sin(beta)])
    nflange = np.array([math.sin(beta), -math.cos(beta)])  # aponta para fora/baixo
    # e — espessura da chapa, perpendicular à aba
    pm = perf.F0 + dflange * perf.Lf * 0.55
    p_dentro, p_fora = perf.corte_normal(pm, nflange)  # n aponta para fora da vasilha
    s_dentro, s_fora = TA(p_dentro), TA(p_fora)
    f.linha([s_fora + nflange * 9, s_dentro - nflange * 9], lw=FINA)
    f.seta(s_fora, -nflange)
    f.seta(s_dentro, nflange)
    f.ombro(s_dentro - nflange * 9, rot("e"), -1, 9)
    # ângulo da aba com a horizontal
    v = perf.F0 + dflange * 0.4
    sv = TA(v)
    f.linha([sv, sv + [24, 0]], lw=FINA)
    f.cota_angulo(sv, 18, 0.0, beta, rot("beta", sufixo="°"))
    # R1 — curva da aba (face externa), cotada a partir do centro
    a_mid = (math.atan2(*(perf.T1 - perf.c1)[::-1]) + beta + math.pi / 2) / 2
    f.cota_raio(TA(perf.c1), m["R1"] * escA, math.degrees(a_mid), rot("R1", "R"),
                comp=12, de_fora=False)
    # borda enrolada
    ponta = TA(perf.cb + (m["b"] / 2) * unit([0.25, 1.0]))
    f.chamada(ponta, ponta + [10, 14], "BORDA ENROLADA " + rot("b", "Ø"), lado=1, comp=40)

    # ---- DETALHE B — fundo, escala 2:1
    escB = 2
    TB = detalhe(cB, rB, escB, (318.0, 142.0), "B")
    f.cota_raio(TB(perf.c0), m["R2"] * escB, -40, rot("R2", "R"), comp=12)
    q_cima = TB((perf.rc - perf.w, m["p"]))
    q_baixo = TB((perf.rc, 0))
    xd = TB((perf.rc - perf.w - 3.0, 0))[0]
    f.cota_v(q_baixo[1], q_cima[1], q_baixo[0], q_cima[0], xd, rot("p"),
             fora=(q_cima[1] - q_baixo[1]) < 9)

    # ================= NOTAS
    nx, ny = 236.0, 104.0
    notas = [
        "NOTAS:",
        "1. Cotas em milímetros. Tolerância geral ±0,5 mm.",
        f"2. Peça estampada em chapa de aço inox, espessura {rot('e')} mm (constante).",
        f"3. {rot('P')}: profundidade interna, do topo da borda ao centro do fundo.",
        f"4. ({fmt(round(H, 1))}): altura total, cota auxiliar = profundidade + rebaixo + chapa.",
        "5. Ø C até o canto vivo virtual (prolongamento da parede e do fundo).",
        "* Cotas estimadas por foto — conferir com paquímetro.",
    ]
    for i, n in enumerate(notas):
        f.texto((nx, ny - i * 5.0), n, h=2.4, ha="left", va="top",
                weight="bold" if i == 0 else "normal")

    # ================= LEGENDA (NBR 10582) no canto inferior direito
    lx0, lx1 = 232.0, 410.0
    f.linha([(lx0, 10), (lx0, 62), (lx1, 62)], lw=0.7 * MM)
    for y in (52.0, 42.0, 32.0, 21.0):
        f.linha([(lx0, y), (lx1, y)], lw=FINA)

    def campo(x0, x1, y0, y1, rotulo, valor, h=3.2, peso="normal"):
        if x0 > lx0:
            f.linha([(x0, y0), (x0, y1)], lw=FINA)
        f.texto((x0 + 1.2, y1 - 1.0), rotulo, h=1.6, ha="left", va="top", cor="#444")
        f.texto(((x0 + x1) / 2, y0 + 1.6), valor, h=h, ha="center", va="bottom", weight=peso)

    campo(lx0, lx1, 52, 62, "TÍTULO", "VASILHA (TIGELA) EM AÇO INOX", h=4.2, peso="bold")
    campo(lx0, 330, 42, 52, "MATERIAL", f"Aço inoxidável — chapa {rot('e')} mm", h=3)
    campo(330, lx1, 42, 52, "QUANTIDADE", "1", h=3)
    campo(lx0, 330, 32, 42, "DESENHISTA", "", h=3)
    campo(330, lx1, 32, 42, "DATA", "02/10/2026", h=3)
    campo(lx0, 280, 21, 32, "ESCALA", "1:1", h=3.5)
    campo(280, 318, 21, 32, "UNIDADE", "mm", h=3.5)
    campo(318, 352, 21, 32, "FOLHA", "A3", h=3.5)
    campo(352, lx1, 21, 32, "DIEDRO", "", h=3)
    campo(lx0, 330, 10, 21, "Nº DO DESENHO", "VAS-001", h=3.5)
    campo(330, 370, 10, 21, "REVISÃO", "0", h=3.5)
    campo(370, lx1, 10, 21, "FOLHA", "1/1", h=3.5)
    # símbolo do 1º diedro: tronco de cone (ponta menor à esquerda) + vista circular à direita
    sx, sy = 368.0, 25.5
    f.linha([(sx, sy - 1.5), (sx + 9, sy - 3.2), (sx + 9, sy + 3.2), (sx, sy + 1.5), (sx, sy - 1.5)],
            lw=0.35 * MM)
    f.circulo((sx + 18, sy), 3.2, lw=0.35 * MM)
    f.circulo((sx + 18, sy), 1.5, lw=0.35 * MM)
    f.centro((sx - 2, sy), (sx + 11, sy))
    f.centro((sx + 13.5, sy), (sx + 22.5, sy))
    f.texto((sx + 31, sy - 0.2), "1º", h=3.5, ha="center", va="center")

    os.makedirs(os.path.dirname(saida_base), exist_ok=True)
    f.fig.savefig(saida_base + ".pdf")
    f.fig.savefig(saida_base + ".png", dpi=200)
    plt.close(f.fig)
    return perf, estimadas


def main():
    medidas = {}
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as fh:
            medidas = json.load(fh)
    nome = "vasilha_desenho_tecnico"
    perf, estimadas = desenhar(medidas, os.path.join(AQUI, nome))
    print(f"Gerado: {nome}.pdf / {nome}.png")
    print(f"Altura total {perf.H:.2f} | início da curva da aba a {perf.T1[1]:.2f} mm do chão"
          f" | parede a {math.degrees(perf.theta):.1f}° da vertical | aba reta {perf.Lf:.2f} mm")
    if estimadas:
        print("Cotas estimadas (*):", ", ".join(estimadas))


if __name__ == "__main__":
    main()
