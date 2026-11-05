"""Ponte de macrovariáveis MakeHuman para o renderizador wgpu.

As funções de interpolação reproduzem as fórmulas de Human._set*Vals
em codigo/makehuman/apps/human.py. Os pesos de cada .target são o produto
dos fatores de categoria reconhecidos pelo crawler em lib/targets.py.

Não substitui Human/Modifier: integração do modelo com poses, simetria,
plugins e eventos da GUI principal permanece trabalho separado.
"""

from pathlib import Path
import math

from .morphs import Deformador, ler_target, pasta_targets


# Mesmas categorias e identificadores definidos em lib/targets.py.
CATEGORIAS = {
    "gender": ("male", "female"),
    "age": ("baby", "child", "young", "old"),
    "race": ("caucasian", "asian", "african"),
    "muscle": ("maxmuscle", "averagemuscle", "minmuscle"),
    "weight": ("minweight", "averageweight", "maxweight"),
    "height": ("minheight", "averageheight", "maxheight"),
    "breastsize": ("mincup", "averagecup", "maxcup"),
    "breastfirmness": ("minfirmness", "averagefirmness", "maxfirmness"),
    "bodyproportions": ("uncommonproportions", "regularproportions", "idealproportions"),
}
VALORES = set(v for valores in CATEGORIAS.values() for v in valores)
ETNIAS = ("african", "asian", "caucasian")
ETNIAS_PADRAO = {nome: 1.0 / 3.0 for nome in ETNIAS}
ROTULOS_ETNIAS = {
    "african": "Africana (alvos MakeHuman)",
    "asian": "Asiática (alvos MakeHuman)",
    "caucasian": "Caucasiana (alvos MakeHuman)",
}

# Caminhos base para cada grupo declarado nos modifiers JSON originais.
GRUPOS = {
    "macrodetails": lambda root: root / "macrodetails",
    "macrodetails-universal": lambda root: root / "macrodetails",
    "macrodetails-height": lambda root: root / "macrodetails" / "height",
    "macrodetails-proportions": lambda root: root / "macrodetails" / "proportions",
    "breast": lambda root: root / "breast",
}

VALORES_PADRAO = {
    "age": 0.5,
    "gender": 0.5,
    "weight": 0.5,
    "muscle": 0.5,
    "height": 0.5,
    "breastSize": 0.5,
    "breastFirmness": 0.5,
    "bodyProportions": 0.5,
}
ROTULOS = {
    "age": "Idade (perfil)",
    "gender": "Gênero morfológico",
    "weight": "Peso (perfil)",
    "muscle": "Musculatura",
    "height": "Altura (perfil)",
    "breastSize": "Volume dos seios",
    "breastFirmness": "Firmeza dos seios",
    "bodyProportions": "Proporções corporais",
}


def _triplo(valor, minimo, medio, maximo):
    # Equivalente ao cálculo das variáveis dos atributos lineares em human.py.
    minimo_v = max(0.0, 1 - valor * 2)
    maximo_v = max(0.0, valor * 2 - 1)
    medio_v = 1 - (minimo_v + maximo_v)
    return {minimo: minimo_v, medio: medio_v, maximo: maximo_v}


