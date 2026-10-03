#!/usr/bin/env python3
"""Imagem ilustrativa 3D do foguete (rasterizador próprio com z-buffer).

A geometria sai do mesmo modelo do desenho (modelo.py): superfícies de revolução
de cada componente + aletas extrudadas. A garrafa PET é renderizada translúcida.
"""
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import shapely
from numba import njit
from shapely.geometry import Polygon

from folha import fmt
from modelo import Foguete

AQUI = os.path.dirname(os.path.abspath(__file__))
ROLL = 0.0  # giro do foguete no próprio eixo (escolhido para as 4 aletas aparecerem)

# materiais
PLA, PET, ESCURO = 0, 1, 2
COR = {
    PLA: np.array([0.88, 0.28, 0.14]),
    PET: np.array([0.80, 0.93, 0.97]),
    ESCURO: np.array([0.08, 0.09, 0.10]),
}


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


# --------------------------------------------------------------------------- malhas

class Malha:
    def __init__(self):
        self.v, self.n, self.f, self.m = [], [], [], []
        self.nv = 0

    def add(self, v, n, f, mat):
        self.v.append(v)
        self.n.append(n)
        self.f.append(f + self.nv)
        self.m.append(np.full(len(f), mat))
        self.nv += len(v)

    def arrays(self):
        return (np.concatenate(self.v), np.concatenate(self.n),
                np.concatenate(self.f), np.concatenate(self.m))


def revolucao(x, r, mat, malha, n_ang=120, inverter=False):
    """Superfície de revolução do perfil (x, r) em torno do eixo x."""
    x, r = np.asarray(x, float), np.asarray(r, float)
    dx, dr = np.gradient(x), np.gradient(r)
    nx, nr = -dr, dx
    s = np.hypot(nx, nr)
    s[s == 0] = 1
    nx, nr = nx / s, nr / s
    if inverter:
        nx, nr = -nx, -nr
    th = np.linspace(0, 2 * np.pi, n_ang + 1)
    c, sn = np.cos(th), np.sin(th)
    V = np.stack([np.repeat(x[:, None], n_ang + 1, 1), r[:, None] * c, r[:, None] * sn], -1)
    N = np.stack([np.repeat(nx[:, None], n_ang + 1, 1), nr[:, None] * c, nr[:, None] * sn], -1)
    P, A = len(x), n_ang + 1
    idx = np.arange(P * A).reshape(P, A)
    a, b = idx[:-1, :-1].ravel(), idx[1:, :-1].ravel()
    cc, d = idx[1:, 1:].ravel(), idx[:-1, 1:].ravel()
    F = np.concatenate([np.stack([a, b, cc], 1), np.stack([a, cc, d], 1)])
    malha.add(V.reshape(-1, 3), N.reshape(-1, 3), F, mat)


def disco(x, r0, r1, normal_x, mat, malha, n_ang=120):
    th = np.linspace(0, 2 * np.pi, n_ang + 1)
    V = np.concatenate([np.stack([np.full_like(th, x), r0 * np.cos(th), r0 * np.sin(th)], 1),
                        np.stack([np.full_like(th, x), r1 * np.cos(th), r1 * np.sin(th)], 1)])
    N = np.tile([normal_x, 0.0, 0.0], (len(V), 1))
    A = n_ang + 1
    i = np.arange(n_ang)
    F = np.concatenate([np.stack([i, i + A, i + A + 1], 1), np.stack([i, i + A + 1, i + 1], 1)])
    malha.add(V, N, F, mat)


