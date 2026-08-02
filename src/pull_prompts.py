"""
Script para fazer pull de prompts do LangSmith Prompt Hub.

Este script:
1. Conecta ao LangSmith usando credenciais do .env
2. Faz pull dos prompts do Hub
3. Salva localmente em prompts/bug_to_user_story_v1.yml

SIMPLIFICADO: Usa serialização nativa do LangChain para extrair prompts.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain import hub
from utils import save_yaml, check_env_vars, print_section_header

load_dotenv()

# Prompt de baixa qualidade publicado no LangSmith Hub (ponto de partida do desafio).
SOURCE_PROMPT = "leonanluppi/bug_to_user_story_v1"
OUTPUT_FILE = "prompts/bug_to_user_story_v1.yml"


def extract_messages(prompt) -> dict:
    """
    Extrai system_prompt e user_prompt de um ChatPromptTemplate do LangChain.

    Percorre as mensagens do template e identifica cada uma pelo tipo
    (system / human). Se o objeto for um PromptTemplate simples (não-chat),
    o template inteiro é tratado como system_prompt.

    Args:
        prompt: Objeto retornado por hub.pull()

    Returns:
        Dicionário com as chaves 'system_prompt' e 'user_prompt'
    """
    messages = getattr(prompt, "messages", None)

    if messages is None:
        return {
            "system_prompt": getattr(prompt, "template", str(prompt)),
            "user_prompt": "{bug_report}",
        }

    system_parts = []
    user_parts = []

    for message in messages:
        template = getattr(getattr(message, "prompt", None), "template", None)
        if template is None:
            template = getattr(message, "content", "")

        message_type = getattr(message, "type", "") or message.__class__.__name__.lower()

        if "system" in message_type:
            system_parts.append(template)
        else:
            user_parts.append(template)

    return {
        "system_prompt": "\n\n".join(system_parts).strip(),
        "user_prompt": "\n\n".join(user_parts).strip() or "{bug_report}",
    }


def pull_prompts_from_langsmith() -> bool:
    """
    Faz pull do prompt inicial (v1) do LangSmith Hub e salva em YAML local.

    Returns:
        True se sucesso, False caso contrário
    """
    print(f"📥 Fazendo pull de: {SOURCE_PROMPT}")

    try:
        prompt = hub.pull(SOURCE_PROMPT)
    except Exception as e:
        print(f"❌ Erro ao fazer pull do prompt '{SOURCE_PROMPT}': {e}")
        print("\nVerifique:")
        print("  - LANGSMITH_API_KEY está configurada corretamente no .env")
        print("  - Você tem acesso ao LangSmith e conexão com a internet")
        return False

    print("   ✓ Prompt recebido do Hub")

    messages = extract_messages(prompt)

    if not messages["system_prompt"]:
        print("❌ O prompt retornado não possui system_prompt")
        return False

    prompt_data = {
        "bug_to_user_story_v1": {
            "description": "Prompt para converter relatos de bugs em User Stories",
            "system_prompt": messages["system_prompt"],
            "user_prompt": messages["user_prompt"],
            "version": "v1",
            "source": SOURCE_PROMPT,
            "input_variables": list(getattr(prompt, "input_variables", [])),
            "tags": ["bug-analysis", "user-story", "product-management"],
        }
    }

    if not save_yaml(prompt_data, OUTPUT_FILE):
        return False

    print(f"   ✓ Prompt salvo em: {OUTPUT_FILE}")
    print(f"   ✓ Variáveis de entrada: {prompt_data['bug_to_user_story_v1']['input_variables']}")
    return True


def main():
    """Função principal"""
    print_section_header("PULL DE PROMPTS DO LANGSMITH HUB")

    if not check_env_vars(["LANGSMITH_API_KEY"]):
        return 1

    if not pull_prompts_from_langsmith():
        return 1

    print("\n✅ Pull concluído com sucesso!")
    print("\nPróximos passos:")
    print(f"1. Analise o prompt em {OUTPUT_FILE}")
    print("2. Refatore a versão otimizada em prompts/bug_to_user_story_v2.yml")
    print("3. Execute: python src/push_prompts.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
