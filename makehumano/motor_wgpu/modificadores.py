"""Catálogo de sliders anatômicos derivado dos arquivos oficiais do MakeHuman.

Apenas alvos .target DIRETOS. Macrovariáveis (idade, peso, gênero, raça,
musculatura etc.) continuam dependentes do sistema original e são excluídas.
"""

from dataclasses import dataclass
import json
from pathlib import Path

from .morphs import pasta_targets


PASTA_MODIFICADORES = (
    Path(__file__).resolve().parents[1] / "codigo" / "makehuman"
    / "data" / "modifiers"
)

NOMES_GRUPOS = {
    "head": "Cabeça",
    "forehead": "Testa",
    "eyebrows": "Sobrancelhas",
    "neck": "Pescoço",
    "eyes": "Olhos",
    "nose": "Nariz",
    "mouth": "Boca",
    "ears": "Orelhas",
    "chin": "Queixo",
    "cheek": "Bochechas",
    "torso": "Torso",
    "hip": "Quadril",
    "stomach": "Abdômen",
    "buttocks": "Glúteos",
    "pelvis": "Pelve",
    "armslegs": "Braços e pernas",
    "breast": "Seios",
    "genitals": "Genitais",
}


@dataclass(frozen=True)
class ModificadorDireto:
    identificador: str
    grupo: str
    rotulo: str
    negativo: Path | None
    positivo: Path

    @property
    def minimo(self) -> int:
        return -100 if self.negativo is not None else 0

    def pesos(self, valor: int | float) -> dict[Path, float]:
        """Converte [-100,100] em pesos positivos dos alvos de cada direção."""
        valor = float(valor)
        if not self.minimo <= valor <= 100:
            raise ValueError("Valor do slider fora de seus limites")
        resultado = {self.positivo: max(0.0, valor / 100.0)}
        if self.negativo is not None:
            resultado[self.negativo] = max(0.0, -valor / 100.0)
        return resultado


def carregar_catalogo(
    pasta_config: Path = PASTA_MODIFICADORES,
    pasta_alvos: Path | None = None,
) -> list[ModificadorDireto]:
    """Usa a configuração oficial e apenas pares de targets que existem.

    Não interpreta alvos condicionais nem presume suporte a macrovariáveis.
    Um modificador só entra no catálogo se todos os arquivos necessários
    existirem. Identificadores mantêm os sufixos min/max para serem únicos.
    """
    pasta_alvos = pasta_targets() if pasta_alvos is None else Path(pasta_alvos)
    pasta_config = Path(pasta_config)
    definicoes = json.loads(
        (pasta_config / "modeling_modifiers.json").read_text(encoding="utf-8")
    )
    sliders = json.loads(
        (pasta_config / "modeling_sliders.json").read_text(encoding="utf-8")
    )
    rotulos = {}
    for categoria in sliders.values():
        for subgrupo in categoria.get("modifiers", {}).values():
            for entrada in subgrupo:
                if "mod" in entrada:
                    rotulos[entrada["mod"]] = entrada.get("label", "")

    itens = []
    utilizados = set()
    for bloco in definicoes:
        grupo = bloco["group"]
        for definicao in bloco["modifiers"]:
            if "macrovar" in definicao or "modifierType" in definicao:
                continue
            if "target" not in definicao or "mid" in definicao:
                continue
            base = definicao["target"]
            minimo = definicao.get("min")
            maximo = definicao.get("max")
            # Configurações incompletas são ignoradas, não inventadas.
            if bool(minimo) != bool(maximo):
                continue
            prefixo = pasta_alvos / grupo / base
            negativo = prefixo.with_name(prefixo.name + "-" + minimo).with_suffix(".target") if minimo else None
            positivo = prefixo.with_name(prefixo.name + "-" + maximo).with_suffix(".target") if maximo else prefixo.with_suffix(".target")
            if not positivo.is_file() or (negativo and not negativo.is_file()):
                continue
            nome = f"{grupo}/{base}"
            if negativo is not None:
                nome += f"-{minimo}|{maximo}"
            if nome in utilizados:
                raise ValueError(f"Modificador duplicado: {nome}")
            utilizados.add(nome)
            rotulo = rotulos.get(nome) or base.replace("-", " ").capitalize()
            itens.append(ModificadorDireto(nome, grupo, rotulo, negativo, positivo))
    return itens