def aleta_malha(fog, a, phi, malha):
    borda = np.column_stack([a.x_ba + a.pontos[:, 0], a.r_ba + a.pontos[:, 1]])
    xr = np.linspace(borda[-1, 0], borda[0, 0], 40)
    raiz = np.column_stack([xr, fog.raio(xr) - 1.0])
    contorno = np.concatenate([borda, raiz[1:-1]])
    poly = Polygon(contorno)
    tris = shapely.constrained_delaunay_triangles(poly)
    u = np.array([0.0, math.cos(phi), math.sin(phi)])   # radial
    t = np.array([0.0, -math.sin(phi), math.cos(phi)])  # tangencial
    meia = a.espessura / 2

    def P3(xy, s):
        return xy[:, :1] * np.array([1.0, 0, 0]) + xy[:, 1:2] * u + s * t

    for g in tris.geoms:
        xy = np.array(g.exterior.coords)[:3]
        for s in (meia, -meia):
            V = P3(xy, s)
            N = np.tile(t * np.sign(s), (3, 1))
            malha.add(V, N, np.array([[0, 1, 2]]), PLA)
    # laterais
    cont = np.concatenate([contorno, contorno[:1]])
    for p, q in zip(cont[:-1], cont[1:]):
        e = q - p
        n2 = np.array([e[1], -e[0]])
        n2 = n2 / (np.linalg.norm(n2) + 1e-12)
        if Polygon(contorno).exterior.is_ccw:
            n2 = -n2
        V = np.concatenate([P3(np.array([p, q]), meia), P3(np.array([q, p]), -meia)])
        N = np.tile(n2[0] * np.array([1.0, 0, 0]) + n2[1] * u, (4, 1))
        malha.add(V, N, np.array([[0, 1, 2], [0, 2, 3]]), PLA)


def montar(fog, roll=0.0):
    m = Malha()
    for c in fog.componentes:
        n = 160 if c.forma not in (None, "conical") else 2
        x, r = c.perfil(n)
        revolucao(x, r, PLA if c.tipo == "nosecone" else PET, m)
    ogiva = fog.componentes[0]
    disco(ogiva.x1, 0, ogiva.r_tras, 1.0, PLA, m)
    ult = fog.componentes[-1]
    r_in = ult.r_tras - ult.espessura
    L = fog.comprimento
    disco(L, r_in, ult.r_tras, 1.0, PET, m)
    revolucao([L, L - 14], [r_in, r_in], ESCURO, m, inverter=True)
    disco(L - 14, 0, r_in, 1.0, ESCURO, m)
    a = fog.aletas[0]
    for k in range(a.n):
        aleta_malha(fog, a, math.radians(a.angulo0 + roll) + k * 2 * math.pi / a.n, m)
    return m.arrays()


# --------------------------------------------------------------------------- rasterização

@njit(cache=True)
def rasterizar(sx, sy, iz, attr, faces, sel, W, H, zbuf, abuf, mbuf, mat, sinal):
    for k in range(faces.shape[0]):
        if not sel[k]:
            continue
        i0, i1, i2 = faces[k, 0], faces[k, 1], faces[k, 2]
        if iz[i0] <= 0 or iz[i1] <= 0 or iz[i2] <= 0:
            continue
        x0, y0, x1, y1, x2, y2 = sx[i0], sy[i0], sx[i1], sy[i1], sx[i2], sy[i2]
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-12:
            continue
        xmin = max(int(math.floor(min(x0, x1, x2))), 0)
        xmax = min(int(math.ceil(max(x0, x1, x2))), W - 1)
        ymin = max(int(math.floor(min(y0, y1, y2))), 0)
        ymax = min(int(math.ceil(max(y0, y1, y2))), H - 1)
        for py in range(ymin, ymax + 1):
            cy = py + 0.5
            for px in range(xmin, xmax + 1):
                cx = px + 0.5
                w0 = ((x1 - cx) * (y2 - cy) - (x2 - cx) * (y1 - cy)) / area
                w1 = ((x2 - cx) * (y0 - cy) - (x0 - cx) * (y2 - cy)) / area
                w2 = 1.0 - w0 - w1
                if w0 < 0 or w1 < 0 or w2 < 0:
                    continue
                q = w0 * iz[i0] + w1 * iz[i1] + w2 * iz[i2]  # 1/z
                z = 1.0 / q
                if sinal * z < zbuf[py, px]:
                    zbuf[py, px] = sinal * z
                    mbuf[py, px] = mat[k]
                    for c in range(attr.shape[1]):
                        abuf[py, px, c] = (w0 * attr[i0, c] * iz[i0] + w1 * attr[i1, c] * iz[i1]
                                           + w2 * attr[i2, c] * iz[i2]) * z


