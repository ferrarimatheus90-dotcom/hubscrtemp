#!/usr/bin/env python3
"""Desenho técnico paramétrico da vasilha (tigela) de aço inox.

Folha A3 paisagem, 1º diedro (ABNT), escala 1:1:
  - vista frontal em meio corte (metade esquerda em vista, metade direita em corte)
  - vista superior
  - detalhe A (aba / borda) 5:1 e detalhe B (fundo) 3:1

Uso:
    python3 vasilha.py                 # guia de medição (cotas em letras)
    python3 vasilha.py medidas.json    # desenho final com os valores medidos

No JSON, qualquer cota ausente ou null continua aparecendo como letra (em vermelho)
e a geometria usa o valor estimado pelas fotos.
"""
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle as MCircle
from matplotlib.patches import Polygon as MPoly
from shapely.geometry import LineString, Point, Polygon, MultiPolygon

AQUI = os.path.dirname(os.path.abspath(__file__))

# Cotas da peça (mm). Valores estimados a partir das fotos, usados só para a forma
# do desenho enquanto a medida real não chega.
ESTIMADAS = {
    "A": 140.0,  # Ø externo total (borda da aba)
    "B": 125.0,  # Ø interno da boca (onde a parede encontra a aba)
    "C": 98.0,   # Ø externo do fundo (parede rente à mesa)
    "D": 50.0,   # Ø do rebaixo central do fundo
    "H": 48.0,   # altura total
    "e": 0.6,    # espessura da chapa
    "R1": 2.0,   # raio da dobra parede/aba
    "R2": 8.0,   # raio externo do fundo (concordância parede/fundo)
    "p": 1.0,    # profundidade do rebaixo central
    "h": 3.0,    # altura da aba (do topo até a borda de baixo)
}
OBRIGATORIAS = ["A", "B", "C", "D", "H", "e"]

MM = 72.0 / 25.4            # pontos por mm
GROSSA = 0.6 * MM           # linha de contorno visível
FINA = 0.25 * MM            # cota, extensão, linha de centro
TXT = 3.0                   # altura de texto das cotas (mm)
VERMELHO = "#c00000"
LARANJA = "#d07000"


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


