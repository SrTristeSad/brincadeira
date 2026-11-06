# Auditoria prática de compatibilidade — 6 de novembro de 2026

Escopo: a aplicação original em `codigo/makehuman`, não o demonstrador isolado
em `motor_wgpu`. O estado abaixo distingue testes exercitados de paridade final.

## Problemas tratados nesta etapa

| Problema | Correção e evidência exigida |
| --- | --- |
| Windows importava a GUI sem testar criação de janela/GPU | Executável congelado agora precisa renderizar `G.world` e concluir testes GPU no Windows e Linux |
| Dependências de plugins dinâmicos ausentes no Python congelado | Hook PyInstaller analisa módulos/plugins; smoke chama exportadores reais |
| Falha ao preparar perfil podia retornar sucesso | Exceção propagada e testes de regressão |
| Diagnóstico limitado a erro no import de `mhmain` | Handler cobre inicialização e exceções não tratadas; iniciador captura stdout/stderr UTF-8 |
| Instância nativa inicialmente permitia todos os backends | Configuração explícita apenas de Vulkan antes de criar o contexto, além da seleção do adaptador |
| Busca de DLL Vulkan no processo congelado Windows | Loader explícito e diretório de dependências mantidos vivos; validar resultado do workflow antes de aprovar o ZIP |
| Transparência só ordenava objetos | Ordenação também de triângulos por profundidade de câmera; teste GPU inverte faces da mesma malha |
| Cor difusa substituía `Light.specular` | Uniforms separados e comparação GPU com luz especular branca/preta |
| Wireframe original não mudava o render Vulkan | Superfície sem textura e arestas pretas, preservando topologia dos quads; teste GPU do controle original |
| Módulos históricos podiam importar PyOpenGL | `texture.py` e `shader.py` agora encaminham ao Vulkan; GLSL arbitrário falha explicitamente |
| `tostring`/`fromstring` binário incompatíveis com NumPy atual | Escrita/leitura modernizada em imagens, grupos de malha, proxies e licenças; roundtrips UTF-8 e PNG, incluindo correção de canais RGBA |
| Mapas especulares e de transparência ignorados | Texturas e intensidades originais no WGSL; testes GPU branco/preto/cinza e intensidade zero |
| Foco e atenuação sem efeito | Cone por posição/foco/ângulo e atenuação por distância; capturas GPU controladas |
| Erros de acesso a `.mhscene` geravam outra exceção | Tratamento de `OSError` compatível com Python 3; roundtrip de luzes, arquivo ausente, permissão negada e preservação da cena após arquivo truncado testados |
| Softness alterava a atenuação no editor original | Evento agora atualiza `areaLightSize`, com regressão nos widgets reais; emissão de área agora amostrada no Vulkan |
| Samples/Soft light sem efeito no renderer | Emissão de área integrada, tamanho zero restaura luz pontual, energia comparada à soma explícita de luzes |
| Atributos opcionais de SceneObject causavam recursão | Consulta de atributo inexistente agora levanta AttributeError, com regressão de hasattr/getattr |
| Reprodução sem looping voltava ao primeiro quadro | Setter e interpolação corrigidos; teste de deformação real retém o último quadro |
| Reduzir fps falhava na propriedade sem setter | Reamostragem por tempo com quadros inteiros, poses originais e invalidação do cache de skinning |
| Rig/pose/exportação com ossos sem cobertura | Plugins oficiais, undo/redo, roundtrip MHM, capturas Vulkan e leitura de pesos/matrizes dos arquivos exportados |
| Displacement sem efeito na viewport/seleção | Amostragem bilinear e posições compartilhadas entre render, picking, ordenação e projeção, sem alterar a malha original |
| Projeção original sem textureTex ou pintura visível | Texture CPU compartilhada com a viewport, arquivo preservado e recarga explícita validada na malha real |
| Intensidade de displacement serializada como uniform customizado | Campo reservado corrigido, gravação canônica e leitura compatível com arquivos antigos |
| Plugins/exportadores só carregavam | Smoke altera geometria, salva/reabre MHM e exporta OBJ/FBX/DAE/STL, verificando estrutura dos arquivos |

