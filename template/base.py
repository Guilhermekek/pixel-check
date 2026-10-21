"""Gera o corpo base de frente, 48x48, a partir do gesto do rabisco do artista (template/rabisco_referencia.png).

Cada segmento é um polígono que segue as diagonais do rabisco (ombro -> cotovelo -> pulso, quadril -> joelho ->
tornozelo), afinando ao longo do caminho: gesto e forma, não colunas retas. O lado direito do personagem
(esquerda da tela) foi desenhado; o outro é o espelho. Cada segmento tem a sua cor e camada; o lado esquerdo do
personagem tem cores diferentes do direito, pra dar pra seguir cada membro quando ele gira ou anima.

Uso: python template/base.py   -> template/base_frente.png (tudo junto) + template/camadas/*.png (uma por parte)
Depois: Aseprite.exe -b --script template/montar_aseprite.lua   -> template/base_frente.aseprite
"""
from pathlib import Path
from PIL import Image

OUT = Path(__file__).parent
W = H = 48
AXIS2 = 47  # eixo de simetria entre as colunas 23 e 24: x espelha em 47 - x

CONTORNO = (22, 18, 32)
CORES = {  # lado esquerdo do personagem em tons mais escuros/frios
    "cabeca": (95, 190, 205), "peito": (232, 122, 52), "cintura": (196, 68, 60),
    "braco_dir": (112, 190, 72), "braco_esq": (124, 64, 168),
    "antebraco_dir": (182, 212, 72), "antebraco_esq": (186, 80, 170),
    "mao_dir": (242, 222, 92), "mao_esq": (226, 132, 200),
    "coxa_dir": (236, 152, 112), "coxa_esq": (150, 52, 60),
    "canela_dir": (242, 202, 84), "canela_esq": (196, 92, 72),
    "pe_dir": (250, 240, 150), "pe_esq": (104, 40, 52),
}
GUIAS = {"topo da cabeça": 6, "olhos": 10, "queixo": 13, "ombros": 15, "cintura": 22,
         "quadril": 28, "joelhos": 35, "pés": 45}

# polígonos em coordenadas de borda de pixel (x, y). Centro/meio = linhas de corpo inteiras, espelhadas depois.
CENTRO = {
    "pescoco": [(22, 13), (26, 13), (26, 15), (22, 15)],
    "peito": [(21, 15), (27, 15), (30, 16), (29, 18), (27, 22), (21, 22), (19, 18), (18, 16)],  # trapézio
    "cintura": [(21, 22), (27, 22), (28, 25), (30, 29), (18, 29), (20, 25)],  # afina e abre no quadril
}
LADO_DIR = {  # só o lado direito do personagem (x < 24); o esquerdo é o espelho
    "braco": [(16, 15), (19, 16), (18, 19), (17, 22), (14, 22), (15, 18)],      # desce quase reto
    "antebraco": [(14, 21), (17, 22), (15, 24), (11, 26), (10, 23)],          # dobra no cotovelo, vai pra fora
    "mao": [(6, 22), (9, 22), (11, 24), (10, 27), (7, 27), (5, 25)],
    "coxa": [(18, 29), (23.5, 29), (22.5, 32), (22, 36), (17, 36), (17, 32)],  # afina no joelho; vão na virilha
    "canela": [(17, 36), (22, 36), (21, 39), (19, 43), (15, 43), (16, 39)],    # desce em diagonal pra fora
    "pe": [(15, 42), (19, 42), (20, 45), (12, 45), (13, 43)],                 # pé aponta pra fora
}
ORDEM = ("pe_esq", "pe_dir", "canela_esq", "canela_dir", "coxa_esq", "coxa_dir", "cintura", "peito",
         "braco_esq", "braco_dir", "antebraco_esq", "antebraco_dir", "mao_esq", "mao_dir", "cabeca")
OLHOS = {(21, 10), (21, 11), (26, 10), (26, 11)}  # mostram pra onde o personagem olha


def fill(poly):
    """Pixels cujo centro cai dentro do polígono (regra par-ímpar)."""
    out = set()
    n = len(poly)
    for y in range(H):
        for x in range(W):
            px, py, inside = x + .5, y + .5, False
            for i in range(n):
                (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
                if (y1 > py) != (y2 > py) and px < x1 + (py - y1) * (x2 - x1) / (y2 - y1):
                    inside = not inside
            if inside:
                out.add((x, y))
    return out


def mirror(px):
    return {(AXIS2 - x, y) for x, y in px}


# cabeça redonda: (y, primeira coluna) do lado direito; vai até o espelho. Curva do rabisco: 2,1,0,1,... degraus
CABECA = {5: 21, 6: 19, 7: 18, 8: 18, 9: 17, 10: 17, 11: 18, 12: 18, 13: 19}


def parts():
    p = {nome: fill(poly) | mirror(fill(poly)) for nome, poly in CENTRO.items()}
    p["cabeca"] = {(x, y) for y, x0 in CABECA.items() for x in range(x0, AXIS2 - x0 + 1)}
    p["cabeca"] |= p.pop("pescoco")
    for nome, poly in LADO_DIR.items():
        right = fill(poly)
        p[nome + "_dir"], p[nome + "_esq"] = right, mirror(right)
    return p


def build():
    raw = parts()
    owner = {}
    for nome in ORDEM:
        for q in raw[nome]:
            owner[q] = nome
    layers = {nome: {} for nome in ORDEM}
    for q, nome in owner.items():
        layers[nome][q] = CONTORNO if nome == "cabeca" and q in OLHOS else CORES[nome]
    every = set(owner)
    contorno = {(x + dx, y + dy) for x, y in every for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - every
    for x, y in sorted(contorno):  # pixel perfect: tira o canto do L nas diagonais (senão o contorno engrossa)
        for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            if ((x + dx, y) in contorno and (x, y + dy) in contorno and (x + dx, y + dy) in every
                    and (x - dx, y) not in contorno and (x, y - dy) not in contorno):
                contorno.discard((x, y))
                break
    layers["contorno"] = {q: CONTORNO for q in contorno}
    return layers


def save():
    layers = build()
    (OUT / "camadas").mkdir(exist_ok=True)
    for old in (OUT / "camadas").glob("*.png"):
        old.unlink()
    flat = Image.new("RGBA", (W, H))
    for nome in ("contorno",) + ORDEM:
        img = Image.new("RGBA", (W, H))
        for (x, y), c in layers[nome].items():
            if 0 <= x < W and 0 <= y < H:
                img.putpixel((x, y), (*c, 255))
        img.save(OUT / "camadas" / f"{nome}.png")
        flat.alpha_composite(img)
    flat.save(OUT / "base_frente.png")
    guias = Image.new("RGBA", (W, H))
    for y in GUIAS.values():
        for x in range(W):
            guias.putpixel((x, y), (0, 200, 255, 110))
    for y in range(0, H, 2):
        guias.putpixel((23, y), (255, 80, 200, 110))  # eixo de simetria (entre 23 e 24)
    guias.save(OUT / "camadas" / "guias.png")
    print("salvo:", OUT / "base_frente.png")


if __name__ == "__main__":
    save()
