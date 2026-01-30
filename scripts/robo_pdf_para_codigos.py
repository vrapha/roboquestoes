# -*- coding: utf-8 -*-
"""
EXTRAÇÃO DE QUESTÕES - (AD / ESP) - VERSÃO MELHORADA

✅ Lê SUMÁRIO (primeiras 12 páginas) e pega:
   - "QUESTÕES EXTRAS .... <página>"
   - "COMENTÁRIOS E GABARITOS .... <página>"
✅ Extrai apenas o intervalo: QUESTÕES EXTRAS -> antes de COMENTÁRIOS
✅ Separa blocos por numeração "1.", "2.", ...
✅ Classifica:
   - 🔵 ACESSO DIRETO (se o bloco contém "ACESSO DIRETO")
   - ⚪ ESP (qualquer outra)
✅ Busca no site:
   - tenta várias queries (texto completo, sem acento, limpo, trechos, janelas, prefixos etc.)
   - valida por enunciado + alternativas (fuzzy tolerante)
   - prioridade: candidatos AD primeiro
   - achou ALTA => para e vai para a próxima (rápido)
✅ Se uma questão ACESSO DIRETO não for encontrada:
   - adiciona NO FINAL do CSV: "Q{n} ACESSO DIRETO (NÃO ENCONTRADA)"

🛠 Ajustes pontuais (mantendo a lógica boa/rápida):
   1) CERTO/ERRADO (A/B) agora entra (não é descartada por ter só 2 alternativas).
   2) PDF com letra repetida (A/A): não sobrescreve; realoca para letra livre.
   3) Fallback super conservador: se enunciado bate MUITO alto, aceita com 2 alternativas OK.
   4) Queries extras removendo início genérico ("Mulher/Homem de XX anos...").

🔧 AJUSTES FINOS (mantendo toda lógica original):
   5) Validação CERTO/ERRADO mais flexível: aceita 1 alternativa OK se enunciado >= 85
   6) Validação com letras duplicadas: conta alternativas únicas, não letras
   7) Fallback extra: enunciado >= 92 + pelo menos 1 alternativa OK = aceita

✅ FIX IMPORTANTE (Playwright / Login):
   - Se debug/storage_state.json NÃO existir: abre navegador, você loga, e o script salva a sessão.
   - Se existir mas a sessão estiver expirada: abre, você loga, e o script regrava a sessão.

⚠️ IMPORTANTE:
- O seu arquivo estava com um bloco duplicado de "if login" FORA da função.
  Isso causava: name 'url' is not defined / name 'page' is not defined.
  Aqui está corrigido: só existe UMA rotina de login, dentro da função.
"""

from __future__ import annotations

import re
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import fitz  # PyMuPDF
import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from rapidfuzz import fuzz
from unidecode import unidecode


# =========================
# CONFIG
# =========================
QUESTIONS_URL = "https://manager.eumedicoresidente.com.br/admin/resources/Question"

# >>> coloque seu PDF aqui (dentro de inputs/)
PDF_PATH = r"inputs\EXTENSIVO_-_Sepse_Neonatal_e_InfecÃ§Ãµes_CongÃªnitas_-_APOSTILA_2025_20250331022148.pdf"

HEADLESS = False

OUT_CODES_CSV = Path("outputs") / "codigos.csv"
CSV_WITH_HEADER = True
TARGET_ENCONTRADAS = 30

# DEBUG (desligue para não poluir o terminal)
DEBUG = False
DEBUG_QS = {6, 14}  # questões que você quer debugar quando DEBUG=True

# Matching
MIN_WORDS_ENUNCIADO = 4
TOKEN_SET_ENUNCIADO = 85
PARTIAL_ENUNCIADO = 88

ALTERNATIVA_TOKEN_SET = 80
ALTERNATIVA_PARTIAL = 83

# Paginação
MAX_PAGES_GENERIC = 14
MAX_PAGES_SPECIFIC = 6
ROWS_PER_PAGE_GENERIC = 50
ROWS_PER_PAGE_SPECIFIC = 25

# Queries
MAX_QUERY_CHARS = 1400
REMOVE_PAREN_CONTENT = True

# Sessão Playwright (site)
STORAGE_STATE = "debug/storage_state.json"

# Índices da tabela no admin
SPECIALTY_TD_INDEX = 3

# Performance / early-stops
MAX_QUERIES_PER_QUESTION = 12
MAX_SEEN_CODES_BEFORE_STOP = 30

EARLY_STOP_IF_GOOD_MEDIA = True
MEDIA_EARLY_MIN_ENUN = 90
MEDIA_EARLY_MIN_ALT_RATIO = 0.70

QUICK_STOP_AFTER_QUERIES = 5
QUICK_STOP_MIN_SCORE = 88

