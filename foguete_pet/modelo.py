"""Leitura do projeto OpenRocket (.ork) e geometria do foguete em milímetros.

O OpenRocket grava tudo em unidades SI (metros, kg, kg/m³). Aqui tudo é
convertido para mm, g e g/cm³, e as formas das transições seguem as mesmas
equações do OpenRocket (Transition.Shape), para o perfil bater com o programa.
"""
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import numpy as np

M_PARA_MM = 1000.0


def numero(texto):
    """'auto 0.0475' ou '0.0475' -> 0.0475"""
    partes = texto.split()
    return float(partes[-1])


# --------------------------------------------------------------------------- formas

def raio_forma(forma, x, R, L, k):
    """Raio de um 'nariz' de raio de base R e comprimento L, a distância x da ponta."""
    x = np.clip(x, 0.0, L)
    if forma == "conical":
        return R * x / L
    if forma == "ogive":
        if L < R:  # OpenRocket escala quando o comprimento é menor que o raio
            x = x * R / L
            L = R
        if k < 0.001:
            return R * x / L
        rho = math.sqrt((L**2 + R**2) * (((2 - k) * L) ** 2 + (k * R) ** 2) / (4 * (k * R) ** 2))
        Lk = L / k
        y0 = math.sqrt(rho**2 - Lk**2)
        return np.sqrt(np.maximum(rho**2 - (Lk - x) ** 2, 0.0)) - y0
    if forma == "parabolic":
        t = x / L
        return R * (2 * t - k * t**2) / (2 - k)
    if forma == "power":
        if k <= 1e-5:
            return np.where(x <= 1e-5, 0.0, R)
        return R * (x / L) ** k
    if forma == "ellipsoid":
        xx = x * R / L
        return np.sqrt(np.maximum(2 * R * xx - xx**2, 0.0))
    raise ValueError(f"forma não suportada: {forma}")


FORMAS_PT = {
    "conical": "cônica",
    "ogive": "ogiva",
    "parabolic": "parabólica",
    "power": "potência",
    "ellipsoid": "elipsoide",
    None: "cilindro",
}


@dataclass
class Material:
    nome: str
    densidade: float  # g/cm³


@dataclass
class Massa:
    nome: str
    pai: "Componente"
    x0: float          # mm, a partir da ponta da ogiva
    comprimento: float
    raio: float
    massa_g: float
    bruto: dict


@dataclass
class Aletas:
    nome: str
    pai: "Componente"
    n: int
    espessura: float
    secao: str
    material: Material
    pontos: np.ndarray        # (x, y) mm, origem no bordo de ataque da raiz
    x_ba: float               # posição axial do bordo de ataque da raiz (mm da ponta)
    r_ba: float               # raio do corpo no bordo de ataque
    angulo0: float            # graus
    bruto: dict


@dataclass
class Componente:
    item: int
    tipo: str          # nosecone / transition / bodytube
    nome: str
    estagio: str
    comprimento: float
    r_diant: float
    r_tras: float
    espessura: float
    forma: str | None
    k: float
    cortada: bool
    material: Material
    x0: float = 0.0
    bruto: dict = field(default_factory=dict)

    @property
    def x1(self):
        return self.x0 + self.comprimento

    def raio(self, x_local):
        """Raio externo a x_local mm do início do componente."""
        L = self.comprimento
        r1, r2 = self.r_diant, self.r_tras
        if self.forma is None or abs(r1 - r2) < 1e-12:
            return np.full_like(np.asarray(x_local, float), r1)
        x = np.asarray(x_local, float)
        if r1 > r2:
            x = L - x
            r1, r2 = r2, r1
        if self.cortada and self.forma == "power":
            c = self._clip(r1, r2)
            return raio_forma(self.forma, c + x, r2, c + L, self.k)
        return r1 + raio_forma(self.forma, x, r2 - r1, L, self.k)

    def _clip(self, r1, r2):
        L = self.comprimento
        lo, hi = 0.0, 1e4
        for _ in range(200):
            c = (lo + hi) / 2
            if raio_forma(self.forma, c, r2, c + L, self.k) > r1:
                hi = c
            else:
                lo = c
        return (lo + hi) / 2

    def perfil(self, n=240):
        if self.forma is None or self.forma == "conical":
            xs = np.array([0.0, self.comprimento])
        else:
            # mais pontos perto da ponta da ogiva
            t = np.linspace(0, 1, n)
            xs = self.comprimento * (t**1.6 if self.tipo == "nosecone" else t)
        return self.x0 + xs, self.raio(xs)


def _material(el):
    m = el.find("material")
    return Material(m.text.strip(), float(m.get("density")) / 1000.0)


def _bruto(el):
    return {c.tag: (c.text or "").strip() for c in el if len(c) == 0}


