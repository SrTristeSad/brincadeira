# Auditoria verificável — MakeHumano original / Vulkan

**Data:** 2026-11-06. **Revisão auditada:** `5640c4e3274289fd17abcae93f9edbb9fd4b9213` do PR #10 (`makehumano/compatibilidade-picking-texturas-20261106`). O PR #10 tem como base a branch experimental do PR #1 (`makehumano/vulkan-texture-refresh`), **não** a `main`. A auditoria foi feita por leitura dos arquivos versionados, da árvore Git, dos workflows e de logs da CI já executada. Não houve execução de aplicativo em GPU física nesta auditoria.

## Veredito

**Integração Vulkan operacional no escopo automatizado; compatibilidade integral com MakeHuman/OpenGL NÃO comprovada.** Não classificar o programa como concluído ou pronto para substituir a versão de produção. Diferenciar:
- **Implementado:** a funcionalidade existe no código da branch.
- **Verificado:** um teste específico exercitou sua operação no ambiente definido.
- **Paridade comprovada:** a saída/semântica foi comparada ao original em cenário equivalente.
- **Não coberto:** não há teste representativo com recursos, programa consumidor ou driver necessário.

## Evidência da CI

- Commit `5640c4e`: **11/11 checks de GitHub Actions aprovados** (contagem de jobs, não de testes).
- Logs `testes (3.12)` e `testes (3.13)`: **352 testes em cada ambiente**, `OK (skipped=1)`; o teste ignorado verifica separadores de arquivo no Windows, não foi executado no Linux.
- Testes com interface original mostram renderização Vulkan, picking, framebuffer, máscara alfa, rasterização UV e demonstrações dos seis presets WGSL no Linux/Xvfb/Lavapipe. O job `vulkan` separado do workflow `testar-wgpu.yml` executa `motor_wgpu.app`, que é um **protótipo distinto**; não deve contar como prova extra da GUI original.
- Commit anterior `47cf1d4` (já com `lib/glmodule.py` removido) tem **13/13 checks verdes**, incluindo ZIP Windows e Linux. Ambos os portáteis foram iniciados na CI; o Windows compara capturas **Vulkan fontes × Vulkan congelado**, não OpenGL × Vulkan.
- A revisão final `5640c4e` contém mudanças de documentação subsequentes e executou novamente 11 checks, mas **não** o workflow de empacotamento. A comprovação dos ZIPs refere-se à revisão anterior indicada.

## Matriz de implementação e comprovação

| Área | Código realmente existente | Evidência disponível | Conclusão |
|---|---|---|---|
| GUI e renderizador original | `CanvasVulkan` e `CenaVulkan` renderizam `G.world` sem `glmodule.py` | Linux GUI + Lavapipe; Windows ZIP anterior | **Implementado/testado em CI**, não em GPUs físicas |
| Câmera, seleção, clipping | `vulkan_picking.py` faz interseção CPU e clipping homogêneo | Testes unitários + smoke de seleção na GUI | **Implementado**, paridade integral do picking não medida |
| Malhas e wireframe | Triângulos/quads, linhas e `GL_POINTS`; cache de buffers por objeto e passe | Testes CPU e smoke GPU para linhas/pontos | **Implementado**; tamanhos de pontos customizados não reproduzidos |
| Captura e baking | `renderToBuffer`, `renderAlphaMask`, `renderSkin`, `grabScreen(productionRender=True)` | Smokes offscreen e de produção | **Implementado/testado** nos casos cobertos |
| Shaders oficiais | Seis presets `xray`, `litsphere`, `phong`, `toon`, `normalmap` e `skin` em WGSL | Capturas e testes com Vulkan por software | **Implementados**, NÃO equivalência visual validada |
| Materiais/efeitos | Mapas normal, AO, bump, especular, transparência e displacement; sombras, atenuação e luzes de área possuem rotas Vulkan | Smokes com materiais/luzes selecionados | **Implementação parcial/avançada**, efeitos não equivalentes em todos os casos |
| Transparência | Ordenação por objeto e por triângulo, alpha blend, MSAA 4x/alpha-to-coverage | Testes sintéticos GPU | **Implementado para casos cobertos**; ciclos/interseções não resolvidos |
| Arquivos do personagem | Carregadores originais, MHM, morphs/poses, olhos oficiais | Testes de roundtrip e smoke | **Implementado/testado parcialmente**; faltam roupas/cabelos reais |
| Exportação e animação | Exportações originais e BVH, FBX/Collada com validadores próprios | Testes de arquivos e parsers próprios | **Testado parcialmente**; interoperabilidade externa não demonstrada |
| Retirada do OpenGL | `glmodule.py` não existe na branch; `Object3D.draw/pick` lançam `NotImplementedError` | AST de imports + GUI sem PyOpenGL | **Removido do runtime principal**, mas há quebra de APIs legadas |

## Lacunas constatadas — não repetir como "não implementado" aquilo que já existe