## Validação local

A suíte completa executou **327 testes sem falhas** (um específico do Windows é pulado localmente), usando Python 3.12,
NumPy 2.5.4 e Qt 5.15.14. Os testes Qt de gravação PNG verificam os canais,
alfa e imagens com largura não alinhada. Os dados binários verificam Unicode
em grupos de malha, tags de proxies e metadados de licença. A criação local do
pacote Linux e a importação congelada também foram exercitadas; os testes GPU
e GUI são executados nos runners dos workflows vinculados ao commit.

A comparação adicional de 55 PNGs entre fontes Windows e executável exige
igualdade exata de pixels no mesmo driver. As capturas são sincronizadas com
fim de startup para não comparar iluminação ainda não carregada. Essa
verificação detecta diferenças do empacotamento; não substitui equivalência
com o renderer original nem validação em outra GPU.

## Correções adicionais de compatibilidade (branch experimental)

- **Picking em limites da câmera:** recorte homogêneo dos triângulos
  contra os seis planos de clip Vulkan antes de dividir por `w`.
  Preserva as partes visíveis dos triângulos que cruzam o plano próximo
  ou o enquadramento lateral, mantendo RGB por FaceGroup, profundidade e culling.
  Foram adicionados casos de regressão de near/far, lateral e profundidade.
- **Texturas substituídas externamente:** a cópia CPU do material agora
  verifica `mtime_ns`, `ctime_ns`, tamanho, dispositivo e inode.
  Assim, a substituição atômica de um PNG com mesmo mtime e tamanho
  não deixa pixels antigos na viewport. Há regressão com PNG válido
  substituído via `os.replace`.

- **Primitivas auxiliares de ponto:** objetos originais com índices
  `N×1` agora usam `point-list` na pipeline Vulkan, mantendo índices,
  coordenadas e cores RGBA. O smoke da GUI gera um ponto temporário sobre
  a geometria da cena original, renderiza em framebuffer real, verifica
  cobertura de alfa e registra `points.json` sem modificar o personagem.
  A rasterização de pontos tem tamanho padrão de um pixel; tamanhos
  personalizados de GL_POINTS ainda não possuem equivalência comprovada.

Estas correções são parciais: não demonstram paridade visual com OpenGL,
compatibilidade de cabelos/roupas ausentes nem execução em GPUs físicas.
Conferir a CI do PR de compatibilidade antes de considerá-las aprovadas.

## Comparação visual reproduzível OpenGL × Vulkan

Foi incluído `testes/comparar_opengl_vulkan.py`, com testes de regressão
para RGBA, tolerância por canal, proporção de pixels divergentes e cobertura
alfa (interseção/união). Não reescala nem alinha automaticamente as capturas,
pois isso esconderia diferenças reais. O comparador pode emitir JSON e mapa
ampliado de diferenças, retornando código 1 quando o limite configurado é
excedido. Exemplo, a partir da raiz do repositório:

```bash
python makehumano/testes/comparar_opengl_vulkan.py original.png atual.png \
  --tolerancia 3 --fracao-maxima 0.01 \
  --json comparacao.json --diferenca diferencas.png
```

É obrigatório fornecer capturas do **mesmo personagem, câmera, iluminação,
resolução e materiais**, uma produzida pelo OpenGL original e outra pelo
Vulkan atual. O repositório não contém referências aprovadas para afirmar
paridade. Os testes de métricas validam o comparador, **não** a equivalência
visual dos seis shaders; a decisão de aprovação depende dessas referências
reais e revisão humana.

## Bloqueadores reais restantes

1. **Validação Windows em GPUs reais:** Vulkan por software no runner é um teste
   de integração, não uma matriz de drivers NVIDIA/AMD/Intel. Não classificar
   um artefato como aprovado enquanto o smoke Windows estiver falhando.
