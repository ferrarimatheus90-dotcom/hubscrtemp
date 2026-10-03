#!/usr/bin/env python3
"""Chaveiro UGT em 3 cores para impressão 3D (FDM multicolor).

Gera:
  chaveiro_ugt.3mf     projeto Bambu Studio/OrcaSlicer: uma peça com 3 partes, cada uma
                       já no seu filamento do AMS (1 preto, 2 vermelho, 3 branco)
  chaveiro_previa.png  frente e verso

Frente (topo): símbolo e nome em vermelho + UGT em branco, em alto-relevo.
Verso (face na mesa): QR Code branco embutido rente à face.

Uso: python3 chaveiro.py [--qr "https://..."]
"""
import argparse
import os
import uuid
import zipfile
from xml.sax.saxutils import escape

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import segno
import trimesh
from manifold3d import CrossSection, FillRule, JoinType, OpType
from matplotlib.font_manager import FontProperties
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from matplotlib.textpath import TextPath
from shapely import affinity
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

AQUI = os.path.dirname(os.path.abspath(__file__))
FONTE = FontProperties(fname="/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")

# ---- medidas (mm)
DIAMETRO = 50.0
BASE = 3.0            # espessura da peça (disco)
RELEVO = 0.8          # altura do relevo da frente
INCRUSTE = 0.6        # profundidade do QR no verso (rente à face, 3 camadas de 0,2)
FURO = 4.5            # furo da argola
ORELHA_R = 5.5        # raio da orelha do furo
QR_LADO = 33.0        # lado do quadrado branco do QR (inclui margem)
QR_MARGEM = 2         # módulos de margem branca em volta do QR
QR_PADRAO = "https://www.ugt.org.br"

CORES = {  # nome, cor de exibição (sRGB)
    "preto": ("Preto (base)", "#1E1E1E"),
    "vermelho": ("Vermelho (símbolo e texto)", "#D7261E"),
    "branco": ("Branco (UGT e QR Code)", "#F2F2F2"),
}
PLA_G_CM3 = 1.24
FILAMENTO_MM2 = np.pi * (1.75 / 2) ** 2


# --------------------------------------------------------------------------- 2D

def texto(s, altura_maiuscula):
    """Texto -> MultiPolygon (mm), com a altura das maiúsculas pedida, base em y = 0."""
    cap = TextPath((0, 0), "H", size=100, prop=FONTE).get_extents().height
    tp = TextPath((0, 0), s, size=100, prop=FONTE)
    g = Polygon()
    for anel in tp.to_polygons(closed_only=True):
        if len(anel) >= 3:
            g = g.symmetric_difference(Polygon(anel).buffer(0))
    k = altura_maiuscula / cap
    return affinity.scale(g, k, k, origin=(0, 0))


def centralizar_x(g, y_topo_maiusc, altura_maiuscula):
    b = g.bounds
    return affinity.translate(g, -(b[0] + b[2]) / 2, y_topo_maiusc - altura_maiuscula)


def contorno():
    R = DIAMETRO / 2
    yc = R - 0.2
    corpo = Point(0, 0).buffer(R, 256).union(Point(0, yc).buffer(ORELHA_R, 128))
    corpo = corpo.buffer(1.5, 64).buffer(-1.5, 64)  # concordância orelha/disco
    furo = Point(0, yc + 0.6).buffer(FURO / 2, 96)
    return corpo.difference(furo), furo


def frente():
    """Relevo da frente: (vermelho, branco)."""
    # símbolo: arco (meia coroa) com o recorte no topo
    yc, Ro, Ri = 4.7, 17.3, 7.9
    arco = Point(0, yc).buffer(Ro, 256).difference(Point(0, yc).buffer(Ri, 256))
    arco = arco.intersection(box(-Ro - 1, yc, Ro + 1, yc + Ro + 1))
    arco = arco.difference(Point(0, yc + Ro).buffer(2.2, 64))
    # UGT
    ugt = centralizar_x(texto("UGT", 9.2), 2.9, 9.2)
    larg = ugt.bounds[2] - ugt.bounds[0]
    if larg > 36.5:
        k = 36.5 / larg
        ugt = affinity.scale(ugt, k, 1.0, origin=(0, 0))
    # nome por extenso, duas linhas
    l1 = texto("UNIÃO GERAL DOS", 3.0)
    l2 = texto("TRABALHADORES", 3.0)
    alvo = 31.5
    for i, l in enumerate((l1, l2)):
        k = alvo / (l.bounds[2] - l.bounds[0])
        k = min(k, 1.15)
        l = affinity.scale(l, k, k, origin=(0, 0))
        h = 3.0 * k
        topo = -8.1 if i == 0 else -8.1 - h - 1.1
        if i == 0:
            l1, h1 = centralizar_x(l, topo, h), h
        else:
            l2 = centralizar_x(l, -8.1 - h1 - 1.1, h)
    vermelho = unary_union([arco, l1, l2])
    return vermelho, ugt


