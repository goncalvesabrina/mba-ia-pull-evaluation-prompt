"""
Testes automatizados para validação de prompts.
"""
import pytest
import yaml
import re
import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils import validate_prompt_structure

PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "bug_to_user_story_v2.yml"
PROMPT_KEY = "bug_to_user_story_v2"


def load_prompts(file_path: str):
    """Carrega prompts do arquivo YAML."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def prompt():
    """Retorna os dados do prompt otimizado (v2)."""
    assert PROMPT_FILE.exists(), f"Arquivo não encontrado: {PROMPT_FILE}"

    prompts = load_prompts(str(PROMPT_FILE))
    assert prompts is not None, "YAML vazio ou inválido"
    assert PROMPT_KEY in prompts, f"Chave '{PROMPT_KEY}' ausente no YAML"

    return prompts[PROMPT_KEY]


@pytest.fixture(scope="module")
def full_text(prompt):
    """Concatena system_prompt e user_prompt em minúsculas para buscas textuais."""
    return f"{prompt.get('system_prompt', '')}\n{prompt.get('user_prompt', '')}".lower()


class TestPrompts:
    def test_prompt_has_system_prompt(self, prompt):
        """Verifica se o campo 'system_prompt' existe e não está vazio."""
        assert "system_prompt" in prompt, "Campo 'system_prompt' ausente"

        system_prompt = prompt["system_prompt"]
        assert isinstance(system_prompt, str), "'system_prompt' deve ser uma string"
        assert system_prompt.strip(), "'system_prompt' está vazio"
        assert len(system_prompt.strip()) > 200, (
            "'system_prompt' é curto demais para um prompt otimizado"
        )

        # O relato do bug deve entrar apenas pelo user prompt (problema da v1).
        assert "{bug_report}" not in system_prompt, (
            "'system_prompt' não deve conter {bug_report}"
        )
        assert "{bug_report}" in prompt.get("user_prompt", ""), (
            "'user_prompt' precisa conter a variável {bug_report}"
        )

    def test_prompt_has_role_definition(self, prompt):
        """Verifica se o prompt define uma persona (ex: "Você é um Product Manager")."""
        system_prompt = prompt.get("system_prompt", "").lower()

        assert "você é" in system_prompt, (
            "O prompt não define uma persona com 'Você é ...'"
        )

        personas = ["product manager", "product owner", "analista", "engenheir"]
        assert any(p in system_prompt for p in personas), (
            f"Nenhuma persona reconhecida encontrada (esperado uma de: {personas})"
        )

    def test_prompt_mentions_format(self, full_text):
        """Verifica se o prompt exige formato Markdown ou User Story padrão."""
        # Template canônico de User Story
        assert "como um" in full_text, "Prompt não exige o formato 'Como um...'"
        assert "eu quero" in full_text, "Prompt não exige o trecho 'eu quero...'"
        assert "para que" in full_text, "Prompt não exige o trecho 'para que...'"

        # Critérios de aceitação no padrão Gherkin (Dado/Quando/Então)
        assert "critérios de aceitação" in full_text, (
            "Prompt não exige uma seção de Critérios de Aceitação"
        )
        for keyword in ("dado que", "quando", "então"):
            assert keyword in full_text, (
                f"Prompt não exige o padrão Dado/Quando/Então (faltou '{keyword}')"
            )

    def test_prompt_has_few_shot_examples(self, prompt):
        """Verifica se o prompt contém exemplos de entrada/saída (técnica Few-shot)."""
        system_prompt = prompt.get("system_prompt", "")
        lowered = system_prompt.lower()

        assert "# exemplos" in lowered or "exemplo 1" in lowered, (
            "Prompt não possui uma seção de exemplos (Few-shot)"
        )

        # Cada exemplo precisa de um par entrada (Relato) -> saída (Saída)
        inputs = len(re.findall(r"^\s*relato:", system_prompt, re.MULTILINE | re.IGNORECASE))
        outputs = len(re.findall(r"^\s*saída:", system_prompt, re.MULTILINE | re.IGNORECASE))

        assert inputs >= 2, f"Few-shot precisa de ao menos 2 entradas, encontradas: {inputs}"
        assert outputs >= 2, f"Few-shot precisa de ao menos 2 saídas, encontradas: {outputs}"
        assert inputs == outputs, (
            f"Exemplos desbalanceados: {inputs} entradas para {outputs} saídas"
        )

    def test_prompt_no_todos(self, prompt):
        """Garante que você não esqueceu nenhum `[TODO]` no texto."""
        for field in ("description", "system_prompt", "user_prompt"):
            text = str(prompt.get(field, ""))
            for marker in ("[TODO]", "TODO", "FIXME", "XXX", "<preencher>"):
                assert marker not in text, (
                    f"Marcador '{marker}' esquecido no campo '{field}'"
                )

    def test_minimum_techniques(self, prompt):
        """Verifica (através dos metadados do yaml) se pelo menos 2 técnicas foram listadas."""
        techniques = prompt.get("techniques_applied")

        assert techniques is not None, "Metadado 'techniques_applied' ausente no YAML"
        assert isinstance(techniques, list), "'techniques_applied' deve ser uma lista"
        assert len(techniques) >= 2, (
            f"Mínimo de 2 técnicas requeridas, encontradas: {len(techniques)}"
        )
        assert all(str(t).strip() for t in techniques), (
            "Há técnicas vazias em 'techniques_applied'"
        )

        # Few-shot é obrigatório pelo enunciado do desafio.
        joined = " ".join(str(t).lower() for t in techniques)
        assert "few-shot" in joined or "few shot" in joined, (
            "A técnica obrigatória Few-shot Learning não está declarada"
        )

    def test_prompt_structure_is_valid(self, prompt):
        """Valida a estrutura do prompt com o utilitário compartilhado do projeto."""
        is_valid, errors = validate_prompt_structure(prompt)
        assert is_valid, f"Estrutura inválida: {errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
