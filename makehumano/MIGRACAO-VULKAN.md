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
| Shaders personalizados GLSL | `vulkan_shader.Shader` anuncia suporte indisponível | **Pendente** |

## Arquitetura

- `qtui.py` conserva os eventos da interface original e cria sempre `CanvasVulkan` como único canvas da GUI.
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

## Pendências que impedem o lançamento

- Converter shaders GLSL personalizados e seus uniforms/atributos para WGSL.
- Reproduzir transparência, culling, ordenação e iluminação conforme os materiais e configurações originais.
- Completar paridade de `renderSkin` para formatos de imagem, texturas dinâmicas e render pass acumulativo.
- A inicialização e o smoke da GUI já não precisam de PyOpenGL; investigar e retirar módulos legados remanescentes no repositório.
- Validar interações, rendering de produção, plugins, arquivos e exportações em cenários reais.
- O backend Vulkan já é o padrão sem chave de piloto; concluir paridade e retirar os arquivos OpenGL obsoletos.
- Validar imagens comparativamente (CPU/smoke não verificam aparência pixel a pixel).

**Nenhum destes itens deve ser mascarado por um retorno fictício ou fallback silencioso.**
