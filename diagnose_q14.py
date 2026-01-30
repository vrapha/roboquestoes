import sys
import os

# Add scripts folder to path so we can import the REAL module
sys.path.append(os.path.join(os.getcwd(), 'scripts'))

try:
    from robo_pdf_para_codigos import extract_questao_completa
except ImportError as e:
    print(f"CRITICAL ERROR: Could not import script: {e}")
    sys.exit(1)


# Redirect stdout to a file to avoid console encoding issues
log_file = os.path.join(os.getcwd(), 'diagnosis_result.txt')
with open(log_file, 'w', encoding='utf-8') as f:
    sys.stdout = f
    
    print("✅ Successfully imported robo_pdf_para_codigos (REAL CODE ON DISK)")

    # Raw string from previous dump
    q14_text = """14. SES-DF 2022 ACESSO DIRETO. Uma paciente de 30 anos de idade, nuligesta, parou de usar anticoncepcional hormonal 
há sete meses para tentar engravidar. Relata aumento da dismenorreia no período, intensidade 8 em 10, que inicia 01 
dia antes e dura 5 dias da menstruação, aliviada parcialmente com analgésicos comuns, associada a dispareunia. Ao 
exame físico, tem dor à mobilização do colo uterino, com mobilidade do útero reduzida e espessamento bilateral de 
ligamentos uterossacros. Considerando esse caso clínico e os conhecimentos médicos correlatos, julgue o item a 
seguir. Como a paciente está tentando gestar há menos de um ano, não há indicação de prosseguir com a investigação. 
A. CERTO. 
B. ERRADO."""

    print("\n\n📊 TESTING Q14 Extraction:")
    try:
        q14 = extract_questao_completa(q14_text)
        print(f"   Enunciado Len: {len(q14.enunciado)}")
        print(f"   Enunciado Last 50: {repr(q14.enunciado[-50:])}")
        print(f"   Alternatives Found: {list(q14.alternativas.keys())}")
        print(f"   Alternatives Content: {q14.alternativas}")
    except Exception as e:
        print(f"   ❌ ERROR extracting Q14: {e}")

    q6_text = """6. UERJ-RJ 2024 ACESSO DIRETO. Mulher de 30 anos, sem comorbidades, com duas gestações anteriores e laqueadura 
tubária há um ano, comparece à UBS com queixa de dismenorreia intensa há dez anos, sendo tratada regularmente 
com analgésicos. O exame ginecológico é normal, mas a ressonância nuclear magnética de pelve demonstra 
espessamento de ligamento uterossacro direito, sugestivo de endometriose. O tratamento de escolha à paciente é: 
 

 
 A. Dienogeste contínuo. 
 A. Histerectomia simples. 
 B. Ooforectomia bilateral. 
 C. Agonista do GnRH isolado."""

    print("\n\n📊 TESTING Q6 Extraction:")
    try:
        q6 = extract_questao_completa(q6_text)
        print(f"   Enunciado Len: {len(q6.enunciado)}")
        print(f"   Enunciado Last 50: {repr(q6.enunciado[-50:])}")
        print(f"   Alternatives Found: {list(q6.alternativas.keys())}")
        print(f"   Alternatives Content: {q6.alternativas}")
    except Exception as e:
        print(f"   ❌ ERROR extracting Q6: {e}")