class Camera:
    def __init__(self, olho, alvo, W, H, f):
        self.olho = np.asarray(olho, float)
        fwd = unit(np.asarray(alvo, float) - self.olho)
        dir_ = unit(np.cross(fwd, [0, 1, 0]))
        cima = np.cross(dir_, fwd)
        self.R = np.stack([dir_, cima, fwd])
        self.W, self.H, self.f = W, H, f
        self.cx, self.cy = W / 2, H / 2

    def projetar(self, P):
        pc = (P - self.olho) @ self.R.T
        z = pc[:, 2]
        sx = self.cx + self.f * pc[:, 0] / z
        sy = self.cy - self.f * pc[:, 1] / z
        return sx, sy, z


def passe(cam, V, N, F, M, sel_mats, mais_longe=False):
    W, H = cam.W, cam.H
    sx, sy, z = cam.projetar(V)
    attr = np.concatenate([N, V], 1)
    zbuf = np.full((H, W), np.inf)
    abuf = np.zeros((H, W, 6))
    mbuf = np.full((H, W), -1, np.int64)
    sel = np.isin(M, sel_mats)
    sinal = -1.0 if mais_longe else 1.0
    rasterizar(sx, sy, 1.0 / z, attr, F.astype(np.int64), sel, W, H, zbuf, abuf, mbuf,
               M.astype(np.int64), sinal)
    return zbuf * sinal, abuf, mbuf


# --------------------------------------------------------------------------- sombreamento

LUZES = [  # direção (para a luz), intensidade
    (unit([-0.55, 0.75, 0.55]), 0.95),
    (unit([0.75, 0.15, 0.55]), 0.35),
    (unit([0.15, 0.45, -0.9]), 0.45),
    (unit([0.0, 0.1, 1.0]), 0.45),
]


def fundo(H, W):
    t = np.linspace(0, 1, H)[:, None, None]
    topo, base = np.array([0.965, 0.972, 0.985]), np.array([0.83, 0.86, 0.90])
    return np.broadcast_to(topo * (1 - t) + base * t, (H, W, 3)).copy()


def ambiente(R):
    """Ambiente falso para reflexos: céu claro em cima, chão escuro embaixo."""
    y = R[..., 1:2]
    ceu = np.array([0.98, 0.99, 1.0]) * (0.75 + 0.25 * np.clip(y, 0, 1))
    chao = np.array([0.30, 0.31, 0.33])
    k = np.clip(y * 6 + 0.5, 0, 1)
    return ceu * k + chao * (1 - k)


def sombrear(cam, abuf, mbuf, cor_atras):
    N = unit(abuf[..., :3] + 1e-12)
    P = abuf[..., 3:]
    Vv = unit(cam.olho - P)
    vira = (N * Vv).sum(-1, keepdims=True) < 0
    N = np.where(vira, -N, N)
    ndv = np.clip((N * Vv).sum(-1, keepdims=True), 0, 1)
    R = 2 * ndv * N - Vv
    out = cor_atras.copy()
    ceu = np.array([0.80, 0.84, 0.92])
    chao = np.array([0.42, 0.40, 0.38])
    amb = (ceu * (0.5 + 0.5 * N[..., 1:2]) + chao * (0.5 - 0.5 * N[..., 1:2])) * 0.38
    dif = np.zeros_like(N)
    spec = np.zeros_like(N[..., :1])
    for L, I in LUZES:
        ndl = np.clip(N @ L, 0, 1)[..., None]
        dif += ndl * I
        Hh = unit(L + Vv)
        spec += np.clip((N * Hh).sum(-1, keepdims=True), 0, 1) ** 60 * I
    fres = 0.04 + 0.96 * (1 - ndv) ** 5

    m = mbuf == PLA
    base = COR[PLA]
    c = base * (amb + dif * 0.85) + spec * 0.45 + fres * ambiente(R) * 0.25
    out[m] = c[m]
    m = mbuf == ESCURO
    out[m] = (COR[ESCURO] * (amb + dif))[m]
    m = mbuf == PET
    # garrafa: transmissão com tingimento (duas paredes) + reflexo de Fresnel
    trans = np.clip(0.90 - 0.62 * (1 - ndv) ** 2.2, 0.15, 1)
    tint = COR[PET]
    refl = ambiente(R) * (0.06 + 0.94 * fres) + spec * 0.75
    leve = tint * (amb + dif * 0.5) * 0.08
    c = cor_atras * (tint * 0.25 + 0.75) * trans + refl * (1 - trans) * 0.85 + leve
    out[m] = c[m]
    return out


