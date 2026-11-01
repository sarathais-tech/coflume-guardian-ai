"""Pipeline de treino: protocolo, teste lacrado, ausência de vazamento e reprodutibilidade."""

import json

import numpy as np
import pandas as pd
import pytest

from ferramentas import ler_resultado_ci, treinar
from guardia import dados as dados_mod
from guardia import treino
from guardia.dados import criar_split, salvar_split
from guardia.mlp import estatisticas_treino
from guardia.simulador import gerar_arquivo, parametros_da_versao


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("t")
    csv = pasta / "sinteticos" / "s.csv"
    gerar_arquivo(csv, 600, 2026, parametros_da_versao("sim-1.1"))
    split = pasta / "split.json"
    salvar_split(criar_split(csv, versao="split_teste"), split)
    return csv, split


SKLEARN = ("baseline", "arvore", "logistica")


class TestProtocolo:
    def test_grades_do_protocolo(self):
        assert {(g["max_depth"], g["min_samples_leaf"]) for g in treino.GRADE_ARVORE} == \
            {(d, m) for d in (3, 4, 5, 6) for m in (20, 50, 100)}
        assert [g["C"] for g in treino.GRADE_LOGISTICA] == [0.01, 0.1, 1.0, 10.0]
        assert treino.ARQUITETURAS_MLP == [(8,), (16,), (16, 8), (32, 16)]
        assert treino.MLP_CONFIG == {"lr": 1e-3, "batch": 64, "l2": 1e-4, "paciencia": 20, "max_epocas": 300}
        assert len(treino.SEMENTES_MLP) == 5 and treino.N_FOLDS == 5 and treino.SEMENTE == 2026

    def test_n_parametros(self):
        assert [treino.n_parametros(a) for a in treino.ARQUITETURAS_MLP] == [121, 241, 369, 993]

    def test_regra_da_menor_arquitetura(self):
        linhas = [{"arquitetura": [8], "n_parametros": 121, "cv_log_loss_media": 0.640},
                  {"arquitetura": [16], "n_parametros": 241, "cv_log_loss_media": 0.638},
                  {"arquitetura": [16, 8], "n_parametros": 369, "cv_log_loss_media": 0.630}]
        # melhor = 0,630; limite = 0,6363 → só [16, 8]
        assert treino.escolher_arquitetura(linhas)["arquitetura"] == [16, 8]
        linhas[0]["cv_log_loss_media"] = 0.636
        assert treino.escolher_arquitetura(linhas)["arquitetura"] == [8]


class TestTesteLacrado:
    def test_pipeline_nunca_pede_o_conjunto_de_teste(self, base, monkeypatch):
        pedidos = []
        original = dados_mod.conjunto

        def espiao(df, split, nome, abrir_teste=False):
            pedidos.append((nome, abrir_teste))
            return original(df, split, nome, abrir_teste=abrir_teste)

        monkeypatch.setattr(treino, "conjunto", espiao)
        res, _ = treino.executar(*base, modelos=SKLEARN)
        assert pedidos == [("treino", False), ("validacao", False)]
        assert res["dados"]["teste_lacrado"] and res["dados"]["conjuntos_carregados"] == ["treino", "validacao"]

    def test_nenhum_participante_de_teste_nos_dados_usados(self, base):
        csv, split = base
        d = treino.preparar(csv, split)
        teste = set(json.loads(split.read_text())["participantes"]["teste"])
        assert not teste & set(d.g_tr) and not teste & set(d.g_va)
        assert not set(d.g_tr) & set(d.g_va)


class TestSemVazamento:
    def test_dobras_separam_participantes(self, base):
        d = treino.preparar(*base)
        folds = treino.dobras(d.g_tr)
        assert len(folds) == 5
        for itr, ite in folds:
            assert not set(d.g_tr[itr]) & set(d.g_tr[ite])
        assert sorted(np.concatenate([ite for _, ite in folds])) == list(range(len(d.g_tr)))

    def test_padronizador_usa_so_os_dados_de_ajuste(self, base):
        d = treino.preparar(*base)
        pad = treino.Padronizador().fit(d.X_tr)
        media, desvio = estatisticas_treino(d.X_tr)
        assert np.array_equal(pad.media_, media) and np.allclose(pad.desvio_, desvio)
        outro = treino.Padronizador().fit(d.X_va)
        assert not np.array_equal(outro.media_, pad.media_)
        assert np.array_equal(pad.transform(d.X_va)[:, 9:], d.X_va[:, 9:])  # one-hot intacto

    def test_baseline_e_a_taxa_do_treino(self, base):
        d = treino.preparar(*base)
        b = treino.BaselineIngenuo().fit(d.X_tr, d.y_tr)
        df = pd.DataFrame({"ini": d.X_tr[:, 1], "cand": d.X_tr[:, 0], "y": d.y_tr})
        for (ini, cand), taxa in df.groupby(["ini", "cand"])["y"].mean().items():
            assert b.taxa_[(int(ini), int(cand))] == pytest.approx(taxa)