def verso_qr(conteudo):
    """Quadrado branco do QR (módulos claros + margem) como CrossSection do manifold.

    Feito direto no manifold (Clipper) porque módulos que se tocam só pela quina
    quebram a triangulação do shapely/trimesh. Já sai espelhado em x: a face de
    baixo é vista virada, e assim o código lê certo com a argola para cima.
    """
    qr = segno.make(conteudo, error="m", micro=False)
    M = np.array([list(r) for r in qr.matrix], dtype=bool)
    n = M.shape[0]
    mod = QR_LADO / (n + 2 * QR_MARGEM)
    x0 = y0 = -QR_LADO / 2
    escuros = []
    for i in range(n):
        for j in range(n):
            if M[i, j]:
                x = x0 + (j + QR_MARGEM) * mod
                y = y0 + QR_LADO - (i + QR_MARGEM + 1) * mod
                escuros.append(CrossSection.square((mod, mod)).translate((-x - mod, y)))
    # 0,01 mm de sobra: módulos encostados só pela quina viram uma peça só
    escuro = CrossSection.batch_boolean(escuros, OpType.Add).offset(0.005, JoinType.Miter)
    branco = CrossSection.square((QR_LADO, QR_LADO)).translate((x0, y0)) - escuro
    return branco, qr.version, n, mod


# --------------------------------------------------------------------------- 3D

def secao(g):
    """shapely (Multi)Polygon -> CrossSection do manifold."""
    aneis = []
    for p in (g.geoms if isinstance(g, MultiPolygon) else [g]):
        aneis.append(np.asarray(p.exterior.coords)[:-1])
        aneis.extend(np.asarray(r.coords)[:-1] for r in p.interiors)
    return CrossSection(aneis, FillRule.EvenOdd)


def extrudar(cs, altura, z0=0.0):
    return cs.extrude(altura).translate((0.0, 0.0, z0))


def para_trimesh(man):
    malha = man.to_mesh()
    return trimesh.Trimesh(np.asarray(malha.vert_properties)[:, :3], np.asarray(malha.tri_verts))


def dentro(cs, raio):
    """Todos os vértices da seção dentro do círculo de raio dado?"""
    return all(np.hypot(*np.asarray(a).T).max() <= raio for a in cs.to_polygons())


def montar(conteudo_qr):
    cont, furo = contorno()
    vermelho2d, ugt2d = frente()
    qr_cs, versao, n, mod = verso_qr(conteudo_qr)
    R = DIAMETRO / 2
    cs = {"contorno": secao(cont), "vermelho": secao(vermelho2d), "ugt": secao(ugt2d), "qr": qr_cs}
    for nome in ("vermelho", "ugt", "qr"):
        assert dentro(cs[nome], R - 1.0), f"{nome} passa da borda"
    for nome, g in (("vermelho", vermelho2d), ("UGT", ugt2d)):
        assert g.distance(furo) > 0.8, f"{nome} encosta no furo"
    base = extrudar(cs["contorno"], BASE) - extrudar(cs["qr"], INCRUSTE)
    vermelho = extrudar(cs["vermelho"], RELEVO, BASE)
    branco = extrudar(cs["ugt"], RELEVO, BASE) + extrudar(cs["qr"], INCRUSTE)
    partes = {"preto": para_trimesh(base), "vermelho": para_trimesh(vermelho),
              "branco": para_trimesh(branco)}
    return partes, dict(cont=cont, furo=furo, vermelho=vermelho2d, ugt=ugt2d, qr=qr_cs,
                        versao=versao, n=n, mod=mod)


