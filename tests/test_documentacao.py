"""Consistência da documentação com as decisões do projeto."""

import hashlib
import re

import pytest

from tests.conftest import RAIZ

DOCS = sorted([RAIZ / "README.md", *(RAIZ / "docs").rglob("*.md")])

# Arquivos citados na documentação que só existem em branches ainda não integrados.
PENDENTES_DE_INTEGRACAO: dict[str, str] = {}

# SHA-256 do protocolo registrado em 28/10/2026 (commit 297bc99). Mudanças nos
# critérios exigem novo commit com justificativa; ajustes de dados e divisão
# são registrados em adendos (docs/protocolo_adendo_*.md).
SHA_PROTOCOLO_PRE_REGISTRADO = "1461ed949773552cc61149972c91ea42532f2d8c02f9d7ba64d646e196701c5c"


def test_protocolo_pre_registrado_nao_foi_alterado():
    atual = hashlib.sha256((RAIZ / "docs" / "protocolo_avaliacao.md").read_bytes()).hexdigest()
    assert atual == SHA_PROTOCOLO_PRE_REGISTRADO


def test_adendo_registra_split_v2_sem_mudar_criterios():
    texto = (RAIZ / "docs" / "protocolo_adendo_01.md").read_text(encoding="utf-8")
    assert "split_v1" in texto and "split_v2" in texto
    assert "sem alterações" in texto


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: str(p.relative_to(RAIZ)))
def test_nao_afirma_que_a_guardia_ja_foi_treinada(doc):
    """Enquanto não houver modelo treinado, nenhum documento pode afirmar o contrário."""
    texto = doc.read_text(encoding="utf-8").lower()
    for frase in ("guardiã foi treinada", "guardia foi treinada", "foi treinada e avaliada", "guardiã já foi treinada"):
        assert frase not in texto, f"{doc.name}: '{frase}'"


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: str(p.relative_to(RAIZ)))
def test_links_internos_existem(doc):
    texto = doc.read_text(encoding="utf-8")
    for alvo in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", texto):
        if alvo.startswith(("http://", "https://", "mailto:")) or alvo.split("/")[-1] in PENDENTES_DE_INTEGRACAO:
            continue
        assert (doc.parent / alvo).resolve().exists(), f"{doc.name}: link quebrado para {alvo}"

