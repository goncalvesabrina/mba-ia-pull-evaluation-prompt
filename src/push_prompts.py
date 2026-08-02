"""
Script para fazer push de prompts otimizados ao LangSmith Prompt Hub.

Este script:
1. Lê os prompts otimizados de prompts/bug_to_user_story_v2.yml
2. Valida os prompts
3. Faz push PÚBLICO para o LangSmith Hub
4. Adiciona metadados (tags, descrição, técnicas utilizadas)

SIMPLIFICADO: Código mais limpo e direto ao ponto.
"""

import os
import sys
from dotenv import load_dotenv
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate
from utils import load_yaml, check_env_vars, print_section_header

load_dotenv()

PROMPTS_FILE = "prompts/bug_to_user_story_v2.yml"
PROMPT_KEY = "bug_to_user_story_v2"


def build_readme(prompt_data: dict) -> str:
    """
    Monta o README publicado junto ao prompt no LangSmith Hub.

    Args:
        prompt_data: Dados do prompt

    Returns:
        Texto em Markdown descrevendo o prompt e as técnicas aplicadas
    """
    techniques = prompt_data.get("techniques_applied", [])
    techniques_md = "\n".join(f"- {t}" for t in techniques)

    return (
        f"# {PROMPT_KEY}\n\n"
        f"{prompt_data.get('description', '').strip()}\n\n"
        f"## Técnicas de Prompt Engineering aplicadas\n\n"
        f"{techniques_md}\n\n"
        f"## Entrada\n\n"
        f"- `bug_report`: relato de bug em texto livre (simples, médio ou complexo)\n\n"
        f"## Saída\n\n"
        f"User Story no formato `Como um... eu quero... para que...`, com critérios "
        f"de aceitação em Dado/Quando/Então e nível de detalhe proporcional à "
        f"complexidade do relato.\n\n"
        f"Versão: {prompt_data.get('version', 'v2')} "
        f"(refatoração de {prompt_data.get('parent_version', 'v1')})\n"
    )


def validate_prompt(prompt_data: dict) -> tuple[bool, list]:
    """
    Valida estrutura básica de um prompt (versão simplificada).

    Args:
        prompt_data: Dados do prompt

    Returns:
        (is_valid, errors) - Tupla com status e lista de erros
    """
    errors = []

    for field in ("description", "system_prompt", "user_prompt", "version"):
        if not str(prompt_data.get(field, "")).strip():
            errors.append(f"Campo obrigatório ausente ou vazio: {field}")

    system_prompt = str(prompt_data.get("system_prompt", ""))
    user_prompt = str(prompt_data.get("user_prompt", ""))

    if "TODO" in system_prompt or "TODO" in user_prompt:
        errors.append("O prompt ainda contém marcadores [TODO]")

    if "{bug_report}" not in user_prompt:
        errors.append("user_prompt precisa conter a variável {bug_report}")

    if "{bug_report}" in system_prompt:
        errors.append(
            "system_prompt não deve conter {bug_report} "
            "(o relato entra apenas pelo user prompt)"
        )

    techniques = prompt_data.get("techniques_applied", [])
    if len(techniques) < 2:
        errors.append(
            f"Mínimo de 2 técnicas requeridas, encontradas: {len(techniques)}"
        )

    return (len(errors) == 0, errors)


def push_prompt_to_langsmith(prompt_name: str, prompt_data: dict) -> bool:
    """
    Faz push do prompt otimizado para o LangSmith Hub (PÚBLICO).

    Args:
        prompt_name: Nome do prompt
        prompt_data: Dados do prompt

    Returns:
        True se sucesso, False caso contrário
    """
    try:
        chat_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", prompt_data["system_prompt"]),
                ("human", prompt_data["user_prompt"]),
            ]
        )
    except Exception as e:
        print(f"❌ Erro ao montar o ChatPromptTemplate: {e}")
        return False

    if set(chat_prompt.input_variables) != {"bug_report"}:
        print(
            "❌ Variáveis de entrada inesperadas no template: "
            f"{sorted(chat_prompt.input_variables)} (esperado: ['bug_report'])"
        )
        print("   Verifique se há chaves soltas no texto do prompt.")
        return False

    tags = [str(t) for t in prompt_data.get("tags", [])]
    description = " ".join(str(prompt_data.get("description", "")).split())

    try:
        url = hub.push(
            prompt_name,
            chat_prompt,
            new_repo_is_public=True,
            new_repo_description=description,
            readme=build_readme(prompt_data),
            tags=tags,
        )
    except Exception as e:
        print(f"❌ Erro ao fazer push de '{prompt_name}': {e}")
        print("\nVerifique:")
        print("  - LANGSMITH_API_KEY está configurada corretamente no .env")
        print("  - USERNAME_LANGSMITH_HUB corresponde ao seu handle do Hub")
        return False

    print(f"   ✓ Push realizado: {url}")

    # new_repo_is_public só vale na criação: garante visibilidade pública também
    # quando o repositório já existia (requisito do desafio).
    try:
        from langsmith import Client

        Client().update_prompt(
            prompt_name,
            description=description,
            tags=tags,
            is_public=True,
        )
        print("   ✓ Prompt marcado como PÚBLICO")
    except Exception as e:
        print(f"   ⚠️  Não foi possível confirmar a visibilidade pública: {e}")
        print("      Torne o prompt público manualmente no dashboard do LangSmith.")

    return True


def main():
    """Função principal"""
    print_section_header("PUSH DE PROMPTS OTIMIZADOS PARA O LANGSMITH HUB")

    if not check_env_vars(["LANGSMITH_API_KEY", "USERNAME_LANGSMITH_HUB"]):
        return 1

    prompts = load_yaml(PROMPTS_FILE)
    if not prompts:
        return 1

    prompt_data = prompts.get(PROMPT_KEY)
    if not prompt_data:
        print(f"❌ Chave '{PROMPT_KEY}' não encontrada em {PROMPTS_FILE}")
        return 1

    print(f"📄 Prompt carregado de: {PROMPTS_FILE}")

    is_valid, errors = validate_prompt(prompt_data)
    if not is_valid:
        print("❌ Prompt inválido:")
        for error in errors:
            print(f"   - {error}")
        return 1

    print("   ✓ Validação OK")
    print(f"   ✓ Técnicas: {', '.join(prompt_data.get('techniques_applied', []))}")

    username = os.getenv("USERNAME_LANGSMITH_HUB")
    prompt_name = f"{username}/{PROMPT_KEY}"

    print(f"\n📤 Publicando: {prompt_name}")

    if not push_prompt_to_langsmith(prompt_name, prompt_data):
        return 1

    print("\n✅ Push concluído com sucesso!")
    print(f"\nConfira em: https://smith.langchain.com/hub/{username}/{PROMPT_KEY}")
    print("\nPróximo passo:")
    print("  python src/evaluate.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