FILAMENTO = {"preto": 1, "vermelho": 2, "branco": 3}   # slot do AMS de cada parte
MESA_CENTRO = (128.0, 128.0)                            # centro da mesa 256 x 256 (cabe na A1 mini)


def _uuid(*chave):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "chaveiro-ugt/" + "/".join(map(str, chave))))


def salvar_3mf(caminho, partes, nome_obj="Chaveiro UGT"):
    """3MF no formato de projeto do Bambu Studio / OrcaSlicer.

    Um único objeto com uma parte por cor; cada parte já sai com o filamento
    (slot do AMS) definido em Metadata/model_settings.config. As configurações
    de impressora/filamento não vão no arquivo: valem as que estiverem abertas.
    """
    nomes = list(partes)
    tudo = trimesh.util.concatenate([partes[n] for n in nomes])
    lo, hi = tudo.bounds
    centro = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2])
    meia_altura = (hi[2] - lo[2]) / 2
    ns = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
          'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
          'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
          'requiredextensions="p"')
    cab = '<?xml version="1.0" encoding="UTF-8"?>\n'
    ident = "1 0 0 0 1 0 0 0 1 0 0 0"
    obj_id = len(nomes) + 1

    sub = []
    for i, nome in enumerate(nomes, 1):
        m = partes[nome]
        v = m.vertices - centro
        vs = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>' for a, b, c in v)
        ts = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in m.faces)
        sub.append(f'<object id="{i}" p:UUID="{_uuid("parte", i)}" type="model">'
                   f"<mesh><vertices>{vs}</vertices><triangles>{ts}</triangles></mesh></object>")
    objetos = (f'{cab}<model unit="millimeter" xml:lang="en-US" {ns}>'
               '<metadata name="BambuStudio:3mfVersion">1</metadata>'
               f'<resources>{"".join(sub)}</resources><build/></model>')

    comps = "".join(f'<component p:path="/3D/Objects/object_1.model" objectid="{i}" '
                    f'p:UUID="{_uuid("comp", i)}" transform="{ident}"/>'
                    for i in range(1, len(nomes) + 1))
    pos = f"1 0 0 0 1 0 0 0 1 {MESA_CENTRO[0]} {MESA_CENTRO[1]} {meia_altura:.4f}"
    raiz = (f'{cab}<model unit="millimeter" xml:lang="en-US" {ns}>'
            '<metadata name="Application">BambuStudio-01.09.00.70</metadata>'
            '<metadata name="BambuStudio:3mfVersion">1</metadata>'
            f'<metadata name="Title">{escape(nome_obj)}</metadata>'
            '<metadata name="Designer">gerado por chaveiro.py</metadata>'
            f'<resources><object id="{obj_id}" p:UUID="{_uuid("objeto")}" type="model">'
            f"<components>{comps}</components></object></resources>"
            f'<build p:UUID="{_uuid("build")}"><item objectid="{obj_id}" p:UUID="{_uuid("item")}" '
            f'transform="{pos}" printable="1"/></build></model>')

    partes_cfg = "".join(
        f'<part id="{i}" subtype="normal_part">'
        f'<metadata key="name" value="{escape(CORES[n][0])}"/>'
        '<metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>'
        f'<metadata key="extruder" value="{FILAMENTO[n]}"/>'
        '<mesh_stat edges_fixed="0" degenerate_facets="0" facets_removed="0" '
        'facets_reversed="0" backwards_edges="0"/></part>'
        for i, n in enumerate(nomes, 1))
    config = (f'{cab}<config><object id="{obj_id}">'
              f'<metadata key="name" value="{escape(nome_obj)}"/>'
              f'<metadata key="extruder" value="{FILAMENTO[nomes[0]]}"/>{partes_cfg}</object>'
              '<plate><metadata key="plater_id" value="1"/><metadata key="plater_name" value=""/>'
              '<metadata key="locked" value="false"/><model_instance>'
              f'<metadata key="object_id" value="{obj_id}"/><metadata key="instance_id" value="0"/>'
              '<metadata key="identify_id" value="1"/></model_instance></plate>'
              f'<assemble><assemble_item object_id="{obj_id}" instance_id="0" transform="{pos}" '
              'offset="0 0 0"/></assemble></config>')

    tipos = (f'{cab}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
             '<Default Extension="config" ContentType="text/xml"/>'
             "</Types>")
    rel_tipo = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
    rels = (f'{cab}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="{rel_tipo}"/></Relationships>')
    rels_modelo = (f'{cab}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'<Relationship Target="/3D/Objects/object_1.model" Id="rel-1" Type="{rel_tipo}"/>'
                   "</Relationships>")
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", tipos)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", raiz)
        z.writestr("3D/_rels/3dmodel.model.rels", rels_modelo)
        z.writestr("3D/Objects/object_1.model", objetos)
        z.writestr("Metadata/model_settings.config", config)