class TestExecucao:
    def test_estrutura_e_metricas(self, base):
        res, objetos = treino.executar(*base, modelos=SKLEARN)
        assert res["fonte"] == "SINTETICO" and "lacrado" in res["aviso"]
        assert res["dados"]["identico_ao_registrado"] is True
        for nome in SKLEARN:
            v = res["modelos"][nome]["validacao"]["metricas"]
            assert {"log_loss", "brier", "roc_auc", "ece", "mae_p_real"} <= set(v)
            assert 0 < v["log_loss"] < 1 and 0 <= v["ece"] < 0.2
        assert len(res["modelos"]["arvore"]["grade"]) == 12 and len(res["modelos"]["logistica"]["grade"]) == 4
        assert set(res["comparacoes_validacao_preliminares"]) == {"logistica_menos_arvore", "arvore_menos_baseline"}
        assert {"python", "numpy", "scikit_learn", "pandas"} <= set(res["ambiente"])

    def test_reproduzivel(self, base):
        a, _ = treino.executar(*base, modelos=SKLEARN)
        b, _ = treino.executar(*base, modelos=SKLEARN)
        for r in (a, b):
            for m in r["modelos"].values():
                m.pop("segundos")
        assert a == b

    def test_oraculo_e_melhor_que_os_modelos(self, base):
        res, _ = treino.executar(*base, modelos=SKLEARN)
        oraculo = res["oraculo_p_real"]["validacao"]["log_loss"]
        assert all(oraculo < m["validacao"]["metricas"]["log_loss"] for m in res["modelos"].values())


class TestLinhaDeComandoEAnotacoes:
    def test_cli_sem_mlp(self, base, tmp_path):
        csv, split = base
        assert treinar.main(["--dados", str(csv), "--split", str(split), "--saida", str(tmp_path),
                             "--modelos", *SKLEARN, "--salvar-modelos", str(tmp_path / "m")]) == 0
        res = json.loads((tmp_path / "validacao.json").read_text(encoding="utf-8"))
        assert set(res["modelos"]) == set(SKLEARN) and res["execucao"]["modelos_pedidos"] == list(SKLEARN)
        assert (tmp_path / "m" / "arvore.joblib").exists()

    def test_anotacoes_ida_e_volta(self):
        conteudo = json.dumps({"x": list(range(30_000))}).encode()
        linhas = treinar.anotacoes(conteudo, "resumo")
        assert linhas[0].startswith("::notice title=guardia-resumo::")
        anot = []
        for linha in linhas[1:]:
            cab, msg = linha[len("::notice "):].split("::", 1)
            anot.append({"title": cab.removeprefix("title="), "message": msg})
        assert len(anot) > 1
        assert ler_resultado_ci.reconstruir(list(reversed(anot))) == conteudo

    def test_anotacao_adulterada_e_rejeitada(self):
        linha = treinar.anotacoes(b'{"a": 1}', "r")[1]
        cab, msg = linha[len("::notice "):].split("::", 1)
        outro = treinar.anotacoes(b'{"a": 2}', "r")[1].split("::", 2)[2]
        with pytest.raises(ValueError, match="SHA-256"):
            ler_resultado_ci.reconstruir([{"title": cab.removeprefix("title="), "message": outro}])


@pytest.mark.skipif(not treino.tensorflow_disponivel(), reason="TensorFlow não instalado (roda no CI)")
def test_mlp_pipeline_curto(base):
    res, objetos = treino.executar(*base, modelos=("arvore", "mlp"), config_mlp={"max_epocas": 3, "paciencia": 1},
                                   arquiteturas_mlp=[(8,), (16,)], sementes_mlp=(2026, 2027))
    mlp = res["modelos"]["mlp"]
    assert len(mlp["grade"]) == 2 and len(mlp["execucoes"]) == 2
    assert mlp["escolhido"]["arquitetura"] in ([8], [16])
    assert mlp["equivalencia_keras_formato_contrato_max"] < 1e-5
    assert "mlp_menos_arvore" in res["comparacoes_validacao_preliminares"]
    assert res["ambiente"]["tensorflow"]
