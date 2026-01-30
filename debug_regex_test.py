import re
import sys

# MOCK functions from the main script
def compact_spaces(text):
    return re.sub(r'\s+', ' ', text).strip()

def normalize_text(text):
    text = text.lower()
    text = re.sub(r'[àáâãäå]', 'a', text)
    text = re.sub(r'[èéêë]', 'e', text)
    text = re.sub(r'[ìíîï]', 'i', text)
    text = re.sub(r'[òóôõö]', 'o', text)
    text = re.sub(r'[ùúûü]', 'u', text)
    text = re.sub(r'[ç]', 'c', text)
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return compact_spaces(text)

def extract_alternativas(texto: str):
    print(f"    [EXTRACT_ALTS] Input text len: {len(texto)}")
    print(f"    [EXTRACT_ALTS] First 50 chars: {repr(texto[:50])}")
    alternativas = {}
    
    realloc_order = {
        "A": ["B", "C", "D", "E"],
        "B": ["C", "D", "E", "A"],
        "C": ["D", "E", "A", "B"],
        "D": ["E", "A", "B", "C"],
        "E": ["A", "B", "C", "D"]
    }

    # REGEX FROM MAIN SCRIPT
    pattern = r"(?:(?:\r?\n)|(?:\s+))([A-E])[\)\.]\s+|(?:(?:\r?\n)|(?:\s+))([A-E])\s*-\s*"
    print(f"    [EXTRACT_ALTS] Splitting with pattern: {pattern}")
    
    partes = re.split(pattern, texto)
    
    print(f"    [EXTRACT_ALTS] Split parts count: {len(partes)}")
    for i, p in enumerate(partes):
        if p:
             print(f"      Part {i}: {repr(p)}")

    letra_atual = None
    for parte in partes:
        if parte is None: continue
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
                        print(f"      [REALLOC] {letra_atual} -> {fb}: {valor[:20]}...")
                        break
                if not realocada:
                    alternativas[letra_atual] = compact_spaces(alternativas[letra_atual] + " " + valor)
            else:
                alternativas[letra_atual] = valor
            letra_atual = None

    for k in ["A", "B"]:
        if k in alternativas:
            v = alternativas[k].strip().upper()
            if "CERTO" in v: alternativas[k] = "CERTO"
            elif "ERRADO" in v: alternativas[k] = "ERRADO"
            
    return alternativas

def extract_questao_completa(block: str):
    print(f"\n--- PROCESSING BLOCK ---")
    print(f"Original Block:\n{repr(block)}")
    
    texto_completo = block.strip()
    numero = None
    m = re.match(r"^\s*(\d+)\s*\.\s", texto_completo)
    if m: numero = int(m.group(1))

    texto = re.sub(r"^\s*\d+\.\s*", "", texto_completo)
    texto = re.sub(r"^.*?\bACESSO\s+DIRETO\b\s*\.\s*", "", texto, flags=re.I | re.S)
    texto = re.sub(r"^[A-Z\-\s0-9]+\d{4}.*?\.\s*", "", texto) # Remove header lines like SES-DF 2022...

    print(f"Text after header removal:\n{repr(texto)}")

    # 1. Tenta achar alternativas com QUEBRA DE LINHA (Padrão)
    match_alts = re.search(r"(?:\r?\n)\s*([A-E][\)\.]\s*|[A-E]\s*-\s*)", texto)
    if match_alts:
        print(f"MATCH STRATEGY 1 (NewLine): Found at index {match_alts.start()}")
        print(f"Matched group: {match_alts.group()}")
    else:
        print("MATCH STRATEGY 1 FAILED")

    # 2. SE FALHAR, tenta busca mais agressiva
    if not match_alts:
        match_alts = re.search(r"(\s+[A-E][\)\.]\s+[A-ZÀ-Ú])", texto)
        if match_alts:
            print(f"MATCH STRATEGY 2 (Space+Letter+Dot+Space+Upper): Found at index {match_alts.start()}")
            print(f"Matched group: {match_alts.group()}")
        else:
            print("MATCH STRATEGY 2 FAILED")

    # 3. CASO ESPECÍFICO: CERTO/ERRADO colado
    if not match_alts and ("CERTO" in texto.upper() or "ERRADO" in texto.upper()):
         match_alts = re.search(r"(\s*[A-E][\)\.]\s*(?:CERTO|ERRADO))", texto, re.I)
         if match_alts:
            print(f"MATCH STRATEGY 3 (CERTO/ERRADO): Found at index {match_alts.start()}")
            print(f"Matched group: {match_alts.group()}")
         else:
            print("MATCH STRATEGY 3 FAILED")

    if match_alts:
        enunciado = texto[:match_alts.start()].strip()
        texto_alts = texto[match_alts.start():].strip()
        print(f"Enunciado Final chars: {repr(enunciado[-20:])}")
        print(f"Texto Alts chars: {repr(texto_alts[:50])}...")
        
        alts = extract_alternativas(texto_alts)
        print(f"Final Alternatives: {alts}")
    else:
        print("NO ALTERNATIVES SPLIT FOUND")


# RAW TEXT DATA FROM USER DUMP
q14_text = """14. SES-DF 2022 ACESSO DIRETO. Uma paciente de 30 anos de idade, nuligesta, parou de usar anticoncepcional hormonal 
há sete meses para tentar engravidar. Relata aumento da dismenorreia no período, intensidade 8 em 10, que inicia 01 
dia antes e dura 5 dias da menstruação, aliviada parcialmente com analgésicos comuns, associada a dispareunia. Ao 
exame físico, tem dor à mobilização do colo uterino, com mobilidade do útero reduzida e espessamento bilateral de 
ligamentos uterossacros. Considerando esse caso clínico e os conhecimentos médicos correlatos, julgue o item a 
seguir. Como a paciente está tentando gestar há menos de um ano, não há indicação de prosseguir com a investigação. 
A. CERTO. 
B. ERRADO."""

q6_text = """6. UERJ-RJ 2024 ACESSO DIRETO. Mulher de 30 anos, sem comorbidades, com duas gestações anteriores e laqueadura 
tubária há um ano, comparece à UBS com queixa de dismenorreia intensa há dez anos, sendo tratada regularmente 
com analgésicos. O exame ginecológico é normal, mas a ressonância nuclear magnética de pelve demonstra 
espessamento de ligamento uterossacro direito, sugestivo de endometriose. O tratamento de escolha à paciente é: 
 

 
 A. Dienogeste contínuo. 
 A. Histerectomia simples. 
 B. Ooforectomia bilateral. 
 C. Agonista do GnRH isolado."""

print("Testing Q14 --------------------------------------------------")
extract_questao_completa(q14_text)
print("\nTesting Q6 ---------------------------------------------------")
extract_questao_completa(q6_text)