STOPWORDS = {
    "a", "o", "os", "as", "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas",
    "e", "ou", "para", "por", "com", "sem", "ao", "aos", "à", "às",
    "que", "qual", "quais", "quando", "onde", "como",
    "assinale", "marque", "indique", "alternativa", "correta", "incorreta", "errada",
    "sobre", "respeito", "relacao", "relacionada", "paciente",
}


# =========================
# SMALL UTILS
# =========================
def dprint(*args, **kwargs):
    """Print de debug controlado por flag."""
    if DEBUG:
        print(*args, **kwargs)


def compact_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def normalize_text(s: str) -> str:
    s = (s or "").lower()
    s = unidecode(s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_for_comparison(s: str) -> str:
    s = normalize_text(s)
    palavras_irrelevantes = [
        "lembre se", "lembrese", "observe", "considere", "assinale",
        "marque", "indique", "dessa forma", "nesse caso", "diante disso",
        "portanto", "logo", "assim", "correta", "incorreta", "verdadeira",
        "falsa", "correto", "incorreto",
    ]
    for palavra in palavras_irrelevantes:
        s = s.replace(palavra, " ")
    s = re.sub(r"\b\d+\b", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def count_pdf_alternatives(pdf_alts: Dict[str, str]) -> int:
    """Conta alternativas únicas (ignora se valor é duplicado)."""
    valores_unicos = set()
    for k in ["A", "B", "C", "D", "E"]:
        if k in pdf_alts and (pdf_alts[k] or "").strip():
            valores_unicos.add(pdf_alts[k].strip())
    return len(valores_unicos)


def is_certo_errado_alts(alts: Dict[str, str]) -> bool:
    if not alts:
        return False
    vals = " ".join((alts.get("A", ""), alts.get("B", ""))).upper()
    return ("CERTO" in vals) or ("ERRADO" in vals)


# =========================
# SUMÁRIO -> RANGE
# =========================
def find_section_pages_via_sumario(pdf_path: str) -> Tuple[int, int]:
    doc = fitz.open(pdf_path)
    max_scan = min(12, doc.page_count)
    parts = []
    for i in range(max_scan):
        t = doc.load_page(i).get_text("text") or ""
        if t.strip():
            parts.append(t)
    doc.close()

    blob = "\n".join(parts)

    m_q = re.search(r"QUEST[ÕO]ES\s+EXTRAS\s+\.{2,}\s*(\d{1,4})\s*$", blob, re.I | re.M)
    m_c = re.search(r"COMENT[ÁA]RIOS\s+E\s+GABARITOS\s+\.{2,}\s*(\d{1,4})\s*$", blob, re.I | re.M)

    if not m_q or not m_c:
        raise RuntimeError(
            "Não consegui localizar no SUMÁRIO:\n"
            f" - QUESTÕES EXTRAS: {'OK' if m_q else 'NÃO'}\n"
            f" - COMENTÁRIOS E GABARITOS: {'OK' if m_c else 'NÃO'}\n"
        )

    start_q_1 = int(m_q.group(1))
    start_c_1 = int(m_c.group(1))

    if start_c_1 <= start_q_1:
        raise RuntimeError(f"SUMÁRIO inconsistente: comentários ({start_c_1}) <= questões extras ({start_q_1}).")

    return start_q_1, start_c_1


def get_extras_range_0based(pdf_path: str) -> Tuple[int, int]:
    start_q_1, start_c_1 = find_section_pages_via_sumario(pdf_path)
    return start_q_1 - 1, start_c_1 - 1


def extract_text_from_page_range(pdf_path: str, start_page: int, end_page_exclusive: int) -> str:
    doc = fitz.open(pdf_path)
    end = min(end_page_exclusive, doc.page_count)
    parts = []
    for i in range(start_page, end):
        t = doc.load_page(i).get_text("text") or ""
        if t.strip():
            parts.append(t)
    doc.close()

    full_text = "\n".join(parts)

    if DEBUG:
        try:
            Path("debug").mkdir(parents=True, exist_ok=True)
            with open("debug/raw_text_dump.txt", "w", encoding="utf-8") as f:
                f.write(full_text)
            dprint(f"    📄 DEBUG: Texto bruto salvo em debug/raw_text_dump.txt ({len(full_text)} chars)")
        except Exception as e:
            dprint(f"    ⚠️ Falha ao salvar debug text: {e}")

    return full_text


# =========================
# QUESTION STRUCTS
# =========================
@dataclass
class QuestionBlock:
    numero: Optional[int]
    tipo: str
    enunciado: str
    alternativas: Dict[str, str]
    texto_completo: str


# =========================
# PARSING DAS QUESTÕES
# =========================
def extract_alternativas(texto: str) -> Dict[str, str]:
    """
    - Captura alternativas A–E
    - Captura CERTO/ERRADO (A/B)
    - Tolerante a letra repetida (A/A etc) sem sobrescrever
    - Regex flexível para pegar " A. " mesmo sem quebra de linha
    """
    alternativas: Dict[str, str] = {}

    realloc_order = {
        "A": ["B", "C", "D", "E"],
        "B": ["C", "D", "E", "A"],
        "C": ["D", "E", "A", "B"],
        "D": ["E", "A", "B", "C"],
        "E": ["A", "B", "C", "D"],
    }

    # separa por: quebra OU espaço + "A.) " / "A- " etc
    partes = re.split(
        r"(?:(?:\r?\n)|(?:\s+))([A-E])[\)\.]\s+|(?:(?:\r?\n)|(?:\s+))([A-E])\s*-\s*",
        texto or "",
    )

    letra_atual = None
    for parte in partes:
        if parte is None:
            continue
        parte = parte.strip()

        if parte in ["A", "B", "C", "D", "E"]:
            letra_atual = parte
            continue

        if letra_atual and parte:
            valor = compact_spaces(parte)

            if letra_atual in alternativas:
                ordem = realloc_order.get(letra_atual, ["B", "C", "D", "E"])
                realocada = False
                for fb in ordem:
                    if fb not in alternativas:
                        alternativas[fb] = valor
                        realocada = True
                        dprint(f"      Reallocating duplicate {letra_atual} -> {fb} for content '{valor[:15]}...'")
                        break

                if not realocada:
                    alternativas[letra_atual] = compact_spaces(alternativas[letra_atual] + " " + valor)
            else:
                alternativas[letra_atual] = valor

            letra_atual = None

    # normaliza CERTO/ERRADO
    for k in ["A", "B"]:
        if k in alternativas:
            v = alternativas[k].strip().upper()
            if "CERTO" in v:
                alternativas[k] = "CERTO"
            elif "ERRADO" in v:
                alternativas[k] = "ERRADO"

    return alternativas


def extract_questao_completa(block: str) -> QuestionBlock:
    texto_completo = (block or "").strip()

    numero = None
    m = re.match(r"^\s*(\d+)\s*\.\s", texto_completo)
    if m:
        numero = int(m.group(1))

    if DEBUG and numero in DEBUG_QS:
        dprint(f"\n    📦 RAW BLOCK Q{numero} (len={len(texto_completo)}):")
        dprint(repr(texto_completo))

    tipo = "ACESSO_DIRETO" if "acesso direto" in texto_completo.lower() else "ESPECIALIDADE"

    texto = re.sub(r"^\s*\d+\.\s*", "", texto_completo)
    texto = re.sub(r"^.*?\bACESSO\s+DIRETO\b\s*\.\s*", "", texto, flags=re.I | re.S)
    texto = re.sub(r"^[A-Z\-\s0-9]+\d{4}.*?\.\s*", "", texto)

    match_alts = re.search(r"(?:\r?\n)\s*([A-E][\)\.]\s*|[A-E]\s*-\s*)", texto)
    if not match_alts:
        match_alts = re.search(r"(\s+[A-E][\)\.]\s+)", texto)
    if not match_alts:
        match_alts = re.search(r"(\s*[A-E][\)\.]\s*(?:CERTO|ERRADO))", texto, re.I)

    if match_alts:
        enunciado = texto[:match_alts.start()].strip()
        texto_alts = "\n" + texto[match_alts.start():].strip()

        if DEBUG and numero in DEBUG_QS:
            dprint(f"    🧩 DEBUG SPLIT Q{numero}:")
            dprint(f"       Split Index: {match_alts.start()}")
            dprint(f"       Enunciado End: {enunciado[-30:]!r}")
            dprint(f"       Alts Start (adjusted): {texto_alts[:30]!r}")
    else:
        enunciado = texto.strip()
        texto_alts = ""

    enunciado = re.sub(r"\bacesso\s+direto\b", "", enunciado, flags=re.I)
    enunciado = compact_spaces(enunciado)
    alternativas = extract_alternativas(texto_alts)

    if DEBUG and numero in DEBUG_QS:
        dprint(f"\n    📋 DEBUG PARSING Q{numero}:")
        dprint(f"       Tipo: {tipo}")
        dprint(f"       Alternativas extraídas: {len(alternativas)} → {list(alternativas.keys())}")
        dprint(f"       Enunciado: {enunciado[:150]}...")

    return QuestionBlock(
        numero=numero,
        tipo=tipo,
        enunciado=enunciado,
        alternativas=alternativas,
        texto_completo=texto_completo,
    )


def split_blocks_by_numbering(text: str) -> List[str]:
    text2 = re.sub(r"(?m)^\s*(\d+)\s*\.\s*", r"\n@@QSTART@@\1. ", text or "")
    parts = text2.split("@@QSTART@@")

    blocks = []
    for p in parts:
        p = p.strip()
        if p and re.match(r"^\d+\.\s", p):
            blocks.append(p)

    if DEBUG:
        nums = []
        for b in blocks:
            m = re.match(r"^(\d+)\.", b)
            if m:
                nums.append(m.group(1))
        dprint(f"    🔍 DEBUG: Blocos identificados (IDs): {nums}")

    return blocks


def parse_questoes_from_pdf(pdf_path: str) -> Tuple[List[QuestionBlock], List[QuestionBlock]]:
    start0, end_excl = get_extras_range_0based(pdf_path)
    print(f"✅ Recorte pelo SUMÁRIO: páginas {start0 + 1} até {end_excl} (1-based)")

    text = extract_text_from_page_range(pdf_path, start0, end_excl)
    blocks = split_blocks_by_numbering(text)
    print(f"📄 {len(blocks)} questões encontradas no intervalo recortado")

    acesso_direto: List[QuestionBlock] = []
    outras: List[QuestionBlock] = []

    questoes_parseadas = []

    for block in blocks:
        try:
            q = extract_questao_completa(block)
            questoes_parseadas.append(q.numero)

            if len(q.enunciado.split()) < MIN_WORDS_ENUNCIADO:
                print(f"  ⚠️ Q{q.numero}: enunciado muito curto ({len(q.enunciado.split())} palavras)")
                continue

            if len(q.alternativas) < 3:
                if not (len(q.alternativas) >= 2 and is_certo_errado_alts(q.alternativas)):
                    print(f"  ⚠️ Q{q.numero}: poucas alternativas ({len(q.alternativas)}) e não é CERTO/ERRADO")
                    continue

            (acesso_direto if q.tipo == "ACESSO_DIRETO" else outras).append(q)
        except Exception as e:
            print(f"⚠️ Erro ao parsear questão: {e}")

    print(f"\n📋 Questões parseadas com sucesso: {questoes_parseadas}")
    print(f"   ACESSO DIRETO: {[q.numero for q in acesso_direto]}")
    print(f"   ESP: {[q.numero for q in outras]}")

    return acesso_direto, outras


# =========================
# QUERY BUILDING
# =========================
def _clean_query_text(s: str) -> str:
    s = unidecode(s or "")
    s = s.replace("-", " ")
    s = re.sub(r"\b\d+([.,]\d+)?\b", " ", s)
    s = re.sub(r"[^A-Za-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _tokenize_for_query(s: str) -> List[str]:
    s = _clean_query_text(s).lower()
    toks = [t for t in s.split() if t and t not in STOPWORDS]
    return toks


def build_queries_from_enunciado(enunciado: str) -> List[str]:
    text = compact_spaces(enunciado or "")
    if not text:
        return []

    queries: List[tuple[str, int]] = []

    def add_unique(q: str, priority: int = 5):
        q = compact_spaces(q)
        if not q:
            return
        if any(existing[0] == q for existing in queries):
            return
        if len(q) > MAX_QUERY_CHARS:
            q = q[:MAX_QUERY_CHARS].rstrip()
        queries.append((q, priority))

    words_raw = text.split()

    for n in [12, 10, 8, 6]:
        if len(words_raw) >= n:
            add_unique(" ".join(words_raw[:n]), priority=1)

    generic_start = re.sub(r"(?i)^(mulher|homem)\s+de\s+\d+\s+anos?\s*,?\s*", "", text).strip()
    generic_start = compact_spaces(generic_start)
    if generic_start and generic_start != text:
        ws = generic_start.split()
        for n in [12, 10, 8]:
            if len(ws) >= n:
                add_unique(" ".join(ws[:n]), priority=1)

    patterns = [
        r"(dor abdominal [a-zà-ÿ]{4,15})",
        r"(exames realizados [a-zà-ÿ\s]{0,20}com)",
        r"(foi admitido [a-zà-ÿ\s]{0,20}com)",
        r"(procura [a-zà-ÿ\s]{0,15}para)",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.I)
        for match in matches[:1]:
            if len(match.split()) >= 2:
                add_unique(match, priority=2)

    if len(words_raw) <= 25:
        add_unique(text, priority=3)

    if REMOVE_PAREN_CONTENT and "(" in text:
        no_paren = re.sub(r"\([^)]*\)", " ", text)
        no_paren = compact_spaces(no_paren)
        if no_paren != text:
            add_unique(no_paren, priority=3)

    noacc = unidecode(text)
    if noacc != text:
        words_na = noacc.split()
        for n in [10, 8]:
            if len(words_na) >= n:
                add_unique(" ".join(words_na[:n]), priority=3)

    text_nums = re.sub(r"[^\w\s]", " ", text)
    text_nums = compact_spaces(text_nums)
    if text_nums != text:
        words_nums = text_nums.split()
        for n in [10, 8]:
            if len(words_nums) >= n:
                add_unique(" ".join(words_nums[:n]), priority=4)

    toks = _tokenize_for_query(text)
    for n in [10, 8, 6]:
        if len(toks) >= n:
            add_unique(" ".join(toks[:n]), priority=5)

    long_words = sorted([w for w in toks if len(w) >= 6], key=len, reverse=True)
    if len(long_words) >= 2:
        add_unique(" ".join(long_words[:2]), priority=5)
    if len(long_words) >= 3:
        add_unique(" ".join(long_words[:3]), priority=5)

    long_idxs = [i for i, w in enumerate(toks) if len(w) >= 8]
    for i in long_idxs[:3]:
        for win in [5, 4]:
            a = max(0, i - win // 2)
            b = min(len(toks), a + win)
            if b - a >= 3:
                add_unique(" ".join(toks[a:b]), priority=5)

    if len(words_raw) >= 18:
        add_unique(" ".join(words_raw[:18]), priority=6)
    if len(words_raw) >= 16:
        add_unique(" ".join(words_raw[:16]), priority=6)

    if len(words_raw) >= 20:
        mid = len(words_raw) // 2
        add_unique(" ".join(words_raw[max(0, mid - 6): mid + 6]), priority=6)

    if len(words_raw) >= 10:
        add_unique(" ".join(words_raw[-10:]), priority=6)

    queries.sort(key=lambda x: x[1])
    return [q[0] for q in queries]


def query_is_generic(q: str) -> bool:
    return len(q.strip().split()) <= 2


def pages_limit_for_query(q: str) -> int:
    return MAX_PAGES_GENERIC if query_is_generic(q) else MAX_PAGES_SPECIFIC


def rows_limit_for_query(q: str) -> int:
    return ROWS_PER_PAGE_GENERIC if query_is_generic(q) else ROWS_PER_PAGE_SPECIFIC


# =========================
# SITE STRUCTS
# =========================
@dataclass
class SiteQuestion:
    code: str
    enunciado: str
    alternativas: Dict[str, str]
    is_acesso_direto: bool
    especialidade: str


@dataclass
class MatchResult:
    code: str
    score_enunciado: int
    num_alternativas: int
    confianca: str
    is_acesso_direto: bool
    especialidade: str


# =========================
# SITE HELPERS
# =========================
def goto_filter_page(page, q: str, page_num: int):
    url = f"{QUESTIONS_URL}?page={page_num}&filters.description={quote_plus(q)}"
    page.goto(url, wait_until="domcontentloaded", timeout=60000)


def wait_results(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeoutError:
        pass

    page.wait_for_function(
        """() => {
            const trs = document.querySelectorAll('table tbody tr');
            if (trs && trs.length > 0) return true;
            const t = document.body ? document.body.innerText : '';
            if (t.includes('Nenhum') && t.includes('registro')) return true;
            if (t.includes('No records')) return true;
            return false;
        }""",
        timeout=25000,
    )


def parse_listagem_texto(raw: str) -> Tuple[str, Dict[str, str], bool]:
    lines = [l.strip() for l in (raw or "").splitlines() if l.strip()]
    is_ad = any("ACESSO DIRETO" in l.upper() for l in lines[:3])

    while lines and lines[0].startswith("(") and lines[0].endswith(")"):
        lines.pop(0)

    alternativas: Dict[str, str] = {}
    enun_parts: List[str] = []

    alt_pat = re.compile(r"^([A-E])[\)\.\-]\s*(.+)$")
    ce_pat = re.compile(r"^(A|B)[\)\.\-]\s*(CERTO|ERRADO)\.?\s*$", re.I)

    in_alts = False
    for l in lines:
        m = alt_pat.match(l)
        if m:
            in_alts = True
            alternativas[m.group(1)] = compact_spaces(m.group(2))
            continue

        m2 = ce_pat.match(l)
        if m2:
            in_alts = True
            alternativas[m2.group(1).upper()] = m2.group(2).upper()
            continue

        if not in_alts:
            enun_parts.append(l)

    enunciado = compact_spaces(" ".join(enun_parts))
    return enunciado, alternativas, is_ad


# =========================
# VALIDATION (AJUSTADA)
# =========================
def validate_question_match(pdf_q: QuestionBlock, site_q: SiteQuestion) -> Tuple[bool, int, int]:
    a_normal = normalize_text(pdf_q.enunciado)
    b_normal = normalize_text(site_q.enunciado)

    a_extra = normalize_for_comparison(pdf_q.enunciado)
    b_extra = normalize_for_comparison(site_q.enunciado)

    ts_enun = int(fuzz.token_set_ratio(a_normal, b_normal))
    pr_enun = int(fuzz.partial_ratio(a_normal, b_normal))

    ts_extra = int(fuzz.token_set_ratio(a_extra, b_extra))
    pr_extra = int(fuzz.partial_ratio(a_extra, b_extra))

    ts_best = max(ts_enun, ts_extra)
    pr_best = max(pr_enun, pr_extra)

    if DEBUG and pdf_q.numero in DEBUG_QS:
        dprint(f"      🕵️ DEBUG VALIDATION Q{pdf_q.numero}:")
        dprint(f"         Site Code: {site_q.code}")
        dprint(
            f"         Enunciado Score: ts={ts_best} (needs {TOKEN_SET_ENUNCIADO}), "
            f"pr={pr_best} (needs {PARTIAL_ENUNCIADO})"
        )

    enunciado_ok = (
        ts_best >= TOKEN_SET_ENUNCIADO
        or pr_best >= PARTIAL_ENUNCIADO
        or ts_extra >= 82
    )
    if not enunciado_ok:
        return False, ts_best, 0

    alternativas_ok = 0

    for letra in ["A", "B", "C", "D", "E"]:
        if letra not in pdf_q.alternativas or letra not in site_q.alternativas:
            continue

        pdf_alt_n = normalize_text(pdf_q.alternativas[letra])
        site_alt_n = normalize_text(site_q.alternativas[letra])

        pdf_alt_x = normalize_for_comparison(pdf_q.alternativas[letra])
        site_alt_x = normalize_for_comparison(site_q.alternativas[letra])

        ts_alt = int(fuzz.token_set_ratio(pdf_alt_n, site_alt_n))
        pr_alt = int(fuzz.partial_ratio(pdf_alt_n, site_alt_n))

        ts_alt_x = int(fuzz.token_set_ratio(pdf_alt_x, site_alt_x))
        pr_alt_x = int(fuzz.partial_ratio(pdf_alt_x, site_alt_x))

        ts_best_alt = max(ts_alt, ts_alt_x)
        pr_best_alt = max(pr_alt, pr_alt_x)

        alt_ok = (
            ts_best_alt >= ALTERNATIVA_TOKEN_SET
            or pr_best_alt >= ALTERNATIVA_PARTIAL
            or ts_alt_x >= 78
        )
        if alt_ok:
            alternativas_ok += 1

    # CERTO/ERRADO: aceitar 1 alternativa OK se enunciado ok
    if is_certo_errado_alts(pdf_q.alternativas):
        match_final = (alternativas_ok >= 1 and ts_best >= 80)
        return match_final, ts_best, alternativas_ok

    total_pdf = count_pdf_alternatives(pdf_q.alternativas)

    if total_pdf <= 3:
        min_needed = 2
        near_needed = 1
        threshold_near = 83
    elif total_pdf == 4:
        min_needed = 3
        near_needed = 2
        threshold_near = 83
    else:
        min_needed = 4
        near_needed = 3
        threshold_near = 86

    match_final = (
        alternativas_ok >= min_needed
        or (alternativas_ok >= near_needed and ts_best >= threshold_near)
    )

    # fallback conservador
    if (not match_final) and total_pdf <= 4 and ts_best >= 88 and alternativas_ok >= 1:
        match_final = True

    if (not match_final) and ts_best >= 92 and alternativas_ok >= 2:
        match_final = True

    return match_final, ts_best, alternativas_ok


# =========================
# FIND CODE
# =========================
def find_code_for_question(page, questao: QuestionBlock) -> Optional[MatchResult]:
    queries = build_queries_from_enunciado(questao.enunciado)
    total_pdf = count_pdf_alternatives(questao.alternativas) or 5
    seen_codes = set()

    best_media = None
    best_baixa = None
    query_count = 0

    for q in queries[:MAX_QUERIES_PER_QUESTION]:
        query_count += 1

        limit_pages = pages_limit_for_query(q)
        per_page_rows = rows_limit_for_query(q)

        for pnum in range(1, limit_pages + 1):
            goto_filter_page(page, q, pnum)
            wait_results(page)

            def get_rows():
                return page.evaluate(
                    f"""() => {{
                        const out = [];
                        const trs = Array.from(document.querySelectorAll('table tbody tr'));
                        for (const tr of trs) {{
                            const tds = tr.querySelectorAll('td');
                            if (!tds || tds.length < {SPECIALTY_TD_INDEX + 1}) continue;

                            const code = (tds[1]?.innerText || '').trim();
                            const desc = (tds[2]?.innerText || '').trim();
                            const esp  = (tds[{SPECIALTY_TD_INDEX}]?.innerText || '').trim();

                            if (code && desc) out.push({{code, desc, esp}});
                        }}
                        return out;
                    }}"""
                )

            rows = get_rows()

            if not rows:
                page.wait_for_timeout(800)
                goto_filter_page(page, q, pnum)
                wait_results(page)
                rows = get_rows()

            if not rows:
                break

            ad_list: List[SiteQuestion] = []
            nonad_list: List[SiteQuestion] = []

            for r in rows[:per_page_rows]:
                code = (r.get("code") or "").strip()
                if not code or code in seen_codes:
                    continue
                seen_codes.add(code)

                raw_desc = (r.get("desc") or "").strip()
                esp = (r.get("esp") or "").strip()
                if not raw_desc:
                    continue

                enun, alts, is_ad = parse_listagem_texto(raw_desc)
                if not enun or len(alts) < 2:
                    continue

                sq = SiteQuestion(code=code, enunciado=enun, alternativas=alts, is_acesso_direto=is_ad, especialidade=esp)
                (ad_list if is_ad else nonad_list).append(sq)

            for bucket in (ad_list, nonad_list):
                for site_q in bucket:
                    match_ok, score_enun, num_alt = validate_question_match(questao, site_q)
                    if not match_ok:
                        continue

                    ratio = num_alt / total_pdf

                    if score_enun >= 90 and ratio >= 0.75:
                        confianca = "ALTA"
                        emoji = "✅"
                    elif score_enun >= 80 and ratio >= 0.70:
                        confianca = "MEDIA"
                        emoji = "🟡"
                    else:
                        confianca = "BAIXA"
                        emoji = "⚠️"

                    ad_tag = " (AD)" if site_q.is_acesso_direto else ""
                    print(
                        f"  {emoji} Match! Código: {site_q.code}{ad_tag} "
                        f"(enun={score_enun}, alt={num_alt}/{total_pdf}, confiança={confianca})"
                    )

                    result = MatchResult(site_q.code, score_enun, num_alt, confianca, site_q.is_acesso_direto, site_q.especialidade)
                    rank = (1000 if site_q.is_acesso_direto else 0) + (score_enun * 10) + num_alt

                    if confianca == "ALTA":
                        return result

                    if confianca == "MEDIA":
                        if best_media is None or rank > best_media[1]:
                            best_media = (result, rank)

                        if query_count <= QUICK_STOP_AFTER_QUERIES and score_enun >= QUICK_STOP_MIN_SCORE:
                            return result
                    else:
                        if best_baixa is None or rank > best_baixa[1]:
                            best_baixa = (result, rank)

            if EARLY_STOP_IF_GOOD_MEDIA and best_media is not None:
                bm = best_media[0]
                if bm.score_enunciado >= MEDIA_EARLY_MIN_ENUN and (bm.num_alternativas / total_pdf) >= MEDIA_EARLY_MIN_ALT_RATIO:
                    return bm

            if len(seen_codes) >= MAX_SEEN_CODES_BEFORE_STOP and best_media is not None:
                break

        if len(seen_codes) >= MAX_SEEN_CODES_BEFORE_STOP and best_media is not None:
            break

    if best_media is not None:
        return best_media[0]
    if best_baixa is not None:
        return best_baixa[0]
    return None


# =========================
# PLAYWRIGHT SESSION FIX
# =========================
def _ensure_parent_dir(path_str: str) -> Path:
    p = Path(path_str)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _create_context_with_optional_state(browser, storage_state_path: str):
    """
    Cria um context:
    - Se o storage_state existir: usa
    - Se não existir: cria sem state
    """
    sp = Path(storage_state_path)
    if sp.exists():
        return browser.new_context(storage_state=str(sp))
    return browser.new_context()


def _ensure_logged_in_and_save_state(page, context, storage_state_path: str):
    """
    Garante login no admin.
    Se cair na tela /admin/login, espera o usuário logar manualmente e salva storage_state.
    """
    page.goto(QUESTIONS_URL, wait_until="domcontentloaded", timeout=60000)

    url = (page.url or "").lower()
    is_login = ("/admin/login" in url) or ("/login" in url) or url.endswith("/login")

    if is_login:
        print("\n🔐 LOGIN NECESSÁRIO (SITE)")
        print("1) Faça login manualmente no navegador que abriu.")
        print("2) Quando terminar, volte aqui — o robô vai detectar e salvar a sessão.\n")

        t0 = time.time()
        while True:
            time.sleep(1)
            url = (page.url or "").lower()
            is_login = ("/admin/login" in url) or ("/login" in url) or url.endswith("/login")

            if not is_login:
                print("✅ Login detectado. Salvando sessão...")
                sp = _ensure_parent_dir(storage_state_path)
                context.storage_state(path=str(sp))
                print(f"💾 Sessão salva em: {sp}")
                break

            if time.time() - t0 > 600:
                raise RuntimeError("Timeout aguardando login (10 minutos).")
    else:
        # Já estava logado: garantir que exista o arquivo (opcional)
        sp = _ensure_parent_dir(storage_state_path)
        if not sp.exists():
            context.storage_state(path=str(sp))
            print(f"✅ Sessão salva em: {sp}")


# =========================
# MAIN
# =========================
def main(
    pdf_path: str | None = None,
    *,
    headless: bool | None = None,
    target_encontradas: int | None = None,
):
    try:
        Path("debug").mkdir(parents=True, exist_ok=True)
        Path("outputs").mkdir(parents=True, exist_ok=True)
        Path("inputs").mkdir(parents=True, exist_ok=True)

        global PDF_PATH, HEADLESS, TARGET_ENCONTRADAS
        if pdf_path:
            PDF_PATH = pdf_path
        if headless is not None:
            HEADLESS = bool(headless)
        if target_encontradas is not None:
            TARGET_ENCONTRADAS = int(target_encontradas)

        if not Path(PDF_PATH).exists():
            raise FileNotFoundError(f"PDF não encontrado: {PDF_PATH}")

        print("=" * 60)
        print("EXTRAÇÃO DE QUESTÕES - (AD / ESP)")
        print("=" * 60)

        start_q_1, start_c_1 = find_section_pages_via_sumario(PDF_PATH)
        print(f"\n✅ SUMÁRIO: QUESTÕES EXTRAS começa na pág {start_q_1}")
        print(f"✅ SUMÁRIO: COMENTÁRIOS E GABARITOS começa na pág {start_c_1}")
        print(f"✅ Intervalo: {start_q_1} até {start_c_1 - 1}")

        ad_questions, outras_questions = parse_questoes_from_pdf(PDF_PATH)

        print(f"\n✅ Questões ACESSO DIRETO: {len(ad_questions)}")
        print(f"✅ Questões NÃO-AD: {len(outras_questions)}")
        print(f"✅ Meta: {TARGET_ENCONTRADAS} códigos")

        ad_nao_encontradas: List[int] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS, slow_mo=30)

            context = _create_context_with_optional_state(browser, STORAGE_STATE)
            page = context.new_page()

            _ensure_logged_in_and_save_state(page, context, STORAGE_STATE)

            results: List[str] = []
            found_count = 0

            all_questions = ad_questions + outras_questions

            for idx, questao in enumerate(all_questions, 1):
                if found_count >= TARGET_ENCONTRADAS:
                    break

                numero_pdf = questao.numero or idx
                tipo_label = "🔵 AD" if questao.tipo == "ACESSO_DIRETO" else "⚪ ESP"
                preview = (questao.enunciado[:100] + "...") if len(questao.enunciado) > 100 else questao.enunciado

                print(f"\n[{idx}/{len(all_questions)}] {tipo_label} Q{numero_pdf}")
                print(f"  {preview}")

                match_result = find_code_for_question(page, questao)

                if match_result:
                    categoria = "ACESSO DIRETO" if questao.tipo == "ACESSO_DIRETO" else "ESP"
                    codigo_contexto = f"{match_result.code} ({categoria}, Q{numero_pdf} PDF)"
                    results.append(codigo_contexto)
                    found_count += 1
                    print(f"  ✅ Código: {codigo_contexto} ({found_count}/{TARGET_ENCONTRADAS})")
                else:
                    print(f"  ❌ Não encontrado ({found_count}/{TARGET_ENCONTRADAS})")
                    if questao.tipo == "ACESSO_DIRETO":
                        ad_nao_encontradas.append(numero_pdf)

            browser.close()

        if ad_nao_encontradas:
            for n in ad_nao_encontradas:
                results.append(f"Q{n} ACESSO DIRETO (NÃO ENCONTRADA)")

        df = pd.DataFrame({"codigo": results})
        df.to_csv(OUT_CODES_CSV, index=False, header=CSV_WITH_HEADER, encoding="utf-8-sig")

        print("\n" + "=" * 60)
        print(f"✅ CSV gerado: {OUT_CODES_CSV}")
        print(f"✅ Total de linhas no CSV: {len(results)}")
        if ad_nao_encontradas:
            print(f"⚠️ AD não encontradas (registradas no final): {len(ad_nao_encontradas)} -> {ad_nao_encontradas}")
        print("=" * 60)

    except Exception:
        print("\n❌ ERRO GERAL:")
        traceback.print_exc()
        try:
            input("\nPressione ENTER para sair...")
        except Exception:
            pass


if __name__ == "__main__":
    main()
