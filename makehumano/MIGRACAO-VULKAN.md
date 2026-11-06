# MakeHumano — migração agressiva do MakeHuman original

**Escopo:** migrar o código original em `codigo/makehuman` para Python moderno e Vulkan via `wgpu`, sem construir outro editor, alterar personagens, modificadores ou formatos.

## Política desta branch

- A aplicação ainda **não deve ser considerada pronta para uso**.
- É permitido quebrar temporariamente recursos OpenGL durante a migração.
- O branch `main` não é alterado até que os testes e a revisão sejam concluídos.
- Não declarar a migração completa enquanto qualquer caminho de renderização ainda exigir OpenGL.

## Serviços já ligados ao Vulkan

| Serviço original | Implementação no backend Vulkan | Situação |
| --- | --- | --- |
| Render da cena `G.world` | `vulkan_scene.CenaVulkan` | Funcional no smoke da GUI |
| `mh.getPickedColor` | `vulkan_picking.selecionar_cor` | Seleção CPU |
| Profundidade de câmera | `vulkan_picking.selecionar_profundidade` | Seleção CPU |
| `mh.grabScreen` | `vulkan_canvas.CanvasVulkan.grabScreen` | Captura de viewport Qt |
| `mh.renderToBuffer` | Framebuffer offscreen Vulkan com resolução independente | Smoke de produção |
| `mh.renderAlphaMask` | Canal alfa do framebuffer, convertido para `Image` RGB | Smoke do alfa |
| `mh.renderSkin` | `vulkan_skin.render_skin`: linhas, triângulos e quads UV | Smoke UV mínimo |
| `mh.Texture` | `vulkan_texture.Texture` em memória CPU | Implementação provisória |
| Material `.mhmat` | Difusa, opacidade, brilho especular, emissão, back/front cull, depthless | Pipeline WGSL; equivalência visual pendente |
| Malhas com `transparentPrimitives` | Desativa escrita de profundidade e descarta fragmentos de alfa zero (`glAlphaFunc(GL_GREATER, 0)` original) | Smoke GPU de camadas sobrepostas; alpha-to-coverage/MSAA pendentes |
| Camadas translúcidas | Composição de opacos antes de transparências, ordenação back-to-front pelo centro da malha dentro de cada bloco de `priority`/`cameraMode`; overlays `depthless` por último | Smoke GPU com duas camadas alpha em ordens de entrada invertidas; ordenação adicional de triângulos alpha dentro da malha em espaço de câmera, sem modificar os índices originais; interseções cíclicas continuam pendentes |
| Normal maps `.mhmat` | Textura e intensidade originais; base tangente derivada de UVs no fragmento | Pipeline validada na CI; comparação visual pendente |
| Iluminação `.mhscene` | Até oito luzes pontuais, ambiente e reflexo Blinn-Phong | Cores difusa e especular independentes preservadas; falta atenuação/foco e luzes de área |
| Shader xray original (.mhmat) | WGSL nativo com `edgefalloff`, `intensity`, cor ambiente e alfa de contorno | Execução GPU validada; comparar imagem |
| Shader LitSphere (pele padrão) | WGSL usa normal em espaço de câmera, textura de LitSphere original e `AdditiveShading`; `autoBlendSkin` usa `EthnicSkinBlender` original | Captura GPU e testes de parâmetros; equivalência visual pendente |
| Shader Phong original | WGSL usa o primeiro ponto de luz da cena, ambiente, difusa, especular e emissão do material original | AO implementado; comparação visual completa pendente |
| Shader Toon original | WGSL reproduz limiar da silhueta e faixas de luz por `smoothstep` com sete parâmetros do GLSL | Port da base; testar equivalência visual |
| Shader normalmap oficial | WGSL usa mapa de normais e iluminação difusa/especular em espaço tangente derivado das UVs | Base implementada; validação visual e tangentes originais pendentes |
| Shader skin oficial | WGSL amostra mapa AO e gradiente horizontal de cor convertido do antigo sampler1D | Base implementada; requer ambos os recursos e comparação visual |
| Shader Phong — mapa AO | Quando configurado, usa `aomapTexture` do material para modular a cor difusa | Implementado; falta teste visual comparativo |
| Seleção do shader no editor de materiais | Seis presets oficiais são reconhecidos; os parâmetros xray/LitSphere/Toon são editáveis na interface original | Validar interações e requisitos de textura para skin/normalmap |
| Equivalência dos shaders GLSL | Os seis presets têm caminhos WGSL; normalmap/skin e recursos avançados ainda não reproduzem integralmente os shaders legados | **Parcial** |
| Shaders GLSL arbitrários | `vulkan_shader.Shader.supported()` permanece falso; nenhum compilador GLSL genérico | **Pendente** |
| Imagens e ativos binários com NumPy 2 | `tobytes`/`frombuffer` e índices UTF-8; conversão QImage unificada | Roundtrip PNG/RGBA e dados binários validados |
| Wireframe original (`Ctrl+F`) | Superfície sem textura + arestas pretas por passes Vulkan; quads não recebem diagonais extras | Teste CPU e comparação GPU sólido/wireframe |
| Imports históricos `texture` e `shader` | Encaminham às implementações Vulkan, sem importar PyOpenGL | Corpos OpenGL removidos; GLSL personalizado continua sem suporte |

