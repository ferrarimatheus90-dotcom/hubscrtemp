#!/usr/bin/env python3
"""
Gera o arquivo 3MF da tag pet NFC (formato gota, 30 mm de diametro).

- Corpo: disco de 30 mm + alca em gota com furo para argola, 4,0 mm de espessura.
- Cavidade interna: 26 mm de diametro x 1,0 mm (tag NFC de 25 mm), de z=2,0 a z=3,0.
- Relevo superior (0,6 mm): anel da borda, simbolo NFC, pata e texto "APROXIME O CELULAR".
  O relevo e' um objeto separado no 3MF para poder receber outro filamento (branco).
- Pausa de impressao: gravada em Metadata/custom_gcode_per_layer.xml antes da camada
  com z=3,2 mm (camada 16 com camadas de 0,2 mm) -> primeira camada que fecha a cavidade.

Dependencias: trimesh, shapely, manifold3d, mapbox_earcut, matplotlib, numpy
"""
import math
import zipfile
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely import affinity
import trimesh
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties, findfont
from matplotlib import ft2font

OUT_DIR = Path(__file__).resolve().parent

# ---------------- parametros (mm) ----------------
R_DISCO = 15.0          # 30 mm de diametro
ESPESSURA = 4.0         # altura total do corpo
R_CAVIDADE = 12.7       # 25,4 mm: tag de 25 mm + 0,2 mm por lado (furo FDM encolhe ~0,1-0,2 mm)
CAV_Z0, CAV_Z1 = 2.0, 2.6   # cavidade: 0,6 mm (3 camadas) para tag adesiva de ~0,3 mm
ALTURA_RELEVO = 0.6
ALTURA_CAMADA = 0.2
Z_PAUSA = CAV_Z1 + ALTURA_CAMADA   # pausa antes da camada que fecha a cavidade

# alca em gota
R_ALCA = 6.0
CY_ALCA = 15.5
# furo triangular arredondado para argola
FURO_APEX_Y, FURO_BASE_Y, FURO_MEIA_BASE, FURO_RAIO = 18.2, 12.8, 3.0, 0.9

# ---------------- contorno 2D ----------------
disco = Point(0, 0).buffer(R_DISCO, resolution=96)
alca = Point(0, CY_ALCA).buffer(R_ALCA, resolution=64)
contorno = unary_union([disco, alca]).convex_hull
furo = Polygon([(0, FURO_APEX_Y), (-FURO_MEIA_BASE, FURO_BASE_Y),
                (FURO_MEIA_BASE, FURO_BASE_Y)]).buffer(FURO_RAIO, join_style="round")
contorno = contorno.difference(furo)
cavidade = Point(0, 0).buffer(R_CAVIDADE, resolution=96)

# ---------------- corpo 3D ----------------
piso = trimesh.creation.extrude_polygon(contorno, CAV_Z0)
anel = trimesh.creation.extrude_polygon(contorno.difference(cavidade), CAV_Z1 - CAV_Z0)
anel.apply_translation([0, 0, CAV_Z0])
teto = trimesh.creation.extrude_polygon(contorno, ESPESSURA - CAV_Z1)
teto.apply_translation([0, 0, CAV_Z1])
corpo = trimesh.boolean.union([piso, anel, teto], engine="manifold")
corpo.merge_vertices()
assert corpo.is_watertight, "corpo nao e' estanque"

# ---------------- relevo 2D ----------------
def elipse(cx, cy, rx, ry, ang=0.0):
    e = affinity.scale(Point(0, 0).buffer(1.0, resolution=48), rx, ry)
    e = affinity.rotate(e, ang, origin=(0, 0))
    return affinity.translate(e, cx, cy)

# anel da borda, interrompido no setor da alca (nao passa sobre o furo da argola)
ANG_CORTE = 35.0   # meio-angulo do setor removido, em graus, em torno de 90 graus
borda = Point(0, 0).buffer(R_DISCO, resolution=96).difference(
    Point(0, 0).buffer(13.3, resolution=96))
setor_alca = Polygon([(0, 0)] + [
    (25 * math.cos(math.radians(a)), 25 * math.sin(math.radians(a)))
    for a in np.linspace(90 - ANG_CORTE, 90 + ANG_CORTE, 30)])
borda = borda.difference(setor_alca)

# pata
pata = [elipse(0, -5.2, 2.8, 2.3)]
for (x, y) in [(-3.7, -1.6), (-1.35, 0.3), (1.35, 0.3), (3.7, -1.6)]:
    pata.append(elipse(x, y, 1.15, 1.35))
pata = unary_union(pata)

