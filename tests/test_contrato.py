"""Consistência entre o contrato em Python e o runtime C++."""

import re

from guardia import contrato as C
from tests.conftest import RUNTIME

TEXTO = RUNTIME.read_text(encoding="utf-8")


def _define(nome):
    m = re.search(rf"#define {nome}\s+(\S+)", TEXTO)
    assert m, f"{nome} não encontrado no runtime"
    return m.group(1).strip('"')


def _constexpr(nome):
    m = re.search(rf"constexpr (?:int|float) {nome} = ([^;]+);", TEXTO)
    assert m, f"{nome} não encontrado no runtime"
    return float(m.group(1).rstrip("f"))


def test_versao_do_contrato():
    assert int(_define("GUARDIA_CONTRATO_MAJOR")) == C.CONTRATO_MAJOR
    assert int(_define("GUARDIA_CONTRATO_MINOR")) == C.CONTRATO_MINOR
    assert int(_define("GUARDIA_CONTRATO_PATCH")) == C.CONTRATO_PATCH
    assert _define("GUARDIA_CONTRATO_VERSAO") == C.CONTRATO_VERSAO


def test_constantes():
    assert int(_define("GUARDIA_HIST_MAX")) == C.HIST_MAX
    pares = {
        "N_CATEGORIAS": C.N_CATEGORIAS, "N_NIVEIS": C.N_NIVEIS, "N_NUMERICAS": C.N_NUMERICAS,
        "N_RESPONDIDAS_MAX": C.N_RESPONDIDAS_MAX, "SEQUENCIA_MAX": C.SEQUENCIA_MAX,
        "FRIO_TAXA": C.FRIO_TAXA, "FRIO_TEMPO": C.FRIO_TEMPO, "FRIO_DICAS": C.FRIO_DICAS,
        "INVALIDO": C.INVALIDO,
    }
    for nome, valor in pares.items():
        assert _constexpr(nome) == valor, nome


def test_documento_do_contrato_cita_a_versao():
    from tests.conftest import RAIZ

    doc = (RAIZ / "docs" / "contrato_integracao.md").read_text(encoding="utf-8")
    assert f"**Versão do contrato:** {C.CONTRATO_VERSAO}" in doc