## Arquitetura

- A instância nativa wgpu é configurada exclusivamente com o backend Vulkan antes de criar o contexto; não inicializa GL/D3D/Metal.
- `qtui.py` conserva os eventos da interface original e cria sempre `CanvasVulkan` como único canvas da GUI.
- O smoke `testes/smoke_gui.py` inicia com o mesmo comando da GUI real, **sem `--noshaders`**, e `mhmain.py` não exibe o aviso modal GLSL antigo; a ausência de compilação GLSL arbitrária ainda é informada no log.
- `mh.py` preserva os nomes de API utilizados pelos plugins existentes, mas encaminha os serviços Vulkan ao canvas.
- `vulkan_scene.py` compartilha o adaptador e dispositivo GPU entre viewport, render offscreen e baking UV.
- `vulkan_offscreen.py` executa a conversão dos pixels BGRA/RGBA e o alinhamento WebGPU de 256 bytes.
- `vulkan_texture.py` mantém imagens CPU e invalida o cache GPU quando ocorre uma atualização.
- `vulkan_skin.py` rasteriza a geometria UV original em outro render pass.

## Validação

O workflow `.github/workflows/testar-wgpu.yml` cobre:

1. Testes de CPU, sem precisar criar GPU.
2. Smoke do motor Vulkan isolado.
3. Smoke da GUI original com Vulkan, incluindo render fora da tela e `renderSkin`.
4. Smoke da GUI original **sem PyOpenGL instalado**; este job é um detector de imports legados, e poderá falhar enquanto houver dependências remanescentes.

Para testar localmente, com Qt, Vulkan e bibliotecas do MakeHuman instaladas:

```bash
python makehumano/executar.py
```

Para testes de CPU:

```bash
python -m unittest discover -s makehumano/testes -p 'test_*wgpu.py' -v
```

## Executáveis portáteis

O empacotamento e o teste do binário congelado estão documentados em
[PORTATIL.md](PORTATIL.md). O smoke agora exercita também um modificador,
salvamento/recarregamento MHM e exportações OBJ, FBX binário, Collada e STL binário pelas ferramentas originais. Capturas dos presets, transparência, normais, especular e wireframe ficam no artefato de diagnóstico. No Windows, a CI compara 14 capturas dos fontes e do executável pixel a pixel, somente após a cena terminar de carregar.
A validação Windows utiliza Vulkan por software na CI; compatibilidade com
GPUs e drivers reais continua necessária antes de um lançamento.

Consulte também a [auditoria prática](AUDITORIA-VULKAN.md) para os bloqueadores
de compatibilidade e os limites dos testes.

## Pendências que impedem o lançamento

- Alcançar equivalência **visual** dos seis presets oficiais WGSL. Normalmap deriva tangentes no fragmento, Skin usa gradiente de uma linha em textura 2D, e Phong incorporou AO; diferenças com o GLSL original ainda precisam ser quantificadas. GLSL arbitrário continua sem compilação.
- Aperfeiçoar a transparência de cabelos e roupas entrelaçadas: já existe ordenação back-to-front pelo centro da malha e smoke para duas camadas; há ordenação por triângulo dentro da malha, com comparação GPU para ordem invertida; faltam interseções cíclicas, `alphaToCoverage`/MSAA e equivalência visual no modelo completo.
- Reproduzir atenuação/foco e luzes de área da cena, outros comportamentos avançados de materiais. A cor especular independente de `Light.specular` já chega aos shaders WGSL e é exercitada por comparação GPU. A transformação de normais já usa inversa-transposta do modelo.
- Criar testes comparativos de imagens, incluindo reflexos, alfa, normal maps e culling, porque o smoke só verifica inicialização e integridade básica.
- Completar paridade de `renderSkin` para formatos de imagem, texturas dinâmicas e render pass acumulativo.
- A inicialização e o smoke da GUI já não precisam de PyOpenGL; investigar e retirar módulos legados remanescentes no repositório.
- Validar interações, rendering de produção, plugins, arquivos e exportações em cenários reais.
- O backend Vulkan já é o padrão sem chave de piloto; concluir paridade e retirar os arquivos OpenGL obsoletos.
- Validar imagens comparativamente (CPU/smoke não verificam aparência pixel a pixel).

