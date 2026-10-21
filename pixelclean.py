"""Limpa pixel art: grade fixa, paleta fixa, sem pixels soltos, linhas "pixel perfect", contorno opcional.

Uso:
  python pixelclean.py rascunho.png saida.png --size 32 --palette paleta.png --outline 1a1c2c
  python pixelclean.py rascunho.png saida.png --size 32 --colors 12
  python pixelclean.py sprite.gif mapa.png --check     (só aponta problemas)
  python pixelclean.py sprite.gif sprite_limpo.gif --merge 20   (junta cores quase iguais, todos os frames)
  python pixelclean.py sprite.gif sprite_rampas.gif --ramps paleta.png      (paleta fixa por rampas)
  python pixelclean.py sprite.gif sprite_limpo.gif --clean mapa.png       (soltos: só rosto, punhos, botas)
  python pixelclean.py --test
"""
import argparse
import colorsys
from collections import Counter
from PIL import Image, ImageDraw, ImageSequence

T = None  # transparente
NOFIX = "só marca"  # checagem sem sugestão automática de cor


def load_grid(path, size, colors, palette_path):
    img = Image.open(path).convert("RGBA")
    if size:
        h = round(img.height * size / img.width)
        img = img.resize((size, h), Image.BOX)
    alpha = img.getchannel("A")
    rgb = img.convert("RGB")
    if palette_path:
        pal = list(dict.fromkeys(Image.open(palette_path).convert("RGB").getdata()))
        p = Image.new("P", (1, 1))
        p.putpalette([c for rgbc in pal for c in rgbc] + [0] * (768 - 3 * len(pal)))
        q = rgb.quantize(palette=p, dither=Image.Dither.NONE)
    else:
        q = rgb.quantize(colors, dither=Image.Dither.NONE)
    q = q.convert("RGB")
    w, h = q.size
    return [[q.getpixel((x, y)) if alpha.getpixel((x, y)) >= 128 else T for x in range(w)] for y in range(h)]


def at(g, x, y):
    return g[y][x] if 0 <= y < len(g) and 0 <= x < len(g[0]) else T


