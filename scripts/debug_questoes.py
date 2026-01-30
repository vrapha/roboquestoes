# -*- coding: utf-8 -*-
"""
DEBUG: Extrai e mostra detalhes das questões 6 e 14
"""

import re
import fitz
from pathlib import Path
from typing import Dict

PDF_PATH = r"inputs\EXTENSIVO_-_Sepse_Neonatal_e_InfecÃ§Ãµes_CongÃªnitas_-_APOSTILA_2025_20250331022148.pdf"


def compact_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def find_section_pages_via_sumario(pdf_path: str):
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
        raise RuntimeError("Não consegui localizar no SUMÁRIO")

    start_q_1 = int(m_q.group(1))
    start_c_1 = int(m_c.group(1))

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
    return "\n".join(parts)


def split_blocks_by_numbering(text: str):
    text2 = re.sub(r"(?m)^\s*(\d+)\.\s", r"\n@@QSTART@@\1. ", text)
    parts = text2.split("@@QSTART@@")
    blocks = []
    for p in parts:
        p = p.strip()
        if p and re.match(r"^\d+\.\s", p):
            blocks.append(p)
    return blocks


def extract_alternativas(texto: str) -> Dict[str, str]:
    alternativas: Dict[str, str] = {}
    
    realloc_order = {
        "A": ["B", "C", "D", "E"],
        "B": ["C", "D", "E", "A"],
        "C": ["D", "E", "A", "B"],
        "D": ["E", "A", "B", "C"],
        "E": ["A", "B", "C", "D"]
    }

    partes = re.split(r"\n\s*([A-E])[\)\.]\s*|\n\s*([A-E])\s*-\s*", texto)

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
                print(f"      ⚠️ Letra {letra_atual} DUPLICADA!")
                ordem = realloc_order.get(letra_atual, ["B", "C", "D", "E"])
                realocada = False
                for fb in ordem:
                    if fb not in alternativas:
                        print(f"         → Realocando para {fb}")
                        alternativas[fb] = valor
                        realocada = True
                        break
                
                if not realocada:
                    print(f"         → Nenhuma letra livre, concatenando")
                    alternativas[letra_atual] = compact_spaces(alternativas[letra_atual] + " " + valor)
            else:
                alternativas[letra_atual] = valor

            letra_atual = None

    # normaliza CERTO/ERRADO
    for k in ["A", "B"]:
        if k in alternativas:
            v = alternativas[k].strip().upper()
            if v.startswith("CERTO"):
                alternativas[k] = "CERTO"
            elif v.startswith("ERRADO"):
                alternativas[k] = "ERRADO"

    return alternativas


def main():
    print("=" * 80)
    print("DEBUG: Questões 6 e 14")
    print("=" * 80)

    if not Path(PDF_PATH).exists():
        print(f"❌ PDF não encontrado: {PDF_PATH}")
        return

    start0, end_excl = find_section_pages_via_sumario(PDF_PATH)
    print(f"\n✅ Intervalo: páginas {start0+1} até {end_excl}")

    text = extract_text_from_page_range(PDF_PATH, start0, end_excl)
    blocks = split_blocks_by_numbering(text)
    print(f"✅ Total de blocos: {len(blocks)}")

    for block in blocks:
        m = re.match(r"^\s*(\d+)\.\s", block)
        if not m:
            continue
        
        numero = int(m.group(1))
        
        if numero not in [6, 14]:
            continue

        print("\n" + "=" * 80)
        print(f"QUESTÃO {numero}")
        print("=" * 80)

        # Mostra bloco completo
        print("\n📄 BLOCO COMPLETO:")
        print("-" * 80)
        print(block[:1000])
        if len(block) > 1000:
            print(f"\n... (mais {len(block) - 1000} caracteres)")
        print("-" * 80)

        # Processa
        texto = re.sub(r"^\s*\d+\.\s*", "", block)
        texto = re.sub(r"^.*?\bACESSO\s+DIRETO\b\s*\.\s*", "", texto, flags=re.I | re.S)
        texto = re.sub(r"^[A-Z\-\s0-9]+\d{4}.*?\.\s*", "", texto)

        match_alts = re.search(r"\n\s*([A-E][\)\.]\s*|[A-E]\s*-\s*)", texto)
        
        if match_alts:
            enunciado = texto[:match_alts.start()].strip()
            texto_alts = texto[match_alts.start():].strip()
            
            print("\n📝 ENUNCIADO:")
            print(enunciado[:500])
            if len(enunciado) > 500:
                print(f"... (mais {len(enunciado) - 500} caracteres)")
            
            print("\n🔤 TEXTO DAS ALTERNATIVAS:")
            print(texto_alts[:800])
            if len(texto_alts) > 800:
                print(f"... (mais {len(texto_alts) - 800} caracteres)")
        else:
            enunciado = texto.strip()
            texto_alts = ""
            print("\n⚠️ NÃO ENCONTREI MARCADOR DE ALTERNATIVAS!")
            print(f"Enunciado: {enunciado[:300]}")

        print("\n🔍 EXTRAINDO ALTERNATIVAS...")
        alternativas = extract_alternativas(texto_alts)
        
        print(f"\n✅ RESULTADO: {len(alternativas)} alternativas")
        for letra in ["A", "B", "C", "D", "E"]:
            if letra in alternativas:
                valor = alternativas[letra]
                print(f"   {letra}. {valor[:100]}{'...' if len(valor) > 100 else ''}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
    input("\nPressione ENTER para sair...")