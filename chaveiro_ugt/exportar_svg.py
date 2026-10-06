#!/usr/bin/env python3
"""SVGs do chaveiro em tamanho real (mm), da mesma geometria do 3MF.

Gera:
  qr_code.svg          QR do verso como fica na peça: módulos brancos sobre o fundo preto
                       (o rebaixo de cantos arredondados), na posição de leitura
  chaveiro_frente.svg  face de cima: contorno preto com o furo, símbolo e texto em
                       vermelho, UGT em branco; cada cor num grupo (id preto/vermelho/branco)

Uso: python3 exportar_svg.py [--qr "https://..."]
"""
import argparse
import os

from shapely.geometry import MultiPolygon

import chaveiro as ch

AQUI = os.path.dirname(os.path.abspath(__file__))


def anel(pontos):
    """Lista de (x, y) em mm -> trecho de path; y invertido porque o SVG cresce para baixo."""
    p = [(x, -y) for x, y in pontos]
    return "M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in p) + " Z"


def path_shapely(g):
    partes = []
    for pol in (g.geoms if isinstance(g, MultiPolygon) else [g]):
        partes.append(anel(list(pol.exterior.coords)[:-1]))
        partes.extend(anel(list(r.coords)[:-1]) for r in pol.interiors)
    return " ".join(partes)


def path_secao(cs):
    """CrossSection do manifold -> path (contornos externos e furos)."""
    return " ".join(anel(list(map(tuple, p))) for p in cs.to_polygons())


def svg(caminho, limites, corpo, titulo):
    x0, y0, x1, y1 = limites  # em coordenadas do SVG (y para baixo)
    w, h = x1 - x0, y1 - y0
    with open(caminho, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.3f}mm" height="{h:.3f}mm" '
                f'viewBox="{x0:.3f} {y0:.3f} {w:.3f} {h:.3f}">\n'
                f"<title>{titulo}</title>\n{corpo}</svg>\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qr", default=ch.QR_PADRAO, help="conteúdo do QR Code (link)")
    args = ap.parse_args()
    preto, vermelho, branco = (ch.CORES[n][1] for n in ("preto", "vermelho", "branco"))

    # QR: sem espelho (no 3MF ele é espelhado só porque fica virado para a mesa)
    qr, versao, n, mod = ch.verso_qr(args.qr, espelhar=False)
    lado = ch.QR_LADO + 2 * ch.REBAIXO_MARGEM
    corpo = (f'<rect id="fundo" x="{-lado / 2:.3f}" y="{-lado / 2:.3f}" width="{lado:.3f}" '
             f'height="{lado:.3f}" rx="{ch.REBAIXO_CANTO:g}" fill="{preto}"/>\n'
             f'<path id="modulos" fill="{branco}" fill-rule="evenodd" d="{path_secao(qr)}"/>\n')
    svg(os.path.join(AQUI, "qr_code.svg"), (-lado / 2, -lado / 2, lado / 2, lado / 2), corpo,
        f"QR Code UGT ({args.qr}) - {n}x{n} módulos de {mod:.2f} mm")

    cont, _ = ch.contorno()
    verm, ugt = ch.frente()
    bx0, by0, bx1, by1 = cont.bounds
    corpo = (f'<g id="preto"><path fill="{preto}" fill-rule="evenodd" d="{path_shapely(cont)}"/></g>\n'
             f'<g id="vermelho"><path fill="{vermelho}" fill-rule="evenodd" d="{path_shapely(verm)}"/></g>\n'
             f'<g id="branco"><path fill="{branco}" fill-rule="evenodd" d="{path_shapely(ugt)}"/></g>\n')
    svg(os.path.join(AQUI, "chaveiro_frente.svg"), (bx0, -by1, bx1, -by0), corpo,
        "Chaveiro UGT - frente")

    print(f"Gerado: qr_code.svg ({lado:g} x {lado:g} mm, QR {ch.QR_LADO:g} mm) e chaveiro_frente.svg "
          f"({bx1 - bx0:.1f} x {by1 - by0:.1f} mm)")


if __name__ == "__main__":
    main()
