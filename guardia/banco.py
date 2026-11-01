"""Validação e classificação do banco de perguntas para o fluxo-0.8.

Não é Machine Learning: verifica formato, cobertura nível × categoria,
viabilidade das partidas e se cada pergunta cabe na tela ST7735 (128×160).

Premissas de tela (docs/banco_questoes.md, seção 5), ajustáveis em ``LayoutTFT``:

- fonte padrão da Adafruit GFX: glifo 5×7 em célula de 6×8 px;
- tamanho 1, retrato (128×160): 21 colunas × 20 linhas;
- paisagem (160×128): 26 colunas × 16 linhas.

A fonte padrão da GFX não exibe corretamente acentos codificados em UTF-8
(cada letra acentuada ocupa 2 bytes). Por isso caracteres fora do ASCII geram
AVISO: o firmware precisa convertê-los ou usar outra fonte.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from guardia import contrato as C
from guardia.politica import problemas_de_viabilidade

COLUNAS_BANCO = (
    "id", "origem", "nivel", "categoria", "enunciado",
    "alt_a", "alt_b", "alt_c", "alt_d", "correta", "dica", "revisado_por",
)
ALTERNATIVAS = ("A", "B", "C", "D")
NOMES_NIVEL = ("Explorador", "Desafiante", "Mestre")
NOMES_CATEGORIA = ("Matemática", "Português", "Lógica", "Conhecimentos gerais")

APTA = "apta"                # pode ser usada como está
AJUSTAR = "ajustar"          # completa e classificada, mas precisa de ajuste (ex.: texto não cabe)
PENDENTE = "pendente"        # falta classificar nível ou categoria
INVALIDA = "invalida"        # faltam dados essenciais


# Texto mais longo do cabeçalho: nível, progresso e temporizador.
CABECALHO_MAIS_LONGO = "DESAFIANTE 3/3 30s"


@dataclass(frozen=True)
class LayoutTFT:
    """Ocupação da tela. Valores padrão: ST7735 em retrato, tamanho 1.

    ``escala`` é o tamanho do texto do CORPO (enunciado, alternativas, dica).
    ``escala_moldura`` é o do cabeçalho e do rodapé; se None, igual a ``escala``.
    O encaixe é verificado em pixels, o que permite combinar os dois tamanhos.
    """

    largura_px: int = 128
    altura_px: int = 160
    celula_px: tuple[int, int] = (6, 8)
    escala: int = 1
    linhas_cabecalho: int = 1   # nível, progresso e temporizador
    linhas_rodape: int = 1      # "*=Dica"
    linhas_separadoras: int = 1  # espaço entre enunciado e alternativas
    escala_moldura: int | None = None

    @property
    def esc_moldura(self) -> int:
        return self.escala_moldura or self.escala

    @property
    def altura_linha_corpo(self) -> int:
        return self.celula_px[1] * self.escala

    @property
    def altura_linha_moldura(self) -> int:
        return self.celula_px[1] * self.esc_moldura

    @property
    def colunas_moldura(self) -> int:
        return self.largura_px // (self.celula_px[0] * self.esc_moldura)

    def descricao(self) -> str:
        orient = "retrato" if self.altura_px >= self.largura_px else "paisagem"
        return (f"{self.largura_px}×{self.altura_px} px ({orient}), corpo tamanho {self.escala} "
                f"({self.colunas} colunas), cabeçalho/rodapé tamanho {self.esc_moldura}, "
                f"{self.linhas_cabecalho} linha(s) de cabeçalho")

    @property
    def colunas(self) -> int:
        return self.largura_px // (self.celula_px[0] * self.escala)

    @property
    def linhas(self) -> int:
        return self.altura_px // (self.celula_px[1] * self.escala)

    @classmethod
    def paisagem(cls, **kw) -> "LayoutTFT":
        return cls(largura_px=160, altura_px=128, **kw)


def quebrar(texto: str, largura: int, recuo: int = 0) -> list[str]:
    """Quebra por palavras; palavras maiores que a linha são cortadas.

    ``recuo`` é aplicado às linhas de continuação (alinha com o texto após "A) ").
    """
    if largura <= recuo:
        raise ValueError("Largura insuficiente.")
    linhas: list[str] = []
    atual = ""
    for palavra in texto.split():
        while True:
            limite = largura - (recuo if linhas else 0)
            candidato = f"{atual} {palavra}" if atual else palavra
            if len(candidato) <= limite:
                atual = candidato
                break
            if atual:
                linhas.append(atual)
                atual = ""
                continue
            linhas.append(palavra[:limite])  # palavra maior que a linha
            palavra = palavra[limite:]
    if atual or not linhas:
        linhas.append(atual)
    return linhas


@dataclass
class Pergunta:
    id: str
    origem: str
    nivel: int | None
    categoria: int | None
    enunciado: str
    alternativas: dict[str, str]
    correta: str
    dica: str
    revisado_por: str
    linha_csv: int = 0


@dataclass
class Avaliacao:
    pergunta: Pergunta
    situacao: str
    motivos: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    linhas_tela: dict[str, int] = field(default_factory=dict)


def _int_ou_none(v: str, maximo: int) -> int | None:
    v = (v or "").strip()
    if v == "":
        return None
    n = int(v)
    if not 0 <= n < maximo:
        raise ValueError(f"valor {n} fora de 0..{maximo - 1}")
    return n


def carregar_banco(caminho: Path) -> list[Pergunta]:
    with open(caminho, encoding="utf-8", newline="") as f:
        leitor = csv.DictReader(f)
        if tuple(leitor.fieldnames or ()) != COLUNAS_BANCO:
            raise ValueError(f"Colunas esperadas: {', '.join(COLUNAS_BANCO)}")
        perguntas = []
        for i, r in enumerate(leitor, start=2):
            try:
                nivel = _int_ou_none(r["nivel"], C.N_NIVEIS)
                categoria = _int_ou_none(r["categoria"], C.N_CATEGORIAS)
            except ValueError as e:
                raise ValueError(f"linha {i} ({r['id']}): {e}") from None
            perguntas.append(
                Pergunta(
                    id=r["id"].strip(), origem=r["origem"].strip(), nivel=nivel, categoria=categoria,
                    enunciado=r["enunciado"].strip(),
                    alternativas={a: r[f"alt_{a.lower()}"].strip() for a in ALTERNATIVAS},
                    correta=r["correta"].strip().upper(), dica=r["dica"].strip(),
                    revisado_por=r["revisado_por"].strip(), linha_csv=i,
                )
            )
    return perguntas


def linhas_por_tela(p: Pergunta, layout: LayoutTFT) -> dict[str, int]:
    """Linhas ocupadas em cada tela do fluxo (pergunta, dica, resposta correta)."""
    col = layout.colunas
    fixo = layout.linhas_cabecalho + layout.linhas_rodape
    pergunta = fixo + len(quebrar(p.enunciado, col)) + layout.linhas_separadoras + sum(
        len(quebrar(f"{a}) {p.alternativas[a]}", col, recuo=3)) for a in ALTERNATIVAS
    )
    dica = layout.linhas_cabecalho + len(quebrar(f"Dica: {p.dica}", col))
    texto_correta = p.alternativas.get(p.correta, "")
    resposta = layout.linhas_cabecalho + len(quebrar(f"Resposta: {p.correta}) {texto_correta}", col, recuo=3))
    return {"pergunta": pergunta, "dica": dica, "resposta": resposta}


def altura_por_tela(p: Pergunta, layout: LayoutTFT) -> dict[str, int]:
    """Altura em pixels de cada tela, com corpo e moldura em escalas possivelmente diferentes."""
    col = layout.colunas
    hc, hm = layout.altura_linha_corpo, layout.altura_linha_moldura
    corpo = len(quebrar(p.enunciado, col)) + layout.linhas_separadoras + sum(
        len(quebrar(f"{a}) {p.alternativas[a]}", col, recuo=3)) for a in ALTERNATIVAS
    )
    texto_correta = p.alternativas.get(p.correta, "")
    return {
        "pergunta": (layout.linhas_cabecalho + layout.linhas_rodape) * hm + corpo * hc,
        "dica": layout.linhas_cabecalho * hm + len(quebrar(f"Dica: {p.dica}", col)) * hc,
        "resposta": layout.linhas_cabecalho * hm
        + len(quebrar(f"Resposta: {p.correta}) {texto_correta}", col, recuo=3)) * hc,
    }


def avaliar(p: Pergunta, layout: LayoutTFT) -> Avaliacao:
    motivos, avisos = [], []
    if not p.id:
        motivos.append("sem id")
    if not p.enunciado:
        motivos.append("sem enunciado")
    faltando = [a for a in ALTERNATIVAS if not p.alternativas[a]]
    if faltando:
        motivos.append(f"alternativas vazias: {', '.join(faltando)}")
    if p.correta not in ALTERNATIVAS:
        motivos.append(f"correta inválida: {p.correta!r}")
    if len({v.casefold() for v in p.alternativas.values() if v}) < len([v for v in p.alternativas.values() if v]):
        motivos.append("alternativas repetidas")
    if motivos:
        return Avaliacao(p, INVALIDA, motivos)

    alturas = altura_por_tela(p, layout)
    ajustes = [f"tela de {tela} usa {h} de {layout.altura_px} px" for tela, h in alturas.items() if h > layout.altura_px]
    if not p.dica:
        ajustes.append("sem dica (a tecla * precisa de texto)")
    texto = " ".join([p.enunciado, p.dica, *p.alternativas.values()])
    especiais = sorted({ch for ch in texto if ord(ch) > 127})
    if especiais:
        avisos.append(f"caracteres fora do ASCII exigem conversão na fonte do TFT: {' '.join(especiais)}")
    if not p.revisado_por:
        avisos.append("sem revisor registrado")

    pendencias = []
    if p.nivel is None:
        pendencias.append("nível não classificado")
    if p.categoria is None:
        pendencias.append("categoria não classificada")
    if pendencias:
        return Avaliacao(p, PENDENTE, pendencias + ajustes, avisos, alturas)
    return Avaliacao(p, AJUSTAR if ajustes else APTA, ajustes, avisos, alturas)


@dataclass
class RelatorioBanco:
    avaliacoes: list[Avaliacao]
    layout: LayoutTFT
    meta_por_celula: int
    duplicados: list[str]

    @property
    def aptas_por_celula(self) -> Counter:
        return Counter(
            (a.pergunta.nivel, a.pergunta.categoria) for a in self.avaliacoes if a.situacao == APTA
        )

    def adicionais_necessarias(self, meta: int | None = None) -> int:
        meta = self.meta_por_celula if meta is None else meta
        cont = self.aptas_por_celula
        return sum(max(0, meta - cont[(n, c)]) for n in range(C.N_NIVEIS) for c in range(C.N_CATEGORIAS))

    def problemas_viabilidade(self) -> list[str]:
        cont = self.aptas_por_celula
        return problemas_de_viabilidade(lambda n, c: cont[(n, c)] > 0)


def analisar(perguntas: list[Pergunta], layout: LayoutTFT | None = None, meta_por_celula: int = 3) -> RelatorioBanco:
    layout = layout or LayoutTFT()
    ids = Counter(p.id for p in perguntas)
    enunciados = Counter(p.enunciado.casefold() for p in perguntas if p.enunciado)
    avaliacoes = [avaliar(p, layout) for p in perguntas]
    for a in avaliacoes:
        if ids[a.pergunta.id] > 1:
            a.situacao, a.motivos = INVALIDA, a.motivos + ["id duplicado"]
        if a.pergunta.enunciado and enunciados[a.pergunta.enunciado.casefold()] > 1:
            a.avisos.append("enunciado repetido no banco")
    duplicados = sorted(i for i, n in ids.items() if n > 1)
    return RelatorioBanco(avaliacoes, layout, meta_por_celula, duplicados)


def relatorio_markdown(r: RelatorioBanco, titulo: str) -> str:
    cab_ok = len(CABECALHO_MAIS_LONGO) <= r.layout.colunas_moldura
    L = [f"# {titulo}", "",
         f"Tela: {r.layout.descricao()}.", "",
         f"Cabeçalho mais longo (`{CABECALHO_MAIS_LONGO}`, {len(CABECALHO_MAIS_LONGO)} caracteres): "
         + ("cabe." if cab_ok else f"**não cabe** em {r.layout.colunas_moldura} colunas."), "",
         "## Situação das perguntas", "",
         f"| id | origem | nível | categoria | situação | altura em px, de {r.layout.altura_px} (pergunta/dica/resposta) | motivos | avisos |",
         "|---|---|---|---|---|---|---|---|"]
    for a in r.avaliacoes:
        p = a.pergunta
        lt = "/".join(str(a.linhas_tela.get(t, "—")) for t in ("pergunta", "dica", "resposta"))
        L.append(
            f"| {p.id} | {p.origem} | {NOMES_NIVEL[p.nivel] if p.nivel is not None else '—'} | "
            f"{NOMES_CATEGORIA[p.categoria] if p.categoria is not None else '—'} | **{a.situacao}** | {lt} | "
            f"{'; '.join(a.motivos) or '—'} | {'; '.join(a.avisos) or '—'} |"
        )
    cont = Counter(a.situacao for a in r.avaliacoes)
    L += ["", "| Situação | Quantidade |", "|---|---|"]
    L += [f"| {s} | {cont[s]} |" for s in (APTA, AJUSTAR, PENDENTE, INVALIDA)]

    aptas = r.aptas_por_celula
    L += ["", "## Perguntas aptas por célula (nível × categoria)", "",
          "| Nível \\ categoria | " + " | ".join(NOMES_CATEGORIA) + " |", "|---|---|---|---|---|"]
    for n in range(C.N_NIVEIS):
        L.append(f"| {NOMES_NIVEL[n]} | " + " | ".join(str(aptas[(n, c)]) for c in range(C.N_CATEGORIAS)) + " |")
    L += ["", "## Perguntas adicionais necessárias", "", "| Meta por célula | Total da meta | Adicionais |", "|---|---|---|"]
    for meta in (1, 3, 5):
        L.append(f"| {meta} | {12 * meta} | {r.adicionais_necessarias(meta)} |")
    probs = r.problemas_viabilidade()
    L += ["", "## Viabilidade das partidas do fluxo-0.8 (só perguntas aptas)", ""]
    L += ["Todas as partidas possíveis são viáveis."] if not probs else [f"- {p}" for p in probs]
    L.append("")
    return "\n".join(L)
