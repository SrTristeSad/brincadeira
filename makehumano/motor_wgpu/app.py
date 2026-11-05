"""Visualizador experimental MakeHumano wgpu, separado do editor OpenGL.

Na pasta makehumano:
    python -m motor_wgpu.app
    python -m motor_wgpu.app --backend vulkan

É um protótipo: não substitui a viewport principal nem exporta rigs/poses.
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
    from .modificadores import carregar_catalogo, NOMES_GRUPOS
    from .projetos import (
        montar_documento, carregar_documento,
        salvar_projeto_com_texturas, carregar_texturas_projeto,
    )
    from .materiais import textura_neutra
    from .exportar import exportar_obj_com_material
    from .materiais_obj import caminhos_materiais, caminhos_mapas
    from .mhm import carregar_mhm
    from .acessorios import (
        carregar_proxy_direto, caminho_olhos_lowpoly,
        carregar_proxy_ponderado, caminho_olhos_highpoly,
    )
    from .roupas import carregar_peca_externa
    from .macro import (
        ControladorMacros, VALORES_PADRAO, ROTULOS, ETNIAS,
        ETNIAS_PADRAO, ROTULOS_ETNIAS,
    )

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
    macros = ControladorMacros(deformador)
    # O personagem original é inicializado com macrovariáveis padrão;
    # precisamos aplicá-las antes dos modificadores locais.
    motor.atualizar_vertices(macros.atualizar())
    print(f"Macrovariáveis: {len(macros.arquivos)} targets no catálogo", flush=True)

    # O pacote original desta cópia possui olhos low-poly completos, mas
    # não inclui roupas. Este é o primeiro acessório com malha independente.
    acessorio_olhos = carregar_proxy_direto(caminho_olhos_lowpoly(), malha)
    acessorio_olhos_high = carregar_proxy_ponderado(
        caminho_olhos_highpoly(), malha
    )
    modelos_olhos = {
        "olhos": acessorio_olhos,
        "olhos_high": acessorio_olhos_high,
    }
    textura_olhos = ler_imagem_qt(acessorio_olhos.textura)
    for nome, acessorio in modelos_olhos.items():
        motor.adicionar_acessorio(
            nome, acessorio.malha,
            acessorio.atualizar(deformador.posicoes_atuais),
            textura_olhos,
            deletar_vertices=getattr(acessorio, "deletar_vertices", None),
        )
    motor.mostrar_acessorio("olhos_high", False)
    coluna.addWidget(QtWidgets.QLabel("<b>Acessórios experimentais</b>"))
    checkbox_olhos = QtWidgets.QCheckBox("Mostrar olhos originais")
    checkbox_olhos.setChecked(True)
    coluna.addWidget(checkbox_olhos)
    combo_olhos = QtWidgets.QComboBox()
    combo_olhos.addItem("Olhos baixa resolução (referência direta)", "olhos")
    combo_olhos.addItem("Olhos alta resolução (proxy ponderado)", "olhos_high")
    coluna.addWidget(combo_olhos)

    pecas_externas = {}
    proximo_acessorio = [0]

    def atualizar_corpo(vertices):
        motor.atualizar_vertices(vertices)
        if checkbox_olhos.isChecked():
            nome = combo_olhos.currentData()
            motor.atualizar_acessorio(
                nome, modelos_olhos[nome].atualizar(
                    deformador.posicoes_atuais
                )
            )
        for nome, (peca, _, _) in pecas_externas.items():
            if motor.acessorios[nome]["visivel"]:
                motor.atualizar_acessorio(
                    nome, peca.atualizar(deformador.posicoes_atuais)
                )

    def alternar_olhos(visivel):
        selecionado = combo_olhos.currentData()
        for nome in modelos_olhos:
            motor.mostrar_acessorio(nome, visivel and nome == selecionado)
        if visivel:
            motor.atualizar_acessorio(
                selecionado, modelos_olhos[selecionado].atualizar(
                    deformador.posicoes_atuais
                )
            )

    checkbox_olhos.toggled.connect(alternar_olhos)
    combo_olhos.currentIndexChanged.connect(
        lambda _: alternar_olhos(checkbox_olhos.isChecked())
    )
    print(
        "Acessórios olhos: "
        f"{len(acessorio_olhos.malha.posicoes_base)} vértices low-poly, "
        f"{len(acessorio_olhos_high.malha.posicoes_base)} high-poly; "
        "ambos com .mhclo e textura própria",
        flush=True,
    )

    coluna.addWidget(QtWidgets.QLabel("<b>Peças externas (.mhclo)</b>"))
    aviso_roupas = QtWidgets.QLabel(
        "Carrega um .mhclo e seu OBJ local. Peças compatíveis acompanham os "
        "morphs e aplicam suas máscaras. Sem rig, física ou materiais .mhmat."
    )
    aviso_roupas.setWordWrap(True)
    coluna.addWidget(aviso_roupas)
    lista_roupas = QtWidgets.QVBoxLayout()
    coluna.addLayout(lista_roupas)

    def adicionar_peca_externa(caminho, textura=None):
        """Registra a peça somente depois de ler e validar o proxy/OBJ."""
        peca = carregar_peca_externa(caminho, malha)
        from .materiais import textura_neutra
        pixels = textura_neutra() if textura is None else textura
        novos_vertices = peca.atualizar(deformador.posicoes_atuais)
        proximo_acessorio[0] += 1
        chave = f"externo_{proximo_acessorio[0]}"
        motor.adicionar_acessorio(
            chave, peca.modelo.malha, novos_vertices, pixels,
            deletar_vertices=peca.deletar_vertices,
        )
        linha = QtWidgets.QWidget()
        botoes = QtWidgets.QHBoxLayout(linha)
        botoes.setContentsMargins(0, 0, 0, 0)
        visivel = QtWidgets.QCheckBox(Path(caminho).stem)
        visivel.setChecked(True)
        visivel.setToolTip(str(Path(caminho)))
        remover = QtWidgets.QPushButton("Remover")
        remover.setToolTip(f"Remover {Path(caminho).name}")
        botoes.addWidget(visivel, 1)
        botoes.addWidget(remover)
        lista_roupas.addWidget(linha)
        pecas_externas[chave] = (peca, visivel, linha)

        def mudar_visibilidade(ativo):
            motor.mostrar_acessorio(chave, ativo)
            if ativo:
                motor.atualizar_acessorio(
                    chave, peca.atualizar(deformador.posicoes_atuais)
                )

        def remover_peca():
            motor.remover_acessorio(chave)
            del pecas_externas[chave]
            lista_roupas.removeWidget(linha)
            linha.setParent(None)
            linha.deleteLater()

        visivel.toggled.connect(mudar_visibilidade)
        remover.clicked.connect(remover_peca)
        print(
            f"Acessório externo {chave}: {Path(caminho).name}, "
            f"proxy {peca.tipo}, "
            f"{len(peca.modelo.malha.indices) // 3} triângulos",
            flush=True,
        )
        return chave

    def escolher_peca_externa():
        caminho, _ = QtWidgets.QFileDialog.getOpenFileName(
            janela, "Selecionar acessório/roupa MakeHuman (.mhclo)",
            str(Path.home()), "Proxies MakeHuman (*.mhclo)",
        )
        if not caminho:
            return
        try:
            # A imagem é opcional: o .mhmat legado ainda não é interpretado.
            imagem, _ = QtWidgets.QFileDialog.getOpenFileName(
                janela, "Textura opcional (cancelar para usar branco)",
                str(Path(caminho).parent),
                "Imagens (*.png *.jpg *.jpeg *.webp *.bmp)",
            )
            pixels = ler_imagem_qt(imagem) if imagem else None
            adicionar_peca_externa(caminho, pixels)
        except (OSError, UnicodeError, ValueError, RuntimeError) as erro:
            QtWidgets.QMessageBox.warning(
                janela, "Acessório não importado", str(erro)
            )

    botao_roupa = QtWidgets.QPushButton("Adicionar peça .mhclo…")
    botao_roupa.clicked.connect(escolher_peca_externa)
    coluna.addWidget(botao_roupa)

    controle("Rotação horizontal", -180, 180, 0,
             lambda valor: motor.ajustar_camera(angulo=valor * 3.14159265 / 180))
    controle("Elevação", -75, 75, 3,
             lambda valor: motor.ajustar_camera(elevacao=valor * 3.14159265 / 180))
    controle("Distância", 15, 50, 28,
             lambda valor: motor.ajustar_camera(distancia=valor))
    slider_rugosidade = controle(
        "Rugosidade da pele", 5, 100, 65,
        lambda valor: motor.ajustar_pele(rugosidade=valor / 100),
    )
    slider_dispersao = controle(
        "Dispersão da pele (aproximada)", 0, 100,
        round(motor.pele.dispersao * 100),
        lambda valor: motor.ajustar_pele(dispersao=valor / 100),
    )
    explicacao_dispersao = QtWidgets.QLabel(
        "Iluminação difusa suavizada nas bordas. Não simula "
        "translucência física nem espessura da pele."
    )
    explicacao_dispersao.setWordWrap(True)
    coluna.addWidget(explicacao_dispersao)

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

    coluna.addWidget(QtWidgets.QLabel("<b>Parâmetros gerais</b>"))
    coluna.addWidget(QtWidgets.QLabel(
        "Macros MakeHuman: idade, peso, musculatura, altura e proporções."
    ))
    controles_macros = {}
    for chave, padrao in VALORES_PADRAO.items():
        coluna.addWidget(QtWidgets.QLabel(ROTULOS[chave]))
        barra = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        barra.setRange(0, 100)
        barra.setValue(round(padrao * 100))
        barra.valueChanged.connect(
            lambda valor, nome=chave: atualizar_corpo(
                macros.definir(nome, valor / 100.0)
            )
        )
        coluna.addWidget(barra)
        controles_macros[chave] = barra

    coluna.addWidget(QtWidgets.QLabel("<b>Misturas de alvos herdadas</b>"))
    nota_etnias = QtWidgets.QLabel(
        "Categorias históricas do MakeHuman, usadas para combinar morphs. "
        "Não representam uma medição de identidade étnica."
    )
    nota_etnias.setWordWrap(True)
    coluna.addWidget(nota_etnias)
    controles_etnias = {}
    rotulos_etnias = {}
    for chave in ETNIAS:
        texto = QtWidgets.QLabel()
        coluna.addWidget(texto)
        barra = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        barra.setRange(0, 1000)
        barra.setValue(round(ETNIAS_PADRAO[chave] * 1000))
        coluna.addWidget(barra)
        controles_etnias[chave] = barra
        rotulos_etnias[chave] = texto

    def sincronizar_etnias():
        # Apenas um callback faz o upload para GPU. Os sliders parceiros são
        # atualizados sem emitir eventos adicionais.
        for nome, slider in controles_etnias.items():
            fracao = macros.perfil.etnias[nome]
            slider.blockSignals(True)
            slider.setValue(round(fracao * 1000))
            slider.blockSignals(False)
            rotulos_etnias[nome].setText(
                f"{ROTULOS_ETNIAS[nome]}: {fracao * 100:.1f}%"
            )

    def alterar_etnia(chave, valor):
        vertices_atualizados = macros.definir_etnia(chave, valor / 1000.0)
        sincronizar_etnias()
        atualizar_corpo(vertices_atualizados)

    for nome, slider in controles_etnias.items():
        slider.valueChanged.connect(
            lambda valor, chave=nome: alterar_etnia(chave, valor)
        )
    sincronizar_etnias()

    coluna.addWidget(QtWidgets.QLabel("<b>Modificadores MakeHuman</b>"))
    coluna.addWidget(QtWidgets.QLabel(
        "Alvos diretos do catálogo original. Os parâmetros gerais acima "
        "são combinados na mesma malha."
    ))
    catalogo = carregar_catalogo()
    grupos = sorted({item.grupo for item in catalogo},
                    key=lambda grupo: NOMES_GRUPOS.get(grupo, grupo))
    caixa_grupos = QtWidgets.QComboBox()
    for grupo in grupos:
        caixa_grupos.addItem(
            f"{NOMES_GRUPOS.get(grupo, grupo)} ({sum(m.grupo == grupo for m in catalogo)})",
            grupo,
        )
    coluna.addWidget(caixa_grupos)

    widget_morph = QtWidgets.QWidget()
    layout_morph = QtWidgets.QVBoxLayout(widget_morph)
    layout_morph.setContentsMargins(0, 0, 0, 0)
    coluna.addWidget(widget_morph)

    valores_morph = {}
    alvos_cache = {}
    controles_morph = {}

    def atualizar_modificador(valor, modificador):
        # Busca arquivos somente quando o usuário usa um slider.
        # O mesmo target é reaproveitado entre alterações de peso.
        alteracoes = {}
        for caminho, peso in modificador.pesos(valor).items():
            chave = str(caminho)
            if chave not in alvos_cache:
                alvos_cache[chave] = ler_target(
                    caminho, len(malha.posicoes_base)
                )
            alteracoes[chave] = (alvos_cache[chave], peso)
        novos_vertices = deformador.definir_pesos(alteracoes)
        atualizar_corpo(novos_vertices)
        valores_morph[modificador.identificador] = valor

    def exibir_grupo(_index):
        while layout_morph.count():
            item = layout_morph.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        controles_morph.clear()
        grupo_atual = caixa_grupos.currentData()
        for modificador in catalogo:
            if modificador.grupo != grupo_atual:
                continue
            nome = QtWidgets.QLabel(modificador.rotulo)
            nome.setWordWrap(True)
            layout_morph.addWidget(nome)
            controle_morph = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            controle_morph.setRange(modificador.minimo, 100)
            controle_morph.setValue(
                valores_morph.get(modificador.identificador, 0)
            )
            controle_morph.valueChanged.connect(
                lambda valor, mod=modificador: atualizar_modificador(valor, mod)
            )
            layout_morph.addWidget(controle_morph)
            controles_morph[modificador.identificador] = controle_morph

    caixa_grupos.currentIndexChanged.connect(exibir_grupo)
    indice_nariz = caixa_grupos.findData("nose")
    caixa_grupos.setCurrentIndex(indice_nariz if indice_nariz >= 0 else 0)
    exibir_grupo(caixa_grupos.currentIndex())

    def restaurar_morphs():
        # Restaurar todos os grupos, inclusive sliders fora da tela.
        valores_morph.clear()
        for slider in controles_morph.values():
            slider.blockSignals(True)
            slider.setValue(0)
            slider.blockSignals(False)
        for chave, slider in controles_macros.items():
            slider.blockSignals(True)
            slider.setValue(round(VALORES_PADRAO[chave] * 100))
            slider.blockSignals(False)
        deformador.restaurar()
        # O MakeHuman padrão possui os macros iniciais ativos.
        atualizar_corpo(macros.restaurar())
        sincronizar_etnias()

    botao_restaurar = QtWidgets.QPushButton("Restaurar todas as deformações")
    botao_restaurar.clicked.connect(restaurar_morphs)
    coluna.addWidget(botao_restaurar)

    coluna.addWidget(QtWidgets.QLabel("<b>Projeto experimental</b>"))

    def aplicar_documento(documento, imagens=None):
        """Restaura sliders, material e imagens já validadas do projeto.

        O chamador carrega os PNGs antes de alterar qualquer estado da GPU.
        """
        if imagens is None:
            imagens = {"cor": None, "normal": None, "rugosidade": None}
        alteracoes = {}
        for modificador in catalogo:
            valor = documento["modificadores"].get(modificador.identificador, 0)
            if not valor:
                continue
            for caminho, peso in modificador.pesos(valor).items():
                nome = str(caminho)
                if nome not in alvos_cache:
                    alvos_cache[nome] = ler_target(caminho, len(malha.posicoes_base))
                alteracoes[nome] = (alvos_cache[nome], peso)

        deformador.restaurar()
        macros.perfil.valores = documento["macros"].copy()
        macros.perfil.etnias = documento["etnias"].copy()
        macros.atualizar()
        if alteracoes:
            deformador.definir_pesos(alteracoes)

        valores_morph.clear()
        valores_morph.update(documento["modificadores"])
        exibir_grupo(caixa_grupos.currentIndex())
        for nome, slider in controles_macros.items():
            slider.blockSignals(True)
            slider.setValue(round(documento["macros"][nome] * 100))
            slider.blockSignals(False)
        sincronizar_etnias()
        motor.ajustar_pele(
            cor=documento["pele"]["cor"],
            rugosidade=documento["pele"]["rugosidade"],
            dispersao=documento["pele"]["dispersao"],
        )
        for slider, valor in (
            (slider_rugosidade, documento["pele"]["rugosidade"]),
            (slider_dispersao, documento["pele"]["dispersao"]),
        ):
            slider.blockSignals(True)
            slider.setValue(round(valor * 100))
            slider.blockSignals(False)
        # Os mapas ausentes são explicitamente neutralizados ao abrir
        # um projeto antigo; não herdamos as texturas do projeto anterior.
        motor.atualizar_textura(
            imagens["cor"] if imagens["cor"] is not None else textura_neutra()
        )
        motor.atualizar_mapa_normal(imagens["normal"])
        motor.atualizar_mapa_rugosidade(imagens["rugosidade"])
        estado.setText("Textura: restaurada do projeto" if imagens["cor"] is not None
                       else "Textura: branca (tonalidade por shader)")
        estado_normal.setText("Normais: restauradas do projeto"
                             if imagens["normal"] is not None
                             else "Normais: não carregado")
        estado_rugosidade.setText("Rugosidade: restaurada do projeto"
                                 if imagens["rugosidade"] is not None
                                 else "Rugosidade: não carregado")
        atualizar_corpo(deformador.vertices)

    def salvar_projeto():
        destino, _ = QtWidgets.QFileDialog.getSaveFileName(
            janela, "Salvar projeto MakeHumano",
            str(Path.home() / "personagem.makehumano.json"),
            "Projeto MakeHumano (*.makehumano.json)",
        )
        if not destino:
            return
        if not destino.endswith(".makehumano.json"):
            destino += ".makehumano.json"
        try:
            documento = montar_documento(macros.perfil, valores_morph, motor.pele, catalogo)
            salvar_projeto_com_texturas(
                destino, documento, catalogo, {
                    "cor": motor.textura_cpu,
                    "normal": (motor.textura_normal_cpu if motor.normal_ativo
                               else None),
                    "rugosidade": (motor.textura_rugosidade_cpu
                                   if motor.rugosidade_ativa else None),
                },
            )
        except (ValueError, OSError) as erro:
            QtWidgets.QMessageBox.warning(janela, "Falha ao salvar", str(erro))
        else:
            print(f"Projeto salvo: {destino}", flush=True)

    def carregar_projeto():
        origem, _ = QtWidgets.QFileDialog.getOpenFileName(
            janela, "Abrir projeto MakeHumano", str(Path.home()),
            "Projeto MakeHumano (*.makehumano.json)",
        )
        if not origem:
            return
        try:
            documento = carregar_documento(origem, catalogo)
            imagens = carregar_texturas_projeto(origem, documento, ler_imagem_qt)
            aplicar_documento(documento, imagens)
        except (ValueError, OSError, RuntimeError) as erro:
            QtWidgets.QMessageBox.warning(janela, "Falha ao abrir", str(erro))
        else:
            print(f"Projeto aberto: {origem}", flush=True)

    botao_salvar = QtWidgets.QPushButton("Salvar personagem…")
    botao_salvar.clicked.connect(salvar_projeto)
    coluna.addWidget(botao_salvar)

    botao_abrir = QtWidgets.QPushButton("Abrir personagem…")
    botao_abrir.clicked.connect(carregar_projeto)
    coluna.addWidget(botao_abrir)

    def importar_mhm():
        caminho, _ = QtWidgets.QFileDialog.getOpenFileName(
            janela, "Importar personagem do MakeHuman original",
            str(Path.home()), "Personagens MakeHuman (*.mhm)"
        )
        if not caminho:
            return
        try:
            importacao = carregar_mhm(caminho, catalogo)
        except (OSError, ValueError) as erro:
            QtWidgets.QMessageBox.warning(
                janela, "Não foi possível importar o MHM", str(erro)
            )
            return

        # Um arquivo MHM pode incluir roupa, pose, materiais e plugins.
        # Solicitar consentimento explícito, sem prometer importação integral.
        resumo = (
            f"{importacao.modificadores_aplicados} de "
            f"{importacao.modificadores_lidos} modificadores reconhecidos.\n"
            "A prévia importa somente a forma corporal; não copia "
            "roupas, poses, esqueleto, materiais nem configurações de câmera."
        )
        if importacao.avisos:
            resumo += (
                "\n\nAvisos:\n"
                + "\n".join(importacao.avisos[:8])
                + ("\n…" if len(importacao.avisos) > 8 else "")
            )
        resposta = QtWidgets.QMessageBox.question(
            janela, "Importação parcial de MHM",
            resumo + "\n\nImportar apenas a forma corporal?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if resposta != QtWidgets.QMessageBox.Yes:
            return
        aplicar_documento(importacao.documento)
        print(
            f"MHM importado parcialmente: {caminho} "
            f"({importacao.modificadores_aplicados} modificadores)",
            flush=True,
        )

    botao_mhm = QtWidgets.QPushButton("Importar MHM original…")
    botao_mhm.clicked.connect(importar_mhm)
    coluna.addWidget(botao_mhm)


    def exportar_personagem():
        destino, _ = QtWidgets.QFileDialog.getSaveFileName(
            janela, "Exportar malha corporal deformada",
            str(Path.home() / "personagem.obj"),
            "Modelo Wavefront OBJ (*.obj)",
        )
        if not destino:
            return
        if Path(destino).suffix.lower() != ".obj":
            destino += ".obj"
        arquivo_mtl, arquivo_png = caminhos_materiais(destino)
        existentes = [
            nome for nome in (
                Path(destino), arquivo_mtl, arquivo_png,
                *caminhos_mapas(destino),
            ) if nome.exists()
        ]
        if existentes:
            resposta = QtWidgets.QMessageBox.question(
                janela, "Substituir arquivos?",
                "A exportação substituirá estes arquivos:\n"
                + "\n".join(str(nome) for nome in existentes),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if resposta != QtWidgets.QMessageBox.Yes:
                return
        try:
            objeto, material, textura = exportar_obj_com_material(
                destino, malha, deformador.vertices,
                motor.pele, motor.textura_cpu,
                mapa_normal_rgba=(
                    motor.textura_normal_cpu if motor.normal_ativo else None
                ),
                mapa_rugosidade_rgba=(
                    motor.textura_rugosidade_cpu if motor.rugosidade_ativa
                    else None
                ),
            )
        except (OSError, ValueError) as erro:
            QtWidgets.QMessageBox.warning(janela, "Falha ao exportar", str(erro))
        else:
            print(
                f"OBJ, MTL e PNG exportados: {objeto}, {material}, {textura}",
                flush=True,
            )

    botao_exportar = QtWidgets.QPushButton("Exportar OBJ com mapas de pele…")
    botao_exportar.clicked.connect(exportar_personagem)
    coluna.addWidget(botao_exportar)
    aviso_exportar = QtWidgets.QLabel(
        "Cria OBJ, MTL, textura difusa e PNGs auxiliares de normais e "
        "rugosidade. Sem roupa, esqueleto ou pose."
    )
    aviso_exportar.setWordWrap(True)
    coluna.addWidget(aviso_exportar)

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

    coluna.addWidget(QtWidgets.QLabel("<b>Mapas de detalhe da pele</b>"))
    explicacao_mapas = QtWidgets.QLabel(
        "Normal map: espaço tangente, convenção OpenGL (+Y). "
        "Rugosidade: canal vermelho multiplicado pelo slider."
    )
    explicacao_mapas.setWordWrap(True)
    coluna.addWidget(explicacao_mapas)

    def criar_controles_mapa(titulo, carregador):
        situacao = QtWidgets.QLabel(f"{titulo}: não carregado")
        situacao.setWordWrap(True)
        coluna.addWidget(situacao)
        botoes = QtWidgets.QHBoxLayout()
        coluna.addLayout(botoes)

        def abrir_mapa():
            origem, _ = QtWidgets.QFileDialog.getOpenFileName(
                janela, f"Carregar {titulo.lower()}", str(Path.home()),
                "Imagens (*.png *.jpg *.jpeg *.webp *.bmp)",
            )
            if not origem:
                return
            try:
                carregador(ler_imagem_qt(origem))
            except (OSError, ValueError, RuntimeError) as erro:
                QtWidgets.QMessageBox.warning(janela, "Mapa inválido", str(erro))
            else:
                situacao.setText(f"{titulo}: {Path(origem).name}")

        def remover_mapa():
            carregador(None)
            situacao.setText(f"{titulo}: não carregado")

        botao_abrir = QtWidgets.QPushButton("Carregar…")
        botao_remover = QtWidgets.QPushButton("Remover")
        botao_abrir.clicked.connect(abrir_mapa)
        botao_remover.clicked.connect(remover_mapa)
        botoes.addWidget(botao_abrir)
        botoes.addWidget(botao_remover)
        return situacao

    estado_normal = criar_controles_mapa(
        "Normais", motor.atualizar_mapa_normal
    )
    estado_rugosidade = criar_controles_mapa(
        "Rugosidade", motor.atualizar_mapa_rugosidade
    )
    coluna.addStretch(1)
    coluna.addWidget(QtWidgets.QLabel(
        "GGX + normal/roughness maps. Não há ainda\n"
        "subsurface scattering ou pintura 3D."
    ))

    if args.smoke:
        eventos_smoke = set()

        def atualizar_smoke():
            # Testar mudanças de material e upload de textura após o 1º frame.
            import numpy as np
            textura = np.full((8, 8, 4), 255, dtype=np.uint8)
            textura[..., :3] = (170, 113, 97)
            motor.atualizar_textura(textura)
            motor.ajustar_pele(cor=(0.92, 0.75, 0.66), rugosidade=0.42)
            motor.ajustar_camera(angulo=0.2)
            eventos_smoke.add("textura")
            print("Textura RGBA e material atualizados em execução", flush=True)

        def terminar_smoke():
            print(f"Quadros desenhados: {motor.frames}", flush=True)
            # rendercanvas em modo ondemand pode coalescer mudanças feitas
            # rapidamente. Verificar eventos completados e múltiplos frames,
            # sem exigir um quadro para cada callback.
            esperados = {"textura", "modificador_positivo", "modificador_negativo",
                         "macros", "restauracao", "etnias", "restauracao_total",
                         "salvar_abrir", "exportar_obj", "material_textura",
                         "mapas_detalhe", "mapas_restaurados",
                         "dispersao", "importar_mhm", "olhos",
                         "olhos_highpoly", "mascara_corpo",
                         "mascaras_acessorios", "roupa_externa"}
            ok = eventos_smoke == esperados and motor.frames >= 6
            print(f"Smoke: eventos {sorted(eventos_smoke)}, aprovado={ok}", flush=True)
            aplicacao.exit(0 if ok else 2)

        def deformar_smoke():
            chave = "nose/nose-scale-horiz-decr|incr"
            controles_morph[chave].setValue(65)
            eventos_smoke.add("modificador_positivo")
            print("Modificador bidirecional original aplicado ao Vulkan", flush=True)

        def deformar_negativo_smoke():
            chave = "nose/nose-scale-horiz-decr|incr"
            controles_morph[chave].setValue(-35)
            eventos_smoke.add("modificador_negativo")
            print("Direção negativa do modificador aplicada ao Vulkan", flush=True)
        
        def macro_smoke():
            controles_macros["muscle"].setValue(75)
            controles_macros["weight"].setValue(65)
            eventos_smoke.add("macros")
            print("Musculatura e peso combinados no Vulkan", flush=True)

        def restaurar_smoke():
            controles_macros["muscle"].setValue(50)
            controles_macros["weight"].setValue(50)
            eventos_smoke.add("restauracao")
            print("Macrovariáveis restauradas aos valores padrão", flush=True)

        def etnia_smoke():
            controles_etnias["african"].setValue(750)
            proporcoes = macros.perfil.etnias
            assert abs(sum(proporcoes.values()) - 1) < 1e-8
            assert abs(proporcoes["african"] - 0.75) < 1e-8
            eventos_smoke.add("etnias")
            print(f"Alvos étnicos normalizados no Vulkan: {proporcoes}", flush=True)

        def restaurar_tudo_smoke():
            botao_restaurar.click()
            proporcoes = macros.perfil.etnias
            assert all(abs(proporcoes[chave] - 1 / 3) < 1e-8 for chave in ETNIAS)
            eventos_smoke.add("restauracao_total")
            print("Todos os modificadores e misturas restaurados", flush=True)

        def carregar_mapas_smoke():
            import numpy as np
            normal = np.tile(
                np.array([150, 115, 250, 255], dtype=np.uint8), (8, 8, 1)
            )
            rugosidade = np.full((8, 8, 4), 255, dtype=np.uint8)
            rugosidade[..., 0] = 130
            motor.atualizar_mapa_normal(normal)
            motor.atualizar_mapa_rugosidade(rugosidade)
            assert motor.normal_ativo and motor.rugosidade_ativa
            np.testing.assert_array_equal(motor.textura_normal_cpu, normal)
            np.testing.assert_array_equal(
                motor.textura_rugosidade_cpu, rugosidade
            )
            eventos_smoke.add("mapas_detalhe")
            print("Mapas de normais e rugosidade aplicados no Vulkan", flush=True)

        def limpar_mapas_smoke():
            motor.atualizar_mapa_normal(None)
            motor.atualizar_mapa_rugosidade(None)
            assert not motor.normal_ativo and not motor.rugosidade_ativa
            eventos_smoke.add("mapas_restaurados")
            print("Mapas neutros restaurados no Vulkan", flush=True)

        def arquivo_smoke():
            from tempfile import TemporaryDirectory
            with TemporaryDirectory(prefix="makehumano-projeto-") as pasta:
                destino = Path(pasta) / "teste.makehumano.json"
                controles_macros["muscle"].setValue(75)
                controles_etnias["asian"].setValue(600)
                controles_morph["nose/nose-scale-horiz-decr|incr"].setValue(40)
                slider_dispersao.setValue(72)
                assert abs(motor.pele.dispersao - 0.72) < 1e-6
                eventos_smoke.add("dispersao")
                print("Dispersão aproximada da pele atualizada no Vulkan", flush=True)
                estado_anterior = deformador.vertices.copy()
                documento = montar_documento(
                    macros.perfil, valores_morph, motor.pele, catalogo
                )
                import numpy as np
                texturas_antes = {
                    "cor": motor.textura_cpu.copy(),
                    "normal": motor.textura_normal_cpu.copy(),
                    "rugosidade": motor.textura_rugosidade_cpu.copy(),
                }
                salvar_projeto_com_texturas(
                    destino, documento, catalogo, texturas_antes
                )
                # Trocar os mapas em memória para verificar o round-trip.
                cor_alterada = np.full((8, 8, 4), 23, dtype=np.uint8)
                motor.atualizar_textura(cor_alterada)
                motor.atualizar_mapa_normal(None)
                motor.atualizar_mapa_rugosidade(None)
                controles_macros["muscle"].setValue(20)
                controles_morph["nose/nose-scale-horiz-decr|incr"].setValue(-40)
                slider_dispersao.setValue(0)
                restaurado = carregar_documento(destino, catalogo)
                imagens_restauradas = carregar_texturas_projeto(
                    destino, restaurado, ler_imagem_qt
                )
                aplicar_documento(restaurado, imagens_restauradas)
                for tipo, pixels_originais in texturas_antes.items():
                    np.testing.assert_array_equal(
                        imagens_restauradas[tipo], pixels_originais
                    )
                assert motor.normal_ativo and motor.rugosidade_ativa
                assert abs(motor.pele.dispersao - 0.72) < 1e-6
                assert slider_dispersao.value() == 72
                import numpy as np
                np.testing.assert_allclose(
                    deformador.vertices, estado_anterior, rtol=2e-5, atol=2e-5,
                )
                assert macros.perfil.valores["muscle"] == 0.75
                assert macros.perfil.etnias["asian"] == 0.6
                eventos_smoke.add("salvar_abrir")
                print("Projeto salvo e reaberto, malha restaurada no Vulkan", flush=True)

                objeto = Path(pasta) / "corpo-deformado.obj"
                _, mtl, png = exportar_obj_com_material(
                    objeto, malha, deformador.vertices,
                    motor.pele, motor.textura_cpu,
                    mapa_normal_rgba=motor.textura_normal_cpu,
                    mapa_rugosidade_rgba=motor.textura_rugosidade_cpu,
                )
                assert mtl.is_file() and png.is_file()
                texto_obj = objeto.read_text(encoding="utf-8")
                texto_mtl = mtl.read_text(encoding="utf-8")
                assert f"mtllib {mtl.name}" in texto_obj
                assert "usemtl PeleMakeHumano" in texto_obj
                assert f"map_Kd {png.name}" in texto_mtl
                assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
                normal_png, rugosidade_png = caminhos_mapas(objeto)
                assert normal_png.is_file() and rugosidade_png.is_file()
                assert normal_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
                assert rugosidade_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
                assert "map_Bump" not in texto_mtl
                eventos_smoke.add("material_textura")
                print("Material MTL e textura PNG exportados da GPU", flush=True)
                reimportado = carregar_obj(objeto)
                np.testing.assert_array_equal(reimportado.origens, malha.origens)
                np.testing.assert_array_equal(reimportado.indices, malha.indices)
                np.testing.assert_allclose(
                    reimportado.vertices[:, :3], deformador.vertices[:, :3],
                    rtol=0, atol=1e-5,
                )
                eventos_smoke.add("exportar_obj")
                print("Corpo deformado exportado como OBJ e reimportado", flush=True)

        def olhos_smoke():
            import numpy as np
            low = motor.acessorios["olhos"]
            high = motor.acessorios["olhos_high"]
            np.testing.assert_allclose(
                low["vertices"],
                acessorio_olhos.atualizar(deformador.posicoes_atuais),
                rtol=0, atol=1e-6,
            )
            assert low["visivel"] and not high["visivel"]
            checkbox_olhos.setChecked(False)
            assert not low["visivel"] and not high["visivel"]
            checkbox_olhos.setChecked(True)
            assert low["visivel"]
            eventos_smoke.add("olhos")

            combo_olhos.setCurrentIndex(1)
            assert high["visivel"] and not low["visivel"]
            assert high["vertices"].shape[0] > low["vertices"].shape[0]
            np.testing.assert_allclose(
                high["vertices"],
                acessorio_olhos_high.atualizar(deformador.posicoes_atuais),
                rtol=0, atol=1e-5,
            )
            # Alterações do rosto atualizam o proxy ponderado ativo.
            controles_macros["age"].setValue(70)
            np.testing.assert_allclose(
                high["vertices"],
                acessorio_olhos_high.atualizar(deformador.posicoes_atuais),
                rtol=0, atol=1e-5,
            )
            combo_olhos.setCurrentIndex(0)
            assert low["visivel"] and not high["visivel"]
            eventos_smoke.add("olhos_highpoly")
            print(
                "Olhos low/high poly alternados e high-poly deformado no Vulkan",
                flush=True,
            )

        def mascara_smoke():
            """Duas máscaras sintéticas vinculadas a acessórios existentes.

            Não apresentamos os olhos como roupa nem deixamos a máscara
            artificial ativa fora deste teste.
            """
            import numpy as np
            from .mascaras import indices_corpo_visiveis
            tamanho = len(malha.posicoes_base)
            corpo_inteiro = len(malha.indices)
            low = np.zeros(tamanho, dtype=bool)
            high = np.zeros(tamanho, dtype=bool)
            low[int(malha.origens[malha.indices[0]])] = True
            high[int(malha.origens[malha.indices[-1]])] = True

            assert motor.acessorios["olhos"]["visivel"]
            assert not motor.acessorios["olhos_high"]["visivel"]
            motor.definir_mascara_acessorio("olhos", low)
            motor.definir_mascara_acessorio("olhos_high", high)
            assert motor.indices_corpo_ativos == len(
                indices_corpo_visiveis(malha, low)
            )

            # Ao mostrar o segundo acessório, as duas máscaras se somam.
            motor.mostrar_acessorio("olhos_high", True)
            assert motor.indices_corpo_ativos == len(
                indices_corpo_visiveis(malha, low | high)
            )
            motor.mostrar_acessorio("olhos", False)
            assert motor.indices_corpo_ativos == len(
                indices_corpo_visiveis(malha, high)
            )
            motor.mostrar_acessorio("olhos_high", False)
            assert motor.indices_corpo_ativos == corpo_inteiro

            # A máscara manual é independente da dos acessórios.
            motor.mostrar_acessorio("olhos", True)
            motor.atualizar_mascara_corpo(high)
            assert motor.indices_corpo_ativos == len(
                indices_corpo_visiveis(malha, low | high)
            )
            motor.atualizar_mascara_corpo(None)
            assert motor.indices_corpo_ativos == len(
                indices_corpo_visiveis(malha, low)
            )

            # Restaurar o estado inicial do visualizador.
            motor.definir_mascara_acessorio("olhos", None)
            motor.definir_mascara_acessorio("olhos_high", None)
            assert motor.indices_corpo_ativos == corpo_inteiro

            # Adição e remoção de acessório temporário com máscara própria.
            motor.adicionar_acessorio(
                "acessorio_teste_mascara", acessorio_olhos.malha,
                acessorio_olhos.atualizar(deformador.posicoes_atuais),
                textura_olhos, deletar_vertices=high,
            )
            assert motor.indices_corpo_ativos == len(
                indices_corpo_visiveis(malha, high)
            )
            motor.remover_acessorio("acessorio_teste_mascara")
            assert "acessorio_teste_mascara" not in motor.acessorios
            assert motor.indices_corpo_ativos == corpo_inteiro
            assert motor.acessorios["olhos"]["visivel"]
            assert not motor.acessorios["olhos_high"]["visivel"]
            eventos_smoke.add("mascara_corpo")
            eventos_smoke.add("mascaras_acessorios")
            print(
                "Máscaras de dois acessórios combinadas, alternadas e "
                "restauradas no Vulkan",
                flush=True,
            )

        def roupa_externa_smoke():
            """Carrega uma peça sintética via a mesma UI das importações reais.

            Os arquivos são temporários. A máscara se aplica só enquanto
            o acessório está visível e não afeta os morphs permanentes.
            """
            import numpy as np
            from tempfile import TemporaryDirectory
            with TemporaryDirectory(prefix="makehumano-roupa-") as pasta:
                pasta = Path(pasta)
                v = malha.posicoes_base
                obj = pasta / "teste_roupa.obj"
                obj.write_text(
                    "".join(
                        "v " + " ".join(str(float(x)) for x in pos) + "\n"
                        for pos in v[:3]
                    )
                    + "vt 0 0\nvt 1 0\nvt 0 1\nf 1/1 2/2 3/3\n",
                    encoding="utf-8",
                )
                vertice = int(malha.origens[malha.indices[0]])
                proxy = pasta / "teste_roupa.mhclo"
                proxy.write_text(
                    "obj_file teste_roupa.obj\n"
                    "x_scale 5399 11998 1.6482\n"
                    "y_scale 791 881 2.7213\n"
                    "z_scale 962 5320 2.2795\n"
                    "verts 0\n"
                    "0 1 2 1 0 0 0 0 0\n"
                    "0 1 2 0 1 0 0 0 0\n"
                    "0 1 2 0 0 1 0 0 0\n"
                    "delete_verts\n"
                    + str(vertice) + "\n", encoding="utf-8",
                )
                cor = np.full((4, 4, 4), 255, dtype=np.uint8)
                cor[..., :3] = [60, 130, 195]
                total = len(malha.indices)
                chave = adicionar_peca_externa(proxy, cor)
                assert chave in pecas_externas
                assert motor.indices_corpo_ativos < total
                modelo, checkbox, linha = pecas_externas[chave]
                anterior = motor.acessorios[chave]["vertices"].copy()
                controles_macros["age"].setValue(60)
                np.testing.assert_allclose(
                    motor.acessorios[chave]["vertices"],
                    modelo.atualizar(deformador.posicoes_atuais),
                    atol=1e-5,
                )
                assert np.isfinite(anterior).all()
                checkbox.setChecked(False)
                assert motor.indices_corpo_ativos == total
                checkbox.setChecked(True)
                assert motor.indices_corpo_ativos < total
                controles_macros["age"].setValue(50)
                botoes = linha.findChildren(QtWidgets.QPushButton)
                assert len(botoes) == 1
                botoes[0].click()
                assert chave not in pecas_externas
                assert chave not in motor.acessorios
                assert motor.indices_corpo_ativos == total
                eventos_smoke.add("roupa_externa")
                print(
                    "Peça .mhclo externa criada, deformada, ocultada, "
                    "reativada e removida no Vulkan",
                    flush=True,
                )

        def importar_mhm_smoke():
            from tempfile import TemporaryDirectory
            import numpy as np
            with TemporaryDirectory(prefix="makehumano-mhm-") as pasta:
                caminho = Path(pasta) / "exemplo.mhm"
                caminho.write_text(
                    "# Written by MakeHuman v1.2.0\n"
                    "version v1.2.0\n"
                    "modifier macrodetails/Gender 0.700000\n"
                    "modifier macrodetails/Age 0.650000\n"
                    "modifier macrodetails-universal/Muscle 0.800000\n"
                    "modifier macrodetails/African 0.600000\n"
                    "modifier macrodetails/Asian 0.200000\n"
                    "modifier macrodetails/Caucasian 0.200000\n"
                    "modifier nose/nose-scale-horiz-decr|incr -0.370000\n"
                    "camera 0 0 0 0 0 1\n"
                    "subdivide False\n",
                    encoding="utf-8",
                )
                conversao = carregar_mhm(caminho, catalogo)
                assert conversao.modificadores_aplicados == 7
                aplicar_documento(conversao.documento)
                assert macros.perfil.valores["gender"] == 0.7
                assert macros.perfil.valores["muscle"] == 0.8
                assert valores_morph["nose/nose-scale-horiz-decr|incr"] == -37
                assert abs(macros.perfil.etnias["african"] - 0.6) < 1e-6
                assert not motor.normal_ativo and not motor.rugosidade_ativa
                assert motor.pele.dispersao == 0
                np.testing.assert_array_equal(
                    motor.textura_cpu, textura_neutra()
                )
                assert np.isfinite(deformador.vertices).all()
                eventos_smoke.add("importar_mhm")
                print(
                    "MHM original importado parcialmente e geometria "
                    "atualizada no Vulkan",
                    flush=True,
                )

        QtCore.QTimer.singleShot(800, atualizar_smoke)
        QtCore.QTimer.singleShot(2000, deformar_smoke)
        QtCore.QTimer.singleShot(4500, deformar_negativo_smoke)
        QtCore.QTimer.singleShot(6400, macro_smoke)
        QtCore.QTimer.singleShot(7700, olhos_smoke)
        QtCore.QTimer.singleShot(8300, mascara_smoke)
        QtCore.QTimer.singleShot(9000, restaurar_smoke)
        QtCore.QTimer.singleShot(10700, etnia_smoke)
        QtCore.QTimer.singleShot(13600, restaurar_tudo_smoke)
        QtCore.QTimer.singleShot(14500, carregar_mapas_smoke)
        QtCore.QTimer.singleShot(15600, arquivo_smoke)
        QtCore.QTimer.singleShot(18500, limpar_mapas_smoke)
        QtCore.QTimer.singleShot(19000, roupa_externa_smoke)
        QtCore.QTimer.singleShot(20600, importar_mhm_smoke)
        QtCore.QTimer.singleShot(27000, terminar_smoke)

    return aplicacao.exec_()


if __name__ == "__main__":
    raise SystemExit(iniciar())
