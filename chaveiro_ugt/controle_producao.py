#!/usr/bin/env python3
"""Ficha de controle de produção em papel (A4) para o pedido de chaveiros UGT.

Cada linha é uma mesa já numerada, com o total acumulado impresso: quem tira a
mesa da impressora só marca o X, anota dia, hora, impressora e defeitos.
Na primeira folha há uma barra de 100 em 100 para pintar.

Uso: python3 controle_producao.py [--meta 2000] [--por-mesa 21] [--impressoras 1] [--extras 8]
"""
import argparse
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle

AQUI = os.path.dirname(os.path.abspath(__file__))
MM = 72.0 / 25.4
LARG, ALT = 210.0, 297.0
MARGEM = 12.0
LINHA = 7.2                      # altura da linha (espaço para escrever à mão)
CAB_TABELA = 9.0                 # altura do cabeçalho da tabela
RODAPE = MARGEM + 10             # a tabela não desce abaixo disto (rodapé da folha)
VERMELHO = "#c8221c"
CINZA_FORTE = "#d9d9d9"
CINZA_LEVE = "#f0f0f0"
FONTE = "DejaVu Sans"

# (título, largura em mm) — com 2 impressoras; com 1, a coluna "Impressora" sai
COLUNAS_2 = [("Mesa", 14), ("Feito", 15), ("Total de\nchaveiros", 25), ("Dia", 22), ("Hora", 20),
             ("Impressora", 22), ("Defeito", 18), ("Quem fez", 50)]
COLUNAS_1 = [("Mesa", 14), ("Feito", 15), ("Total de\nchaveiros", 25), ("Dia", 26), ("Hora", 24),
             ("Defeito", 22), ("Quem fez", 60)]
COLUNAS = COLUNAS_2


def pt(mm_altura):
    """Altura de texto em mm -> pontos."""
    return mm_altura / 0.72 * MM


class Pagina:
    def __init__(self, pdf):
        self.pdf = pdf
        self.fig = plt.figure(figsize=(LARG / 25.4, ALT / 25.4))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, LARG)
        self.ax.set_ylim(0, ALT)
        self.ax.axis("off")

    def ret(self, x, y, w, h, fc="none", ec="#000", lw=0.25, z=1):
        self.ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw * MM, zorder=z))

    def txt(self, x, y, s, h=3.0, cor="#000", peso="normal", ha="left", va="center", **kw):
        self.ax.text(x, y, s, fontsize=pt(h), color=cor, fontweight=peso, ha=ha, va=va,
                     family=FONTE, zorder=5, **kw)

    def fechar(self):
        self.pdf.savefig(self.fig)
        return self.fig


def cabecalho_tabela(p, y_topo):
    x = MARGEM
    h = CAB_TABELA
    p.ret(MARGEM, y_topo - h, LARG - 2 * MARGEM, h, fc=CINZA_FORTE, lw=0.35)
    for nome, w in COLUNAS:
        p.txt(x + w / 2, y_topo - h / 2, nome, h=2.4, peso="bold", ha="center", linespacing=1.0)
        p.ax.plot([x, x], [y_topo, y_topo - h], color="#000", lw=0.25 * MM, zorder=2)
        x += w
    return y_topo - h


def linha_mesa(p, y, mesa, total, marco, extra=False):
    """Uma linha da tabela. marco = texto de destaque (ou None)."""
    fundo = CINZA_LEVE if marco else "none"
    p.ret(MARGEM, y - LINHA, LARG - 2 * MARGEM, LINHA, fc=fundo, lw=0.25)
    x = MARGEM
    meio = y - LINHA / 2
    for i, (nome, w) in enumerate(COLUNAS):
        if i:
            p.ax.plot([x, x], [y, y - LINHA], color="#000", lw=0.2 * MM, zorder=2)
        if nome == "Mesa":
            p.txt(x + w / 2, meio, "" if extra else str(mesa), h=3.0, peso="bold", ha="center")
        elif nome == "Feito":
            p.ret(x + w / 2 - 2.6, meio - 2.6, 5.2, 5.2, lw=0.45, z=3)
        elif nome.startswith("Total"):
            if extra:
                p.txt(x + w / 2, meio, "+ ____", h=2.8, ha="center", cor="#555")
            else:
                cor = VERMELHO if marco and marco[1] else "#000"
                p.txt(x + w / 2, meio, f"{total:,}".replace(",", "."), h=3.4, peso="bold", ha="center", cor=cor)
        elif nome == "Dia":
            p.txt(x + w / 2, meio - 0.8, "____/____", h=2.4, ha="center", cor="#888")
        elif nome == "Hora":
            p.txt(x + w / 2, meio - 0.8, "___:___", h=2.4, ha="center", cor="#888")
        elif nome == "Impressora":
            p.txt(x + w / 2, meio, "1      2", h=2.8, ha="center", cor="#555")
        x += w
    if marco:  # etiqueta do marco, à direita, dentro da coluna "Quem fez"
        texto, forte = marco
        p.txt(LARG - MARGEM - 1.5, y - LINHA / 2, texto, h=1.9, ha="right",
              cor=VERMELHO if forte else "#444", peso="bold")
    return y - LINHA