# simbolo NFC: ponto + 3 arcos a direita
def arco(cx, cy, r, largura, a0, a1):
    pts_ext = [(cx + (r + largura / 2) * math.cos(math.radians(a)),
                cy + (r + largura / 2) * math.sin(math.radians(a)))
               for a in np.linspace(a0, a1, 40)]
    pts_int = [(cx + (r - largura / 2) * math.cos(math.radians(a)),
                cy + (r - largura / 2) * math.sin(math.radians(a)))
               for a in np.linspace(a1, a0, 40)]
    return Polygon(pts_ext + pts_int).buffer(0.001)

nfc_cx, nfc_cy = -4.0, 7.3
nfc = [Point(nfc_cx, nfc_cy).buffer(0.9, resolution=32)]
for r in (2.4, 3.8, 5.2):
    nfc.append(arco(nfc_cx, nfc_cy, r, 0.85, -48, 48))
nfc = unary_union(nfc)

# texto em arco na parte de baixo
TEXTO = "APROXIME O CELULAR"
TAM_FONTE = 3.2        # em; altura das maiusculas ~2,3 mm
ESPACO = 0.25
R_BASE = 12.4          # raio da linha de base (pes das letras para fora)
fp = FontProperties(family="DejaVu Sans", weight="bold")
arquivo_fonte = findfont(fp)
ft = ft2font.FT2Font(arquivo_fonte)
ft.set_size(TAM_FONTE, 72)  # 1 pt = 1 unidade -> avanco direto em mm

def glifo_poligono(ch):
    if not ch.strip():
        return None
    tp = TextPath((0, 0), ch, size=TAM_FONTE, prop=fp)
    polys = [Polygon(p) for p in tp.to_polygons() if len(p) >= 3]
    polys = [p.buffer(0) for p in polys if p.is_valid or p.buffer(0).area > 0]
    polys.sort(key=lambda p: p.area, reverse=True)
    res = None
    for p in polys:
        if res is None:
            res = p
        elif res.contains(p.representative_point()):
            res = res.difference(p)
        else:
            res = res.union(p)
    return res

def avanco(ch):
    return ft.load_char(ord(ch)).linearHoriAdvance / 65536.0

avancos = [avanco(c) for c in TEXTO]
comprimento = sum(avancos) + ESPACO * (len(TEXTO) - 1)
ang_total = comprimento / R_BASE
ang = math.radians(270) - ang_total / 2   # comeca a esquerda, le da esquerda p/ direita
letras = []
for ch, adv in zip(TEXTO, avancos):
    centro = ang + (adv / 2) / R_BASE
    g = glifo_poligono(ch)
    if g is not None and not g.is_empty:
        g = affinity.translate(g, -adv / 2, 0)   # centraliza o avanco
        s, c = math.sin(centro), math.cos(centro)
        # x local -> tangente; y local -> em direcao ao centro
        g = affinity.affine_transform(g, [-s, -c, c, -s, R_BASE * c, R_BASE * s])
        letras.append(g)
    ang += (adv + ESPACO) / R_BASE
texto = unary_union(letras)

relevo_2d = unary_union([borda, pata, nfc, texto]).buffer(0)
# limpa vertices quase coincidentes das fontes (evitam triangulos degenerados)
relevo_2d = shapely.set_precision(relevo_2d.simplify(0.01, preserve_topology=True), 0.001).buffer(0)
pecas = relevo_2d.geoms if hasattr(relevo_2d, "geoms") else [relevo_2d]
relevo = trimesh.util.concatenate(
    [trimesh.creation.extrude_polygon(pc, ALTURA_RELEVO) for pc in pecas if pc.area > 0.01])
relevo.apply_translation([0, 0, ESPESSURA])
relevo.merge_vertices()
relevo.update_faces(relevo.nondegenerate_faces(height=1e-6))
assert relevo.is_watertight, "relevo nao e' estanque"
print("Relevo: triangulos degenerados restantes:", int((relevo.area_faces < 1e-9).sum()))

# ---------------- exportacao 3MF ----------------
def mesh_xml(mesh):
    v = "".join(f'<vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>' for x, y, z in mesh.vertices)
    t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in mesh.faces)
    return f"<mesh><vertices>{v}</vertices><triangles>{t}</triangles></mesh>"

modelo = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<model unit="millimeter" xml:lang="en-US" '
    'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n'
    '<metadata name="Title">Tag NFC Pet - Aproxime o celular</metadata>\n'
    '<metadata name="Application">gerar_tag_nfc.py</metadata>\n'
    '<resources>\n'
    f'<object id="1" name="Corpo (preto)" type="model">{mesh_xml(corpo)}</object>\n'
    f'<object id="2" name="Relevo (branco)" type="model">{mesh_xml(relevo)}</object>\n'
    '<object id="3" name="Tag NFC Pet 30mm" type="model"><components>'
    '<component objectid="1" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
    '<component objectid="2" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
    '</components></object>\n'
    '</resources>\n'
    '<build>\n'
    '<item objectid="3" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n'
    '</build>\n'
    '</model>\n'
)