class Perfil:
    """Perfil de revolução (metade direita, eixo em x = 0, mesa em y = 0).

    `pele` é a face externa da chapa (fundo por baixo, parede por fora, aba por baixo);
    a chapa de espessura e fica à esquerda do sentido de percurso.
    """

    CURL = 0.9       # raio da borda enrolada (estimado)
    VARREDURA = 160  # graus da borda enrolada

    def __init__(self, m):
        self.m = m
        A, B, H, e, h = m["A"], m["B"], m["H"], m["e"], m["h"]
        self.xE = A / 2 - self.CURL - e - 1
        self.yfl = H - e
        self.alfa = math.radians(5)
        for _ in range(60):
            self._construir()
            xmax, ymax = self.banda.bounds[2], self.banda.bounds[3]
            L = max(self.xE - self.Q1[0], 1.0)
            self.xE += A / 2 - xmax
            self.yfl += H - ymax
            self.alfa += (self.y_borda - (H - h)) / L * 0.8
            self.alfa = min(max(self.alfa, math.radians(-5)), math.radians(35))
        self._construir()

    def _construir(self):
        m = self.m
        e, p = m["e"], m["p"]
        rc = m["D"] / 2
        w = max(1.5 * p, 1.0)
        self.rc, self.w = rc, w
        P0, P1, P2 = (0.0, p), (rc - w, p), (rc, 0.0)
        Q0 = np.array([m["C"] / 2, 0.0])
        Q1 = np.array([m["B"] / 2 + e, self.yfl])
        E = np.array([self.xE, self.yfl - (self.xE - Q1[0]) * math.tan(self.alfa)])
        self.Q0, self.Q1, self.E = Q0, Q1, E
        arco0, self.c0 = arco_canto(P2, Q0, Q1, m["R2"])
        arco1, self.c1 = arco_canto(Q0, Q1, E, m["R1"])
        # borda enrolada para baixo (giro horário a partir do fim da aba)
        a = self.alfa
        cc = E + self.CURL * np.array([-math.sin(a), -math.cos(a)])
        a0 = math.pi / 2 - a
        enrolado = [cc + self.CURL * np.array([math.cos(a0 - t), math.sin(a0 - t)])
                    for t in np.linspace(0, math.radians(self.VARREDURA), 40)]
        self.cc = cc
        self.arco0, self.arco1 = arco0, arco1
        pts = [P0, P1, P2] + arco0 + arco1 + [E] + enrolado[1:]
        self.pele = np.array(pts, float)
        linha = LineString(self.pele)
        self.banda = linha.buffer(e, single_sided=True, cap_style="flat", join_style="round")
        self.interna = np.array(linha.offset_curve(e, join_style="round").coords)
        # ponto mais baixo da borda (lado de fora da parede)
        ext = np.array(self.banda.exterior.coords)
        mask = ext[:, 0] > Q1[0] + m["R1"] + 0.5
        i = np.argmin(np.where(mask, ext[:, 1], np.inf))
        self.y_borda, self.x_borda = ext[i, 1], ext[i, 0]
        j = np.argmax(ext[:, 1])
        self.x_topo = ext[j, 0]  # topo da dobra (y = H)

    def raio_max(self, y):
        """Maior raio da peça na altura y (silhueta da vista externa)."""
        corte = self.banda.intersection(LineString([(0, y), (1e3, y)]))
        if corte.is_empty:
            return None
        return corte.bounds[2]

    def silhueta(self, passo=0.02):
        H = self.m["H"]
        ys = np.arange(passo / 2, H, passo)
        pts = [(0.0, 0.0)]
        for y in ys:
            r = self.raio_max(y)
            if r is not None:
                pts.append((r, y))
        pts.append((self.x_topo, H))
        pts.append((0.0, H))
        return np.array(pts)

    def espessura_em_x(self, x):
        corte = self.banda.intersection(LineString([(x, -5), (x, 300)]))
        return corte.bounds[1], corte.bounds[3]


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

    def circ_centro(self, c, r):
        seq = [8, 1.5, 0.5, 1.5]
        dash = tuple(s * MM / FINA for s in seq)
        self.ax.add_patch(MCircle(c, r, fill=False, lw=FINA, ls=(0, dash), zorder=2))

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

    def preencher(self, geom, desloc, esc, cor="k"):
        polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
        for g in polys:
            if g.is_empty:
                continue
            xy = np.array(g.exterior.coords) * esc + desloc
            self.ax.add_patch(MPoly(xy, closed=True, fc=cor, ec="k", lw=FINA, zorder=3))

    # ---- cotas
    def cota_h(self, xa, xb, ya, yb, yd, txt, cor="k", fora=False, folga=1.0):
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
        self.texto(((xa + xb) / 2, yd + 0.8), txt, cor=cor)

    def cota_v(self, ya, yb, xa, xb, xd, txt, cor="k", fora=False, folga=1.0, txt_lado=-1):
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
        self.texto((xd + 0.8 * txt_lado, (ya + yb) / 2), txt, cor=cor,
                   rotation=90, ha=ha, va="center")

    def cota_meia(self, x_eixo, xb, yb, yd, txt, cor="k"):
        """Cota de diâmetro em meio corte: uma seta só, linha passa do eixo."""
        s = 1 if yd > yb else -1
        self.linha([(xb, yb + s * 1.0), (xb, yd + s * 2)], lw=FINA)
        self.linha([(x_eixo - 9, yd), (xb, yd)], lw=FINA)
        self.seta((xb, yd), (1, 0))
        self.texto(((x_eixo + xb) / 2, yd + 0.8), txt, cor=cor)

    def cota_raio(self, c, R, ang, txt, cor="k", comp=9, de_fora=True, ombro=6):
        """Cota de raio: seta tocando o arco, apontada para o centro (de fora)
        ou saindo do centro (de dentro)."""
        u = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
        c = np.asarray(c, float)
        p_arco = c + R * u
        if de_fora:
            p_fim = p_arco + comp * u
            self.linha([p_arco, p_fim], lw=FINA)
            self.seta(p_arco, -u)
        else:
            p_fim = c - comp * u
            self.linha([p_arco, p_fim], lw=FINA)
            self.seta(p_arco, u)
        lado = 1 if p_fim[0] >= p_arco[0] else -1
        p_ombro = p_fim + np.array([lado * ombro, 0])
        self.linha([p_fim, p_ombro], lw=FINA)
        self.texto(((p_fim[0] + p_ombro[0]) / 2, p_fim[1] + 0.8), txt, cor=cor)