class PerfilMacro:
    """Fatores para oito macros e três parâmetros étnicos interdependentes."""

    def __init__(self):
        self.valores = VALORES_PADRAO.copy()
        self.etnias = ETNIAS_PADRAO.copy()

    def definir(self, chave: str, valor: float) -> None:
        if chave not in self.valores:
            raise KeyError(f"Macrovariável desconhecida: {chave}")
        valor = float(valor)
        if not math.isfinite(valor) or not 0.0 <= valor <= 1.0:
            raise ValueError(f"{chave} precisa de valor finito entre 0 e 1")
        self.valores[chave] = valor

    def definir_etnia(self, chave: str, valor: float) -> None:
        """Reproduz Human._setEthnicVals(exclude) de apps/human.py.

        O parâmetro selecionado é mantido; os dois restantes são ajustados
        proporcionalmente para totalizar 1. Quando os demais são zero, usamos
        exatamente os casos especiais do MakeHuman original.
        """
        if chave not in ETNIAS:
            raise KeyError(f"Categoria étnica desconhecida: {chave}")
        valor = float(valor)
        if not math.isfinite(valor) or not (0.0 <= valor <= 1.0):
            raise ValueError("Fração étnica precisa estar entre 0 e 1")
        self.etnias[chave] = valor
        outras = tuple(nome for nome in ETNIAS if nome != chave)
        restante = 1.0 - valor
        total_outras = sum(self.etnias[nome] for nome in outras)

        if total_outras == 0.0:
            if valor == 0.0:
                # Human._setEthnicVals reinicializa os três com 1/3.
                self.etnias = ETNIAS_PADRAO.copy()
            elif abs(valor - 1.0) <= 0.001:
                for nome in outras:
                    self.etnias[nome] = 0.0
                self.etnias[chave] = 1.0
            else:
                # O original injeta 0.01 nos outros dois e renormaliza.
                for nome in outras:
                    self.etnias[nome] = restante / len(outras)
        else:
            for nome in outras:
                self.etnias[nome] = restante * (
                    self.etnias[nome] / total_outras
                )

    def restaurar(self):
        self.valores = VALORES_PADRAO.copy()
        self.etnias = ETNIAS_PADRAO.copy()

    def fatores(self) -> dict[str, float]:
        a = self.valores["age"]
        if a < 0.5:
            idade = {
                "old": 0.0,
                "baby": max(0.0, 1 - a * 5.333),
                "young": max(0.0, (a - 0.1875) * 3.2),
            }
            idade["child"] = max(0.0, min(1.0, 5.333 * a) - idade["young"])
        else:
            idade = {
                "child": 0.0, "baby": 0.0,
                "old": max(0.0, a * 2 - 1),
            }
            idade["young"] = 1 - idade["old"]

        genero = self.valores["gender"]
        fatores = {
            **idade,
            "male": genero, "female": 1 - genero,
            **self.etnias,
        }
        fatores.update(_triplo(self.valores["weight"], "minweight", "averageweight", "maxweight"))
        fatores.update(_triplo(self.valores["muscle"], "minmuscle", "averagemuscle", "maxmuscle"))
        fatores.update(_triplo(self.valores["height"], "minheight", "averageheight", "maxheight"))
        fatores.update(_triplo(self.valores["breastSize"], "mincup", "averagecup", "maxcup"))
        fatores.update(_triplo(self.valores["breastFirmness"], "minfirmness", "averagefirmness", "maxfirmness"))
        fatores.update(_triplo(self.valores["bodyProportions"], "uncommonproportions", "regularproportions", "idealproportions"))
        return fatores


def arquivos_macro(root: Path | None = None) -> tuple[Path, ...]:
    """Catálogo baseado em diretórios e sufixos originais, sem inventar targets."""
    root = pasta_targets() if root is None else Path(root)
    macro = root / "macrodetails"
    grupos = [
        *(p for p in macro.glob("*.target") if not p.name.startswith("universal-")),
        *macro.glob("universal-*.target"),
        *(macro / "height").glob("*.target"),
        *(macro / "proportions").glob("*.target"),
        *(p for p in (root / "breast").glob("*.target")
          if p.stem.split("-")[0] in {"male", "female"}),
    ]
    return tuple(sorted(set(grupos)))


def fatores_alvo(arquivo: Path, fatores: dict[str, float]) -> float:
    """Equivale ao produto dos factors calculados pelo TargetsCrawler.

    O crawler interpreta os tokens do nome e dos diretórios, ignorando os
    tokens que não forem categorias registradas.
    """
    peso = 1.0
    for parte in arquivo.stem.replace("_", "-").split("-"):
        if parte in VALORES:
            peso *= fatores[parte]
    return peso


class ControladorMacros:
    """Alimenta o Deformador existente; não cria outro mecanismo de mesh."""

    def __init__(self, deformador: Deformador, pasta: Path | None = None):
        self.deformador = deformador
        self.perfil = PerfilMacro()
        self.arquivos = arquivos_macro(pasta)
        self._carregados = {}
        self._ativos = set()

    def definir(self, chave: str, valor: float):
        self.perfil.definir(chave, valor)
        return self.atualizar()

    def definir_etnia(self, chave: str, valor: float):
        self.perfil.definir_etnia(chave, valor)
        return self.atualizar()

    def restaurar(self):
        self.perfil.restaurar()
        return self.atualizar()

    def atualizar(self):
        fatores = self.perfil.fatores()
        pesos = {}
        for arquivo in self.arquivos:
            peso = fatores_alvo(arquivo, fatores)
            if peso > 0:
                pesos[str(arquivo)] = (arquivo, peso)

        atualizacoes = {}
        for nome in self._ativos - pesos.keys():
            atualizacoes[nome] = (self._carregados[nome], 0.0)
        for nome, (arquivo, peso) in pesos.items():
            if nome not in self._carregados:
                self._carregados[nome] = ler_target(
                    arquivo, len(self.deformador.malha.posicoes_base)
                )
            atualizacoes[nome] = (self._carregados[nome], peso)

        resultado = self.deformador.definir_pesos(atualizacoes)
        self._ativos = set(pesos)
        return resultado
