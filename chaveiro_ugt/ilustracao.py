#!/usr/bin/env python3
"""Imagem ilustrativa do chaveiro (frente e verso) a partir da mesma geometria do 3MF.

Reaproveita o rasterizador com z-buffer de ../foguete_pet/render.py.
"""
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "foguete_pet"))
from render import Camera, rasterizar, suavizar, unit  # noqa: E402

import chaveiro as ch  # noqa: E402

PRETO, VERMELHO, BRANCO, METAL = 0, 1, 2, 3
MATERIAL = {  # cor base, especular, brilho
    PRETO: (np.array([0.055, 0.055, 0.06]), 0.22, 28),
    VERMELHO: (np.array([0.78, 0.07, 0.05]), 0.28, 34),
    BRANCO: (np.array([0.90, 0.90, 0.88]), 0.20, 30),
    METAL: (np.array([0.72, 0.73, 0.76]), 1.10, 90),
}
LUZES = [(unit([-0.45, 0.70, 0.55]), 1.00), (unit([0.70, 0.20, 0.45]), 0.35),
         (unit([0.0, 0.15, 1.0]), 0.30)]


def rot(eixo, graus):
    a = math.radians(graus)
    c, s = math.cos(a), math.sin(a)
    if eixo == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if eixo == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def facetada(m):
    """Vértices por face com a normal da face (relevo com quinas vivas)."""
    V = m.vertices[m.faces].reshape(-1, 3)
    N = np.repeat(m.face_normals, 3, axis=0)
    return V, N, np.arange(len(V)).reshape(-1, 3)


def argola(centro, R=11.0, r=0.85, n=160, k=24):
    """Argola (toro) no plano YZ do chaveiro, passando pelo furo."""
    u = np.linspace(0, 2 * np.pi, n + 1)
    v = np.linspace(0, 2 * np.pi, k + 1)
    U, Vv = np.meshgrid(u, v, indexing="ij")
    cy, cz = centro[1] + R, centro[2]
    eixo = np.stack([np.zeros_like(U), cy - R * np.cos(U), cz + R * np.sin(U)], -1)
    radial = np.stack([np.zeros_like(U), -np.cos(U), np.sin(U)], -1)
    N = np.cos(Vv)[..., None] * radial + np.sin(Vv)[..., None] * np.array([1.0, 0, 0])
    P = eixo + r * N
    idx = np.arange((n + 1) * (k + 1)).reshape(n + 1, k + 1)
    a, b = idx[:-1, :-1].ravel(), idx[1:, :-1].ravel()
    c, d = idx[1:, 1:].ravel(), idx[:-1, 1:].ravel()
    F = np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])
    return P.reshape(-1, 3), N.reshape(-1, 3), F


def cena(partes, furo_c):
    """Dois chaveiros: frente (esquerda) e verso (direita), cada um com argola."""
    tudo = np.concatenate([m.vertices for m in partes.values()])
    centro = (tudo.min(0) + tudo.max(0)) / 2
    pecas = []
    for nome, mat in (("preto", PRETO), ("vermelho", VERMELHO), ("branco", BRANCO)):
        V, N, F = facetada(partes[nome])
        pecas.append((V, N, F, mat))
    pecas.append((*argola(np.array([furo_c[0], furo_c[1], centro[2]])), METAL))

    poses = [  # (rotação, deslocamento) — frente e verso
        (rot("y", 24) @ rot("x", -12), np.array([-31.0, -2.0, 0.0])),
        (rot("y", 180 - 24) @ rot("x", 12), np.array([31.0, -2.0, 0.0])),
    ]
    Vs, Ns, Ms, Fs, Ls, NLs = [], [], [], [], [], []
    off = 0
    for R, t in poses:
        for V, N, F, mat in pecas:
            Vs.append((V - centro) @ R.T + t)
            Ns.append(N @ R.T)
            Ls.append(V)  # coordenadas do modelo (para as linhas de camada)
            NLs.append(N[:, 2:3])  # normal z do modelo: lateral x topo
            Fs.append(F + off)
            Ms.append(np.full(len(F), mat))
            off += len(V)
    return (np.concatenate(Vs), np.concatenate(Ns), np.concatenate(Fs), np.concatenate(Ms),
            np.concatenate([np.concatenate(Ls), np.concatenate(NLs)], 1))


def passe(cam, V, N, L, F, M):
    sx, sy, z = cam.projetar(V)
    attr = np.concatenate([N, V, L], 1)
    zbuf = np.full((cam.H, cam.W), np.inf)
    abuf = np.zeros((cam.H, cam.W, 10))
    mbuf = np.full((cam.H, cam.W), -1, np.int64)
    rasterizar(sx, sy, 1.0 / z, attr, F.astype(np.int64), np.ones(len(F), bool),
               cam.W, cam.H, zbuf, abuf, mbuf, M.astype(np.int64), 1.0)
    return zbuf, abuf, mbuf


