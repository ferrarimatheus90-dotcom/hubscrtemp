#!/usr/bin/env python3
"""Desenho técnico do foguete PET a partir do arquivo OpenRocket.

Gera desenho_tecnico_foguete.pdf (2 folhas A3) e um PNG por folha:
  folha 1 — vista lateral 1:2, vista frontal (pela ogiva), detalhes A (5:1) e B (2:1)
  folha 2 — tabela de conversão das medidas, aleta em verdadeira grandeza 1:1,
            coordenadas da aleta, massas e materiais
"""
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from shapely.geometry import LineString, Point

from folha import FINA, GROSSA, MEDIA, MM, Folha, fmt
from modelo import FORMAS_PT, Foguete

AQUI = os.path.dirname(os.path.abspath(__file__))
DATA = "03/10/2026"


def titulo_foguete(f):
    return f"FOGUETE PET — {f.nome.upper()}"


def recorta(pts, circulo):
    """Recorta uma polilinha por um círculo (shapely) -> lista de arrays."""
    g = LineString(pts).intersection(circulo)
    if g.is_empty:
        return []
    geoms = getattr(g, "geoms", [g])
    return [np.array(gg.coords) for gg in geoms if gg.geom_type == "LineString"]


def forma_texto(c):
    if c.forma is None:
        return "cilindro"
    if c.forma == "conical":
        return "cônica"
    if c.forma == "ogive":
        return "ogiva tangente (k=1)" if abs(c.k - 1) < 1e-9 else f"ogiva k={fmt(c.k)}"
    txt = f"{FORMAS_PT[c.forma]} k={fmt(c.k)}"
    return txt + (" cortada" if c.cortada else "")


# =========================================================================== folha 1