# --------------------------------------------------------------------------- desenho

def desenhar(medidas, saida_base):
    m = {k: (medidas.get(k) if medidas.get(k) is not None else v) for k, v in ESTIMADAS.items()}
    faltando = [k for k in ESTIMADAS if medidas.get(k) is None]
    guia = bool(set(faltando) & set(OBRIGATORIAS))

    def rot(k, prefixo=""):
        if k in faltando:
            cor = VERMELHO if k in OBRIGATORIAS else LARANJA
            return (k if k.startswith("R") else prefixo + k), cor
        return prefixo + fmt(m[k]), "k"

    perf = Perfil(m)
    A, B, C, D, H, e = (m[k] for k in "ABCDHe")
    f = Folha()

    # ---- margens e moldura (NBR 10068: esquerda 25, demais 10 para A3)
    f.linha([(25, 10), (410, 10), (410, 287), (25, 287), (25, 10)], lw=0.7 * MM)

    # ================= VISTA FRONTAL (meio corte) — escala 1:1
    X0, Y0 = 125.0, 192.0
    o = np.array([X0, Y0])

    sil = perf.silhueta()
    sil_esq = sil * [-1, 1] + o
    f.linha(sil_esq)
    # aresta inferior da borda enrolada, à frente da parede
    f.linha([(X0 - perf.x_borda, Y0 + perf.y_borda), (X0, Y0 + perf.y_borda)])

    # metade em corte: chapa enegrecida
    f.preencher(perf.banda, o, 1.0)
    f.linha([(X0, Y0 + H), (X0 + perf.x_topo, Y0 + H)])  # topo da aba ao fundo
    f.centro((X0, Y0 - 6), (X0, Y0 + H + 6))

    # círculos indicadores dos detalhes
    cA = np.array([(perf.Q1[0] + A / 2) / 2 + 0.5, H - 2.0])
    rA = 8.5
    f.circulo(o + cA, rA, lw=FINA)
    f.texto(o + cA + [rA * 0.75, rA * 0.75], "A", h=4, ha="left", va="bottom")
    cB = np.array([(perf.rc - perf.w + C / 2) / 2, 3.0])
    rB = (C / 2 - perf.rc + perf.w) / 2 + 2.5
    f.circulo(o + cB, rB, lw=FINA)
    f.texto(o + cB + [rB * 0.72, rB * 0.72], "B", h=4, ha="left", va="bottom")

    # cotas — acima
    txt, cor = rot("B", "Ø")
    f.cota_h(X0 - B / 2, X0 + B / 2, Y0 + H, Y0 + H, Y0 + H + 10, txt, cor)
    txt, cor = rot("A", "Ø")
    yc = perf.cc[1]
    f.cota_h(X0 - A / 2, X0 + A / 2, Y0 + yc, Y0 + yc, Y0 + H + 20, txt, cor)
    # cotas — abaixo (Ø do fundo até o canto vivo virtual)
    t_fundo = perf.arco0[0]
    t_parede = perf.arco0[-1]
    for s in (-1, 1):
        f.linha([o + [s * t_fundo[0], 0], o + [s * C / 2, 0]], lw=FINA)
        f.linha([o + [s * t_parede[0], t_parede[1]], o + [s * C / 2, 0]], lw=FINA)
    txt, cor = rot("C", "Ø")
    f.cota_h(X0 - C / 2, X0 + C / 2, Y0, Y0, Y0 - rB + cB[1] - 4, txt, cor, folga=0.0)
    txt, cor = rot("D", "Ø")
    f.cota_meia(X0, X0 + D / 2, Y0, Y0 - rB + cB[1] - 13, txt, cor)
    # altura
    txt, cor = rot("H")
    f.cota_v(Y0, Y0 + H, X0 - t_fundo[0], X0 - perf.x_topo, X0 - A / 2 - 10, txt, cor)

    # ================= VISTA SUPERIOR — escala 1:1 (abaixo da frontal, 1º diedro)
    Xs, Ys = X0, 85.0
    cs = (Xs, Ys)
    f.circulo(cs, A / 2)                                  # borda externa
    f.circulo(cs, perf.E[0], lw=FINA)                     # início da borda enrolada (tangência)
    f.circulo(cs, B / 2)                                  # boca (dobra parede/aba)
    r_fundo_int = perf.arco0[0][0]                        # tangência fundo/raio
    f.circulo(cs, r_fundo_int, lw=FINA)
    f.circulo(cs, perf.rc)                                # rebaixo central (aresta)
    f.circulo(cs, perf.rc - perf.w)
    f.centro((Xs - A / 2 - 5, Ys), (Xs + A / 2 + 5, Ys))
    f.centro((Xs, Ys - A / 2 - 4), (Xs, Ys + A / 2 + 4))

    # ================= DETALHE A — aba, escala 5:1
    def detalhe(cr, rr, esc, centro_folha, letra):
        clip = Point(cr).buffer(rr, 128)
        desloc = np.asarray(centro_folha) - np.asarray(cr) * esc
        f.preencher(perf.banda.intersection(clip), desloc, esc)
        f.circulo(centro_folha, rr * esc, lw=FINA)
        f.texto((centro_folha[0], centro_folha[1] - rr * esc - 4),
                f"DETALHE {letra}  ESCALA {esc}:1", h=3.5, va="top")
        return lambda p: np.asarray(p, float) * esc + desloc

    escA = 5
    TA = detalhe(cA, rA, escA, (318.0, 236.0), "A")
    # linha do topo da aba ao fundo (vista além do corte), recortada
    x_ini = max(perf.x_topo, cA[0] - math.sqrt(max(rA**2 - (H - cA[1])**2, 0)))
    x_fim = cA[0] + math.sqrt(max(rA**2 - (H - cA[1])**2, 0))
    # e — espessura da aba
    xm = (perf.Q1[0] + perf.m["R1"] + 1.0 + perf.E[0]) / 2
    y_baixo, y_cima = perf.espessura_em_x(xm)
    p1, p2 = TA((xm, y_baixo)), TA((xm, y_cima))
    txt, cor = rot("e")
    f.linha([p1 - [0, 9], p2 + [0, 9]], lw=FINA)
    f.seta(p1, (0, 1))
    f.seta(p2, (0, -1))
    f.texto((p2[0] + 1.2, p2[1] + 4), txt, cor=cor, ha="left", va="center")
    # h — altura da aba
    txt, cor = rot("h")
    ptop, pbor = TA((perf.x_topo, H)), TA((perf.x_borda, perf.y_borda))
    f.cota_v(pbor[1], ptop[1], pbor[0], ptop[0], TA((A / 2, 0))[0] + 6, txt, cor,
             fora=(ptop[1] - pbor[1]) < 9, txt_lado=1)
    # R1 — dobra (face externa), cotada a partir do centro
    txt, cor = rot("R1", "R")
    f.cota_raio(TA(perf.c1), m["R1"] * escA, 150, txt, cor, comp=10, de_fora=False)

    # ================= DETALHE B — fundo, escala 3:1
    escB = 2
    TB = detalhe(cB, rB, escB, (318.0, 145.0), "B")
    # R2 — raio externo do fundo
    txt, cor = rot("R2", "R")
    f.cota_raio(TB(perf.c0), m["R2"] * escB, -40, txt, cor, comp=12)
    # p — profundidade do rebaixo central
    txt, cor = rot("p")
    q_cima = TB((perf.rc - perf.w, m["p"]))
    q_baixo = TB((perf.rc, 0))
    xd = TB((perf.rc - perf.w - 3.0, 0))[0]
    f.cota_v(q_baixo[1], q_cima[1], q_baixo[0], q_cima[0], xd, txt, cor,
             fora=(q_cima[1] - q_baixo[1]) < 9)

    # ================= NOTAS
    nx, ny = 236.0, 96.0
    e_txt = fmt(e) if "e" not in faltando else "e"
    notas = [
        "NOTAS:",
        "1. Cotas em milímetros.",
        f"2. Peça estampada em chapa de aço inox, espessura {e_txt} mm (constante).",
        "3. Cotas de Ø C até o canto vivo virtual (prolongamento parede/fundo).",
        "4. Borda da aba enrolada para baixo. Tolerância geral: ±0,5 mm.",
    ]
    for i, n in enumerate(notas):
        f.texto((nx, ny - i * 5.2), n, h=2.6, ha="left", va="top",
                weight="bold" if i == 0 else "normal")

    # ================= LEGENDA (NBR 10582) 178 x 50 no canto inferior direito
    lx0, lx1, ly0, ly1 = 232.0, 410.0, 10.0, 62.0
    f.linha([(lx0, ly0), (lx0, ly1), (lx1, ly1)], lw=0.7 * MM)
    linhas_y = [52.0, 42.0, 32.0, 21.0]
    for y in linhas_y:
        f.linha([(lx0, y), (lx1, y)], lw=FINA)

    def campo(x0, x1, y0, y1, rotulo, valor, h=3.2, cor="k", peso="normal"):
        if x0 > lx0:
            f.linha([(x0, y0), (x0, y1)], lw=FINA)
        f.texto((x0 + 1.2, y1 - 1.0), rotulo, h=1.6, ha="left", va="top", cor="#444")
        f.texto(((x0 + x1) / 2, y0 + 1.6), valor, h=h, ha="center", va="bottom",
                cor=cor, weight=peso)

    campo(lx0, lx1, 52, 62, "TÍTULO", "VASILHA (TIGELA) EM AÇO INOX", h=4.2, peso="bold")
    campo(lx0, 330, 42, 52, "MATERIAL", f"Aço inoxidável — chapa {e_txt} mm", h=3)
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

    if guia:
        f.texto((217.5, 291.5),
                "GUIA DE MEDIÇÃO — letras em vermelho: medir com o paquímetro;"
                " em laranja: opcionais (se não medir, uso estimativa das fotos)",
                h=3.0, cor=VERMELHO, va="center", weight="bold")

    os.makedirs(os.path.dirname(saida_base), exist_ok=True)
    f.fig.savefig(saida_base + ".pdf")
    f.fig.savefig(saida_base + ".png", dpi=200)
    plt.close(f.fig)
    return guia, faltando


def main():
    medidas = {}
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as fh:
            medidas = json.load(fh)
    guia = any(medidas.get(k) is None for k in OBRIGATORIAS)
    nome = "vasilha_guia_medicao" if guia else "vasilha_desenho_tecnico"
    guia, faltando = desenhar(medidas, os.path.join(AQUI, nome))
    print(f"Gerado: {nome}.pdf / {nome}.png")
    if faltando:
        print("Cotas ainda sem medida (usando estimativa):", ", ".join(faltando))


if __name__ == "__main__":
    main()
