"""Folha A3 com primitivas de desenho técnico (linhas ABNT, cotas, balões, tabelas)."""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle as MCircle
from matplotlib.patches import Polygon as MPoly

MM = 72.0 / 25.4            # pontos por mm
GROSSA = 0.6 * MM           # contorno visível
MEDIA = 0.35 * MM           # arestas em região muito densa
FINA = 0.25 * MM            # cota, extensão, linha de centro
TXT = 3.0                   # altura de texto das cotas (mm)


def fonte(h_mm):
    """Altura de maiúscula em mm -> tamanho de fonte em pt."""
    return h_mm / 0.73 * MM


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def fmt(v, casas=2):
    v = round(float(v), casas)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.{casas}f}".rstrip("0").rstrip(".").replace(".", ",")


class Folha:
    def __init__(self):
        self.fig = plt.figure(figsize=(420 / 25.4, 297 / 25.4))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, 420)
        self.ax.set_ylim(0, 297)
        self.ax.set_aspect("equal")
        self.ax.axis("off")
        self.linha([(25, 10), (410, 10), (410, 287), (25, 287), (25, 10)], lw=0.7 * MM)

    # ---- traços
    def linha(self, pts, lw=GROSSA, cor="k", z=3, ls="-"):
        pts = np.asarray(pts, float)
        self.ax.plot(pts[:, 0], pts[:, 1], color=cor, lw=lw, ls=ls,
                     solid_capstyle="butt", solid_joinstyle="round", zorder=z)

    def centro(self, p1, p2):
        dash = tuple(s * MM / FINA for s in (8, 1.5, 0.5, 1.5))
        self.linha([p1, p2], lw=FINA, ls=(0, dash), z=2)

    def circulo(self, c, r, lw=GROSSA, cor="k", fc="none"):
        self.ax.add_patch(MCircle(c, r, fill=fc != "none", fc=fc, lw=lw, ec=cor, zorder=3))

    def poligono(self, xy, fc="k", lw=FINA, z=3):
        self.ax.add_patch(MPoly(np.asarray(xy, float), closed=True, fc=fc, ec="k", lw=lw, zorder=z))

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

    # ---- cotas
    def cota_h(self, xa, xb, ya, yb, yd, txt, fora=None, folga=1.0, txt_dx=0.0):
        for x, y in ((xa, ya), (xb, yb)):
            if y is None:
                continue
            s = 1 if yd > y else -1
            self.linha([(x, y + s * folga), (x, yd + s * 2)], lw=FINA)
        if fora is None:
            fora = abs(xb - xa) < 8
        if fora:
            self.linha([(xa - 6, yd), (xb + 6, yd)], lw=FINA)
            self.seta((xa, yd), (1, 0))
            self.seta((xb, yd), (-1, 0))
        else:
            self.linha([(xa, yd), (xb, yd)], lw=FINA)
            self.seta((xa, yd), (-1, 0))
            self.seta((xb, yd), (1, 0))
        self.texto(((xa + xb) / 2 + txt_dx, yd + 0.8), txt)

    def cota_v(self, ya, yb, xa, xb, xd, txt, fora=None, folga=1.0, txt_lado=-1, txt_dy=0.0):
        for y, x in ((ya, xa), (yb, xb)):
            if x is None:
                continue
            s = 1 if xd > x else -1
            self.linha([(x + s * folga, y), (xd + s * 2, y)], lw=FINA)
        if fora is None:
            fora = abs(yb - ya) < 8
        if fora:
            self.linha([(xd, ya - 6), (xd, yb + 6)], lw=FINA)
            self.seta((xd, ya), (0, 1))
            self.seta((xd, yb), (0, -1))
        else:
            self.linha([(xd, ya), (xd, yb)], lw=FINA)
            self.seta((xd, ya), (0, -1))
            self.seta((xd, yb), (0, 1))
        ha = "right" if txt_lado < 0 else "left"
        self.texto((xd + 0.8 * txt_lado, (ya + yb) / 2 + txt_dy), txt,
                   rotation=90, ha=ha, va="center")

    def cadeia_h(self, xs, y_feat, yd, rotulos):
        """Cotas em cadeia horizontais; textos de trechos curtos ficam alternados."""
        for x, yf in zip(xs, y_feat):
            s = 1 if yd > yf else -1
            self.linha([(x, yf + s * 1.0), (x, yd + s * 2)], lw=FINA)
        self.linha([(xs[0], yd), (xs[-1], yd)], lw=FINA)
        alterna = 0
        for i, (xa, xb) in enumerate(zip(xs[:-1], xs[1:])):
            curto = (xb - xa) < 7
            if curto:
                self.seta((xa, yd), (1, 0), L=1.8, larg=0.7)
                self.seta((xb, yd), (-1, 0), L=1.8, larg=0.7)
                if i == 0:
                    self.linha([(xa - 4, yd), (xa, yd)], lw=FINA)
                if i == len(xs) - 2:
                    self.linha([(xb, yd), (xb + 4, yd)], lw=FINA)
            else:
                self.seta((xa, yd), (-1, 0))
                self.seta((xb, yd), (1, 0))
            dy = 0.8
            if curto:
                dy = 0.8 if alterna % 2 == 0 else -4.2
                alterna += 1
            self.texto(((xa + xb) / 2, yd + dy), rotulos[i], h=2.6 if curto else TXT)

    def cota_diam_interna(self, x, ya, yb, txt, lado=1):
        """Cota de diâmetro traçada por dentro da vista, setas tocando a silhueta."""
        self.linha([(x, ya), (x, yb)], lw=FINA)
        self.seta((x, ya), (0, -1))
        self.seta((x, yb), (0, 1))
        self.texto((x + 0.8 * lado, (ya + yb) / 2), txt, rotation=90,
                   ha="left" if lado > 0 else "right", va="center")

    def chamada(self, ponta, p_fim, txt, lado=1, comp=None, h=TXT, ponto=False):
        ponta, p_fim = np.asarray(ponta, float), np.asarray(p_fim, float)
        self.linha([ponta, p_fim], lw=FINA)
        if ponto:
            self.circulo(ponta, 0.6, lw=0, fc="k")
        else:
            self.seta(ponta, ponta - p_fim)
        comp = comp if comp is not None else 2.0 + 0.62 * h * len(txt)
        p_ombro = p_fim + np.array([lado * comp, 0])
        self.linha([p_fim, p_ombro], lw=FINA)
        self.texto(((p_fim[0] + p_ombro[0]) / 2, p_fim[1] + 0.8), txt, h=h)

    def balao(self, ponta, centro, n, r=3.4):
        ponta, centro = np.asarray(ponta, float), np.asarray(centro, float)
        d = unit(ponta - centro)
        self.linha([centro + d * r, ponta], lw=FINA)
        self.circulo(ponta, 0.55, lw=0, fc="k")
        self.ax.add_patch(MCircle(centro, r, fill=True, fc="white", ec="k", lw=FINA, zorder=5))
        txt = str(n)
        self.texto(centro, txt, h=2.6 if len(txt) < 3 else 2.0, ha="center", va="center")

    # ---- tabela
    def tabela(self, x0, y0, larguras, cabecalho, linhas, h_linha=5.0, h_cab=9.0,
               h_txt=2.2, alinh=None):
        """Desenha tabela com canto superior esquerdo em (x0, y0). Retorna y final."""
        W = sum(larguras)
        n = len(linhas)
        y_fim = y0 - h_cab - n * h_linha
        self.linha([(x0, y0), (x0 + W, y0), (x0 + W, y_fim), (x0, y_fim), (x0, y0)], lw=0.5 * MM)
        self.linha([(x0, y0 - h_cab), (x0 + W, y0 - h_cab)], lw=0.5 * MM)
        for i in range(1, n):
            y = y0 - h_cab - i * h_linha
            self.linha([(x0, y), (x0 + W, y)], lw=FINA * 0.7)
        x = x0
        for j, w in enumerate(larguras):
            if j:
                self.linha([(x, y0), (x, y_fim)], lw=FINA)
            self.texto((x + w / 2, y0 - h_cab / 2), cabecalho[j], h=h_txt * 0.95,
                       ha="center", va="center", weight="bold", linespacing=1.15)
            for i, lin in enumerate(linhas):
                a = (alinh or ["c"] * len(larguras))[j]
                xt = {"c": x + w / 2, "l": x + 1.2, "r": x + w - 1.2}[a]
                ha = {"c": "center", "l": "left", "r": "right"}[a]
                self.texto((xt, y0 - h_cab - (i + 0.5) * h_linha), lin[j], h=h_txt,
                           ha=ha, va="center")
            x += w
        return y_fim

    # ---- legenda (NBR 10582) 178 x 52 no canto inferior direito
    def legenda(self, titulo, subtitulo, material, escala, folha, data, numero="FOG-001"):
        lx0, lx1 = 232.0, 410.0
        self.linha([(lx0, 10), (lx0, 62), (lx1, 62)], lw=0.7 * MM)
        for y in (52.0, 42.0, 32.0, 21.0):
            self.linha([(lx0, y), (lx1, y)], lw=FINA)

        def campo(x0, x1, y0, y1, rotulo, valor, h=3.2, peso="normal"):
            if x0 > lx0:
                self.linha([(x0, y0), (x0, y1)], lw=FINA)
            self.texto((x0 + 1.2, y1 - 1.0), rotulo, h=1.6, ha="left", va="top", cor="#444")
            self.texto(((x0 + x1) / 2, y0 + 1.6), valor, h=h, ha="center", va="bottom", weight=peso)

        campo(lx0, lx1, 52, 62, "TÍTULO", titulo, h=4.0, peso="bold")
        campo(lx0, 330, 42, 52, "CONTEÚDO", subtitulo, h=2.8)
        campo(330, lx1, 42, 52, "MATERIAL", material, h=2.6)
        campo(lx0, 330, 32, 42, "DESENHISTA", "", h=3)
        campo(330, lx1, 32, 42, "DATA", data, h=3)
        campo(lx0, 280, 21, 32, "ESCALA", escala, h=3.2)
        campo(280, 318, 21, 32, "UNIDADE", "mm", h=3.5)
        campo(318, 352, 21, 32, "FORMATO", "A3", h=3.5)
        campo(352, lx1, 21, 32, "DIEDRO", "", h=3)
        campo(lx0, 330, 10, 21, "Nº DO DESENHO", numero, h=3.5)
        campo(330, 370, 10, 21, "REVISÃO", "0", h=3.5)
        campo(370, lx1, 10, 21, "FOLHA", folha, h=3.5)
        # símbolo do 1º diedro
        sx, sy = 368.0, 25.5
        self.linha([(sx, sy - 1.5), (sx + 9, sy - 3.2), (sx + 9, sy + 3.2), (sx, sy + 1.5),
                    (sx, sy - 1.5)], lw=0.35 * MM)
        self.circulo((sx + 18, sy), 3.2, lw=0.35 * MM)
        self.circulo((sx + 18, sy), 1.5, lw=0.35 * MM)
        self.centro((sx - 2, sy), (sx + 11, sy))
        self.centro((sx + 13.5, sy), (sx + 22.5, sy))
        self.texto((sx + 31, sy - 0.2), "1º", h=3.5, ha="center", va="center")

    def notas(self, x, y, linhas, h=2.4, passo=4.6, titulo=True):
        for i, n in enumerate(linhas):
            self.texto((x, y - i * passo), n, h=h, ha="left", va="top",
                       weight="bold" if titulo and i == 0 else "normal")