**Nenhum destes itens deve ser mascarado por um retorno fictício ou fallback silencioso.**

### Mapas e controles de luz do editor original

`specularMapTexture` modula a cor especular RGB; intensidade zero preserva o
material sem mapa. `transparencyMapTexture` reduz alfa por
`1 - intensidade * média(RGB)`: branco transparente, preto opaco, conforme o
uso do mapa como fator de transparência no exportador original. Faces com
mapa ativo entram na ordenação de transparência e não escrevem profundidade;
alfa zero é descartado. Isso não resolve interseções cíclicas de superfícies.

As luzes usam posição/foco em coordenadas de mundo. `fov` define o ângulo total
do cone; 180 graus mantém a luz pontual sem cone. `attenuation` aplica
`1 / (1 + attenuation * distância²)` às contribuições difusa e especular,
conservando as cenas anteriores quando zero. Luz ambiente não é atenuada.
Os modelos LitSphere e Xray mantêm sua iluminação própria. O controle
Softness grava o tamanho de área correto. A integração de área descrita
abaixo não implementa sombras.

Os smokes opcionais `vulkan_smoke_materials.py` e `vulkan_smoke_lighting.py`
renderizam pela mesma cena Vulkan da interface original e conservam capturas
e marcadores JSON. Não constituem um editor ou renderer alternativo.

### Bump e oclusão ambiente

O renderer interpreta `bumpMapTexture`/`bumpMapIntensity` como altura linear
(média RGB). O gradiente da altura perturba a normal em coordenadas de mundo,
sem alterar a malha, UVs, picking ou cobertura alfa. Altura constante, força
zero e `shaderConfig.bump=False` preservam a iluminação anterior. Normal maps
têm prioridade sobre bump, como em `Material._updateShaderConfig`. Isso não
implementa displacement nem substitui sombras.

`aoMapTexture`/`aoMapIntensity` e os nomes de uniforms originais são respeitados
no material básico e no Phong: mistura entre branco e o mapa pela intensidade.
AO modula a cor difusa sem apagar reflexão especular ou emissão; o material
básico shadeless ignora o mapa. O Skin conserva seu uso próprio do canal azul
para o gradiente de iluminação. Os smokes verificam mapas constantes, altura
variável, intensidade zero, controles desligados e prioridade de normal maps.

### Contrato de projeção UV

`renderSkin` aceita coordenadas de textura Nx2, Nx3 e Nx4, preservando Z e W
para a matriz de textura usada pela ferramenta de projeção original. Destinos
`Image` são lidos sem mutação, como no contrato original; destinos `Texture`
são atualizados para passes acumulados e invalidam o cache GPU. Conversão de
RGBA para destinos L/LA usa a conversão original de Image, conservando alfa
em LA. O smoke exercita composição, matrizes de objeto/textura e coordenadas
homogêneas equivalentes pela API `mh.renderSkin`.

A divisão projectiva por W/Q ocorre no fragmento, após interpolar as
coordenadas homogêneas. Um cenário GPU com Q variável detecta a distorção
que ocorreria dividindo as coordenadas ainda no vertex shader.

A projeção usa destino `rgba8unorm` próprio para compor bytes das imagens,
independente do formato sRGB/BGRA da janela. O readback considera o formato
da textura alvo, evitando trocar canais quando o destino difere do swapchain.
O teste GPU detectou a mistura incorreta ao herdar sRGB e valida novamente os
valores RGBA esperados da composição sobre a imagem existente.

### Emissão de área na viewport

`areaLights > 1` ativa a integração de um emissor quadrado orientado para
`focus`, com largura `areaLightSize`. Pares de amostras opostas mantêm o
centro; seus pesos somam um, conservando a energia. O padrão é determinístico
e não introduz cintilação entre frames. `areaLightSize=0` ou `areaLights=1`
restaura exatamente a luz pontual. A cena original não é modificada.

Para limitar o custo interativo, a viewport usa no máximo 16 amostras por
emissor e até oito emissores originais. O número de Samples salvo permanece
intacto. Os presets Phong, Toon, normalmap e Skin conservam o uso do primeiro
emissor, integrando suas amostras; o material básico integra os oito.
LitSphere e Xray preservam seus modelos próprios. Isso implementa emissão
espacial e variação dos reflexos, **sem oclusão nem sombras suaves**.

