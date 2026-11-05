"""Gera a imagem (PNG/PDF) do cardápio da padaria usando Pillow."""
import io
import math
import re
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageOps

LARGURA = 1240
ALTURA_MIN = 1600
MARGEM = 90
COL_ESQ = 520         
COL_DIR_X = MARGEM + COL_ESQ + 60
RODAPE = 130          
ORNAMENTO = 150      


TEMAS = {
    "Azul da fachada": ("#17306B", "#F5C84C", "#FFFFFF"),
    "Chocolate":       ("#5E2C1A", "#FFF3C4", "#FFFFFF"),
    "Creme":           ("#FFF6E5", "#8A4B14", "#3B2A1E"),
    "Verde":           ("#1F4D3A", "#F4D58D", "#FFFFFF"),
}

FONTES_BOLD = ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "LiberationSans-Bold.ttf",
               "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "Helvetica.ttc")
FONTES_REG = ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "LiberationSans-Regular.ttf",
              "/System/Library/Fonts/Supplemental/Arial.ttf", "Helvetica.ttc")
FONTES_ITALIC = ("DejaVuSerif-Italic.ttf", "georgiai.ttf", "Georgia Italic.ttf", "LiberationSerif-Italic.ttf",
                 "/System/Library/Fonts/Supplemental/Georgia Italic.ttf", "timesi.ttf")
# serifada negrito para o nome e as seções (Georgia no Windows/Mac)
FONTES_SERIF_BOLD = ("georgiab.ttf", "Georgia Bold.ttf", "DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf",
                     "/System/Library/Fonts/Supplemental/Georgia Bold.ttf", "timesbd.ttf")


@lru_cache(maxsize=None)          # carregar fonte do disco é lento; faz uma vez só
def _fonte(candidatas, tamanho):
    for nome in candidatas:
        try:
            return ImageFont.truetype(nome, tamanho)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=tamanho)
    except TypeError:
        return ImageFont.load_default()


def formatar_preco(texto):
    """'40' -> 'R$40,00'. Se não for número, devolve o texto como foi digitado."""
    t = str(texto).strip()
    if not t:
        return ""
    limpo = re.sub(r"[^\d,.\-]", "", t)
    try:
        if "," in limpo:
            limpo = limpo.replace(".", "").replace(",", ".")
        valor = float(limpo)
        return "R$" + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except ValueError:
        return t


def _quebrar(draw, texto, fonte, largura_max):
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = (atual + " " + palavra).strip()
        if draw.textlength(teste, font=fonte) <= largura_max:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def _hex(cor):
    cor = cor.lstrip("#")
    return tuple(int(cor[i:i + 2], 16) for i in (0, 2, 4))


def _misturar(a, b, p):
    """Mistura duas cores: p=0 -> a, p=1 -> b."""
    return tuple(int(x * (1 - p) + y * p) for x, y in zip(a, b))


def _graos(d, cx, cy, comp, larg, ang, cor):
    """Elipse inclinada (um grão de trigo)."""
    pts = []
    for k in range(14):
        t = 2 * math.pi * k / 14
        x, y = comp / 2 * math.cos(t), larg / 2 * math.sin(t)
        pts.append((cx + x * math.cos(ang) - y * math.sin(ang),
                    cy + x * math.sin(ang) + y * math.cos(ang)))
    d.polygon(pts, fill=cor)


def _espiga(d, x, y_base, altura, cor):
    """Espiga de trigo: caule + grãos aos pares."""
    d.line((x, y_base, x, y_base - altura * 0.7), fill=cor, width=4)
    n = 5
    for k in range(n):
        yy = y_base - altura * 0.30 - k * altura * 0.115
        tam = altura * 0.20 * (1 - k * 0.08)
        for lado in (-1, 1):
            _graos(d, x + lado * tam * 0.30, yy - tam * 0.2, tam, tam * 0.40,
                   -math.pi / 2 + lado * 0.6, cor)
    _graos(d, x, y_base - altura + altura * 0.1, altura * 0.20, altura * 0.08, -math.pi / 2, cor)