def remove_orphans(g):
    """Pixel sem nenhum vizinho (8 direções) da mesma cor vira a cor mais comum ao redor."""
    out = [row[:] for row in g]
    for y in range(len(g)):
        for x in range(len(g[0])):
            n = [at(g, x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy]
            if g[y][x] not in n:
                out[y][x] = Counter(n).most_common(1)[0][0]
    return out


def pixel_perfect(g):
    """Remove o pixel do 'cotovelo' em linhas de 1px (formato L), deixando a diagonal limpa."""
    # ponytail: vale pra qualquer cor; um "canal" de 1px de cor de preenchimento também é afinado.
    # Se incomodar, restringir às cores de contorno.
    out = [row[:] for row in g]
    w, hgt = len(g[0]), len(g)

    def differs(x, y, c):  # fora da imagem conta como igual, pra não comer a borda
        return 0 <= x < w and 0 <= y < hgt and out[y][x] != c

    for y in range(hgt):
        for x in range(w):
            c = out[y][x]
            if c is T:
                continue
            for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                h, v = at(out, x + dx, y), at(out, x, y + dy)
                if (h == c and v == c and at(out, x + dx, y + dy) != c and differs(x - dx, y - dy, c)
                        and differs(x - dx, y, c) and differs(x, y - dy, c)):
                    out[y][x] = at(out, x - dx, y - dy)  # assume a cor do lado de fora
                    break
    return out


def add_outline(g, color):
    out = [row[:] for row in g]
    for y in range(len(g)):
        for x in range(len(g[0])):
            if g[y][x] is T and any(at(g, x + dx, y + dy) not in (T, color)
                                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                out[y][x] = color
    return out


def neck_cuts(g):
    """Contorno escuro com pele em cima (queixo) e embaixo (pescoço), na altura do queixo: a cabeça parece solta."""
    rows = [y for y in range(len(g)) if any(c is not T for c in g[y])]
    top, bottom = rows[0], rows[-1]
    skin = lambda x, y: at(g, x, y) is not T and ramp_of(at(g, x, y)) == "pele"
    return [(x, y) for y in range(round(top + (bottom - top) * .3), round(top + (bottom - top) * .5))
            for x in range(len(g[0]))
            if g[y][x] is not T and sum(g[y][x]) < 40 and skin(x, y - 1) and skin(x, y + 1)]


def check(path, dst, scale, near=20):
    """Só diagnostica (não altera): cores quase iguais, cores raras, pixels soltos, cotovelos. Aceita GIF animado."""
    frames = [f.convert("RGBA") for f in ImageSequence.Iterator(Image.open(path))]
    grids = [[[f.getpixel((x, y))[:3] if f.getpixel((x, y))[3] >= 128 else T for x in range(f.width)]
              for y in range(f.height)] for f in frames]
    cnt = Counter(c for g in grids for row in g for c in row if c is not T)
    print(f"{len(frames)} frame(s), {len(cnt)} cores no total")

    cols = sorted(cnt)
    dist = lambda a, b: sum((p - q) ** 2 for p, q in zip(a, b)) ** .5
    pairs = [(a, b) for i, a in enumerate(cols) for b in cols[i + 1:] if dist(a, b) < near]
    print(f"\n{len(pairs)} pares de cores quase idênticas (diferença < {near}, invisível no jogo):")
    for a, b in pairs:
        print(f"  #{bytes(a).hex()} ({cnt[a]}px)  ~  #{bytes(b).hex()} ({cnt[b]}px)")
    rare = {c for c in cols if cnt[c] <= 2}
    print(f"\n{len(rare)} cores usadas em só 1-2 pixels no sprite inteiro:", " ".join(f"#{bytes(c).hex()}" for c in rare))

    w, h = frames[0].size
    sheet = Image.new("RGBA", (w * scale * len(frames), h * scale), (255, 255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    print("\nframe  soltos  cotovelos  raras  pescoço  altura")
    for i, (f, g) in enumerate(zip(frames, grids)):
        sheet.alpha_composite(f.resize((w * scale, h * scale), Image.NEAREST), (i * w * scale, 0))
        pp = pixel_perfect(g)
        marks = {"soltos": [], "cotovelos": [], "raras": [], "pescoço": neck_cuts(g)}
        for y in range(h):
            for x in range(w):
                c = g[y][x]
                if c is T:
                    continue
                if c in rare:
                    marks["raras"].append((x, y))
                elif c not in [at(g, x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy]:
                    marks["soltos"].append((x, y))
                elif pp[y][x] != c:
                    marks["cotovelos"].append((x, y))
        for (k, color) in (("soltos", "red"), ("cotovelos", "orange"), ("raras", "magenta"), ("pescoço", "cyan")):
            for x, y in marks[k]:
                x0, y0 = i * w * scale + x * scale, y * scale
                draw.rectangle((x0, y0, x0 + scale - 1, y0 + scale - 1), outline=color, width=max(1, scale // 5))
        box = f.getbbox()
        print(f"{i + 1:>5}  {len(marks['soltos']):>6}  {len(marks['cotovelos']):>9}  {len(marks['raras']):>5}  "
              f"{len(marks['pescoço']):>7}  {box[3] - box[1] if box else 0:>6}")
    sheet.save(dst)
    print(f"\nmapa salvo em {dst}  (vermelho=solto, laranja=cotovelo, rosa=cor rara, ciano=pescoço cortado)")


def merge_gif(path, dst, near=20):
    """Junta cores quase idênticas na mais usada (mesma troca em todos os frames) e salva o GIF."""
    im = Image.open(path)
    frames = [f.convert("RGBA") for f in ImageSequence.Iterator(im)]
    cnt = Counter(p[:3] for f in frames for p in f.getdata() if p[3] >= 128)
    dist = lambda a, b: sum((p - q) ** 2 for p, q in zip(a, b)) ** .5
    keep, remap = [], {}
    for c, _ in cnt.most_common():  # a mais usada vira a "oficial"; as parecidas apontam pra ela
        target = next((k for k in keep if dist(c, k) < near), None)
        if target is None:
            keep.append(c)
        remap[c] = target or c
    save_gif([recolor(f, remap) for f in frames], im, dst)
    print(f"{len(cnt)} -> {len(keep)} cores. salvo: {dst}")


# Rampas: nome -> (regra sobre hue°, saturação, luminosidade; nº de tons). A ordem importa: a 1ª que bater ganha.
# ponytail: regras afinadas pra essa personagem; outro personagem com outras cores = ajustar aqui.
RAMPS = [
    ("cabelo", lambda h, s, l: l < .06 or (200 <= h <= 290 and l < .3), 5),
    ("tecido", lambda h, s, l: (200 <= h <= 290) or s < .1, 5),
    ("pele", lambda h, s, l: 5 <= h <= 35 and l >= .55, 4),
    ("marrom", lambda h, s, l: 5 <= h <= 35, 2),
    ("vermelho", lambda h, s, l: True, 5),
]


def ramp_of(c):
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in c))
    return next(name for name, rule, _ in RAMPS if rule(h * 360, s, l))


def build_ramp(counts, k):
    """k-means 1D na luminosidade (pesado por nº de pixels). Cada tom = média RGB do grupo, então o matiz se mantém."""
    lum = lambda c: .299 * c[0] + .587 * c[1] + .114 * c[2]
    cols = sorted(counts, key=lum)
    k = min(k, len(cols))
    centers = [lum(cols[round(i * (len(cols) - 1) / max(k - 1, 1))]) for i in range(k)]
    for _ in range(20):
        groups = [[] for _ in centers]
        for c in cols:
            groups[min(range(k), key=lambda i: abs(lum(c) - centers[i]))].append(c)
        groups = [g for g in groups if g]
        centers = [sum(lum(c) * counts[c] for c in g) / sum(counts[c] for c in g) for g in groups]
        k = len(centers)
    remap = {}
    for g in groups:
        n = sum(counts[c] for c in g)
        tone = tuple(round(sum(c[i] * counts[c] for c in g) / n) for i in range(3))
        remap.update({c: tone for c in g})
    return remap


def ramps_gif(path, dst, pal_dst):
    im = Image.open(path)
    frames = [f.convert("RGBA") for f in ImageSequence.Iterator(im)]
    cnt = Counter(p[:3] for f in frames for p in f.getdata() if p[3] >= 128)
    remap, rows = {}, []
    for name, _, k in RAMPS:
        part = {c: n for c, n in cnt.items() if ramp_of(c) == name}
        if not part:
            continue
        r = build_ramp(part, k)
        remap.update(r)
        rows.append(sorted(set(r.values()), key=sum))
        print(f"{name:>9}: {len(part):>2} cores -> {' '.join('#' + bytes(c).hex() for c in rows[-1])}")
    save_gif([recolor(f, remap) for f in frames], im, dst)
    pal = Image.new("RGBA", (max(map(len, rows)), len(rows)))
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            pal.putpixel((x, y), (*c, 255))
    pal.save(pal_dst)
    print(f"{len(cnt)} -> {len(set(remap.values()))} cores. salvo: {dst} e paleta {pal_dst}")


def regions(g):
    """Rosto, mãos/punhos e botas, achados pela pele e pela altura do frame.
    Devolve {(x, y): materiais que podem mudar ali}: no rosto só pele, pra não mexer em mechas e brilho do cabelo."""
    h, w = len(g), len(g[0])
    rows = [y for y in range(h) if any(c is not T for c in g[y])]
    top, bottom = rows[0], rows[-1]
    rel = lambda y: (y - top) / (bottom - top)
    skin = [(x, y) for y in range(h) for x in range(w) if g[y][x] is not T and ramp_of(g[y][x]) == "pele"]
    mask = {}
    for px, py in skin:
        if rel(py) < .4:  # rosto (acima do queixo; pescoço/decote ficam de fora)
            mask[(px, py)] = {"pele"}
        elif rel(py) > .55:  # mãos + punhos em volta delas
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    mask.setdefault((px + dx, py + dy), {"pele", "tecido"})
    for y in range(round(top + (bottom - top) * .8), h):  # botas
        for x in range(w):
            mask[(x, y)] = {"cabelo", "tecido", "pele", "marrom", "vermelho"}
    return mask


def clean_loose(g, mask):
    """Tira tom solto só quando ele é do MESMO material dos vizinhos (ex: pele média perdida na pele clara).
    Pixel de outro material (brilho do olho, boca, mecha de cabelo, contorno) é detalhe proposital e fica.
    mask: {(x, y): materiais permitidos ali}."""
    out = [row[:] for row in g]
    for (x, y), allowed in mask.items():
        c = at(g, x, y)
        if c is T or ramp_of(c) not in allowed:
            continue
        n = [v for v in (at(g, x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy) if v is not T]
        if c in n or len(n) < 5:
            continue
        top = Counter(n).most_common(1)[0][0]
        if ramp_of(top) == ramp_of(c):
            out[y][x] = top
    return out


def clean_gif(path, dst, map_dst, scale=10):
    im = Image.open(path)
    frames = [f.convert("RGBA") for f in ImageSequence.Iterator(im)]
    w, h = frames[0].size
    out, total = [], 0
    sheet = Image.new("RGBA", (w * scale * len(frames), h * scale), (255, 255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for i, f in enumerate(frames):
        g = [[f.getpixel((x, y))[:3] if f.getpixel((x, y))[3] >= 128 else T for x in range(w)] for y in range(h)]
        mask = regions(g)
        new = clean_loose(g, mask)
        img = Image.new("RGBA", (w, h))
        img.putdata([(0, 0, 0, 0) if c is T else (*c, 255) for row in new for c in row])
        out.append(img)
        sheet.alpha_composite(img.resize((w * scale, h * scale), Image.NEAREST), (i * w * scale, 0))
        for x, y in mask:  # área analisada em cinza claro, pixel trocado em verde
            if 0 <= x < w and 0 <= y < h and new[y][x] is not T:
                x0, y0 = i * w * scale + x * scale, y * scale
                changed = new[y][x] != g[y][x]
                total += changed
                if changed:
                    draw.rectangle((x0, y0, x0 + scale - 1, y0 + scale - 1), outline="lime", width=2)
    save_gif(out, im, dst)
    sheet.save(map_dst)
    print(f"{total} pixels trocados. salvo: {dst}, mapa: {map_dst} (verde = trocado)")


# Pares de frames que são a mesma pose espelhada (rotação de 8 direções). (i, i) = compara com o próprio espelho.
MIRROR_PAIRS = [(0, 0), (4, 4), (1, 7), (2, 6), (3, 5)]


def sym_gif(path, dst, scale=10, pairs=MIRROR_PAIRS):
    """Só APONTA diferenças de formato entre lados que costumam ser iguais (rosto, mãos, botas).
    Compara material (pele/cabelo/tecido...), não tom: luz vinda de um lado não conta como problema.
    Assimetria pode ser proposital (design, movimento, luz) - quem decide é o artista."""
    frames = [f.convert("RGBA") for f in ImageSequence.Iterator(Image.open(path))]
    w, h = frames[0].size
    mats = [[[T if f.getpixel((x, y))[3] < 128 else ramp_of(f.getpixel((x, y))[:3]) for x in range(w)]
             for y in range(h)] for f in frames]
    names = {frozenset({"pele"}): "rosto", frozenset({"pele", "tecido"}): "mãos"}
    sheet = Image.new("RGBA", (w * scale * len(frames), h * scale), (200, 200, 200, 255))
    draw = ImageDraw.Draw(sheet)
    for i, f in enumerate(frames):
        sheet.alpha_composite(f.resize((w * scale, h * scale), Image.NEAREST), (i * w * scale, 0))
    for a, b in pairs:
        ma = mats[a]
        mb = [row[::-1] for row in mats[b]]  # espelho
        # acha o deslocamento horizontal que mais casa (o personagem nem sempre está no centro exato)
        dx = min(range(-6, 7), key=lambda d: sum(ma[y][x] != (mb[y][x - d] if 0 <= x - d < w else T)
                                                   for y in range(h) for x in range(w)))
        mask = regions([[T if m is T else frames[a].getpixel((x, y))[:3] for x, m in enumerate(row)]
                        for y, row in enumerate(ma)])
        found = Counter()
        for (x, y), allowed in mask.items():
            if not (0 <= x < w and 0 <= y < h and 0 <= x - dx < w):
                continue
            if ma[y][x] != mb[y][x - dx]:
                found[names.get(frozenset(allowed), "botas")] += 1
                for fi, fx in ((a, x), (b, w - 1 - (x - dx))):  # marca nos dois frames do par
                    x0 = fi * w * scale + fx * scale
                    draw.rectangle((x0, y * scale, x0 + scale - 1, y * scale + scale - 1), outline="yellow", width=2)
        label = f"frame {a + 1}" + (" x espelho" if a == b else f" x frame {b + 1}")
        print(f"{label:>20}: " + (", ".join(f"{n} {c}px" for n, c in found.items()) or "nada"))
    sheet.save(dst)
    print(f"\nmapa: {dst}  (amarelo = formato diferente do outro lado; confira, pode ser proposital)")


# ---------- lint: checagens baseadas no Pixel Logic. Todas só APONTAM; quem decide é o artista. ----------

lum = lambda c: .299 * c[0] + .587 * c[1] + .114 * c[2]


def jaggies(g):
    """Degrau curto no meio de dois maiores numa escada (ex: 3-1-3, 2-2-1-2-2).
    Olha o perfil da silhueta pelos 4 lados. Sugestão: redistribuir os 3 degraus em tamanhos iguais.
    Devolve {(x, y): cor sugerida | T (apagar)}."""
    # ponytail: só o contorno externo; linhas internas (mechas, dobras) ficam de fora por enquanto.
    h, w = len(g), len(g[0])
    opaque = lambda x, y: g[y][x] is not T
    profiles = [  # (posições, borda na posição, (pos, valor) -> (x, y), lado de dentro: +1 ou -1)
        (range(w), lambda x: next((y for y in range(h) if opaque(x, y)), None), lambda p, v: (p, v), 1),
        (range(w), lambda x: next((y for y in reversed(range(h)) if opaque(x, y)), None), lambda p, v: (p, v), -1),
        (range(h), lambda y: next((x for x in range(w) if opaque(x, y)), None), lambda p, v: (v, p), 1),
        (range(h), lambda y: next((x for x in reversed(range(w)) if opaque(x, y)), None), lambda p, v: (v, p), -1),
    ]
    out = {}
    for positions, edge, to_xy, inside in profiles:
        runs = []  # [valor, [posições]]; buraco (None) quebra a sequência
        for p in positions:
            v = edge(p)
            if v is None:
                runs.append(None)
            elif runs and runs[-1] and runs[-1][0] == v:
                runs[-1][1].append(p)
            else:
                runs.append([v, [p]])
        for a, b, c in zip(runs, runs[1:], runs[2:]):
            if not (a and b and c and abs(b[0] - a[0]) == 1 and b[0] - a[0] == c[0] - b[0]
                    and len(b[1]) < len(a[1]) and len(b[1]) < len(c[1])):
                continue
            for p in b[1]:
                out.setdefault(to_xy(p, b[0]), NOFIX)
            # sugestão: mesmos 3 valores, tamanhos divididos por igual (o maior fica do lado do degrau maior)
            ps = a[1] + b[1] + c[1]
            n, r = divmod(len(ps), 3)
            sizes = [n + (i < r) for i in range(3)]
            if len(a[1]) < len(c[1]):
                sizes.reverse()
            new_vals = [a[0]] * sizes[0] + [b[0]] * sizes[1] + [c[0]] * sizes[2]
            old_vals = [a[0]] * len(a[1]) + [b[0]] * len(b[1]) + [c[0]] * len(c[1])
            for p, vo, vn in zip(ps, old_vals, new_vals):
                color = g[to_xy(p, vo)[1]][to_xy(p, vo)[0]]
                if (vn - vo) * inside > 0:  # borda entra: apaga
                    for v in range(vo, vn, inside):
                        out[to_xy(p, v)] = T
                elif vn != vo:  # borda sai: pinta com a cor da borda
                    for v in range(vn, vo, inside):
                        out[to_xy(p, v)] = color
    return out


def thick_outline(g):
    """Contorno que engrossa pra 2px: pixel de borda, atrás dele outro da MESMA cor, e atrás um mais claro.
    Sugestão: o pixel de dentro vira a cor de dentro."""
    out = {}
    for y in range(len(g)):
        for x in range(len(g[0])):
            c = g[y][x]
            if c is T:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):  # (dx, dy) aponta pro lado transparente
                qx, qy = x - dx, y - dy
                # o de dentro (q) não pode encostar no lado de fora: senão é o contorno correndo num degrau, não espessura
                inner = all(at(g, qx + ex, qy + ey) is not T for ex, ey in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                if at(g, x + dx, y + dy) is T and at(g, qx, qy) == c and inner:
                    r = at(g, x - 2 * dx, y - 2 * dy)
                    if r is not T and lum(r) > lum(c) + 30:
                        out[(x - dx, y - dy)] = r
    return out


def banding(g, min_len=2, max_len=5):
    """Duas fileiras de cores diferentes, mesmo tamanho, coladas e alinhadas (ou em degrau de 1px).
    Sugestão: encurtar 1px a fileira de dentro (a ponta vira a cor que está atrás dela)."""
    h, w = len(g), len(g[0])

    def runs(line):
        out, start = [], 0
        for i in range(1, len(line) + 1):
            if i == len(line) or line[i] != line[start]:
                if line[start] is not T and min_len <= i - start <= max_len:
                    out.append((start, i - 1, line[start]))
                start = i
        return out

    out = {}
    for lines, to_xy in (([g[y] for y in range(h)], lambda i, p: (p, i)),
                         ([[g[y][x] for y in range(h)] for x in range(w)], lambda i, p: (i, p))):
        rs = [runs(l) for l in lines]

        def thin(i, s, e, c):  # a fileira tem 1px de espessura: do outro lado não continua a mesma cor
            return not 0 <= i < len(lines) or all(lines[i][p] != c for p in range(s, e + 1))

        for i in range(len(lines) - 1):
            for s0, e0, c0 in rs[i]:
                for s1, e1, c1 in rs[i + 1]:
                    # duas tiras finas abraçadas = banding; áreas largas de sombra (ex: rosto) não contam
                    if c0 != c1 and e0 - s0 == e1 - s1 and abs(s0 - s1) <= 1                             and thin(i - 1, s0, e0, c0) and thin(i + 2, s1, e1, c1):
                        for k, (s, e) in ((i, (s0, e0)), (i + 1, (s1, e1))):
                            for p in range(s, e + 1):
                                out.setdefault(to_xy(k, p), NOFIX)
                        behind = lines[i + 2][e1] if i + 2 < len(lines) else T
                        out[to_xy(i + 1, e1)] = behind if behind is not T else c0
    return out


def blending(g, min_diff=25, min_hue=45, min_chroma=20):
    """Cores de matiz bem diferente (ex: saia vermelha x jaqueta azul) encostadas com quase o mesmo brilho:
    no tamanho real viram uma mancha só. Tons do mesmo matiz são sombreamento, não contam; preto puro também não."""
    def hue(c):
        return colorsys.rgb_to_hls(*(v / 255 for v in c))[0] * 360

    def differs(c, n):
        d = abs(hue(c) - hue(n))
        return min(d, 360 - d) > min_hue and min(max(c) - min(c), max(n) - min(n)) >= min_chroma

    out = {}
    for y in range(len(g)):
        for x in range(len(g[0])):
            c = g[y][x]
            for d in ((1, 0), (0, 1)):
                n = at(g, x + d[0], y + d[1])
                if c is not T and n is not T and abs(lum(c) - lum(n)) < min_diff and differs(c, n):
                    out[(x, y)] = out[(x + d[0], y + d[1])] = NOFIX  # sem sugestão: qual lado clarear é escolha sua
    return out


def contour_elbows(g):
    """Cotovelos (pixel perfect) só na borda da silhueta, onde a linha é linha de verdade.
    Canto de 90° (dois braços retos de 2px+, ex: bico de tênis) é forma, não cotovelo: fica de fora."""
    pp = pixel_perfect(g)
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))

    def square_corner(x, y):
        c = g[y][x]
        arms = [(dx, dy) for dx, dy in dirs if at(g, x + dx, y + dy) == c and at(g, x + 2 * dx, y + 2 * dy) == c]
        return any(a[0] == 0 and b[1] == 0 for a in arms for b in arms)  # um braço vertical e um horizontal

    return {(x, y): pp[y][x] for y in range(len(g)) for x in range(len(g[0]))
            if pp[y][x] != g[y][x] and any(at(g, x + dx, y + dy) is T for dx, dy in dirs) and not square_corner(x, y)}


def loose_same_material(g):
    """Tom solto no meio do mesmo material (o que o --clean trocaria). Cabelo fica de fora: mecha é proposital."""
    every = {(x, y): {name for name, _, _ in RAMPS} - {"cabelo"} for y in range(len(g)) for x in range(len(g[0]))}
    new = clean_loose(g, every)
    return {(x, y): new[y][x] for (x, y) in every if new[y][x] != g[y][x]}


def neck_fix(g):
    """Pescoço cortado: o contorno vira o tom mais escuro entre a pele de cima e a de baixo (sombra do queixo)."""
    return {(x, y): min(g[y - 1][x], g[y + 1][x], key=lum) for x, y in neck_cuts(g)}


def regions_by_material(g, min_size=25):
    """Áreas ligadas (4 vizinhos) do mesmo material (rampa). Devolve listas de (x, y)."""
    h, w = len(g), len(g[0])
    seen, out = set(), []
    for y0 in range(h):
        for x0 in range(w):
            if g[y0][x0] is T or (x0, y0) in seen:
                continue
            mat, stack, area = ramp_of(g[y0][x0]), [(x0, y0)], []
            seen.add((x0, y0))
            while stack:
                x, y = stack.pop()
                area.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (x + dx, y + dy)
                    if n not in seen and at(g, *n) is not T and ramp_of(at(g, *n)) == mat:
                        seen.add(n)
                        stack.append(n)
            if len(area) >= min_size:
                out.append(area)
    return out


def pillow_shading(g, min_r=.5, margin=.2):
    """Sombra que só acompanha a borda (escuro em volta, claro no meio) em vez de vir de uma direção de luz.
    Mede, em cada área do mesmo material: o brilho segue a distância até a borda mais do que segue uma direção?"""
    from statistics import correlation, StatisticsError, mean
    out = {}
    # o contorno (quase preto) não é sombra: sai da conta, senão todo sprite com contorno vira "pillow"
    g = [[T if c is T or max(c) < 12 else c for c in row] for row in g]
    for area in regions_by_material(g):
        xs, ys = [x for x, _ in area], [y for _, y in area]
        if max(xs) - min(xs) < 4 or max(ys) - min(ys) < 4:  # fina demais (perna, braço): é cilindro, não almofada
            continue
        inside = set(area)
        dist, frontier = {}, [p for p in area if any((p[0] + dx, p[1] + dy) not in inside
                                                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
        for p in frontier:
            dist[p] = 1
        while frontier:  # distância até a borda da área, por camadas
            nxt = []
            for x, y in frontier:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (x + dx, y + dy)
                    if n in inside and n not in dist:
                        dist[n] = dist[(x, y)] + 1
                        nxt.append(n)
            frontier = nxt
        lums = [lum(g[y][x]) for x, y in area]
        try:
            r_ring = correlation([min(dist[p], 3) for p in area], lums)
            r_dir = max(correlation([x * dx + y * dy for x, y in area], lums)
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)))
        except StatisticsError:  # área de uma cor só, ou fina demais: nada a medir
            continue
        # pillow de verdade: a borda é mais escura que o miolo nos 4 lados, não só de um
        cx, cy = mean(xs), mean(ys)
        core = mean(lum(g[y][x]) for x, y in area if dist[(x, y)] > 1) if any(d > 1 for d in dist.values()) else 0
        sides = [[lum(g[y][x]) for x, y in area if dist[(x, y)] == 1 and test(x - cx, y - cy)]
                 for test in (lambda dx, dy: dx < -abs(dy) / 2, lambda dx, dy: dx > abs(dy) / 2,
                              lambda dx, dy: dy < -abs(dx) / 2, lambda dx, dy: dy > abs(dx) / 2)]
        all_sides = all(s and mean(s) < core - 10 for s in sides)
        if r_ring >= min_r and r_ring - r_dir >= margin and all_sides:
            out.update({p: NOFIX for p in area if dist[p] == 1})
    return out


def color_tips(g):
    """Dicas de cor que não são erro (estilo): rampas sem hue shift, preto puro. Devolve [(dica, como fazer)]."""
    cols = {c for row in g for c in row if c is not T}
    tips = []
    for name, _, _ in RAMPS:
        ramp = sorted((c for c in cols if ramp_of(c) == name), key=lum)
        if len(ramp) < 3:
            continue
        hues = [colorsys.rgb_to_hls(*(v / 255 for v in c))[0] * 360 for c in (ramp[0], ramp[-1])]
        shift = min(abs(hues[0] - hues[1]), 360 - abs(hues[0] - hues[1]))
        sats = [max(c) - min(c) for c in ramp]
        if shift < 8 and min(sats) > 15:  # rampa colorida que só escurece, sem mudar o matiz
            tips.append((f"rampa '{name}' quase sem hue shift ({shift:.0f} graus)",
                         "puxe as sombras pro roxo/azul e as luzes pro amarelo; dá mais vida"))
    if any(max(c) < 8 for c in cols):
        tips.append(("usa preto puro", "um escuro com um pouco de cor (roxo, azul, marrom) costuma ficar mais bonito"))
    return tips


def preview(f, dst, scale=3):
    """Prévia lado a lado: tamanho real, ampliado, silhueta e desfocado (o desfoque deixa banding e linha torta à mostra)."""
    from PIL import ImageFilter
    w, h = f.size
    big = f.resize((w * scale, h * scale), Image.NEAREST)
    sil = Image.new("RGBA", big.size, (30, 30, 40, 255))
    sil.putalpha(big.getchannel("A"))
    blur = big.filter(ImageFilter.GaussianBlur(scale * .5))
    gap = 8
    out = Image.new("RGBA", (w + gap + 3 * (w * scale + gap), h * scale), (128, 128, 128, 255))
    out.alpha_composite(f, (0, 0))
    for i, im in enumerate((big, sil, blur)):
        out.alpha_composite(im, (w + gap + i * (w * scale + gap), 0))
    out.save(dst)


# nome: (função, cor da marca, o problema, como corrigir). A função devolve {(x, y): cor sugerida | T | None}.
LINT = {
    "degraus": (jaggies, (255, 220, 0), "degrau curto entre dois maiores na borda",
                "deixe os degraus do mesmo tamanho (ex: 3-1-3 vira 3-2-2); sugestão apaga/pinta a borda"),
    "contorno 2px": (thick_outline, (40, 120, 255), "o contorno engrossa pra 2px",
                     "pinte o pixel de dentro com a cor que está atrás dele"),
    "banding": (banding, (180, 0, 255), "duas fileiras finas do mesmo tamanho coladas",
                "encurte ou alongue 1 das fileiras em 1px pra quebrar o alinhamento"),
    "se misturam": (blending, (0, 230, 230), "cores diferentes com brilho quase igual",
                    "clareie um dos lados ou escureça o outro (1 tom da rampa); sem sugestão automática"),
    "cotovelos": (contour_elbows, (255, 130, 0), "cotovelo em L na borda",
                  "apague o pixel do canto do L; a diagonal fica com 1px"),
    "tom solto": (loose_same_material, (255, 0, 0), "tom perdido no meio do mesmo material",
                  "use a cor que mais aparece em volta dele"),
    "pescoço": (neck_fix, (0, 255, 0), "contorno separando queixo do pescoço",
                "use o tom de sombra da pele no lugar do contorno"),
    "pillow shading": (pillow_shading, (255, 120, 180), "sombra só em volta da borda, sem direção de luz",
                       "escolha de onde vem a luz: escureça só o lado oposto e clareie o lado da luz"),
}


def lint(path, dst):
    """Analisa 1 frame e salva: dst = camada de marcas, dst.txt = relatório (nome|problema|como corrigir|qtd),
    dst.fix = sugestões (nome x y r g b a; a=0 apaga)."""
    f = next(ImageSequence.Iterator(Image.open(path))).convert("RGBA")
    w, h = f.size
    g = [[f.getpixel((x, y))[:3] if f.getpixel((x, y))[3] >= 128 else T for x in range(w)] for y in range(h)]
    marks = Image.new("RGBA", (w, h))
    report, fixes = [], []
    empty = all(c is T for row in g for c in row)
    for name, (fn, color, why, how) in LINT.items():  # ordem = prioridade: a marca de cima vence
        found = {} if empty else fn(g)
        for (x, y), sug in found.items():
            if not (0 <= x < w and 0 <= y < h):
                continue
            if marks.getpixel((x, y))[3] == 0:
                marks.putpixel((x, y), (*color, 255))
            if sug is T and g[y][x] is T or sug == NOFIX:
                continue
            fixes.append(f"{name} {x} {y} " + ("0 0 0 0" if sug is T else f"{sug[0]} {sug[1]} {sug[2]} 255"))
        if found:
            report.append(f"{name}|{why}|{how}|{len(found)}")
    if not empty:
        report += [f"dica|{why}|{how}|-" for why, how in color_tips(g)]
        preview(f, dst + ".view.png")
    marks.save(dst)
    with open(dst + ".txt", "w", encoding="utf-8") as out:
        out.write("\n".join(report))
    with open(dst + ".fix", "w", encoding="utf-8") as out:
        out.write("\n".join(fixes))
    print("\n".join(f"{r.split('|')[3]:>4}  {r.split('|')[0]}: {r.split('|')[2]}" for r in report) or "nada encontrado")


# ---------- limpar traço: redesenha uma linha torta com degraus regulares ----------

def stroke_path(pixels):
    """Ordena os pixels de um traço: do ponto mais distante a outro (8 vizinhos), pelo caminho mais curto."""
    pixels = set(pixels)
    nbrs = lambda p: [(p[0] + dx, p[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                      if (dx or dy) and (p[0] + dx, p[1] + dy) in pixels]

    def bfs(start):
        prev, queue = {start: None}, [start]
        for p in queue:
            for n in nbrs(p):
                if n not in prev:
                    prev[n] = p
                    queue.append(n)
        return queue[-1], prev  # o último visitado é o mais longe

    a, _ = bfs(min(pixels))
    b, prev = bfs(a)
    path = [b]
    while prev[path[-1]] is not None:
        path.append(prev[path[-1]])
    return path


def smooth_chain(path, win=2):
    """Média móvel do caminho (tira o tremido da mão) e rasteriza de volta em pixels ligados, sem cotovelo."""
    n = len(path)
    pts = []
    for i in range(n):
        a, b = max(0, i - win), min(n, i + win + 1)
        pts.append((sum(p[0] for p in path[a:b]) / (b - a), sum(p[1] for p in path[a:b]) / (b - a)))
    pts[0], pts[-1] = path[0], path[-1]  # as pontas ficam onde você desenhou
    chain = [path[0]]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        k = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) * 2))
        for t in range(1, k + 1):
            q = (round(x0 + (x1 - x0) * t / k), round(y0 + (y1 - y0) * t / k))
            if q != chain[-1]:
                while max(abs(q[0] - chain[-1][0]), abs(q[1] - chain[-1][1])) > 1:  # garante pixels encostados
                    c = chain[-1]
                    chain.append((c[0] + (q[0] > c[0]) - (q[0] < c[0]), c[1] + (q[1] > c[1]) - (q[1] < c[1])))
                chain.append(q)
    out = [chain[0]]
    for q in chain[1:]:  # cotovelo: se o anterior do anterior já encosta neste, o do meio sobra
        while len(out) >= 2 and max(abs(q[0] - out[-2][0]), abs(q[1] - out[-2][1])) <= 1:
            out.pop()
        if q not in out[-3:]:
            out.append(q)
    return out


def regular_steps(chain):
    """Regra de curva do Pixel Logic: os degraus só crescem ou só diminuem (sem 3-1-3).
    Divide o traço em trechos de direção constante e reordena os degraus de cada trecho; as pontas não mudam."""
    sign = lambda v: (v > 0) - (v < 0)
    pieces, cur, sx, sy = [], [chain[0]], 0, 0
    for p, q in zip(chain, chain[1:]):
        dx, dy = sign(q[0] - p[0]), sign(q[1] - p[1])
        if (dx and sx and dx != sx) or (dy and sy and dy != sy):  # mudou de quadrante: novo trecho
            pieces.append((cur, sx, sy))
            cur, sx, sy = [p], 0, 0
        cur.append(q)
        sx, sy = sx or dx, sy or dy
    pieces.append((cur, sx, sy))
    out = [chain[0]]
    for piece, sx, sy in pieces:
        # degrau = (eixo, quantos passos retos) terminado por 1 passo diagonal
        tokens, k, axis = [], 0, None
        for p, q in zip(piece, piece[1:]):
            dx, dy = q[0] - p[0], q[1] - p[1]
            if dx and dy:
                tokens.append((axis, k))
                k, axis = 0, None
            else:
                k, axis = k + 1, ("x" if dx else "y")
        value = lambda t: -t[1] if t[0] == "x" else t[1]  # deitado = negativo, em pé = positivo
        (x0, y0), (x1, y1) = piece[0], piece[-1]
        chord = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** .5 or 1
        straight = max(abs((y1 - y0) * x - (x1 - x0) * y + x1 * y0 - y1 * x0) / chord for x, y in piece) <= 1
        axes = {t[0] for t in tokens if t[1]}
        if straight and len(axes) == 1 and tokens:
            # reta: degraus espalhados por igual (3-3-4-3-3-4), sem entortar a ponta
            ax, total, n = axes.pop(), sum(t[1] for t in tokens), len(tokens)
            tokens = [(ax, (i + 1) * total // n - i * total // n) for i in range(n)]
        else:
            # curva: degraus só crescendo ou só diminuindo
            half = len(tokens) // 2
            rising = sum(map(value, tokens[:half])) <= sum(map(value, tokens[half:]))
            tokens.sort(key=value, reverse=not rising)
        x, y = piece[0]
        for i, (ax, k) in enumerate(tokens + [(axis, k)]):
            for _ in range(k):
                x, y = (x + sx, y) if ax == "x" else (x, y + sy)
                out.append((x, y))
            if i < len(tokens):  # o último pedaço (sem diagonal no fim) não ganha passo diagonal
                x, y = x + sx, y + sy
                out.append((x, y))
    return out


def clean_stroke(pixels):
    """Traço torto -> traço limpo: acha o caminho, tira o tremido e deixa os degraus regulares."""
    path = stroke_path(pixels)
    if len(path) < 3:
        return set(pixels), path
    return set(regular_steps(smooth_chain(path))), path


def trace(src, mask_path, dst):
    """Limpa o traço dentro da seleção. src = camada (tamanho do sprite), mask = seleção (branco = selecionado).
    O traço é a cor mais usada dentro da seleção. Salva a camada corrigida em dst."""
    img = Image.open(src).convert("RGBA")
    mask = Image.open(mask_path).convert("L")
    w, h = img.size
    sel = [(x, y) for y in range(h) for x in range(w) if mask.getpixel((x, y)) > 127 and img.getpixel((x, y))[3] >= 128]
    if not sel:
        print("nada selecionado")
        return
    color = Counter(img.getpixel(p) for p in sel).most_common(1)[0][0]
    stroke = [p for p in sel if img.getpixel(p) == color]
    new, path = clean_stroke(stroke)
    near = {(x + dx, y + dy) for x, y in path for dx in range(-2, 3) for dy in range(-2, 3)}
    out = img.copy()
    for p in stroke:  # apaga o traço velho (só perto do caminho; o resto da seleção fica como está)
        if p in near and p not in new:
            around = [img.getpixel(n) for n in ((p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1))
                      if 0 <= n[0] < w and 0 <= n[1] < h and img.getpixel(n) != color]
            out.putpixel(p, Counter(around).most_common(1)[0][0] if around else (0, 0, 0, 0))
    for x, y in new:
        if 0 <= x < w and 0 <= y < h:
            out.putpixel((x, y), color)
    out.save(dst)
    print(f"traço: {len(stroke)} px -> {len(new)} px")


# ---------- animação: compara os frames entre si ----------

def frames_too_different(grids, limit=.25):
    """Frames vizinhos trocam mais de 25% dos pixels: é rotação/troca de pose, não animação no tempo."""
    changes = []
    for i in range(len(grids)):
        a, b = grids[i - 1], grids[i]
        cells = [(p, q) for ra, rb in zip(a, b) for p, q in zip(ra, rb) if p is not T or q is not T]
        changes.append(sum(p != q for p, q in cells) / max(len(cells), 1))
    return sum(changes) / len(changes) > limit


def flicker(grids, r=2):
    """Line boiling: pixel que muda num frame só e volta (A-B-A entre vizinhos), numa área que fica parada
    (o quadrado 5x5 em volta é igual no frame anterior e no seguinte). Sugestão: voltar pra A.
    Devolve {(frame, x, y): cor | T}."""
    n, out = len(grids), {}
    if n < 3 or frames_too_different(grids):
        return out
    h, w = len(grids[0]), len(grids[0][0])
    for i in range(n):
        prev, cur, nxt = grids[i - 1], grids[i], grids[(i + 1) % n]  # animação em loop
        for y in range(h):
            for x in range(w):
                if prev[y][x] == nxt[y][x] != cur[y][x] and all(
                        at(prev, x + dx, y + dy) == at(nxt, x + dx, y + dy)
                        for dx in range(-r, r + 1) for dy in range(-r, r + 1)):
                    out[(i, x, y)] = prev[y][x]
    return out


def flashing_colors(grids, max_share=.25):
    """Cor que só aparece em poucos frames: na animação ela 'pisca'. Sugestão: a cor estável mais parecida."""
    n = len(grids)
    frames_of = {}
    for i, g in enumerate(grids):
        for c in {c for row in g for c in row if c is not T}:
            frames_of.setdefault(c, set()).add(i)
    dist = lambda a, b: sum((p - q) ** 2 for p, q in zip(a, b))
    rare = {c for c, fs in frames_of.items() if len(fs) / n <= max_share}
    stable = [c for c in frames_of if c not in rare]
    # quase idêntica a uma cor estável (ex: #010005 x #010006) não pisca de verdade: ninguém vê
    rare = {c for c in rare if all(dist(c, s) > 12 ** 2 for s in stable)}
    if not rare or not stable:
        return {}
    near = {c: min(stable, key=lambda s: (ramp_of(s) != ramp_of(c), dist(s, c))) for c in rare}
    return {(i, x, y): near[c] for i, g in enumerate(grids) for y, row in enumerate(g)
            for x, c in enumerate(row) if c in rare}


def baseline_report(grids):
    """Pé (base da silhueta) que muda de altura entre frames: o personagem 'pula' parado."""
    bottoms = [max((y for y, row in enumerate(g) if any(c is not T for c in row)), default=None) for g in grids]
    valid = [b for b in bottoms if b is not None]
    if not valid:
        return None
    usual = Counter(valid).most_common(1)[0][0]
    odd = [f"{i + 1} (y={b})" for i, b in enumerate(bottoms) if b is not None and b != usual]
    return (f"base dos pés muda em: {', '.join(odd)}; o normal é y={usual}") if odd else None


ANIM = {
    "tremendo": (flicker, (255, 255, 0), "pixel muda num frame só e volta (line boiling)",
                 "se a parte devia ficar parada, use a cor dos frames vizinhos"),
    "cor piscando": (flashing_colors, (255, 0, 255), "cor que só aparece em poucos frames",
                     "troque pela cor parecida que aparece nos outros frames"),
}


def anim(path, n, dst):
    """Recebe uma tira horizontal com n frames lado a lado. Salva: dst = tira de marcas,
    dst.txt = relatório (nome|problema|como|qtd), dst.fix = sugestões (nome frame x y r g b a)."""
    strip = Image.open(path).convert("RGBA")
    w, h = strip.width // n, strip.height
    grids = [[[strip.getpixel((i * w + x, y))[:3] if strip.getpixel((i * w + x, y))[3] >= 128 else T
               for x in range(w)] for y in range(h)] for i in range(n)]
    marks = Image.new("RGBA", strip.size)
    report, fixes, fixed = [], [], set()
    for name, (fn, color, why, how) in ANIM.items():
        found = fn(grids)
        for (i, x, y), sug in found.items():
            if marks.getpixel((i * w + x, y))[3] == 0:
                marks.putpixel((i * w + x, y), (*color, 255))
            if (i, x, y) in fixed:  # a 1ª checagem (tremida: volta à cor dos vizinhos) vence
                continue
            fixed.add((i, x, y))
            fixes.append(f"{name} {i + 1} {x} {y} " + ("0 0 0 0" if sug is T else f"{sug[0]} {sug[1]} {sug[2]} 255"))
        if found:
            per = Counter(i + 1 for i, _, _ in found)
            report.append(f"{name}|{why} (frames: {', '.join(f'{k}:{v}' for k, v in sorted(per.items()))})|{how}|{len(found)}")
    if frames_too_different(grids):
        report.append("dica|os frames mudam demais entre si (parece rotação ou troca de pose)|"
                      "'tremendo' foi desligado; ele só serve pra animação no tempo (idle, andar)|-")
    base = baseline_report(grids)
    if base:
        report.append(f"dica|{base}|se não for pulo/agachamento, alinhe os pés na mesma linha|-")
    marks.save(dst)
    with open(dst + ".txt", "w", encoding="utf-8") as out:
        out.write("\n".join(report))
    with open(dst + ".fix", "w", encoding="utf-8") as out:
        out.write("\n".join(fixes))
    print("\n".join(report) or "nada encontrado")


def recolor(f, remap):
    f = f.copy()
    f.putdata([(*remap[p[:3]], 255) if p[3] >= 128 else (0, 0, 0, 0) for p in f.getdata()])
    return f


def save_gif(frames, im, dst):
    frames[0].save(dst, save_all=True, append_images=frames[1:], loop=0, disposal=2,
                   duration=im.info.get("duration", 100), transparency=0)


def save(g, path, scale):
    h, w = len(g), len(g[0])
    img = Image.new("RGBA", (w, h))
    img.putdata([(0, 0, 0, 0) if c is T else (*c, 255) for row in g for c in row])
    img.save(path)
    if scale > 1:
        img.resize((w * scale, h * scale), Image.NEAREST).save(path.rsplit(".", 1)[0] + f"_x{scale}.png")


def test():
    K, W = (0, 0, 0), (255, 255, 255)
    # linha em L dentro do fundo: o cotovelo (x=1,y=2) some, pontas ficam
    g = [[W, W, W, W], [W, K, W, W], [W, K, K, W], [W, W, W, W]]
    r = pixel_perfect(g)
    assert r[2][1] == W and r[1][1] == K and r[2][2] == K, r
    # escada com cotovelos vira diagonal limpa
    g = [[W] * 5, [W, K, W, W, W], [W, K, K, W, W], [W, W, K, K, W], [W] * 5]
    r = pixel_perfect(g)
    assert sum(row.count(K) for row in r) == 3, r
    # pixel solto some
    g = [[W, W, W], [W, K, W], [W, W, W]]
    assert remove_orphans(g)[1][1] == W
    # quadrado cheio não é afetado
    g = [[K] * 3 for _ in range(3)]
    assert pixel_perfect(g) == g
    # contorno aparece só em volta do opaco
    g = [[T, T, T], [T, W, T], [T, T, T]]
    o = add_outline(g, K)
    assert o[0][1] == K and o[0][0] is T and o[1][1] == W
    # rampa: 4 tons viram 2, o escuro fica escuro e o claro fica claro
    r = build_ramp({(0, 0, 0): 10, (10, 10, 10): 1, (200, 200, 200): 5, (220, 220, 220): 5}, 2)
    assert len(set(r.values())) == 2 and r[(0, 0, 0)] == r[(10, 10, 10)] and r[(200, 200, 200)] == (210, 210, 210), r
    assert ramp_of((248, 192, 151)) == "pele" and ramp_of((0, 0, 0)) == "cabelo" and ramp_of((140, 1, 41)) == "vermelho"
    # tom solto do mesmo material some; brilho (outro material) fica
    S1, S2, Wt = (247, 187, 144), (233, 141, 104), (231, 241, 251)
    g = [[S1] * 3, [S1, S2, S1], [S1] * 3]
    assert clean_loose(g, {(1, 1): {"pele", "tecido"}})[1][1] == S1
    g = [[S1] * 3, [S1, Wt, S1], [S1] * 3]
    assert clean_loose(g, {(1, 1): {"pele", "tecido"}})[1][1] == Wt
    # pescoço cortado: linha preta entre queixo e pescoço, na altura do queixo
    g = [[K] * 3 for _ in range(10)]
    g[2][1], g[3][1], g[4][1] = S1, K, S1
    assert neck_cuts(g) == [(1, 3)], neck_cuts(g)
    g[3][1] = S2  # ligado com sombra de pele: ok
    assert neck_cuts(g) == []
    # degraus: topo da silhueta com escada 3-1-3 -> o degrau de 1 é marcado
    g = [[T] * 7 for _ in range(4)]
    for x, y0 in zip(range(7), (0, 0, 0, 1, 2, 2, 2)):
        for y in range(y0, 4):
            g[y][x] = K
    # sugestão: 3-1-3 vira 3-2-2 -> pinta (4, 1) com a cor da borda
    assert jaggies(g) == {(3, 1): NOFIX, (4, 1): K}, jaggies(g)
    # escada regular 2-2-2 não é marcada
    for x, y0 in zip(range(6), (0, 0, 1, 1, 2, 2)):
        for y in range(4):
            g[y][x] = K if y >= y0 else T
    g = [row[:6] for row in g]
    assert jaggies(g) == {}, jaggies(g)
    # contorno 2px: borda preta dupla antes da pele
    g = [[T, K, K, S1, S1] for _ in range(3)]
    assert thick_outline(g) == {(2, 1): S1}, thick_outline(g)  # só o do meio: os outros encostam fora da imagem
    # degrau de 2px na diagonal: o contorno corre na horizontal, não é espessura
    g = [[T, T, T, T], [T, K, K, S1], [T, T, T, K]]
    assert thick_outline(g) == {}, thick_outline(g)
    assert thick_outline([[T, K, S1, S1, S1]]) == {}
    # banding: duas fileiras de 3, cores diferentes, alinhadas
    g = [[S1, S1, S1, K], [S2, S2, S2, K]]
    assert {(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)} <= set(banding(g))
    assert banding([[S1, S1, S1, K], [S2, S2, K, K]]) == {}
    # cotovelo: canto em escada na borda é marcado; canto reto de 90° (bico de tênis) não
    g = [[T, T, T, T], [T, K, T, T], [T, K, K, T], [T, T, K, T]]
    assert (1, 2) in contour_elbows(g), contour_elbows(g)
    g = [[T, T, T, T], [T, K, K, K], [T, K, S1, S1], [T, K, S1, S1]]
    assert contour_elbows(g) == {}, contour_elbows(g)
    # pillow: quadrado de pele escuro na borda e claro no meio = pillow; degradê da esquerda pra direita = luz ok
    P1, P2, P3 = (215, 110, 89), (233, 141, 104), (247, 187, 144)
    ring = lambda x, y: min(x, y, 6 - x, 6 - y)
    g = [[(P1, P2, P3, P3)[ring(x, y)] for x in range(7)] for y in range(7)]
    assert len(pillow_shading(g)) == 24, len(pillow_shading(g))
    g = [[(P1, P1, P2, P2, P2, P3, P3)[x] for x in range(7)] for y in range(7)]
    assert pillow_shading(g) == {}
    # mistura: preto e vermelho bem escuro encostados
    assert sorted(blending([[(25, 18, 42), (56, 0, 24)]])) == [(0, 0), (1, 0)]  # azul-escuro x vermelho-escuro
    assert blending([[(25, 18, 42), (38, 32, 56)]]) == {}  # dois azuis = sombreamento
    assert blending([[(0, 0, 2), S1]]) == {}
    # limpar traço: reta tremida 20x5 vira degraus regulares, ligada, pontas no lugar
    import random
    random.seed(1)
    wobbly = {(x, round(x / 4 + random.choice((0, 0, .6, -.6)))) for x in range(21)}
    clean, path = clean_stroke(wobbly)
    pts = sorted(clean)
    assert {path[0], path[-1]} <= clean, "pontas mudaram"
    assert all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1 for a, b in zip(pts, pts[1:])), pts
    runs = [len([p for p in pts if p[1] == y]) for y in sorted({p[1] for p in pts})]
    assert max(runs[1:-1]) - min(runs[1:-1]) <= 1, runs  # degraus do meio: no máximo 1px de diferença
    # animação: pixel A-B-A é tremida; cor que só existe em 1 de 4 frames pisca
    A, B = (10, 10, 10), (200, 200, 200)
    base = [[A] * 6 for _ in range(6)]
    odd = [row[:] for row in base]
    odd[3][3] = B
    fr = [base, odd, base, base]
    assert flicker(fr) == {(1, 3, 3): A}, flicker(fr)
    assert flashing_colors(fr) == {(1, 3, 3): A}, flashing_colors(fr)
    # frames bem diferentes entre si (rotação): tremida desligada
    other = [[B] * 6 for _ in range(6)]
    assert flicker([base, other, base, other]) == {}
    print("ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--size", type=int, help="largura final em pixels (ex: 16, 32, 64)")
    ap.add_argument("--colors", type=int, default=16, help="nº de cores se não houver --palette")
    ap.add_argument("--palette", help="PNG com as cores da paleta do jogo")
    ap.add_argument("--outline", help="cor hex do contorno, ex: 1a1c2c")
    ap.add_argument("--scale", type=int, default=8, help="salva também uma prévia ampliada")
    ap.add_argument("--check", action="store_true", help="só diagnostica; dst vira o mapa de problemas")
    ap.add_argument("--merge", type=int, metavar="DIST", help="só junta cores com diferença < DIST (ex: 20)")
    ap.add_argument("--ramps", metavar="PALETA.png", help="monta rampas fixas (pele, cabelo...) e salva a paleta aqui")
    ap.add_argument("--clean", metavar="MAPA.png", help="tira pixels soltos só no rosto, punhos e botas")
    ap.add_argument("--sym", action="store_true", help="só aponta diferenças entre lados (rosto, mãos, botas)")
    ap.add_argument("--trace", metavar="SELECAO.png", help="limpa o traço dentro da seleção (Aseprite)")
    ap.add_argument("--anim", type=int, metavar="N", help="tira com N frames -> checagens de animação (Aseprite)")
    ap.add_argument("--lint", action="store_true", help="1 frame -> camada de marcas + .txt (usado pelo Aseprite)")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test:
        test()
    elif a.check:
        check(a.src, a.dst, a.scale)
    elif a.trace:
        trace(a.src, a.trace, a.dst)
    elif a.anim:
        anim(a.src, a.anim, a.dst)
    elif a.lint:
        lint(a.src, a.dst)
    elif a.sym:
        sym_gif(a.src, a.dst)
    elif a.clean:
        clean_gif(a.src, a.dst, a.clean)
    elif a.ramps:
        ramps_gif(a.src, a.dst, a.ramps)
    elif a.merge:
        merge_gif(a.src, a.dst, a.merge)
    else:
        g = load_grid(a.src, a.size, a.colors, a.palette)
        g = pixel_perfect(remove_orphans(g))
        if a.outline:
            g = add_outline(g, tuple(bytes.fromhex(a.outline)))
        save(g, a.dst, a.scale)
        print("salvo:", a.dst)
