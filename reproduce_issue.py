
import re

def split_blocks_by_numbering(text: str):
    # Updated regex from scripts/robo_pdf_para_codigos.py
    # (?m)^      -> start of line
    # \s*        -> optional spaces (indentation)
    # (\d+)      -> question number
    # \s*        -> optional spaces (between number and dot)
    # \.         -> literal dot
    # \s*        -> optional spaces after dot
    text2 = re.sub(r"(?m)^\s*(\d+)\s*\.\s*", r"\n@@QSTART@@\1. ", text)
    parts = text2.split("@@QSTART@@")
    
    blocks = []
    for p in parts:
        p = p.strip()
        # Validate if it starts with number + dot
        if p and re.match(r"^\d+\.\s", p):
            blocks.append(p)
    return blocks

def test_q14():
    print("--- Testing Q14 ---")
    # Simulating text that might come from PDF extraction
    # Case 1: Perfect spacing
    text_perfect = """
13. SES-DF 2021 Blah blah.
A. Opcao 1
B. Opcao 2

14. SES-DF 2022 ACESSO DIRETO. Uma paciente de 30 anos...
A. CERTO.
B. ERRADO.
"""
    blocks = split_blocks_by_numbering(text_perfect)
    print(f"Blocks found (Perfect): {[b[:20] for b in blocks]}")
    
    # Case 2: No newline before 14
    text_no_newline = """
13. SES-DF 2021 Blah blah.
A. Opcao 1
B. Opcao 2
14. SES-DF 2022 ACESSO DIRETO. Uma paciente de 30 anos...
A. CERTO.
B. ERRADO.
"""
    blocks = split_blocks_by_numbering(text_no_newline)
    print(f"Blocks found (No Newline): {[b[:20] for b in blocks]}")

    # Case 3: Strange spacing (tabs, non-breaking spaces)
    text_strange = """
13. Ends here.
14.  SES-DF 2022 ACESSO DIRETO. Uma paciente de 30 anos...
"""
    blocks = split_blocks_by_numbering(text_strange)
    print(f"Blocks found (Strange): {[b[:20] for b in blocks]}")

def test_q6():
    print("\n--- Testing Q6 ---")
    text_q6 = """
5. Anterior question.
A. x
B. y

6. UERJ-RJ 2024 ACESSO DIRETO. Mulher de 30 anos...
A. Dienogeste contínuo.
A. Histerectomia simples.
B. Ooforectomia bilateral.
C. Agonista do GnRH isolado.
"""
    blocks = split_blocks_by_numbering(text_q6)
    print(f"Blocks found (Q6): {[b[:20] for b in blocks]}")
    
    if len(blocks) >= 2:
        # Test parsing logic for Q6 Block
        block6 = blocks[1]
        print(f"Block 6 content:\n{block6}")
        
        # Simulating extract_alternativas
        alternativas = {}
        realloc_order = {
            "A": ["B", "C", "D", "E"],
            "B": ["C", "D", "E", "A"],
            "C": ["D", "E", "A", "B"],
            "D": ["E", "A", "B", "C"],
            "E": ["A", "B", "C", "D"]
        }
        
        partes = re.split(r"\n\s*([A-E])[\)\.]\s*|\n\s*([A-E])\s*-\s*", block6)
        
        letra_atual = None
        for parte in partes:
            if parte is None: continue
            parte = parte.strip()
            if parte in ["A", "B", "C", "D", "E"]:
                letra_atual = parte
                continue
            
            if letra_atual and parte:
                valor = parte # simplifying compact_spaces
                if letra_atual in alternativas:
                    print(f"Duplicate {letra_atual} found checking realloc...")
                    ordem = realloc_order.get(letra_atual, [])
                    realocada = False
                    for fb in ordem:
                        if fb not in alternativas:
                            alternativas[fb] = valor
                            realocada = True
                            print(f"Reallocated to {fb}")
                            break
                    if not realocada:
                        alternativas[letra_atual] += " " + valor
                else:
                    alternativas[letra_atual] = valor
                letra_atual = None
                
        print(f"Parsed Alternatives: {alternativas}")

if __name__ == "__main__":
    with open("reproduction.log", "w", encoding="utf-8") as f:
        # Redirect print to file
        import builtins
        original_print = builtins.print
        def print(*args, **kwargs):
            kwargs["file"] = f
            original_print(*args, **kwargs)
            
        test_q14()
        test_q6()
