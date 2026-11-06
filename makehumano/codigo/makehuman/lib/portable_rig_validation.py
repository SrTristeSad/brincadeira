"""Leitura independente dos dados de skinning gerados pelos smokes."""
from dataclasses import dataclass
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zlib
import numpy as np


@dataclass
class _Node:
    name: bytes
    properties: bytes
    children: list


def _nodes(data, start, stop, wide, depth=0):
    if depth > 64:
        raise ValueError("FBX: hierarquia excede o limite de leitura")
    header = struct.Struct("<QQQB" if wide else "<IIIB")
    result = []
    while start < stop:
        if start + header.size > stop:
            raise ValueError("FBX: registro truncado")
        end, count, length, name_length = header.unpack_from(data, start)
        if end == 0:
            if count or length or name_length:
                raise ValueError("FBX: terminador inválido")
            break
        name_start = start + header.size
        props_start = name_start + name_length
        children_start = props_start + length
        if not children_start <= end <= stop or end <= start:
            raise ValueError("FBX: limites de registro inválidos")
        result.append(_Node(data[name_start:props_start], data[props_start:children_start],
                            _nodes(data, children_start, end, wide, depth+1)))
        start = end
    return result


def _array(properties):
    types = {b"i": "<i4", b"l": "<i8", b"f": "<f4", b"d": "<f8"}
    if len(properties) < 13 or properties[:1] not in types:
        raise ValueError("FBX: array de skinning inválido")
    count, encoding, length = struct.unpack_from("<III", properties, 1)
    payload = properties[13:]
    if len(payload) != length or encoding not in (0, 1):
        raise ValueError("FBX: comprimento/encoding do array inválido")
    if encoding == 1:
        payload = zlib.decompress(payload)
    dtype = np.dtype(types[properties[:1]])
    if len(payload) != count*dtype.itemsize:
        raise ValueError("FBX: quantidade de elementos incompatível")
    return np.frombuffer(payload, dtype=dtype)


def validar_fbx_rig(path, minimum_bones):
    data = Path(path).read_bytes()
    if len(data) < 27 or data[:23] != b"Kaydara FBX Binary  \x00\x1a\x00":
        raise ValueError("FBX: cabeçalho binário inválido")
    version = struct.unpack_from("<I", data, 23)[0]
    roots = _nodes(data, 27, len(data), version >= 7500)
    objects = next((n for n in roots if n.name == b"Objects"), None)
    if objects is None:
        raise ValueError("FBX: objetos ausentes")
    bones = [n for n in objects.children if n.name == b"Model" and b"LimbNode" in n.properties]
    clusters = [n for n in objects.children if n.name == b"Deformer" and b"Cluster" in n.properties]
    if len(bones) < minimum_bones or not clusters:
        raise ValueError("FBX: esqueleto ou clusters ausentes")
    total_weights = 0
    for node in clusters:
        children = {n.name: n for n in node.children}
        if not {b"Indexes", b"Weights", b"Transform", b"TransformLink"} <= children.keys():
            raise ValueError("FBX: cluster sem índices/pesos/matrizes")
        indices = _array(children[b"Indexes"].properties)
        weights = _array(children[b"Weights"].properties)
        if indices.dtype.kind not in "iu" or len(indices) != len(weights) or np.any(indices < 0):
            raise ValueError("FBX: índices de cluster inválidos")
        if not np.isfinite(weights).all() or np.any(weights < 0) or np.any(weights > 1.000001):
            raise ValueError("FBX: pesos de cluster inválidos")
        for name in (b"Transform", b"TransformLink"):
            matrix = _array(children[name].properties)
            if matrix.size != 16 or not np.isfinite(matrix).all():
                raise ValueError("FBX: matriz de vínculo inválida")
        total_weights += len(weights)
    if total_weights == 0:
        raise ValueError("FBX: nenhum peso exportado")
    return {"bones": len(bones), "clusters": len(clusters), "weights": total_weights}


def validar_collada_rig(path, minimum_bones):
    ns = {"c": "http://www.collada.org/2005/11/COLLADASchema"}
    root = ET.parse(path).getroot()
    bones = root.findall('.//c:node[@type="JOINT"]', ns)
    skins = root.findall(".//c:controller/c:skin", ns)
    if len(bones) < minimum_bones or not skins:
        raise ValueError("Collada: esqueleto ou controladores ausentes")
    total_vertices = 0
    for skin in skins:
        sources = {s.attrib["id"]: s for s in skin.findall("c:source", ns)}
        vertex_weights = skin.find("c:vertex_weights", ns)
        if vertex_weights is None:
            raise ValueError("Collada: vertex_weights ausente")
        inputs = {i.attrib["semantic"]: i for i in vertex_weights.findall("c:input", ns)}
        if not {"JOINT", "WEIGHT"} <= inputs.keys():
            raise ValueError("Collada: referências a ossos/pesos ausentes")
        weights_source = sources[inputs["WEIGHT"].attrib["source"].lstrip("#")]
        joints_source = sources[inputs["JOINT"].attrib["source"].lstrip("#")]
        weights_node = weights_source.find("c:float_array", ns)
        joints_node = joints_source.find("c:IDREF_array", ns)
        if joints_node is None:
            joints_node = joints_source.find("c:Name_array", ns)
        if weights_node is None or joints_node is None:
            raise ValueError("Collada: dados de pesos/ossos ausentes")
        weights = np.fromstring(weights_node.text or "", sep=" ")
        joints = (joints_node.text or "").split()
        counts = np.fromstring(vertex_weights.find("c:vcount", ns).text or "", sep=" ", dtype=int)
        values = np.fromstring(vertex_weights.find("c:v", ns).text or "", sep=" ", dtype=int)
        stride = 1+max(int(i.attrib["offset"]) for i in inputs.values())
        if len(counts) != int(vertex_weights.attrib["count"]) or len(values) != stride*int(counts.sum()):
            raise ValueError("Collada: índices/pesos incompatíveis com os vértices")
        if np.any(counts <= 0) or not np.isfinite(weights).all() or np.any(weights < 0):
            raise ValueError("Collada: vértices sem pesos ou pesos inválidos")
        values = values.reshape(-1, stride)
        ji = values[:, int(inputs["JOINT"].attrib["offset"])]
        wi = values[:, int(inputs["WEIGHT"].attrib["offset"])]
        if np.any(ji < 0) or np.any(ji >= len(joints)) or np.any(wi < 0) or np.any(wi >= len(weights)):
            raise ValueError("Collada: índice de osso/peso fora do array")
        sums = np.add.reduceat(weights[wi], np.r_[0, np.cumsum(counts)[:-1]])
        if not np.allclose(sums, 1., atol=1e-3):
            raise ValueError("Collada: pesos exportados não normalizados")
        total_vertices += len(counts)
    return {"bones": len(bones), "skins": len(skins), "vertices": total_vertices}