def suavizar(img, r):
    """Desfoque de caixa separável (3 passes ~ gaussiano)."""
    for _ in range(3):
        for eixo in (0, 1):
            c = np.cumsum(np.pad(img, [(r + 1, r) if i == eixo else (0, 0) for i in range(img.ndim)],
                                 mode="edge"), axis=eixo)
            sl_hi = [slice(None)] * img.ndim
            sl_lo = [slice(None)] * img.ndim
            sl_hi[eixo] = slice(2 * r + 1, None)
            sl_lo[eixo] = slice(None, -(2 * r + 1))
            img = (c[tuple(sl_hi)] - c[tuple(sl_lo)]) / (2 * r + 1)
    return img


# --------------------------------------------------------------------------- cena

def renderizar(fog, W=1600, H=900, ss=2):
    V0, N0, F, M = montar(fog, roll=ROLL)
    # pose: ponta para cima/direita, levemente afastando do observador
    d = unit([1.0, 0.47, -0.24])
    e1 = unit(np.cross(d, [0, 1, 0]))
    e2 = np.cross(e1, d)
    L = fog.comprimento
    to_w = np.stack([-d, e2, e1], 1)  # colunas: eixo x local -> -d (cauda), y -> e2, z -> e1
    V = (V0 - [L / 2, 0, 0]) @ to_w.T
    N = N0 @ to_w.T
    Ws, Hs = W * ss, H * ss
    cam = Camera([-60, 260, 1150], [10, -5, 0], Ws, Hs, f=1.0)
    sx, sy, z = cam.projetar(V)
    # enquadra: escala focal para ocupar ~62% da largura
    larg = (sx.max() - sx.min())
    cam.f = 0.60 * Ws / larg
    sx, sy, z = cam.projetar(V)
    cam.cx += Ws * 0.5 - (sx.min() + sx.max()) / 2 - 0.02 * Ws
    cam.cy += Hs * 0.5 - (sy.min() + sy.max()) / 2 + 0.02 * Hs

    img = fundo(Hs, Ws)
    # sombra suave num "chão" abaixo do foguete
    y_chao = V[:, 1].min() - 25
    Vs = V.copy()
    Vs[:, 1] = y_chao
    zs, _, ms = passe(cam, Vs, N, F, M, [PLA, PET, ESCURO])
    sombra = suavizar((ms >= 0).astype(float), int(18 * ss))
    img *= (1 - 0.16 * sombra)[..., None]

    z_op, a_op, m_op = passe(cam, V, N, F, M, [PLA, ESCURO])
    cor = sombrear(cam, a_op, m_op, img)
    z_tras, a_tras, m_tras = passe(cam, V, N, F, M, [PET], mais_longe=True)
    m_tras = np.where(z_tras < z_op, m_tras, -1)
    cor = sombrear(cam, a_tras, m_tras, cor)
    z_pet, a_pet, m_pet = passe(cam, V, N, F, M, [PET])
    m_pet = np.where((z_pet < z_op) & (z_pet < z_tras - 0.5), m_pet, -1)
    cor = sombrear(cam, a_pet, m_pet, cor)
    # contorno leve da silhueta
    obj = (m_op >= 0) | (m_pet >= 0) | (m_tras >= 0)
    borda = np.zeros_like(obj)
    borda[1:-1, 1:-1] = obj[1:-1, 1:-1] & ~(obj[:-2, 1:-1] & obj[2:, 1:-1] & obj[1:-1, :-2] & obj[1:-1, 2:])
    borda = suavizar(borda.astype(float), 1) > 0.15
    cor[borda] = cor[borda] * 0.45 + np.array([0.15, 0.17, 0.2]) * 0.55
    cor = np.clip(cor, 0, 1)
    cor = cor.reshape(H, ss, W, ss, 3).mean((1, 3))

    def ponto(x_axial, r=0.0, phi=0.0):
        p = np.array([[x_axial, r * math.cos(phi), r * math.sin(phi)]])
        pw = (p - [L / 2, 0, 0]) @ to_w.T
        a, b, _ = cam.projetar(pw)
        return a[0] / ss, b[0] / ss

    return cor, ponto


