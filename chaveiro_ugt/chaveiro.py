#!/usr/bin/env python3
"""Chaveiro UGT em 3 cores para impressão 3D (FDM multicolor).

Gera:
  chaveiro_ugt.3mf     projeto Bambu Studio/OrcaSlicer: uma peça com 3 partes, cada uma
                       já no seu filamento do AMS (1 preto, 2 vermelho, 3 branco)
  chaveiro_previa.png  frente e verso

Frente (topo): símbolo e nome em vermelho + UGT em branco, em alto-relevo.
Verso (face na mesa): QR Code branco em relevo de 0,8 mm dentro de um rebaixo; o topo dos
módulos e a borda preta ficam no mesmo nível, apoiados na mesa (peça única, sem cola).

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
RELEVO_QR = 0.8       # relevo do QR no verso = profundidade do rebaixo (4 camadas de 0,2)
REBAIXO_MARGEM = 0.8  # folga do rebaixo em volta do QR
REBAIXO_CANTO = 2.0   # raio dos cantos do rebaixo
FURO = 4.5            # furo da argola
ORELHA_R = 5.5        # raio da orelha do furo
QR_LADO = 32.0        # lado do QR (só os módulos; a margem é o preto da base em volta)
QR_PADRAO = "https://www.ugt.org.br/"

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


def contorno():
    R = DIAMETRO / 2
    yc = R - 0.2
    corpo = Point(0, 0).buffer(R, 256).union(Point(0, yc).buffer(ORELHA_R, 128))
    corpo = corpo.buffer(1.5, 64).buffer(-1.5, 64)  # concordância orelha/disco
    furo = Point(0, yc + 0.6).buffer(FURO / 2, 96)
    return corpo.difference(furo), furo


# Símbolo e textos medidos na arte do cliente (círculos ajustados ao contorno
# traçado da imagem; erro máx. ~0,3 mm). Coordenadas em mm, centro do disco = (0, 0).
SIMBOLO_EXTERNO = ((0.0, 4.6), 17.3)    # borda externa do arco
SIMBOLO_INTERNO = ((-3.85, 4.6), 9.9)   # abertura (deslocada à esquerda: perna esq. fina)
SIMBOLO_MORDIDA = ((-4.1, 20.5), 4.0)   # recorte no topo, alinhado com a abertura
SIMBOLO_BASE = 6.05                     # base reta das duas pernas
CAIXA_UGT = (-17.5, 17.5, -5.3, 4.35)   # x0, x1, y0, y1
CAIXA_LINHA1 = (-17.2, 17.2, -10.45, -7.4)   # inclui o til do Ã
CAIXA_LINHA2 = (-15.6, 15.6, -14.3, -11.9)
ENGROSSAR_TEXTO = 0.06                  # mm por lado no texto pequeno (traço ≥ ~0,5 mm)


def encaixar(g, caixa):
    """Escala (não uniforme) e move g para ocupar exatamente a caixa (x0, x1, y0, y1)."""
    x0, x1, y0, y1 = caixa
    b = g.bounds
    g = affinity.scale(g, (x1 - x0) / (b[2] - b[0]), (y1 - y0) / (b[3] - b[1]), origin=(b[0], b[1]))
    return affinity.translate(g, x0 - b[0], y0 - b[1])


def frente():
    """Relevo da frente: (vermelho, branco)."""
    (cxe, cye), re_ = SIMBOLO_EXTERNO
    (cxi, cyi), ri = SIMBOLO_INTERNO
    (cxm, cym), rm = SIMBOLO_MORDIDA
    simbolo = Point(cxe, cye).buffer(re_, 512).intersection(
        box(-re_ - 1, SIMBOLO_BASE, re_ + 1, cye + re_ + 1))
    simbolo = simbolo.difference(Point(cxi, cyi).buffer(ri, 512))
    simbolo = simbolo.difference(Point(cxm, cym).buffer(rm, 256))
    ugt = encaixar(texto("UGT", 10.0), CAIXA_UGT)
    l1 = encaixar(texto("UNIÃO GERAL DOS", 3.0), CAIXA_LINHA1).buffer(ENGROSSAR_TEXTO, 16)
    l2 = encaixar(texto("TRABALHADORES", 3.0), CAIXA_LINHA2).buffer(ENGROSSAR_TEXTO, 16)
    vermelho = unary_union([simbolo, l1, l2])
    return vermelho, ugt


def verso_qr(conteudo, espelhar=True):
    """Módulos do QR em branco direto sobre a base preta (como na arte do cliente).

    É o QR "invertido": os módulos que num QR comum seriam pretos saem brancos,
    e o preto da base faz o fundo e a margem. Feito no manifold (Clipper) porque
    módulos que se tocam só pela quina quebram a triangulação do shapely/trimesh.
    espelhar=True para o QR na face de baixo (vista virada): assim lê certo com a
    argola para cima. Na metade do verso o QR fica no topo da impressão: sem espelho.
    """
    qr = segno.make(conteudo, error="m", micro=False)
    M = np.array([list(r) for r in qr.matrix], dtype=bool)
    n = M.shape[0]
    mod = QR_LADO / n
    x0 = y0 = -QR_LADO / 2
    modulos = []
    for i in range(n):
        for j in range(n):
            if M[i, j]:
                x = x0 + j * mod
                y = y0 + QR_LADO - (i + 1) * mod
                xm = -x - mod if espelhar else x
                modulos.append(CrossSection.square((mod, mod)).translate((xm, y)))
    # 0,01 mm de sobra: módulos encostados só pela quina viram uma peça só
    branco = CrossSection.batch_boolean(modulos, OpType.Add).offset(0.005, JoinType.Miter)
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
    # rebaixo do verso: quadrado do QR + folga, cantos arredondados
    lado = QR_LADO + 2 * REBAIXO_MARGEM
    rebaixo = (CrossSection.square((lado, lado)).translate((-lado / 2, -lado / 2))
               .offset(-REBAIXO_CANTO, JoinType.Miter).offset(REBAIXO_CANTO, JoinType.Round))
    cs = {"contorno": secao(cont), "vermelho": secao(vermelho2d), "ugt": secao(ugt2d), "qr": qr_cs,
          "rebaixo": rebaixo}
    for nome in ("vermelho", "ugt", "qr", "rebaixo"):
        assert dentro(cs[nome], R - 1.0), f"{nome} passa da borda"
    for nome, g in (("vermelho", vermelho2d), ("UGT", ugt2d)):
        assert g.distance(furo) > 0.8, f"{nome} encosta no furo"
    # o preto perde o rebaixo inteiro; os módulos brancos ocupam parte dele (o resto é vão),
    # então o fundo preto do rebaixo fica 0,8 mm acima da mesa, em ponte entre os módulos
    base = extrudar(cs["contorno"], BASE) - extrudar(cs["rebaixo"], RELEVO_QR)
    vermelho = extrudar(cs["vermelho"], RELEVO, BASE)
    branco = extrudar(cs["ugt"], RELEVO, BASE) + extrudar(cs["qr"], RELEVO_QR)
    partes = {"preto": para_trimesh(base), "vermelho": para_trimesh(vermelho),
              "branco": para_trimesh(branco)}
    return partes, dict(cont=cont, furo=furo, vermelho=vermelho2d, ugt=ugt2d, qr=qr_cs,
                        rebaixo=rebaixo, versao=versao, n=n, mod=mod)


BASE_METADE = 1.5      # cada metade: as duas coladas dão os 3 mm da base
GABARITO_FOLGA = 0.2   # folga do encaixe no gabarito de colagem (por lado)
GABARITO_PAREDE = 4.0
GABARITO_ALTURA = 3.5


def montar_metades(conteudo_qr):
    """Versão em duas metades coladas costas com costas: relevo para fora nos dois lados.

    Cada metade é impressa com o relevo para cima e a face de colar na mesa.
    Frente: logo e nome em relevo. Verso: QR em relevo (sem espelho: é o topo da
    impressão; ao virar a metade sobre a frente, girando pelo eixo vertical, ele
    fica lido certo com a argola para cima).
    """
    cont, furo = contorno()
    vermelho2d, ugt2d = frente()
    qr_cs, versao, n, mod = verso_qr(conteudo_qr, espelhar=False)
    R = DIAMETRO / 2
    assert dentro(qr_cs, R - 1.0), "QR passa da borda"
    cs_cont = secao(cont)
    frente_ = {"preto": para_trimesh(extrudar(cs_cont, BASE_METADE)),
               "vermelho": para_trimesh(extrudar(secao(vermelho2d), RELEVO, BASE_METADE)),
               "branco": para_trimesh(extrudar(secao(ugt2d), RELEVO, BASE_METADE))}
    verso_ = {"preto": para_trimesh(extrudar(cs_cont, BASE_METADE)),
              "branco": para_trimesh(extrudar(qr_cs, RELEVO_QR, BASE_METADE))}
    return {"frente": frente_, "verso": verso_}, dict(qr=qr_cs, versao=versao, n=n, mod=mod)


def gabarito():
    """Moldura sem fundo com o formato do chaveiro: alinha as metades na colagem."""
    cont, _ = contorno()
    silhueta = Polygon(cont.exterior)
    cavidade = silhueta.buffer(GABARITO_FOLGA, 128)
    externo = silhueta.buffer(GABARITO_FOLGA + GABARITO_PAREDE, 128)
    return para_trimesh(extrudar(secao(externo.difference(cavidade)), GABARITO_ALTURA))


FILAMENTO = {"preto": 1, "vermelho": 2, "branco": 3}   # slot do AMS de cada parte
MESA_CENTRO = (128.0, 128.0)                            # centro da mesa 256 x 256 (cabe na A1 mini)


def _uuid(*chave):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "chaveiro-ugt/" + "/".join(map(str, chave))))


def salvar_3mf(caminho, objetos, titulo="Chaveiro UGT"):
    """3MF no formato de projeto do Bambu Studio / OrcaSlicer.

    objetos = [(nome, {cor: malha}, (x, y) na mesa)]. Cada objeto tem uma parte por
    cor, já no filamento (slot do AMS) certo via Metadata/model_settings.config.
    As configurações de impressora/filamento não vão no arquivo: valem as abertas.
    """
    ns = ('xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
          'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
          'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" '
          'requiredextensions="p"')
    cab = '<?xml version="1.0" encoding="UTF-8"?>\n'
    ident = "1 0 0 0 1 0 0 0 1 0 0 0"
    rel_tipo = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
    arquivos, raiz_objs, itens, cfg_objs, instancias, montagem, rels = {}, [], [], [], [], [], []
    pid = 0
    proximo = sum(len(p) for _, p, _ in objetos) + 1  # ids dos objetos depois dos das partes
    for k, (nome_obj, partes, (mx, my)) in enumerate(objetos, 1):
        nomes = list(partes)
        lo, hi = trimesh.util.concatenate([partes[n] for n in nomes]).bounds
        centro = (lo + hi) / 2
        meia_altura = (hi[2] - lo[2]) / 2
        arq = f"3D/Objects/object_{k}.model"
        sub, comps, partes_cfg = [], [], []
        for n in nomes:
            pid += 1
            m = partes[n]
            v = m.vertices - centro
            vs = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>' for a, b, c in v)
            ts = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in m.faces)
            sub.append(f'<object id="{pid}" p:UUID="{_uuid("parte", pid)}" type="model">'
                       f"<mesh><vertices>{vs}</vertices><triangles>{ts}</triangles></mesh></object>")
            comps.append(f'<component p:path="/{arq}" objectid="{pid}" '
                         f'p:UUID="{_uuid("comp", pid)}" transform="{ident}"/>')
            partes_cfg.append(
                f'<part id="{pid}" subtype="normal_part">'
                f'<metadata key="name" value="{escape(CORES[n][0])}"/>'
                '<metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>'
                f'<metadata key="extruder" value="{FILAMENTO[n]}"/>'
                '<mesh_stat edges_fixed="0" degenerate_facets="0" facets_removed="0" '
                'facets_reversed="0" backwards_edges="0"/></part>')
        arquivos[arq] = (f'{cab}<model unit="millimeter" xml:lang="en-US" {ns}>'
                         '<metadata name="BambuStudio:3mfVersion">1</metadata>'
                         f'<resources>{"".join(sub)}</resources><build/></model>')
        rels.append(f'<Relationship Target="/{arq}" Id="rel-{k}" Type="{rel_tipo}"/>')
        oid = proximo
        proximo += 1
        pos = f"1 0 0 0 1 0 0 0 1 {mx} {my} {meia_altura:.4f}"
        raiz_objs.append(f'<object id="{oid}" p:UUID="{_uuid("objeto", k)}" type="model">'
                         f'<components>{"".join(comps)}</components></object>')
        itens.append(f'<item objectid="{oid}" p:UUID="{_uuid("item", k)}" transform="{pos}" '
                     'printable="1"/>')
        cfg_objs.append(f'<object id="{oid}"><metadata key="name" value="{escape(nome_obj)}"/>'
                        f'<metadata key="extruder" value="{FILAMENTO[nomes[0]]}"/>'
                        f'{"".join(partes_cfg)}</object>')
        instancias.append(f'<model_instance><metadata key="object_id" value="{oid}"/>'
                          '<metadata key="instance_id" value="0"/>'
                          f'<metadata key="identify_id" value="{k}"/></model_instance>')
        montagem.append(f'<assemble_item object_id="{oid}" instance_id="0" transform="{pos}" '
                        'offset="0 0 0"/>')
    raiz = (f'{cab}<model unit="millimeter" xml:lang="en-US" {ns}>'
            '<metadata name="Application">BambuStudio-01.09.00.70</metadata>'
            '<metadata name="BambuStudio:3mfVersion">1</metadata>'
            f'<metadata name="Title">{escape(titulo)}</metadata>'
            '<metadata name="Designer">gerado por chaveiro.py</metadata>'
            f'<resources>{"".join(raiz_objs)}</resources>'
            f'<build p:UUID="{_uuid("build")}">{"".join(itens)}</build></model>')
    config = (f'{cab}<config>{"".join(cfg_objs)}'
              '<plate><metadata key="plater_id" value="1"/><metadata key="plater_name" value=""/>'
              f'<metadata key="locked" value="false"/>{"".join(instancias)}</plate>'
              f'<assemble>{"".join(montagem)}</assemble></config>')
    tipos = (f'{cab}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
             '<Default Extension="config" ContentType="text/xml"/>'
             "</Types>")
    rels_raiz = (f'{cab}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 f'<Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="{rel_tipo}"/></Relationships>')
    rels_modelo = (f'{cab}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'{"".join(rels)}</Relationships>')
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", tipos)
        z.writestr("_rels/.rels", rels_raiz)
        z.writestr("3D/3dmodel.model", raiz)
        z.writestr("3D/_rels/3dmodel.model.rels", rels_modelo)
        for arq, xml in arquivos.items():
            z.writestr(arq, xml)
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
            fundo_rebaixo = [np.asarray(a) for a in geo["rebaixo"].to_polygons()]
            ax.add_patch(PathPatch(Path.make_compound_path(
                *[Path(np.vstack([a, a[:1]]), closed=True) for a in fundo_rebaixo]),
                fc="#111111", ec="#3a3a3a", lw=0.8))
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
    cx, cy = MESA_CENTRO
    salvar_3mf(os.path.join(AQUI, "chaveiro_ugt.3mf"), [("Chaveiro UGT", partes, (cx, cy))])
    metades, geo_m = montar_metades(args.qr)
    for lado, m in metades.items():
        for nome, malha in m.items():
            assert malha.is_watertight, f"metade {lado}/{nome} não está fechada"
    salvar_3mf(os.path.join(AQUI, "chaveiro_ugt_metades.3mf"),
               [("Metade frente", metades["frente"], (cx - 33, cy)),
                ("Metade verso", metades["verso"], (cx + 33, cy))], "Chaveiro UGT - metades")
    salvar_3mf(os.path.join(AQUI, "teste_peca_unica_e_metades.3mf"),
               [("Peça única (QR no rebaixo)", partes, (cx - 66, cy)),
                ("Metade frente", metades["frente"], (cx, cy)),
                ("Metade verso", metades["verso"], (cx + 66, cy))], "Teste chaveiro UGT")
    gab = gabarito()
    assert gab.is_watertight
    gab.export(os.path.join(AQUI, "gabarito_colagem.stl"))
    previa(geo, os.path.join(AQUI, "chaveiro_previa.png"), args.qr)

    print(f"QR: versão {geo['versao']} ({geo['n']}×{geo['n']} módulos de {geo['mod']:.2f} mm) -> {args.qr}")
    tot_v = 0
    for nome, m in partes.items():
        v = m.volume / 1000
        tot_v += v
        print(f"{CORES[nome][0]:28s} volume {v:5.2f} cm³  massa (sólida) {v * PLA_G_CM3:5.2f} g  "
              f"filamento 1,75 ≈ {m.volume / FILAMENTO_MM2 / 1000:5.2f} m")
    for lado, m in metades.items():
        v = sum(x.volume for x in m.values()) / 1000
        print(f"Metade {lado:6s}: {v:.2f} cm³ ≈ {v * PLA_G_CM3:.1f} g  ("
              + ", ".join(f"{n} {x.volume / 1000 * PLA_G_CM3:.2f} g" for n, x in m.items()) + ")")
    print(f"Gabarito de colagem: {gab.volume / 1000 * PLA_G_CM3:.1f} g")
    b = trimesh.util.concatenate(list(partes.values())).bounds
    print(f"Total {tot_v:.2f} cm³ ≈ {tot_v * PLA_G_CM3:.1f} g · tamanho "
          f"{b[1][0] - b[0][0]:.1f} × {b[1][1] - b[0][1]:.1f} × {b[1][2] - b[0][2]:.1f} mm")


if __name__ == "__main__":
    main()
