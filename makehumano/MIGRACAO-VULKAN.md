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
