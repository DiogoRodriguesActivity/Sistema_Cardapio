"""Gerador de Cardápio para Padaria.  Execute com:  streamlit run app.py"""
import json
from pathlib import Path
import streamlit as st
from menu_render import (renderizar_cardapio, para_png, para_preview,
                         formatar_preco, reduzir_foto, TEMAS)

st.set_page_config(page_title="Cardápio da Padaria", page_icon="🥖", layout="wide")
st.title("Gerador de Cardápio da Padaria")

# O cardápio fica salvo nesta pasta: ao fechar e abrir de novo, tudo continua aqui.
PASTA = Path(__file__).parent
ARQ_DADOS = PASTA / "cardapio_salvo.json"
ARQ_FOTO = PASTA / "cardapio_foto.jpg"


def carregar():
    try:
        return json.loads(ARQ_DADOS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def salvar(dados, foto):
    try:
        texto = json.dumps(dados, ensure_ascii=False, indent=1)
        if texto != st.session_state.get("ultimo_json"):
            ARQ_DADOS.write_text(texto, encoding="utf-8")
            st.session_state.ultimo_json = texto
        h = hash(foto) if foto else None
        if h != st.session_state.get("ultima_foto"):
            if foto:
                ARQ_FOTO.write_bytes(foto)
            elif ARQ_FOTO.exists():
                ARQ_FOTO.unlink()
            st.session_state.ultima_foto = h
    except OSError:
        pass  # pasta sem permissão de escrita: o cardápio funciona, só não fica salvo


def novo_id():
    st.session_state.prox_id += 1
    return st.session_state.prox_id


@st.cache_data(show_spinner=False, max_entries=6)
def gerar(nome, slogan, sobre, tel, end, secoes, foto, tema):
    """Só redesenha quando algo muda; PNG e prévia saem de uma vez."""
    img = renderizar_cardapio(nome, slogan, secoes, foto, *TEMAS[tema],
                              sobretitulo=sobre, telefone=tel, endereco=end)
    return para_png(img), para_preview(img)


# ---------------- estado ----------------
if "secoes" not in st.session_state:
    st.session_state.salvo = carregar()
    st.session_state.prox_id = 0
    secoes = st.session_state.salvo.get("secoes") or [{"nome": "PÃES", "itens": []},
                                                      {"nome": "DOCES", "itens": []}]
    for s in secoes:
        s["id"] = novo_id()          # id fixo: evita misturar campos ao excluir uma seção
    st.session_state.secoes = secoes
    st.session_state.foto = ARQ_FOTO.read_bytes() if ARQ_FOTO.exists() else None
salvo = st.session_state.salvo


def usar_foto(arquivo):
    ident = (arquivo.name, arquivo.size)
    if st.session_state.get("foto_id") != ident:      # só reduz uma vez por foto nova
        st.session_state.foto_id = ident
        st.session_state.foto = reduzir_foto(arquivo.getvalue())


# ---------------- barra lateral ----------------
with st.sidebar:
    st.header("🏪 Padaria")
    sobre = st.text_input("Linha pequena acima do nome", salvo.get("sobretitulo", "Panificadora"))
    nome = st.text_input("Nome da padaria", salvo.get("nome", "Delícias & Sabores"))
    slogan = st.text_input("Slogan", salvo.get("slogan", "Tradição e sabor em cada fornada"))
    telefone = st.text_input("Telefone", salvo.get("telefone", "(31) 3191-6678"))
    endereco = st.text_input("Endereço (opcional)", salvo.get("endereco", ""))

    st.header("🎨 Cores")
    temas = list(TEMAS)
    tema = st.radio("Escolha um tema", temas,
                    index=temas.index(salvo["tema"]) if salvo.get("tema") in TEMAS else 0)

col_edit, col_prev = st.columns([1, 1], gap="large")

with col_edit:
    # ---------------- foto ----------------
    st.subheader("📷 Foto")
    arq = st.file_uploader("Imagem (JPG/PNG)", type=["jpg", "jpeg", "png"])
    if arq:
        usar_foto(arq)
    if st.session_state.foto and st.button("🗑️ Remover foto"):
        st.session_state.foto = None
        st.rerun()

    # ---------------- seções e itens ----------------
    st.subheader("📝 Itens do cardápio")
    for i, sec in enumerate(st.session_state.secoes):
        sid = sec["id"]
        with st.expander(f"{sec['nome'] or 'Nova seção'}  ({len(sec['itens'])} itens)", expanded=True):
            sec["nome"] = st.text_input("Nome da seção", sec["nome"], key=f"sec_{sid}")

            with st.form(f"form_{sid}", clear_on_submit=True):
                c1, c2, c3 = st.columns([2, 3, 1.3])
                titulo = c1.text_input("Título", placeholder="Pão de Queijo")
                descricao = c2.text_input("Descrição", placeholder="Opcional")
                preco = c3.text_input("Preço", placeholder="12,00")
                if st.form_submit_button("➕ Adicionar item"):
                    if titulo.strip():
                        sec["itens"].append({"titulo": titulo.strip(),
                                             "descricao": descricao.strip(),
                                             "preco": preco.strip()})
                        st.rerun()
                    else:
                        st.warning("Digite pelo menos o título.")

            for j, it in enumerate(sec["itens"]):
                a, c = st.columns([8, 1])
                a.markdown(f"**{it['titulo']}** {formatar_preco(it['preco'])}")
                if c.button("❌", key=f"del_{sid}_{j}"):
                    sec["itens"].pop(j)
                    st.rerun()

            if st.button("🗑️ Excluir seção", key=f"delsec_{sid}"):
                st.session_state.secoes.pop(i)
                st.rerun()

    if st.button("➕ Nova seção"):
        st.session_state.secoes.append({"id": novo_id(), "nome": "", "itens": []})
        st.rerun()

# ---------------- pré-visualização e download ----------------
with col_prev:
    st.subheader("Pré-visualização")
    png, prev = gerar(nome, slogan, sobre, telefone, endereco, st.session_state.secoes,
                      st.session_state.foto, tema)
    st.image(prev, use_container_width=True)
    st.download_button("Baixar cardápio (PNG)", png, "cardapio.png", "image/png", use_container_width=True)

salvar({"sobretitulo": sobre, "nome": nome, "slogan": slogan, "telefone": telefone,
        "endereco": endereco, "tema": tema,
        "secoes": st.session_state.secoes}, st.session_state.foto)