content_types = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
    '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
    '<Default Extension="xml" ContentType="application/xml"/>\n'
    '</Types>\n'
)
rels = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
    '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
    'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
    '</Relationships>\n'
)
# Pausa lida pelo Bambu Studio / OrcaSlicer (type 1 = PausePrint)
pausa = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<custom_gcodes_per_layer>\n'
    '<plate>\n'
    '<plate_info id="1"/>\n'
    f'<layer top_z="{Z_PAUSA:.2f}" type="1" extruder="1" color="" extra="" gcode="M400 U1"/>\n'
    '<mode value="SingleExtruder"/>\n'
    '</plate>\n'
    '</custom_gcodes_per_layer>\n'
)

saida = OUT_DIR / "tag_nfc_pet_30mm.3mf"
with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", content_types)
    z.writestr("_rels/.rels", rels)
    z.writestr("3D/3dmodel.model", modelo)
    z.writestr("Metadata/custom_gcode_per_layer.xml", pausa)

# STL de apoio (corpo + relevo unidos) para fatiadores que ignoram o 3MF
unido = trimesh.boolean.union([corpo, relevo], engine="manifold")
unido.export(OUT_DIR / "tag_nfc_pet_30mm_unico.stl")

# ---------------- preview ----------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from shapely.geometry.polygon import orient

def patch(geom, **kw):
    geoms = geom.geoms if hasattr(geom, "geoms") else [geom]
    verts, codes = [], []
    for g in geoms:
        g = orient(g, 1.0)
        for ring in [g.exterior, *g.interiors]:
            xy = np.asarray(ring.coords)
            verts.extend(xy.tolist())
            codes.extend([MplPath.MOVETO] + [MplPath.LINETO] * (len(xy) - 2) + [MplPath.CLOSEPOLY])
    return PathPatch(MplPath(verts, codes), **kw)

fig = plt.figure(figsize=(15, 5.5))
ax1 = fig.add_subplot(1, 3, 1)
ax1.add_patch(patch(contorno, facecolor="#222", edgecolor="none"))
ax1.add_patch(patch(relevo_2d, facecolor="white", edgecolor="none"))
ax1.plot(*Point(0, 0).buffer(R_CAVIDADE).exterior.xy, "--", color="#e33", lw=1,
         label="cavidade da tag (26 mm)")
ax1.set_xlim(-17, 17); ax1.set_ylim(-17, 24)
ax1.set_aspect("equal"); ax1.set_title("Vista superior (mm)"); ax1.legend(loc="upper right")
ax1.grid(alpha=.3)

ax2 = fig.add_subplot(1, 3, 2)
sec = unido.section(plane_origin=[0, 0, 0], plane_normal=[1, 0, 0])
for ent in sec.entities:
    pts = sec.vertices[ent.points]
    ax2.plot(pts[:, 1], pts[:, 2], color="#222")
ax2.axhline(Z_PAUSA, color="#e33", ls="--", lw=1, label=f"pausa: z = {Z_PAUSA:.1f} mm")
ax2.axhspan(CAV_Z0, CAV_Z1, xmin=0.08, xmax=0.92, color="#e33", alpha=.08)
ax2.set_xlim(-17, 24); ax2.set_ylim(-2, 8)
ax2.set_aspect("equal"); ax2.set_title("Corte em x = 0 (y x z, mm)"); ax2.legend(loc="upper right")
ax2.grid(alpha=.3)

ax3 = fig.add_subplot(1, 3, 3, projection="3d")
for m, cor in [(corpo, "#2a2a2a"), (relevo, "#f2f2f2")]:
    tri = m.vertices[m.faces]
    pc = Poly3DCollection(tri, facecolors=cor, linewidths=0, shade=True,
                          lightsource=matplotlib.colors.LightSource(azdeg=315, altdeg=55))
    ax3.add_collection3d(pc)
ax3.set_xlim(-18, 18); ax3.set_ylim(-18, 24); ax3.set_zlim(-15, 20)
ax3.set_box_aspect((36, 42, 35)); ax3.view_init(elev=55, azim=-60)
ax3.set_axis_off(); ax3.set_title("Vista 3D")
plt.tight_layout()
plt.savefig(OUT_DIR / "preview.png", dpi=130)

b = contorno.bounds
print(f"Contorno: {b[2]-b[0]:.1f} x {b[3]-b[1]:.1f} mm, altura total {ESPESSURA+ALTURA_RELEVO:.1f} mm")
print(f"Corpo: {len(corpo.faces)} faces, estanque={corpo.is_watertight}, volume={corpo.volume:.0f} mm3")
print(f"Relevo: {len(relevo.faces)} faces, estanque={relevo.is_watertight}")
print(f"Pausa antes da camada com z={Z_PAUSA:.1f} mm (camada {round(Z_PAUSA/ALTURA_CAMADA)} com camadas de {ALTURA_CAMADA} mm)")
print("Gerado:", saida)