# --------------------------------------------------------------------------- prévia

def previa(geo, caminho, conteudo):
    fig, axs = plt.subplots(1, 2, figsize=(10, 5.6), dpi=160)
    fundo = "#e9ecef"
    fig.patch.set_facecolor(fundo)
    for ax, titulo, verso in ((axs[0], "FRENTE", False), (axs[1], "VERSO", True)):
        ax.set_facecolor(fundo)
        cont = geo["cont"]
        if verso:
            cont = affinity.scale(cont, -1, 1, origin=(0, 0))
        x, y = cont.exterior.xy
        ax.fill(x, y, color=CORES["preto"][1], lw=0)
        for anel in cont.interiors:
            ax.fill(*anel.xy, color=fundo, lw=0)
        if verso:  # visto de trás: desfaz o espelhamento
            aneis = [np.asarray(a) * [-1, 1] for a in geo["qr"].to_polygons()]
            caminho_qr = Path.make_compound_path(*[Path(np.vstack([a, a[:1]]), closed=True)
                                                  for a in aneis])
            ax.add_patch(PathPatch(caminho_qr, fc=CORES["branco"][1], lw=0))
        else:
            for g, c in ((geo["vermelho"], "vermelho"), (geo["ugt"], "branco")):
                for p in (g.geoms if isinstance(g, MultiPolygon) else [g]):
                    ax.fill(*p.exterior.xy, color=CORES[c][1], lw=0)
                    for anel in p.interiors:
                        ax.fill(*anel.xy, color=CORES["preto"][1], lw=0)
        ax.set_aspect("equal")
        ax.set_xlim(-29, 29)
        ax.set_ylim(-28, 34)
        ax.axis("off")
        ax.set_title(titulo, fontsize=13, weight="bold", color="#1d2733")
    fig.text(0.5, 0.03, f"Ø{DIAMETRO:g} mm · base {BASE:g} mm · relevo {RELEVO:g} mm · "
             f"furo Ø{FURO:g} mm · QR: {conteudo}".replace(".", ",").replace("https,//", "https://")
             .replace(",org,br", ".org.br").replace("www,", "www."),
             ha="center", fontsize=9.5, color="#1d2733")
    fig.savefig(caminho, facecolor=fundo)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qr", default=QR_PADRAO, help="conteúdo do QR Code (link)")
    args = ap.parse_args()

    partes, geo = montar(args.qr)
    for nome, m in partes.items():
        assert m.is_watertight, f"{nome} não está fechado"
    salvar_3mf(os.path.join(AQUI, "chaveiro_ugt.3mf"), partes)
    previa(geo, os.path.join(AQUI, "chaveiro_previa.png"), args.qr)

    print(f"QR: versão {geo['versao']} ({geo['n']}×{geo['n']} módulos de {geo['mod']:.2f} mm) -> {args.qr}")
    tot_v = 0
    for nome, m in partes.items():
        v = m.volume / 1000
        tot_v += v
        print(f"{CORES[nome][0]:28s} volume {v:5.2f} cm³  massa (sólida) {v * PLA_G_CM3:5.2f} g  "
              f"filamento 1,75 ≈ {m.volume / FILAMENTO_MM2 / 1000:5.2f} m")
    b = trimesh.util.concatenate(list(partes.values())).bounds
    print(f"Total {tot_v:.2f} cm³ ≈ {tot_v * PLA_G_CM3:.1f} g · tamanho "
          f"{b[1][0] - b[0][0]:.1f} × {b[1][1] - b[0][1]:.1f} × {b[1][2] - b[0][2]:.1f} mm")


if __name__ == "__main__":
    main()