def folha1(fog):
    F = Folha()
    esc = 0.5
    X0, Y0 = 38.0, 212.0

    def S(x, r):
        return np.column_stack([X0 + np.asarray(x) * esc, Y0 + np.asarray(r) * esc]) \
            if np.ndim(x) else np.array([X0 + x * esc, Y0 + r * esc])

    xs, rs = fog.perfil()
    L = fog.comprimento
    r_fim = fog.componentes[-1].r_tras
    aleta = fog.aletas[0]
    borda, _ = fog.contorno_aleta(aleta)

    # ---------------- vista lateral (frontal do desenho), escala 1:2
    F.linha(S(xs, rs))
    F.linha(S(xs, -rs))
    F.linha([S(L, -r_fim), S(L, r_fim)])
    for c in fog.componentes[1:]:
        lw = MEDIA if c.item >= 8 else GROSSA
        F.linha([S(c.x0, -c.r_diant), S(c.x0, c.r_diant)], lw=lw)
    # aletas em verdadeira grandeza (cima e baixo) e de topo (voltada ao observador)
    F.linha(S(borda[:, 0], borda[:, 1]))
    F.linha(S(borda[:, 0], -borda[:, 1]))
    x_ponta = borda[:, 0].max()
    F.linha([S(aleta.x_ba, 0), S(x_ponta, 0)], lw=aleta.espessura * esc * MM, z=4)
    F.centro(S(-6, 0), S(L + 8, 0))

    # cotas acima
    r_ba = aleta.r_ba
    F.cadeia_h([X0, S(175, 0)[0], S(L, 0)[0]],
               [Y0, Y0 + fog.raio(175) * esc, Y0 + r_fim * esc], 265.5,
               [fmt(175), fmt(L - 175)])
    F.cota_h(S(aleta.x_ba, 0)[0], S(L, 0)[0], Y0 + r_ba * esc, Y0 + r_fim * esc, 272.5,
             fmt(L - aleta.x_ba, 1))
    F.cota_h(X0, S(L, 0)[0], Y0, Y0 + r_fim * esc, 279.5, fmt(L))
    # cotas abaixo — trechos da garrafa
    est = [175, 215, 285, 357, 454, L]
    F.cadeia_h([S(x, 0)[0] for x in est], [Y0 - fog.raio(x) * esc for x in est],
               Y0 - aleta.r_ba * esc - 52 * esc - 9,
               [fmt(b - a) for a, b in zip(est[:-1], est[1:])])
    # diâmetros
    rb = fog.raio(175)
    F.cota_v(Y0 - rb * esc, Y0 + rb * esc, S(175, 0)[0], S(175, 0)[0], X0 - 8,
             "Ø" + fmt(2 * rb))
    for x, txt_x in ((217.6, 215), (282.6, 285), (321.0, 321)):
        r = fog.raio(x)
        F.cota_diam_interna(S(x, 0)[0], Y0 - r * esc, Y0 + r * esc,
                            "Ø" + fmt(round(2 * fog.raio(txt_x), 1)), lado=1)

    # balões
    def ancora(x, frac=0.75):
        return S(x, fog.raio(x) * frac)

    for item, x, cx in ((1, 125, 95), (2, 196, 128), (3, 250, 160), (5, 330, 190), (7, 372, 211)):
        F.balao(ancora(x), (cx, 250.5), item)
    F.balao(S(aleta.x_ba + 62, aleta.r_ba + 30), (290, 256), 20)

    # indicação dos detalhes
    cA_real, rA_real = np.array([285.5, 46.5]), 5.0
    F.circulo(S(*cA_real), rA_real * esc + 1.5, lw=FINA)
    F.texto(S(*cA_real) + [2.5, 3.0], "A", h=3.5, ha="left", va="bottom")
    cB_real, rB_real = np.array([468.0, 0.0]), 27.0
    F.circulo(S(*cB_real), rB_real * esc, lw=FINA)
    F.texto(S(*cB_real) + [10.5, -11.5], "B", h=3.5, ha="left", va="top")

    # ---------------- vista pela ogiva (à direita da lateral — 1º diedro)
    XE = 350.0
    ce = np.array([XE, Y0])
    R = fog.raio_max * esc
    F.circulo(ce, R)
    r_ext = (aleta.r_ba + aleta.pontos[:, 1].max()) * esc
    meia = aleta.espessura * esc / 2
    for ang in (0, 90, 180, 270):
        a = np.radians(ang + aleta.angulo0)
        d, n = np.array([np.cos(a), np.sin(a)]), np.array([-np.sin(a), np.cos(a)])
        F.poligono([ce + d * R + n * meia, ce + d * r_ext + n * meia,
                    ce + d * r_ext - n * meia, ce + d * R - n * meia], fc="k", lw=FINA)
    F.centro(ce - [r_ext + 5, 0], ce + [r_ext + 5, 0])
    F.centro(ce - [0, r_ext + 5], ce + [0, r_ext + 5])
    F.cota_h(XE - r_ext, XE + r_ext, Y0, Y0, Y0 - r_ext - 8, fmt(fog.envergadura(), 1))
    p45 = ce + R * np.array([np.cos(np.radians(40)), np.sin(np.radians(40))])
    F.chamada(p45, p45 + [9, 12], "Ø" + fmt(2 * fog.raio_max), lado=1)
    F.chamada(ce + [-meia, r_ext * 0.8], ce + [-14, r_ext * 0.8 + 8],
              f"4 ALETAS A 90°, e={fmt(aleta.espessura)}", lado=-1, h=2.6)

    # ---------------- DETALHE A — degrau do rótulo (itens 4 a 6), 5:1
    escA = 5
    cA_folha = np.array([187.0, 103.0])
    circA = Point(*cA_real).buffer(rA_real, 128)

    def TA(x, r):
        return (np.column_stack([x, r]) - cA_real) * escA + cA_folha

    perfil_top = np.column_stack([xs, rs])
    for seg in recorta(perfil_top, circA):
        F.linha(TA(seg[:, 0], seg[:, 1]))
    for c in fog.componentes:
        if 3 <= c.item <= 6:
            for seg in recorta([(c.x0, -100), (c.x0, c.r_diant)], circA):
                F.linha(TA(seg[:, 0], seg[:, 1]))
    F.circulo(cA_folha, rA_real * escA, lw=FINA)
    F.texto(cA_folha - [0, rA_real * escA + 3.5], "DETALHE A  ESCALA 5:1", h=3.5, va="top")
    F.texto(cA_folha - [0, rA_real * escA + 9.5], "(igual em x = 356, item 6)", h=2.4, va="top")
    p1, p2 = TA(285, 47.0)[0], TA(286, 46.5)[0]
    F.cota_h(p1[0], p2[0], p1[1], p2[1], p1[1] + 8, "1")
    p3 = TA(290, 46.5)[0]
    F.cota_v(p2[1], p1[1], p3[0], p1[0], p3[0] + 4, "0,5", txt_lado=1)
    F.balao(TA(285.5, 45.0)[0], cA_folha + [-7, -19], 4)
    F.balao(TA(288.5, 44.5)[0], cA_folha + [5, -16], 5)
    F.balao(TA(283.0, 45.5)[0], cA_folha + [-17, -9], 3)

    # ---------------- DETALHE B — gargalo (itens 8 a 19), 2:1
    escB = 2
    cB_folha = np.array([96.0, 87.0])
    circB = Point(*cB_real).buffer(rB_real, 128)

    def TB(x, r):
        return (np.column_stack([np.atleast_1d(x), np.atleast_1d(r)]) - cB_real) * escB + cB_folha

    for sinal in (1, -1):
        for seg in recorta(np.column_stack([xs, sinal * rs]), circB):
            F.linha(TB(seg[:, 0], seg[:, 1]))
    F.linha(TB([L, L], [-r_fim, r_fim]))
    for c in fog.componentes:
        if c.item >= 8:
            F.linha(TB([c.x0, c.x0], [-c.r_diant, c.r_diant]))
    # aleta de topo, à frente do gargalo
    x_fim_aleta = min(x_ponta, cB_real[0] + np.sqrt(rB_real**2))
    for s in (1, -1):
        for seg in recorta([(aleta.x_ba, s * aleta.espessura / 2), (x_ponta, s * aleta.espessura / 2)],
                           circB):
            F.linha(TB(seg[:, 0], seg[:, 1]), lw=MEDIA)
    F.linha(TB([x_ponta, x_ponta], [-aleta.espessura / 2, aleta.espessura / 2]), lw=MEDIA)
    for seg in recorta([(cB_real[0] - rB_real, 0), (L + 4, 0)], circB.buffer(4)):
        p = TB(seg[:, 0], seg[:, 1])
        F.centro(p[0], p[-1])
    F.circulo(cB_folha, rB_real * escB, lw=FINA)
    F.texto(cB_folha - [0, rB_real * escB + 2.5], "DETALHE B  ESCALA 2:1", h=3.5, va="top")
    # cadeia de comprimentos do gargalo
    est = [454, 462, 465, 470, 471, 476, 481, L]
    yd = TB(0, -20)[0][1] - 5
    F.cadeia_h([TB(x, 0)[0][0] for x in est], [TB(x, -fog.raio(x - 1e-6))[0][1] for x in est], yd,
               [fmt(b - a) for a, b in zip(est[:-1], est[1:])])
    # diâmetros
    for x, rot in ((458, 27.5), (467.5, 26.5), (473.5, 28)):
        r = fog.raio(x)
        a, b = TB(x, -r)[0], TB(x, r)[0]
        F.cota_diam_interna(a[0], a[1], b[1], "Ø" + fmt(rot), lado=1)
    pt, pb = TB(464, 20)[0], TB(464, -20)[0]
    F.cota_v(pb[1], pt[1], pb[0], pt[0], TB(447.0, 0)[0][0], "Ø40")
    # balões do gargalo
    baloes = [(8, 458, 0), (9, 463, 1), (10, 464.6, 0), (11, 467.5, 1), (12, 470.5, 0),
              (13, 473.5, 1), ("14–18", 478.5, 0), (19, 482.5, 1)]
    xs_bal = np.linspace(66, 130, len(baloes))
    for (item, x, fila), xb in zip(baloes, xs_bal):
        r = fog.raio(x)
        ponta = TB(x, r * 0.55)[0]
        F.balao(ponta, (xb, 132 + 9 * fila), item, r=4.2 if isinstance(item, str) else 3.4)

    # ---------------- notas
    a = fog.aletas[0]
    F.notas(236, 146, [
        "NOTAS:",
        "1. Cotas em mm, convertidas do arquivo OpenRocket rocket.ork (SI: m × 1000).",
        "2. Posições axiais (x) medidas a partir da ponta da ogiva.",
        "3. Item 1 — ogiva tangente (k = 1) em PLA, casca de 1 mm.",
        "4. Itens 2 a 19 — garrafa PET (parede 1 mm; gargalo 2 a 3,25 mm).",
        f"5. Item 20 — {a.n} aletas em PLA, e = {fmt(a.espessura)} mm, seção arredondada,",
        "    a 90°; forma e coordenadas na folha 2.",
        "6. Formas, espessuras e conversão de todos os itens: tabela da folha 2.",
        "7. Massas internas M1 (25 g), M2 (28 g) e M3 (7 g) não representadas.",
        "8. Arestas do gargalo (itens 8 a 19) em traço médio na escala 1:2.",
    ], h=2.3, passo=4.4)
    F.legenda(titulo_foguete(fog), "Conjunto — vistas e detalhes", "PLA / garrafa PET",
              "1:2 (indicadas)", "1/2", DATA)
    return F