def _texto_espacado(d, xy, texto, fonte, cor, espaco):
    """Texto com espaço extra entre as letras (como 'P A N I F I C A D O R A' da fachada)."""
    x, y = xy
    for ch in texto:
        d.text((x, y), ch, font=fonte, fill=cor)
        x += d.textlength(ch, font=fonte) + espaco


def reduzir_foto(dados, lado_max=1200):
    """Diminui a foto logo que ela chega: deixa tudo mais leve no PC lento."""
    foto = ImageOps.exif_transpose(Image.open(io.BytesIO(dados))).convert("RGB")
    foto.thumbnail((lado_max, lado_max))
    buf = io.BytesIO()
    foto.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def renderizar_cardapio(nome, slogan, secoes, foto_bytes=None,
                        cor_fundo="#17306B", cor_titulo="#F5C84C", cor_texto="#FFFFFF",
                        sobretitulo="", telefone="", endereco=""):
    """secoes = [{"nome": "PÃES", "itens": [{"titulo","descricao","preco"}]}]"""
    fundo, c_titulo, c_texto = _hex(cor_fundo), _hex(cor_titulo), _hex(cor_texto)
    c_desc = _misturar(c_texto, fundo, 0.28)
    c_linha = _misturar(c_titulo, fundo, 0.55)     # pontilhado e filetes, mais discretos

    f_sobre = _fonte(FONTES_BOLD, 34)
    f_slogan = _fonte(FONTES_ITALIC, 40)
    f_secao = _fonte(FONTES_SERIF_BOLD, 74)
    f_item = _fonte(FONTES_REG, 34)
    f_desc = _fonte(FONTES_REG, 26)

    medidor = ImageDraw.Draw(Image.new("RGB", (10, 10)))


    for tam_nome in range(96, 43, -4):
        f_nome = _fonte(FONTES_SERIF_BOLD, tam_nome)
        if all(medidor.textlength(p, font=f_nome) <= COL_ESQ for p in nome.upper().split()):
            break

    larg_dir = LARGURA - MARGEM - COL_DIR_X

    # ---- mede a coluna esquerda ----
    linhas_nome = _quebrar(medidor, nome.upper(), f_nome, COL_ESQ)
    linhas_slogan = _quebrar(medidor, slogan, f_slogan, COL_ESQ) if slogan.strip() else []
    y_esq = MARGEM + (62 if sobretitulo.strip() else 0)
    passo_nome = int(tam_nome * 1.22)
    y_esq += passo_nome * len(linhas_nome)
    if linhas_slogan:
        y_esq += 15 + 52 * len(linhas_slogan)
    y_orn = y_esq + 50
    y_esq = y_orn + ORNAMENTO + 40

    # ---- mede a coluna direita ----
    y = MARGEM
    layout = []
    for sec in secoes:
        if not sec["itens"] and not sec["nome"].strip():
            continue
        layout.append(("secao", sec["nome"].upper(), y))
        y += 125
        for it in sec["itens"]:
            desc = _quebrar(medidor, it["descricao"], f_desc, larg_dir) if it["descricao"].strip() else []
            layout.append(("item", it, y, desc))
            y += 52 + 34 * len(desc) + (14 if desc else 8)
        y += 70

    rodape = [t for t in (f"Telefone: {telefone.strip()}" if telefone.strip() else "",
                          endereco.strip()) if t]
    alt_rodape = RODAPE if rodape else 0
    corpo = max(ALTURA_MIN - alt_rodape, y + MARGEM - 30, y_esq + 300 + MARGEM)
    altura = corpo + alt_rodape

    img = Image.new("RGB", (LARGURA, altura), fundo)
    d = ImageDraw.Draw(img)

    yy = MARGEM
    if sobretitulo.strip():
        _texto_espacado(d, (MARGEM, yy), sobretitulo.upper(), f_sobre, c_titulo, 8)
        yy += 62
    for linha in linhas_nome:
        d.text((MARGEM, yy), linha, font=f_nome, fill=c_titulo)
        yy += passo_nome
    if linhas_slogan:
        yy += 15
        for linha in linhas_slogan:
            d.text((MARGEM, yy), linha, font=f_slogan, fill=c_titulo)
            yy += 52
    for k, alt in enumerate((ORNAMENTO - 20, ORNAMENTO, ORNAMENTO - 20)):
        _espiga(d, MARGEM + 40 + k * 70, y_orn + ORNAMENTO, alt, c_titulo)


    if foto_bytes:
        try:
            foto = Image.open(io.BytesIO(foto_bytes))
            foto = ImageOps.exif_transpose(foto).convert("RGB")
            alt_foto = min(700, corpo - MARGEM - y_esq)
            foto = ImageOps.fit(foto, (COL_ESQ, alt_foto), Image.LANCZOS)
            mascara = Image.new("L", foto.size, 0)
            ImageDraw.Draw(mascara).rounded_rectangle((0, 0, *foto.size), 28, fill=255)
            img.paste(foto, (MARGEM, corpo - MARGEM - alt_foto), mascara)
        except Exception:
            pass


    for bloco in layout:
        if bloco[0] == "secao":
            d.text((COL_DIR_X, bloco[2]), bloco[1], font=f_secao, fill=c_titulo)
            d.line((COL_DIR_X, bloco[2] + 98, LARGURA - MARGEM, bloco[2] + 98), fill=c_linha, width=3)
        else:
            _, it, y0, desc = bloco
            titulo = it["titulo"]
            preco = formatar_preco(it["preco"])
            # o título só perde espaço para o preço que realmente existe
            larg_titulo_item = larg_dir - (d.textlength(preco, font=f_item) + 30 if preco else 0)
            if d.textlength(titulo, font=f_item) > larg_titulo_item:
                while d.textlength(titulo + "...", font=f_item) > larg_titulo_item and len(titulo) > 4:
                    titulo = titulo[:-1]
                titulo = titulo.rstrip() + "..."
            d.text((COL_DIR_X, y0), titulo, font=f_item, fill=c_texto)
            if preco:
                x_preco = LARGURA - MARGEM - d.textlength(preco, font=f_item)
                d.text((x_preco, y0), preco, font=f_item, fill=c_texto)
                x = COL_DIR_X + d.textlength(titulo, font=f_item) + 16      # pontilhado até o preço
                while x < x_preco - 16:
                    d.ellipse((x, y0 + 28, x + 4, y0 + 32), fill=c_linha)
                    x += 14
            for i, linha in enumerate(desc):
                d.text((COL_DIR_X, y0 + 46 + 34 * i), linha, font=f_desc, fill=c_desc)

    if rodape:
        topo = altura - RODAPE
        d.line((MARGEM, topo, LARGURA - MARGEM, topo), fill=c_linha, width=3)
        yr = topo + (38 if len(rodape) == 2 else 48)
        for i, texto in enumerate(rodape):
            fonte = f_item if i == 0 else f_desc
            d.text(((LARGURA - d.textlength(texto, font=fonte)) / 2, yr), texto, font=fonte,
                   fill=c_titulo if i == 0 else c_desc)
            yr += 48
    return img


def para_png(img):
    buf = io.BytesIO()
    img.save(buf, "PNG", compress_level=1)      # compressão rápida: o PC da padaria agradece
    return buf.getvalue()


def para_pdf(img):
    buf = io.BytesIO()
    img.save(buf, "PDF", resolution=150)
    return buf.getvalue()


def para_preview(img, largura=900):
    """Versão pequena e leve só para mostrar na tela."""
    pequena = img.resize((largura, round(img.height * largura / img.width)), Image.BILINEAR)
    buf = io.BytesIO()
    pequena.save(buf, "JPEG", quality=85)
    return buf.getvalue()