1. **Sem linha de base OpenGL para imagens (prioridade P0 para certificação).** `testes/comparar_opengl_vulkan.py` consegue calcular diferenças de dois PNGs RGBA, mas `test_compare_opengl_vulkan_wgpu.py` utiliza matrizes pequenas artificiais. A árvore Git do PR #10 não contém capturas OpenGL pareadas. `compare_portable_frames.py` compara somente duas execuções Vulkan do mesmo código. Não há medida de equivalência pixel a pixel dos seis presets, sombras, alfa e objetos reais.
2. **GLSL personalizado não suportado (incompatibilidade real).** Em `lib/vulkan_shader.py`, `Shader.supported()` devolve `False`; `configuracao_shader_nativo` devolve modo padrão e nome pendente para shaders não reconhecidos, com aviso no console. Em `plugins/7_material_editor.py`, presets desconhecidos aparecem como `[Pendente WGSL]`. Isso preserva a indicação no material, mas **não reproduz o shader**.
3. **APIs de desenho imediato removidas (incompatibilidade real para extensões).** `Object3D.draw()` e `Object3D.pick()` agora lançam `NotImplementedError`, ao invés de acionar uma API Vulkan equivalente. Código interno opera pela cena, mas extensões que chamam esses métodos não são compatíveis. Precisam de contrato de migração e testes de plugins reais.
4. **Transparência em interseções/ciclos (limite algorítmico).** `vulkan_scene.ordenar_triangulos_vulkan` ordena os centros de triângulos; `ordenar_objetos_vulkan` ordena centros dos objetos. Uma ordenação total não soluciona geometrias translúcidas que se cruzam ciclicamente. Não há OIT geral nem prova para cabelos reais. **MSAA e alpha-to-coverage já existem** e não devem ser relistados como ausentes.
5. **Displacement e iluminação avançada (diferença funcional).** `vulkan_displacement.posicoes_render` desloca vértices por mapa, mas não implementa tesselação nem recalcula as normais pós-deslocamento. Refração e transmissão colorida completas não foram verificadas/implementadas na rota atual, conforme auditoria do renderer. Sombras e luzes de área **já existem**: não chamar genericamente de ausentes.
6. **Falta de ativos representativos (bloqueio de validação).** Na árvore auditada, `data/hair/` contém só `clear.thumb`, `data/clothes/` não contém arquivos e há apenas os olhos oficiais. Faltam roupas/cabelos licenciados, com camadas transparentes, proxies, poses e máscaras, para confirmar o comportamento em uso real.
7. **Falta de hardware e consumidores independentes (bloqueio de validação).** A CI exercita Vulkan por software (Lavapipe) e um ZIP Windows; não demonstra operação em drivers físicos NVIDIA/AMD/Intel nem FPS/VRAM. FBX/DAE/BVH não foram certificados por Blender/meshes externos em cenários completos de personagens com roupas e animações. Os smokes automatizados não substituem uma campanha de mouse, teclado, editor de materiais e plugins.
8. **Documentação desatualizada (problema de gestão).** O cabeçalho de `lib/vulkan_scene.py` ainda chama picking, offscreen e transparência de pendentes, embora existam implementações. `MIGRACAO-VULKAN.md` ainda inclui trechos que dão a entender que alpha-to-coverage/MSAA ou foco/atenuação não existem. Isso ajuda a explicar o histórico de alegações contraditórias. Rever apenas após decidir critérios e atualizar a matriz única.

## Critérios objetivos para uma conclusão futura

- Fornecer pares de capturas **OpenGL original × Vulkan** com cena, resolução, câmera e iluminação equivalentes. Publicar métricas por preset, máscara alfa e materiais reais; corrigir diffs além dos limites acordados.
- Garantir teste representativo de roupas/cabelos licenciados e de pelo menos um caso de transparência com interseções; resolver defeito real observado, sem afirmar que OIT específico é obrigatório antes de medir.
- Declarar política explícita para **GLSL personalizado** e **Object3D.draw/pick**: suporte portado ou incompatibilidade aceita formalmente. Não prometer compatibilidade universal sem isso.
- Reabrir exportações com consumidores independentes e documentar problemas observados, cobrindo poses, rig, animação e acessórios.
- Registrar execução em GPUs físicas Windows/Linux, entradas de mouse/teclado e testes de desempenho com critérios reprodutíveis.
- Só então decidir promoção da branch experimental; **não integrar na `main` automaticamente**.

## Referências internas auditadas

- `makehumano/codigo/makehuman/lib/{vulkan_scene.py,vulkan_shader.py,vulkan_canvas.py,vulkan_picking.py,vulkan_displacement.py,object3d.py}`
- `makehumano/codigo/makehuman/plugins/7_material_editor.py`
- `makehumano/testes/{smoke_gui.py,comparar_opengl_vulkan.py,compare_portable_frames.py,test_compare_opengl_vulkan_wgpu.py,test_no_legacy_gl_wgpu.py}`
- `.github/workflows/{testar-wgpu.yml,testar-makehumano.yml,smoke-gui-makehumano.yml,empacotar-makehumano.yml}`
- Logs GitHub Actions do commit `5640c4e`: jobs `128130404621`, `128130404937`, `128130450415` e `128130450061`; portáteis da revisão `47cf1d4`: jobs `128130031269` e `128130031643`.

**Esta é uma auditoria de evidências do repositório e CI, não uma certificação manual de todas as funcionalidades nem um teste em GPU física.**
