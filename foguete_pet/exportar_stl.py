#!/usr/bin/env python3
"""Gera os STL das peças impressas do foguete: ogiva (bico) e aletas (asas).

Medidas lidas do rocket.ork (mesmo modelo do desenho técnico), em mm:
  - ogiva_bico.stl       casca da ogiva, base aberta apoiada na mesa, ponta para cima
  - aleta_1x.stl         uma aleta deitada (imprimir 4 vezes)
  - aletas_4x_mesa.stl   as 4 aletas encaixadas numa mesa de impressão
"""
import itertools
import math
import os
import sys

import numpy as np
import trimesh
from shapely import affinity
from shapely.geometry import Polygon

from modelo import Foguete

AQUI = os.path.dirname(os.path.abspath(__file__))
SECOES = 180          # divisões na revolução da ogiva
FOLGA_MESA = 4.0      # distância mínima entre aletas na mesa (mm)


def perfil_casca(c, n=170):
    """Meia-seção (x, r) da casca da ogiva: contorno externo + interno deslocado de e."""
    t = np.linspace(0, 1, n) ** 2.2  # mais pontos perto da ponta
    x = c.comprimento * t
    r = c.raio(x)
    dx, dr = np.gradient(x), np.gradient(r)
    s = np.hypot(dx, dr)
    nx, nr = -dr / s, dx / s           # normal externa
    xi, ri = x - c.espessura * nx, r - c.espessura * nr
    # parte interna só onde ainda há raio; fecha no eixo
    dentro = ri > 0
    k = np.argmax(dentro)
    x_eixo = np.interp(0.0, [ri[k - 1], ri[k]], [xi[k - 1], xi[k]])
    interno = np.column_stack([np.r_[x_eixo, xi[dentro]], np.r_[0.0, ri[dentro]]])
    interno[-1] = [c.comprimento, c.r_tras - c.espessura]  # base plana
    externo = np.column_stack([x, r])
    externo[-1] = [c.comprimento, c.r_tras]
    # descarta pontos quase no eixo (geram triângulos degenerados na revolução)
    externo = np.vstack([externo[:1], externo[1:][externo[1:, 1] > 0.05]])
    interno = np.vstack([interno[:1], interno[1:][interno[1:, 1] > 0.05]])
    return np.concatenate([externo, interno[::-1]])


def ogiva_stl(fog):
    c = fog.componentes[0]
    assert c.tipo == "nosecone"
    perfil = perfil_casca(c)
    # revolve do trimesh: (raio, altura); base na mesa (z = 0), ponta para cima
    pts = np.column_stack([perfil[:, 1], c.comprimento - perfil[:, 0]])
    if Polygon(pts).exterior.is_ccw is False:
        pts = pts[::-1]
    pts = np.vstack([pts, pts[:1]])
    malha = trimesh.creation.revolve(pts, sections=SECOES)
    malha.merge_vertices()
    malha.fix_normals()
    return malha, perfil


def contorno_aleta(fog, a):
    """Contorno 2D da aleta (coordenadas da aleta, mm) com a raiz acompanhando o ombro."""
    borda = a.pontos
    xr = np.linspace(borda[-1, 0], 0.0, 80)[1:-1]
    raiz = np.column_stack([xr, fog.raio(a.x_ba + xr) - a.r_ba])
    return Polygon(np.concatenate([borda, raiz]))


def arranjo_mesa(poly, n=4, folga=FOLGA_MESA):
    """Encaixa n cópias da aleta: pares (normal + girada 180°) empilhados."""
    girada = affinity.rotate(poly, 180, origin="centroid")
    melhor = None
    minx, miny, maxx, maxy = poly.bounds
    for dx, dy in itertools.product(np.arange(-40, 120, 2.0), np.arange(-20, 90, 2.0)):
        g = affinity.translate(girada, dx, dy)
        if g.distance(poly) < folga:
            continue
        par = poly.union(g)
        b = par.bounds
        area = (b[2] - b[0]) * (b[3] - b[1]) * max(b[2] - b[0], 2 * (b[3] - b[1]) + folga)
        if melhor is None or area < melhor[0]:
            melhor = (area, g)
    par = [poly, melhor[1]]
    b = poly.union(melhor[1]).bounds
    altura_par = b[3] - b[1]
    pecas = []
    for i in range(n // 2):
        for p in par:
            pecas.append(affinity.translate(p, -b[0], -b[1] + i * (altura_par + folga)))
    return pecas


def main():
    ork = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "rocket.ork")
    fog = Foguete(ork)
    rho = {}

    # ---- ogiva
    ogiva, _ = ogiva_stl(fog)
    ogiva.export(os.path.join(AQUI, "ogiva_bico.stl"))
    c = fog.componentes[0]
    rho["ogiva"] = c.material.densidade

    # ---- aletas
    a = fog.aletas[0]
    poly = contorno_aleta(fog, a)
    aleta = trimesh.creation.extrude_polygon(poly, a.espessura)
    aleta.apply_translation([-poly.bounds[0], -poly.bounds[1], 0])
    aleta.export(os.path.join(AQUI, "aleta_1x.stl"))
    pecas = arranjo_mesa(poly, a.n)
    mesa = trimesh.util.concatenate([trimesh.creation.extrude_polygon(p, a.espessura) for p in pecas])
    mesa.export(os.path.join(AQUI, "aletas_4x_mesa.stl"))

    for nome, m, dens in (("ogiva_bico.stl", ogiva, c.material.densidade),
                          ("aleta_1x.stl", aleta, a.material.densidade),
                          ("aletas_4x_mesa.stl", mesa, a.material.densidade)):
        tam = m.bounds[1] - m.bounds[0]
        print(f"{nome:20s} estanque={m.is_watertight}  volume={m.volume / 1000:6.2f} cm³  "
              f"massa≈{m.volume / 1000 * dens:5.1f} g  tamanho={tam[0]:.1f} x {tam[1]:.1f} x {tam[2]:.1f} mm  "
              f"triângulos={len(m.faces)}")


if __name__ == "__main__":
    main()