def sombrear(cam, abuf, mbuf, fundo):
    N = unit(abuf[..., :3] + 1e-12)
    P, L = abuf[..., 3:6], abuf[..., 6:9]
    nz_modelo = abuf[..., 9:10]
    Vv = unit(cam.olho - P)
    N = np.where((N * Vv).sum(-1, keepdims=True) < 0, -N, N)
    ndv = np.clip((N * Vv).sum(-1, keepdims=True), 0, 1)
    R = 2 * ndv * N - Vv
    amb = 0.30 + 0.12 * N[..., 1:2]
    out = fundo.copy()
    for mat, (cor, ks, brilho) in MATERIAL.items():
        m = mbuf == mat
        if not m.any():
            continue
        dif = np.zeros_like(N[..., :1])
        spec = np.zeros_like(N[..., :1])
        for Ld, I in LUZES:
            dif += np.clip(N @ Ld, 0, 1)[..., None] * I
            Hh = unit(Ld + Vv)
            spec += np.clip((N * Hh).sum(-1, keepdims=True), 0, 1) ** brilho * I
        fres = 0.04 + 0.96 * (1 - ndv) ** 5
        ceu = 0.55 + 0.45 * np.clip(R[..., 1:2], -1, 1)
        if mat == METAL:
            c = cor * (0.25 + 0.55 * ceu) + spec * ks + 0.15 * dif * cor
        else:
            c = cor * (amb + dif * 0.85) + spec * ks + fres * ceu * 0.12
            # textura de impressão FDM: linhas de camada nas laterais, riscas no topo
            camada = 1 - 0.07 * (0.5 + 0.5 * np.cos(2 * np.pi * L[..., 2:3] / 0.2))
            topo = 1 - 0.05 * (0.5 + 0.5 * np.cos(2 * np.pi * (L[..., 0:1] + L[..., 1:2]) / 0.6))
            lateral = np.abs(nz_modelo) < 0.5
            c = c * np.where(lateral, camada, topo)
        out[m] = c[m]
    return out


def main():
    partes, geo = ch.montar(ch.QR_PADRAO)
    furo = geo["furo"].centroid
    V, N, F, M, L = cena(partes, (furo.x, furo.y))

    W, H, ss = 1800, 1050, 2
    cam = Camera([0, 18, 230], [0, 2, 0], W * ss, H * ss, f=1.0)
    sx, sy, _ = cam.projetar(V)
    cam.f = min(0.70 * W * ss / (sx.max() - sx.min()), 0.66 * H * ss / (sy.max() - sy.min()))
    sx, sy, _ = cam.projetar(V)
    cam.cx += W * ss * 0.5 - (sx.min() + sx.max()) / 2
    cam.cy += H * ss * 0.51 - (sy.min() + sy.max()) / 2
    sx, sy, _ = cam.projetar(V)
    base_pecas = sy.max() / ss  # para as legendas ficarem logo abaixo das peças
    meio = len(V) // 2  # primeira metade dos vértices = chaveiro da frente
    centros = [sx[:meio].mean() / ss, sx[meio:].mean() / ss]

    t = np.linspace(0, 1, H * ss)[:, None, None]
    fundo = np.broadcast_to(np.array([0.80, 0.81, 0.82]) * (1 - t) + np.array([0.64, 0.65, 0.67]) * t,
                            (H * ss, W * ss, 3)).copy()
    z, a, m = passe(cam, V, N, L, F, M)
    # sombra suave projetada no fundo, deslocada para baixo/direita
    obj = (m >= 0).astype(float)
    dy, dx = int(22 * ss), int(16 * ss)
    desl = np.zeros_like(obj)
    desl[dy:, dx:] = obj[:-dy, :-dx]  # desloca sem dar a volta na imagem
    fundo *= (1 - 0.35 * suavizar(desl, int(16 * ss)))[..., None]
    img = sombrear(cam, a, m, fundo)
    img = np.clip(img, 0, 1).reshape(H, ss, W, ss, 3).mean((1, 3))

    fig = plt.figure(figsize=(W / 200, H / 200), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(img)
    ax.axis("off")
    escuro = "#1d2733"
    ax.text(60, 70, "Chaveiro UGT — impressão 3D em 3 cores", fontsize=18, weight="bold",
            color=escuro, family="DejaVu Sans", va="center")
    ax.text(60, 118, "Imagem ilustrativa gerada do arquivo de impressão (chaveiro_ugt.3mf)",
            fontsize=10.5, color="#3a4654", family="DejaVu Sans", va="center")
    for x, t1, t2 in ((centros[0], "FRENTE", "logo e nome em alto-relevo (0,8 mm)"),
                      (centros[1], "VERSO", "QR Code em relevo (0,8 mm) · ugt.org.br")):
        ax.text(x, base_pecas + 50, t1, fontsize=13, weight="bold", color=escuro, ha="center",
                family="DejaVu Sans")
        ax.text(x, base_pecas + 90, t2, fontsize=10.5, color=escuro, ha="center",
                family="DejaVu Sans")
    ax.text(W - 60, H - 30, "Ø 50 mm · espessura 3,8 mm · PLA preto, vermelho e branco",
            fontsize=9.5, color="#3a4654", ha="right", family="DejaVu Sans")
    fig.savefig(os.path.join(AQUI, "chaveiro_ilustracao.png"), dpi=200)
    print("Gerado: chaveiro_ilustracao.png")


if __name__ == "__main__":
    main()