def rodape(p, folha, total_folhas, ultima_mesa_folha):
    y = MARGEM + 4
    p.txt(MARGEM, y, "Defeitos nesta folha: ________     Conferido por: ____________________", h=2.8)
    p.txt(LARG - MARGEM, y, f"Folha {folha} de {total_folhas}", h=2.6, ha="right", cor="#444")


def gerar(meta=2000, por_mesa=21, extras=8, impressoras=1):
    global COLUNAS
    COLUNAS = COLUNAS_1 if impressoras == 1 else COLUNAS_2
    mesas = math.ceil(meta / por_mesa)
    totais = [min(meta, por_mesa * (i + 1)) for i in range(mesas)]
    # marcos: a cada 100 (pintar a barra); 500, 1000, 1500 e a meta em destaque
    marcos = {}
    anterior = 0
    for i, t in enumerate(totais):
        for m in range((anterior // 100 + 1) * 100, t + 1, 100):
            forte = m % 500 == 0 or m == meta
            ultima = meta - por_mesa * (mesas - 1)
            fim = f"FIM! Só {ultima} peças nesta mesa" if ultima < por_mesa else "FIM! Pedido completo"
            texto = fim if m == meta else (f"Passou de {m:,}".replace(",", ".") +
                                                              " · pinte a barra")
            marcos[i] = (texto, forte)
        anterior = t

    caminho = os.path.join(AQUI, "controle_producao.pdf")
    paginas_png = []
    with PdfPages(caminho) as pdf:
        # quantas linhas cabem entre o cabeçalho da tabela e o rodapé
        y_tab_1 = 175.0                  # folha 1: abaixo das instruções e da barra
        y_tab_n = ALT - MARGEM - 9       # demais folhas: abaixo do título "continuação"
        cap1 = int((y_tab_1 - CAB_TABELA - RODAPE) // LINHA)
        capn = int((y_tab_n - CAB_TABELA - RODAPE) // LINHA)
        linhas = [("mesa", i) for i in range(mesas)] + [("titulo_extra", None)] + [("extra", None)] * extras
        folhas = []
        resto = linhas[:]
        folhas.append(resto[:cap1]); resto = resto[cap1:]
        while resto:
            folhas.append(resto[:capn]); resto = resto[capn:]

        for n, conteudo in enumerate(folhas, 1):
            p = Pagina(pdf)
            if n == 1:
                y = ALT - MARGEM
                p.txt(MARGEM, y - 5, "CONTROLE DE PRODUÇÃO", h=5.2, peso="bold")
                p.txt(MARGEM, y - 13, "Chaveiros UGT", h=4.6, peso="bold", cor=VERMELHO)
                p.txt(LARG - MARGEM, y - 13, f"Meta: {meta:,} chaveiros".replace(",", "."), h=4.0,
                      peso="bold", ha="right")
                maq = "1 impressora" if impressoras == 1 else f"{impressoras} impressoras"
                p.txt(LARG - MARGEM, y - 21, f"{por_mesa} por mesa · {mesas} mesas · {maq}", h=2.6, ha="right",
                      cor="#444")
                p.txt(MARGEM, y - 21, "Início: ____/____/______    Entrega: ____/____/______", h=2.8)
                # instruções
                y0 = y - 27
                p.ret(MARGEM, y0 - 49, LARG - 2 * MARGEM, 49, fc="none", lw=0.5)
                p.txt(MARGEM + 4, y0 - 5, "COMO PREENCHER", h=3.4, peso="bold", cor=VERMELHO)
                passos = [
                    "Tirou uma mesa pronta da impressora? Marque um X no quadrado da próxima mesa.",
                    "Escreva o dia e a hora." if impressoras == 1 else
                    "Escreva o dia, a hora e faça um círculo na impressora (1 ou 2).",
                    "Se alguma peça saiu com defeito, escreva quantas na coluna Defeito.",
                    "O número em Total mostra quantos chaveiros já foram feitos até aquela mesa.",
                    "Quando a linha cinza disser \"pinte a barra\", pinte o próximo quadrado abaixo.",
                ]
                for k, s in enumerate(passos):
                    yy = y0 - 12.5 - k * 7.4
                    p.ax.add_patch(plt.Circle((MARGEM + 7, yy), 2.6, fc="#000", ec="none", zorder=4))
                    p.txt(MARGEM + 7, yy, str(k + 1), h=2.6, peso="bold", ha="center", cor="#fff")
                    p.txt(MARGEM + 12, yy, s, h=2.9)
                # barra de 100 em 100
                yb = y0 - 49 - 8
                p.txt(MARGEM, yb, "BARRA DE PROGRESSO — pinte um quadrado a cada 100 chaveiros", h=3.0, peso="bold")
                nq = meta // 100
                w = (LARG - 2 * MARGEM) / nq
                for k in range(nq):
                    xq = MARGEM + k * w
                    forte = (k + 1) * 100 % 500 == 0
                    p.ret(xq, yb - 14, w, 10, lw=0.6 if forte else 0.35)
                    p.txt(xq + w / 2, yb - 17, f"{(k + 1) * 100}", h=1.9 if (k + 1) * 100 < 1000 else 1.75,
                          ha="center", cor=VERMELHO if forte else "#444", peso="bold" if forte else "normal")
                y = cabecalho_tabela(p, y_tab_1)
            else:
                p.txt(MARGEM, ALT - MARGEM - 3, "CONTROLE DE PRODUÇÃO — Chaveiros UGT (continuação)", h=3.4, peso="bold")
                y = cabecalho_tabela(p, y_tab_n)
            for tipo, i in conteudo:
                if tipo == "mesa":
                    y = linha_mesa(p, y, i + 1, totais[i], marcos.get(i))
                elif tipo == "titulo_extra":
                    p.ret(MARGEM, y - LINHA, LARG - 2 * MARGEM, LINHA, fc=CINZA_FORTE, lw=0.35)
                    p.txt(MARGEM + 3, y - LINHA / 2, "MESAS EXTRAS — para repor peças com defeito "
                          "(escreva quantas peças boas saíram)", h=2.7, peso="bold")
                    y -= LINHA
                else:
                    y = linha_mesa(p, y, None, None, None, extra=True)
            if n == len(folhas) and y - (MARGEM + 12) > 30:  # sobra da última folha: anotações
                y -= 8
                p.txt(MARGEM, y, "ANOTAÇÕES — troca de rolo, peça que falhou, bico entupido, manutenção", h=3.0,
                      peso="bold")
                y -= 4
                p.ret(MARGEM, MARGEM + 10, LARG - 2 * MARGEM, y - (MARGEM + 10), lw=0.4)
                yl = y - 8
                while yl > MARGEM + 14:
                    p.ax.plot([MARGEM + 4, LARG - MARGEM - 4], [yl, yl], color="#bbb", lw=0.2 * MM, zorder=2)
                    yl -= 8
            rodape(p, n, len(folhas), None)
            fig = p.fechar()
            png = os.path.join(AQUI, f"controle_producao_folha{n}.png")
            fig.savefig(png, dpi=110)  # prévia (não versionada)
            paginas_png.append(png)
            plt.close(fig)
    return caminho, paginas_png, mesas, len(folhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", type=int, default=2000)
    ap.add_argument("--por-mesa", type=int, default=21)
    ap.add_argument("--extras", type=int, default=8)
    ap.add_argument("--impressoras", type=int, default=1, choices=(1, 2))
    a = ap.parse_args()
    caminho, pngs, mesas, folhas = gerar(a.meta, a.por_mesa, a.extras, a.impressoras)
    print(f"Gerado: {os.path.basename(caminho)} — {mesas} mesas em {folhas} folhas A4")


if __name__ == "__main__":
    main()