class Foguete:
    def __init__(self, caminho):
        raiz = ET.parse(caminho).getroot().find("rocket")
        self.nome = raiz.findtext("name")
        self.componentes: list[Componente] = []
        self.massas: list[Massa] = []
        self.aletas: list[Aletas] = []
        self.estagios = []
        x = 0.0
        item = 0
        for estagio in raiz.find("subcomponents").findall("stage"):
            nome_est = estagio.findtext("name")
            n_comp = 0
            subs = estagio.find("subcomponents")
            for el in (list(subs) if subs is not None else []):
                if el.tag not in ("nosecone", "transition", "bodytube"):
                    continue
                item += 1
                n_comp += 1
                L = numero(el.findtext("length")) * M_PARA_MM
                if el.tag == "bodytube":
                    r1 = r2 = numero(el.findtext("radius")) * M_PARA_MM
                    forma, k = None, 0.0
                else:
                    r1 = 0.0 if el.tag == "nosecone" else numero(el.findtext("foreradius")) * M_PARA_MM
                    r2 = numero(el.findtext("aftradius")) * M_PARA_MM
                    forma = el.findtext("shape")
                    k = float(el.findtext("shapeparameter") or 0.0)
                c = Componente(
                    item=item, tipo=el.tag, nome=el.findtext("name"), estagio=nome_est,
                    comprimento=L, r_diant=r1, r_tras=r2,
                    espessura=numero(el.findtext("thickness")) * M_PARA_MM,
                    forma=forma, k=k, cortada=(el.findtext("shapeclipped") == "true"),
                    material=_material(el), x0=x, bruto=_bruto(el),
                )
                self.componentes.append(c)
                x += L
                self._filhos(el, c)
            self.estagios.append((nome_est, n_comp))
        self.comprimento = x

    def _filhos(self, el, pai):
        subs = el.find("subcomponents")
        if subs is None:
            return
        for f in subs:
            if f.tag == "masscomponent":
                metodo = f.find("axialoffset").get("method")
                off = numero(f.findtext("axialoffset")) * M_PARA_MM
                Lm = numero(f.findtext("packedlength")) * M_PARA_MM
                x0 = pai.x0 + off if metodo == "top" else pai.x1 + off - Lm
                self.massas.append(Massa(f.findtext("name"), pai, x0, Lm,
                                         numero(f.findtext("packedradius")) * M_PARA_MM,
                                         numero(f.findtext("mass")) * 1000.0, _bruto(f)))
            elif f.tag == "freeformfinset":
                pts = np.array([(float(p.get("x")), float(p.get("y")))
                                for p in f.find("finpoints")]) * M_PARA_MM
                corda = pts[-1, 0]
                metodo = f.find("axialoffset").get("method")
                off = numero(f.findtext("axialoffset")) * M_PARA_MM
                if metodo == "bottom":
                    x_ba = pai.x1 + off - corda
                elif metodo == "top":
                    x_ba = pai.x0 + off
                else:  # middle
                    x_ba = pai.x0 + pai.comprimento / 2 + off - corda / 2
                self.aletas.append(Aletas(
                    f.findtext("name"), pai, int(f.findtext("fincount")),
                    numero(f.findtext("thickness")) * M_PARA_MM, f.findtext("crosssection"),
                    _material(f), pts, x_ba, float(self.raio(x_ba)),
                    float(f.findtext("rotation") or 0.0), _bruto(f)))

    def raio(self, x):
        """Raio externo do corpo na posição axial x (mm a partir da ponta)."""
        x = np.atleast_1d(np.asarray(x, float))
        r = np.zeros_like(x)
        for c in self.componentes:
            m = (x >= c.x0) & (x <= c.x1)
            r[m] = c.raio(x[m] - c.x0)
        return r if r.size > 1 else float(r[0])

    def perfil(self):
        xs, rs = [], []
        for c in self.componentes:
            x, r = c.perfil()
            xs.append(x)
            rs.append(r)
        return np.concatenate(xs), np.concatenate(rs)

    def contorno_aleta(self, a: Aletas, n_raiz=60):
        """Polígono da aleta em (x axial, r) incluindo a raiz que acompanha o corpo."""
        borda = np.column_stack([a.x_ba + a.pontos[:, 0], a.r_ba + a.pontos[:, 1]])
        xr = np.linspace(borda[-1, 0], borda[0, 0], n_raiz)[1:-1]
        raiz = np.column_stack([xr, self.raio(xr)])
        return borda, raiz

    @property
    def raio_max(self):
        x, r = self.perfil()
        return r.max()

    def envergadura(self):
        a = self.aletas[0]
        return 2 * (a.r_ba + a.pontos[:, 1].max())


if __name__ == "__main__":
    import os
    f = Foguete(os.path.join(os.path.dirname(__file__), "rocket.ork"))
    print(f.nome, f"comprimento {f.comprimento:.1f} mm, Ø máx {2 * f.raio_max:.1f}, "
          f"envergadura {f.envergadura():.1f}")
    for c in f.componentes:
        print(f"{c.item:2d} {c.nome:18s} {c.tipo:10s} x {c.x0:6.1f}-{c.x1:6.1f}  L {c.comprimento:6.2f}"
              f"  Ø {2 * c.r_diant:6.2f} -> {2 * c.r_tras:6.2f}  e {c.espessura:.2f}"
              f"  {FORMAS_PT[c.forma]} k={c.k:g}{' cortada' if c.cortada else ''}  {c.material.nome}")
    for m in f.massas:
        print("massa", m.nome, m.pai.nome, f"x {m.x0:.1f}..{m.x0 + m.comprimento:.1f}", f"{m.massa_g:g} g")
    for a in f.aletas:
        print("aletas", a.n, f"BA x={a.x_ba:.2f} r={a.r_ba:.2f} esp {a.espessura:.2f}",
              "ponta", a.pontos[:, 1].max() + a.r_ba)
        b, _ = f.contorno_aleta(a)
        print("  raio do corpo no BF da raiz:", f.raio(b[-1, 0]), "ponto:", b[-1, 1])
