"""Visualizador experimental MakeHumano wgpu, separado do editor OpenGL.

Na pasta makehumano:
    python -m motor_wgpu.app
    python -m motor_wgpu.app --backend vulkan

É um protótipo: não substitui a viewport principal, não salva personagens.
"""

import argparse
import os
import sys
from pathlib import Path

from .malha import caminho_base_obj, carregar_obj


def ler_imagem_qt(caminho):
    """Converte uma imagem escolhida pelo usuário em RGBA8 contígua."""
    from PyQt5 import QtGui
    import numpy as np

    imagem = QtGui.QImage(str(caminho))
    if imagem.isNull():
        raise ValueError(f"Não foi possível abrir a imagem: {caminho}")
    imagem = imagem.convertToFormat(QtGui.QImage.Format_RGBA8888)
    altura, largura = imagem.height(), imagem.width()
    rgba = np.frombuffer(imagem.bits().asstring(largura * altura * 4), dtype=np.uint8)
    return rgba.copy().reshape((altura, largura, 4))


def iniciar():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend", choices=["auto", "vulkan", "metal", "d3d12", "opengl"],
        default="auto", help="Backend gráfico (padrão: escolha automática)",
    )
    parser.add_argument("--smoke", action="store_true", help="Testar se GPU desenha quadros no Xvfb")
    args = parser.parse_args()
    if args.backend != "auto":
        os.environ["WGPU_BACKEND_TYPE"] = args.backend.capitalize() if args.backend != "d3d12" else "D3D12"

    from PyQt5 import QtCore, QtWidgets, QtGui
    from rendercanvas.qt import QRenderWidget
    from .gpu import MotorWgpu
    from .morphs import Deformador, ler_target, pasta_targets

    malha = carregar_obj(caminho_base_obj())
    print(
        f"Malha MakeHuman: {len(malha.vertices)} vértices UV, "
        f"{len(malha.indices) // 3} triângulos", flush=True
    )
    aplicacao = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    janela = QtWidgets.QMainWindow()
    janela.setWindowTitle("MakeHumano • Prévia wgpu (experimental)")
    janela.resize(1040, 700)
    raiz = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(raiz)
    janela.setCentralWidget(raiz)
    tela = QRenderWidget(raiz, update_mode="ondemand")
    tela.setMinimumSize(360, 400)
    layout.addWidget(tela, 1)
    # A coluna de opções cresce com os controles de morph: usar rolagem
    # evita esconder botões em monitores menores.
    painel = QtWidgets.QWidget()
    coluna = QtWidgets.QVBoxLayout(painel)
    rolagem = QtWidgets.QScrollArea()
    rolagem.setWidgetResizable(True)
    rolagem.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    rolagem.setFixedWidth(260)
    rolagem.setWidget(painel)
    layout.addWidget(rolagem)

    coluna.addWidget(QtWidgets.QLabel("<b>Visualizador experimental</b>"))
    coluna.addWidget(QtWidgets.QLabel("O MakeHuman original continua intacto."))

    def controle(titulo, minimo, maximo, valor, callback):
        coluna.addWidget(QtWidgets.QLabel(titulo))
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(minimo, maximo)
        slider.setValue(valor)
        slider.valueChanged.connect(callback)
        coluna.addWidget(slider)
        return slider

    # A janela deve existir antes de negociar a superfície de apresentação.
    janela.show()
    motor = MotorWgpu(tela, malha)
    print(f"Adaptador gráfico: {motor.adapter.info}", flush=True)
    deformador = Deformador(malha)

    controle("Rotação horizontal", -180, 180, 0,
             lambda valor: motor.ajustar_camera(angulo=valor * 3.14159265 / 180))
    controle("Elevação", -75, 75, 3,
             lambda valor: motor.ajustar_camera(elevacao=valor * 3.14159265 / 180))
    controle("Distância", 15, 50, 28,
             lambda valor: motor.ajustar_camera(distancia=valor))
    controle("Rugosidade da pele", 5, 100, 65,
             lambda valor: motor.ajustar_pele(rugosidade=valor / 100))

    coluna.addWidget(QtWidgets.QLabel("Tonalidade da pele"))
    cores = {
        "Clara": (1.0, 0.85, 0.76),
        "Média": (0.76, 0.48, 0.33),
        "Escura": (0.36, 0.20, 0.15),
    }
    for nome, rgb in cores.items():
        botao = QtWidgets.QPushButton(nome)
        botao.clicked.connect(lambda _checked=False, cor=rgb: motor.ajustar_pele(cor=cor))
        coluna.addWidget(botao)

    coluna.addWidget(QtWidgets.QLabel("<b>Deformações MakeHuman</b>"))
    coluna.addWidget(QtWidgets.QLabel("Alvos .target originais (demonstração)"))
    exemplos = (
        ("Nariz: largura +", "nose/nose-scale-horiz-incr.target"),
        ("Torso: formato V +", "torso/torso-vshape-incr.target"),
        ("Abdômen: tônus +", "stomach/stomach-tone-incr.target"),
        ("Mão esquerda: tamanho +", "armslegs/l-hand-scale-incr.target"),
    )
    controles_morph = []
    for titulo, caminho_relativo in exemplos:
        alvo = ler_target(
            pasta_targets() / caminho_relativo,
            len(malha.posicoes_base),
        )

        def mudar_morph(valor, nome=caminho_relativo, target=alvo):
            alterados = deformador.definir_peso(nome, target, valor / 100.0)
            motor.atualizar_vertices(alterados)

        controles_morph.append(controle(titulo, 0, 100, 0, mudar_morph))

    def restaurar_morphs():
        # Evitar uma atualização da GPU para cada slider durante o reset.
        for slider in controles_morph:
            slider.blockSignals(True)
            slider.setValue(0)
            slider.blockSignals(False)
        motor.atualizar_vertices(deformador.restaurar())

    botao_restaurar = QtWidgets.QPushButton("Restaurar deformações")
    botao_restaurar.clicked.connect(restaurar_morphs)
    coluna.addWidget(botao_restaurar)

    estado = QtWidgets.QLabel("Textura: branca (tonalidade por shader)")
    estado.setWordWrap(True)
    coluna.addWidget(estado)

    def escolher_textura():
        arquivo, _ = QtWidgets.QFileDialog.getOpenFileName(
            janela, "Carregar textura de pele UV", str(Path.home()),
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if arquivo:
            try:
                pixels = ler_imagem_qt(arquivo)
                motor.atualizar_textura(pixels)
            except (OSError, ValueError, RuntimeError) as erro:
                QtWidgets.QMessageBox.warning(janela, "Textura inválida", str(erro))
            else:
                estado.setText(f"Textura: {Path(arquivo).name}")

    botao_textura = QtWidgets.QPushButton("Carregar textura da pele…")
    botao_textura.clicked.connect(escolher_textura)
    coluna.addWidget(botao_textura)
    coluna.addStretch(1)
    coluna.addWidget(QtWidgets.QLabel(
        "WGSL + GGX simplificado. Não há ainda\n"
        "subsurface scattering ou pintura 3D."
    ))

    if args.smoke:
        def atualizar_smoke():
            # Testar mudanças de material e upload de textura após o 1º frame.
            import numpy as np
            textura = np.full((8, 8, 4), 255, dtype=np.uint8)
            textura[..., :3] = (170, 113, 97)
            motor.atualizar_textura(textura)
            motor.ajustar_pele(cor=(0.92, 0.75, 0.66), rugosidade=0.42)
            motor.ajustar_camera(angulo=0.2)
            print("Textura RGBA e material atualizados em execução", flush=True)

        def terminar_smoke():
            print(f"Quadros desenhados: {motor.frames}", flush=True)
            # Um quadro inicial e outros após atualizar textura e geometria.
            aplicacao.exit(0 if motor.frames >= 3 else 2)

        def deformar_smoke():
            controles_morph[0].setValue(65)
            print("Morph target original aplicado ao buffer Vulkan", flush=True)

        QtCore.QTimer.singleShot(800, atualizar_smoke)
        QtCore.QTimer.singleShot(2000, deformar_smoke)
        QtCore.QTimer.singleShot(8500, terminar_smoke)

    return aplicacao.exec_()


if __name__ == "__main__":
    raise SystemExit(iniciar())
