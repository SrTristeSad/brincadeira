"""Estado de material para comparar os harnesses OpenGL e Vulkan.

Diagnóstico puro: não importa os renderizadores nem modifica objetos.
Compatível com Python/NumPy usados nos dois ambientes isolados.
"""
import hashlib
import json
from pathlib import Path


MAPAS = (
    "diffuseTexture", "aoMapTexture", "normalMapTexture", "specularMapTexture",
    "transparencyMapTexture", "bumpMapTexture", "displacementMapTexture",
)


def _serializar(valor):
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    if hasattr(valor, "values") and not isinstance(valor, dict):
        return _serializar(valor.values)
    if hasattr(valor, "tolist"):
        return _serializar(valor.tolist())
    if isinstance(valor, (list, tuple)):
        return [_serializar(v) for v in valor]
    if isinstance(valor, dict):
        return {str(k): _serializar(v) for k, v in sorted(
            valor.items(), key=lambda item: str(item[0])
        )}
    if isinstance(valor, Path):
        return str(valor)
    # Evitar repr com endereço de memória dependente de execução.
    return {"tipo": type(valor).__name__}


def _arquivo(valor):
    if valor is None:
        return None
    if not isinstance(valor, (str, Path)):
        # O original permite Image/Texture em memória: não inventar hash de
        # um arquivo que nunca foi lido do disco.
        dados = getattr(valor, "data", None)
        if dados is not None and hasattr(dados, "tobytes"):
            return {
                "origem": "memoria",
                "sha256_pixels": hashlib.sha256(dados.tobytes()).hexdigest(),
                "shape": _serializar(getattr(dados, "shape", None)),
            }
        return {"origem": "objeto", "tipo": type(valor).__name__}
    caminho = Path(valor)
    saida = {
        "origem": "arquivo",
        "nome": caminho.name,
        "caminho": str(caminho),
        "existe": caminho.is_file(),
    }
    if caminho.is_file():
        hash_file = hashlib.sha256()
        with caminho.open("rb") as arquivo:
            for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
                hash_file.update(bloco)
        saida["sha256"] = hash_file.hexdigest()
        saida["bytes"] = caminho.stat().st_size
    return saida


def descrever_material(material):
    """Obtém estado antes da captura, sem alternar material ou shader."""
    if material is None:
        raise ValueError("Material ausente")
    campos = (
        "name", "shader", "shaderConfig", "shaderDefines",
        "shaderParameters", "diffuseColor", "ambientColor",
        "specularColor", "emissiveColor", "shininess", "opacity",
        "transparent", "alphaToCoverage",
    )
    resultado = {}
    for campo in campos:
        try:
            valor = getattr(material, campo, None)
        except Exception as exc:
            resultado[campo] = {"erro_leitura": type(exc).__name__}
            continue
        if campo == "shader" and valor is not None:
            # A raiz de instalação difere entre os checkouts; preservar o
            # caminho completo e também o nome lógico do shader.
            resultado[campo] = {"caminho": str(valor), "nome": Path(str(valor)).name}
        else:
            resultado[campo] = _serializar(valor)
    resultado["mapas"] = {}
    for nome in MAPAS:
        try:
            resultado["mapas"][nome] = _arquivo(getattr(material, nome, None))
        except Exception as exc:
            resultado["mapas"][nome] = {"erro_leitura": type(exc).__name__}
    # Dados efetivos que controlam compilação no GLSL legado. A propriedade
    # shaderConfig é um dicionário de configurações, não prova de #define ativo.
    defines = resultado.get("shaderDefines")
    resultado["define_diffuse_ativo"] = (
        "DIFFUSE" in defines if isinstance(defines, list) else None
    )
    return resultado


def _ler_campo_scene(obj, nome):
    """Evita recursão do __getattr__ antigo em campos inexistentes.

    SceneObject original implementa __getattr__ usando hasattr(self, attr),
    que chama __getattr__ novamente quando um atributo não foi declarado.
    Seus campos válidos estão em _attributes e _{nome}.
    """
    try:
        conhecidos = object.__getattribute__(obj, "_attributes")
    except AttributeError:
        return getattr(obj, nome, None)
    if nome in conhecidos:
        return object.__getattribute__(obj, "_" + nome)
    try:
        return object.__getattribute__(obj, nome)
    except AttributeError:
        return None


def descrever_iluminacao(cena):
    """Captura as entradas da cena; não executa iluminação."""
    if cena is None:
        return None
    ambiente = _ler_campo_scene(getattr(cena, "environment", None), "ambience") if getattr(cena, "environment", None) is not None else None
    luzes = []
    for luz in getattr(cena, "lights", ()) or ():
        luzes.append({campo: _serializar(_ler_campo_scene(luz, campo))
                      for campo in ("position", "focus", "color", "diffuse", "specular",
                                    "fov", "attenuation", "areaLights",
                                    "areaLightSize")})
    return {"ambiente": _serializar(ambiente), "luzes": luzes}


def salvar_estado(destino, material, cena=None, *, referencia=None):
    """Cria registro JSON em diretório de testes sem modificar a aplicação."""
    caminho = Path(destino)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    resultado = {
        "tipo": "ESTADO_MATERIAL_CAPTURA",
        "referencia": referencia,
        "material": descrever_material(material),
        "iluminacao": descrever_iluminacao(cena),
        "aviso": "Inspeção do estado; não constitui equivalência visual.",
    }
    caminho.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return resultado