# =========================================================================== folha 2

def folha2(fog):
    F = Folha()
    F.texto((30, 282), "TABELA 1 — CONVERSÃO DAS MEDIDAS DO OPENROCKET (SI) PARA MILÍMETROS",
            h=3.2, ha="left", va="center", weight="bold")
    cab = ["Item", "Componente\n(arquivo)", "Estágio", "Forma", "x início\n(mm)", "x fim\n(mm)",
           "Compr.\n(m)", "Compr.\n(mm)", "Raio diant.\n(m)", "Ø diant.\n(mm)",
           "Raio tras.\n(m)", "Ø tras.\n(mm)", "Espessura\n(m)", "Espessura\n(mm)", "Material"]
    larg = [10, 30, 22, 40, 17, 17, 21, 18, 23, 18, 23, 18, 23, 19, 33]
    larg = [w * 377 / sum(larg) for w in larg]
    linhas = []
    for c in fog.componentes:
        linhas.append([
            str(c.item), c.nome, c.estagio, forma_texto(c), fmt(c.x0), fmt(c.x1),
            fmt(c.comprimento / 1000, 5), fmt(c.comprimento),
            fmt(c.r_diant / 1000, 5), fmt(2 * c.r_diant),
            fmt(c.r_tras / 1000, 5), fmt(2 * c.r_tras),
            fmt(c.espessura / 1000, 5), fmt(c.espessura), c.material.nome.replace(" - 100% infill", " 100%"),
        ])
    a = fog.aletas[0]
    corda = a.pontos[-1, 0]
    linhas.append([
        "20", f"Aletas ({a.n}×)", fog.componentes[a.pai.item - 1].estagio, "formato livre",
        fmt(a.x_ba), fmt(a.x_ba + a.pontos[:, 0].max()),
        fmt(corda / 1000, 5), fmt(corda) + "*", "—", "—", "—", "—",
        fmt(a.espessura / 1000, 5), fmt(a.espessura), a.material.nome.replace(" - 100% infill", " 100%"),
    ])
    y = F.tabela(28, 276, larg, cab, linhas, h_linha=5.0, h_cab=9.5, h_txt=2.15,
                 alinh=["c", "l", "l", "l"] + ["r"] * 10 + ["l"])
    F.texto((28, y - 2.5), "* item 20: corda da raiz. Aletas presas ao item 7 (ombro), "
            f"posição pela base do item 7: {fmt(float(a.bruto['axialoffset']) * 1000)} mm "
            f"(arquivo: {a.bruto['axialoffset']} m).", h=2.1, ha="left", va="top")

    # ---------------- aleta 1:1
    o = np.array([46.0, 100.0])
    borda = a.pontos
    xr = np.linspace(borda[-1, 0], 0, 60)
    raiz_y = fog.raio(a.x_ba + xr) - a.r_ba
    F.linha(borda + o)
    F.linha(np.column_stack([xr, raiz_y]) + o)
    for i, p in enumerate(borda):
        F.circulo(p + o, 0.45, lw=0, fc="k")
        dx, dy, ha = (-1.2, 1.0, "right") if i < 6 else (1.3, 0.0, "left")
        if i == 0:
            dx, dy, ha = (-1.2, -1.5, "right")
        F.texto(p + o + [dx, dy], f"P{i + 1}", h=1.9, ha=ha, va="center")
    P1, P7, P15 = borda[0] + o, borda[np.argmax(borda[:, 0])] + o, borda[-1] + o
    ptop = borda[np.argmax(borda[:, 1])] + o
    F.cota_h(P1[0], P15[0], P1[1], P15[1], P15[1] - 7, fmt(corda, 1))
    F.cota_h(P1[0], P7[0], P1[1] - 0.0, P7[1], P15[1] - 14, fmt(P7[0] - P1[0], 1))
    F.cota_v(P1[1], ptop[1], P1[0], ptop[0], P1[0] - 9, fmt(ptop[1] - P1[1], 1))
    F.cota_v(P15[1], P1[1], P15[0], None, P1[0] - 9, fmt(P1[1] - P15[1], 1))
    for d, rot in (((1, 0), "x"), ((0, 1), "y")):
        d = np.array(d, float)
        F.linha([o, o + d * 14], lw=FINA)
        F.seta(o + d * 14, d, L=2.2, larg=0.8)
        F.texto(o + d * 14 + (np.array([1.5, -1.0]) if rot == "x" else np.array([-1.0, 1.2])), rot,
                h=2.4, ha="left" if rot == "x" else "right", va="center")
    F.texto((o[0] + 56, 47), "ALETA (ITEM 20) — VERDADEIRA GRANDEZA  ESCALA 1:1", h=3.2, va="top")
    F.notas(32, 40.5, [
        f"Origem em P1 (bordo de ataque da raiz), a {fmt(a.x_ba)} mm da ponta da ogiva.",
        "A raiz (P15 → P1) acompanha o perfil do ombro da garrafa (item 7).",
        f"Espessura {fmt(a.espessura)} mm, seção arredondada, {a.n} aletas a 90°.",
    ], h=2.2, passo=4.2, titulo=False)

    # ---------------- coordenadas da aleta
    F.texto((170, 156), "TABELA 2 — PONTOS DA ALETA", h=2.6, ha="left", va="center", weight="bold")
    linhas = [[f"P{i + 1}", fmt(px / 1000, 5), fmt(px), fmt(py / 1000, 5), fmt(py)]
              for i, (px, py) in enumerate(borda)]
    F.tabela(170, 152, [9, 17, 13, 17, 13], ["Ponto", "x (m)", "x (mm)", "y (m)", "y (mm)"],
             linhas, h_linha=4.6, h_cab=7.0, h_txt=2.0, alinh=["c", "r", "r", "r", "r"])

    # ---------------- massas
    F.texto((250, 156), "TABELA 3 — COMPONENTES DE MASSA (INTERNOS)", h=2.6, ha="left",
            va="center", weight="bold")
    linhas = []
    for i, m in enumerate(fog.massas):
        linhas.append([f"M{i + 1}", f"{m.pai.item} ({m.pai.nome})", fmt(float(m.bruto['axialoffset']), 4),
                       f"{fmt(m.x0, 1)}–{fmt(m.x0 + m.comprimento, 1)}",
                       fmt(m.comprimento / 1000, 4), fmt(m.comprimento),
                       fmt(m.raio / 1000, 5), fmt(2 * m.raio), fmt(m.massa_g / 1000, 3), fmt(m.massa_g)])
    y = F.tabela(250, 152, [8, 29, 14, 19, 13, 13, 14, 11, 13, 12],
                 ["", "Dentro do\nitem", "Desloc.\n(m)", "x (mm)", "Compr.\n(m)", "Compr.\n(mm)",
                  "Raio\n(m)", "Ø\n(mm)", "Massa\n(kg)", "Massa\n(g)"],
                 linhas, h_linha=5.0, h_cab=8.5, h_txt=2.0,
                 alinh=["c", "l", "r", "c", "r", "r", "r", "r", "r", "r"])
    F.texto((250, y - 2.0), f"Total: {fmt(sum(m.massa_g for m in fog.massas))} g "
            "(deslocamento medido do topo do item).", h=2.0, ha="left", va="top")

    # ---------------- materiais
    F.texto((250, 117), "TABELA 4 — MATERIAIS", h=2.6, ha="left", va="center", weight="bold")
    usos = {}
    for c in fog.componentes:
        usos.setdefault(c.material.nome, (c.material, []))[1].append(c.item)
    for a_ in fog.aletas:
        usos.setdefault(a_.material.nome, (a_.material, []))[1].append(20)
    linhas = []
    for nome, (mat, itens) in usos.items():
        faixa = f"{min(itens)} a {max(itens)}" if len(itens) > 2 else " e ".join(map(str, itens))
        linhas.append([nome, fmt(mat.densidade * 1000), fmt(mat.densidade, 3), faixa])
    F.tabela(250, 113, [44, 28, 28, 52], ["Material", "Densidade\n(kg/m³)", "Densidade\n(g/cm³)",
                                          "Itens"], linhas, h_linha=5.0, h_cab=8.5, h_txt=2.1,
             alinh=["l", "r", "r", "c"])

    F.notas(250, 91, [
        "NOTAS:",
        "1. Comprimentos: m × 1000 = mm. Massas: kg × 1000 = g.",
        "    Densidades: kg/m³ ÷ 1000 = g/cm³. Ø = 2 × raio do arquivo.",
        "2. x medido a partir da ponta da ogiva.",
        "3. Formas com as equações do OpenRocket (k = parâmetro da forma).",
        "4. O arquivo tem 4 estágios (2 vazios); aqui tudo é um conjunto só.",
    ], h=2.2, passo=4.3)
    F.legenda(titulo_foguete(fog), "Tabelas de conversão e aleta", "PLA / garrafa PET",
              "1:1 (aleta)", "2/2", DATA)
    return F


def main():
    ork = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "rocket.ork")
    fog = Foguete(ork)
    folhas = [folha1(fog), folha2(fog)]
    with PdfPages(os.path.join(AQUI, "desenho_tecnico_foguete.pdf")) as pdf:
        for i, F in enumerate(folhas, 1):
            pdf.savefig(F.fig)
            F.fig.savefig(os.path.join(AQUI, f"desenho_tecnico_foguete_folha{i}.png"), dpi=200)
            plt.close(F.fig)
    print("Gerado: desenho_tecnico_foguete.pdf (+ PNG por folha)")


if __name__ == "__main__":
    main()