2. **Paridade de materiais e shaders:** os seis presets executam em WGSL, mas
   ainda faltam referências comparativas do original. Displacement agora
   desloca os vértices de render/picking/projeção, mas não faz tesselação
   nem recalcula normais de sombreamento. Mapas especulares e de transparência separados agora têm
   testes analíticos GPU, incluindo intensidade zero. Bump altera as normais
   por gradiente de altura, com prioridade para normal maps. AO agora respeita
   intensidade no material básico e no Phong. A interface pode expor parâmetros
   cujos efeitos não são integralmente implementados.
3. **Iluminação avançada:** sombras de oclusores estão integradas ao
   Vulkan, incluindo recorte alpha, transmissão escalar por camadas,
   penumbra por amostras de área e controles originais de
   Material. A BVH acompanha morphs/poses/displacement sem alterar a malha.
   Faltam refração/transmissão colorida, avaliação ampliada do viés e desempenho
   em GPUs físicas. LitSphere e Xray conservam sua iluminação própria.
   Não há paridade comprovada com renderizadores externos originais.
   Ver [etapa de sombras](SOMBRAS-VULKAN.md).
4. **Transparência avançada:** ordenar triângulos corrige a dependência simples
   da ordem, mas não resolve ciclos/interseções entre faces ou objetos.
   MSAA 4x e alpha-to-coverage agora têm testes GPU sintéticos.
   Ainda faltam cabelos reais, mais drivers e comparação de cobertura entre GPUs.
5. **Recursos de roupas e cabelos:** este checkout contém a base, olhos e os
   carregadores originais, mas `data/hair` só contém `clear.thumb` e não há uma
   biblioteca de roupas completa. Os olhos oficiais high/low-poly são
   exercitados no carregador original, com morph visível, undo/redo e UUID
   preservado no MHM. Isso não valida cabelos ou roupas ausentes. Não inventar
   ou substituir esses ativos.
   A validação integral requer exemplos reais licenciados, inclusive cabelos
   recortados e roupas sobrepostas, exercitados nos carregadores originais.
6. **Exportação ampliada:** o smoke valida malha/olhos nos quatro formatos e
   o rig oficial em repouso no FBX binário/Collada, relendo ossos, matrizes e
   pesos. Rig/pose oficiais também são salvos/reabertos em MHM.
   O BVH com dois quadros de repouso/T-pose é exportado pelo plugin e
   recarregado, comparando poses locais dos 163 ossos. Animações FBX/Collada,
   demais opções BVH, rigs alternativos, proxies/roupas e demais opções
   ainda precisam ser reabertos em consumidores independentes.
7. **Legado gráfico restante:** `lib/glmodule.py` ainda contém a implementação
   obsoleta e os métodos históricos `Object3D.draw/pick` a referenciam. O
   renderer ativo e os serviços `mh` passam pelo Vulkan. Retirar esse arquivo
   exige resolver/aposentar explicitamente esses contratos, sem fingir que
   redraw da cena equivale a uma chamada de desenho dentro de um render pass.
8. **GLSL personalizado:** não existe tradução genérica para WGSL. Os presets
   oficiais possuem rotas nativas; scripts GLSL externos continuam pendentes.
9. **Interações completas:** os smokes chamam APIs originais e verificam pixels;
   incluem undo/redo do modificador original, mas não cobrem toda sequência
   de mouse/teclado e todas as
   ferramentas de projeção. `renderSkin` agora verifica coordenadas 3D/4D,
   matrizes de textura/objeto, composição sobre Texture existente e destino LA;
   O fluxo mapImageGL original também é exercitado sobre a malha real,
   incluindo cópia de trabalho e displacement. Faltam sequências completas
   de mouse/teclado com imagens externas.

## Critério de entrega

Manter o PR aberto, a `main` intacta e os pacotes identificados como testes.
Os artefatos de diagnóstico conservam logs completos, modelos exportados e
capturas reais; um teste de importação ou uma compilação bem-sucedida não
substitui um quadro Vulkan válido e ferramentas exercitadas.