def main():
    ork = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "rocket.ork")
    fog = Foguete(ork)
    W, H = 2000, 1125
    img, ponto = renderizar(fog, W, H, ss=2)

    fig = plt.figure(figsize=(W / 200, H / 200), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(img, extent=(0, W, H, 0))
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    escuro = "#1d2733"

    def chamada(p, txt, xt, yt, ha):
        ax.annotate(txt, xy=p, xytext=(xt, yt), ha=ha, va="center", fontsize=10.5, color=escuro,
                    family="DejaVu Sans", linespacing=1.35,
                    arrowprops=dict(arrowstyle="-", color=escuro, lw=0.9, shrinkA=4, shrinkB=0))
        ax.plot(*p, "o", ms=3.2, color=escuro)

    a = fog.aletas[0]
    chamada(ponto(70, 30, 2.2), "Ogiva — PLA (impressa em 3D)\nogiva tangente, 175 mm",
            1500, 140, "left")
    chamada(ponto(300, 46.5, 2.0), "Corpo — garrafa PET\nØ 95 mm, parede 1 mm", 1520, 520, "left")
    chamada(ponto(480, 14.0, 1.6), "Bocal — gargalo da garrafa\nØ 28 mm (rosca padrão)", 130, 960, "left")
    texto_aleta = np.array([250.0, 600.0])
    p_aleta = min((ponto(a.x_ba + 70, a.r_ba + 25, math.radians(ROLL + a.angulo0) + k * 2 * math.pi / a.n)
                   for k in range(a.n)), key=lambda p: np.hypot(*(np.array(p) - texto_aleta)))
    chamada(p_aleta,
            f"{a.n} aletas — PLA {fmt(a.espessura)} mm\nenvergadura {fmt(fog.envergadura(), 1)} mm",
            90, 780, "left")

    ax.text(70, 85, f"Foguete PET — {fog.nome}", fontsize=21, weight="bold", color=escuro,
            family="DejaVu Sans", va="center")
    ax.text(70, 140, "Imagem ilustrativa gerada do projeto OpenRocket (rocket.ork)",
            fontsize=11, color="#4a5664", family="DejaVu Sans", va="center")
    massas = sum(m.massa_g for m in fog.massas)
    ficha = (f"Comprimento total   {fog.comprimento:.0f} mm\n"
             f"Diâmetro máximo     {2 * fog.raio_max:.0f} mm\n"
             f"Envergadura aletas  {fog.envergadura():.1f} mm\n".replace(".", ",") +
             f"Massas internas     {massas:.0f} g (M1+M2+M3)")
    ax.text(70, 250, ficha, fontsize=10.5, color=escuro, family="DejaVu Sans Mono", va="top",
            linespacing=1.6, bbox=dict(boxstyle="round,pad=0.7", fc="white", ec="#c5cdd6", lw=0.8))
    fig.savefig(os.path.join(AQUI, "foguete_ilustracao.png"), dpi=200)
    print("Gerado: foguete_ilustracao.png")


if __name__ == "__main__":
    main()