O smoke compara a emissão de área com uma soma explícita de luzes pontuais
com energia dividida, verifica tamanho zero, repetibilidade, resposta de
Samples e o preset Phong. Eventos dos widgets originais Soft light, Softness
e Samples e o roundtrip `.mhscene` também são exercitados.

### Multisampling e alpha-to-coverage

A opção original `--multisampling` ativa MSAA 4x na viewport e nos passes de
cena offscreen. Cor e profundidade usam quatro amostras; o alvo final é
resolvido para a textura legível pela CPU. Sem a opção, o padrão continua
uma amostra. `renderSkin` conserva seu destino linear de pintura independente.

Materiais translúcidos com `alphaToCoverage=True` usam cobertura multisample
no lugar de alpha blending, com profundidade por amostra, como no contrato
original. Linhas não ativam A2C. O cache de pipelines distingue contagem e
modo de cobertura; alvos são recriados ao mudar resolução ou multisampling.
A cobertura e o alfa resolvido são quantizados pelo hardware; isso não
implementa transparência OIT nem garante paridade entre todos os drivers.

O smoke alterna 1x/4x no mesmo renderer, verifica cobertura parcial nas
bordas, a resposta do controle de A2C, alfa zero e o retorno exato ao modo
anterior. Preserva capturas dos quatro cenários para comparação do portátil.

### Rig, pose e reprodução originais

O smoke usa os plugins `3_libraries_skeleton` e `3_libraries_pose` para
selecionar `default.mhskel`, aplicar `tpose.bvh` e desfazer/refazer as ações
originais. Verifica pesos normalizados, deformação das coordenadas e dos
pixels, além de salvar/reabrir um MHM com referências ao rig/pose. Restaura
rig, pose, animações e histórico ao terminar, sem alterar os assets oficiais.

Um track temporário de repouso/T-pose testa skinning em dois quadros e a
retenção do último quadro sem looping. Corrigidos `setLooping`, interpolação
no último quadro e `sparsify`: a redução de fps seleciona por tempo, mantém
contagem inteira e invalida o bake sem tratar matrizes de skinning como poses.
As poses BVH oficiais também são verificadas em CPU com NumPy atual.

O rig em repouso é exportado pelos exportadores originais FBX/Collada.
`portable_rig_validation.py` relê registros e arrays FBX (inclusive zlib),
ossos, clusters, pesos e matrizes de vínculo. No Collada, verifica joints,
controladores, limites dos índices e normalização dos pesos. Isso é validação
estrutural independente; não substitui importação em Blender/outro consumidor
nem comprova exportação de animações completas.

### Displacement de vértices e cópia de trabalho da textura

`displacementMapTexture` e `displacementMapIntensity` agora afetam o buffer de
vértices Vulkan. A CPU amostra L/LA/RGB/RGBA com filtro bilinear, clamp-to-edge
e orientação vertical das imagens Qt; alfa não representa altura. Preto é
zero, branco equivale a uma unidade local vezes a intensidade (0..1), na
direção da normal normalizada. Os vértices editáveis, morph targets e UVs
permanecem intactos. Não há tesselação nem recálculo das normais de
sombreamento; bump/normal maps continuam disponíveis para os detalhes.

Render, picking/profundidade, ordenação de transparência, wireframe e a
projeção original usam as mesmas posições deslocadas. Malhas sem UVs geram
erro explícito ao ativar o mapa. Mapa preto, intensidade zero e configuração
desligada preservam a posição anterior. O mapa não é gravado como deformação
no personagem exportado: formatos e referências aos mapas são preservados.

Restaurada a propriedade `Object3D.textureTex` usada por mapImageGL. O renderer
agora lê a mesma Texture CPU editável da ferramenta original, em vez de
reabrir o arquivo e ignorar a pintura. A recarga explícita descarta a cópia
em memória; modificações externas são detectadas por timestamp/tamanho.
O arquivo de origem não é sobrescrito pela projeção. O smoke usa a malha
real com uma textura temporária de teste e restaura o Material original.

A intensidade de displacement agora consta uma única vez entre os campos
reservados do Material. Arquivos antigos contendo `shaderParam
displacementmapIntensity` continuam legíveis, com seu valor efetivo migrado
para o campo canônico. Novas gravações não duplicam a propriedade.

A projeção obtém sua direção com a matriz de modelo da câmera original,
incluindo rotação orbital, em vez do atributo obsoleto `mesh.transform`.
O controlador de smoke interrompe a inicialização ao detectar um traceback
ou erro de desenho, preservando o diagnóstico sem repetir a mesma falha
até o timeout.
