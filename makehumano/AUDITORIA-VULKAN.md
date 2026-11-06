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
| Erros de acesso a `.mhscene` geravam outra exceção | Tratamento de `OSError` compatível com Python 3; roundtrip de luzes, arquivo ausente e permissão negada testados |
| Softness alterava a atenuação no editor original | Evento agora atualiza `areaLightSize`, com regressão nos widgets reais; não implementa luzes de área |
| Plugins/exportadores só carregavam | Smoke altera geometria, salva/reabre MHM e exporta OBJ/FBX/DAE/STL, verificando estrutura dos arquivos |

## Validação local

A suíte completa executou **245 testes com sucesso**, usando Python 3.12,
NumPy 2.5.4 e Qt 5.15.14. Os testes Qt de gravação PNG verificam os canais,
alfa e imagens com largura não alinhada. Os dados binários verificam Unicode
em grupos de malha, tags de proxies e metadados de licença. A criação local do
pacote Linux e a importação congelada também foram exercitadas; os testes GPU
e GUI são executados nos runners dos workflows vinculados ao commit.

A comparação adicional de 23 PNGs entre fontes Windows e executável exige
igualdade exata de pixels no mesmo driver. As capturas são sincronizadas com
fim de startup para não comparar iluminação ainda não carregada. Essa
verificação detecta diferenças do empacotamento; não substitui equivalência
com o renderer original nem validação em outra GPU.

## Bloqueadores reais restantes

1. **Validação Windows em GPUs reais:** Vulkan por software no runner é um teste
   de integração, não uma matriz de drivers NVIDIA/AMD/Intel. Não classificar
   um artefato como aprovado enquanto o smoke Windows estiver falhando.
2. **Paridade de materiais e shaders:** os seis presets executam em WGSL, mas
   ainda faltam referências comparativas do original. Bump/displacement
   ainda não possuem cobertura completa no
   shader atual. Mapas especulares e de transparência separados agora têm
   testes analíticos GPU, incluindo intensidade zero. A interface pode expor parâmetros
   cujos efeitos não são integralmente implementados.
3. **Iluminação avançada:** sombras e luzes de área continuam pendentes.
   Foco, ângulo total do cone e atenuação quadrática agora afetam os presets
   iluminados. `Light.specular` independente foi tratado. LitSphere e Xray
   conservam seus modelos de iluminação próprios. Não há paridade comprovada
   com todos os renderizadores externos originais.
4. **Transparência avançada:** ordenar triângulos corrige a dependência simples
   da ordem, mas não resolve ciclos/interseções entre faces ou objetos.
   Alpha-to-coverage e MSAA ainda precisam ser portados e comparados.
5. **Recursos de roupas e cabelos:** este checkout contém a base, olhos e os
   carregadores originais, mas `data/hair` só contém `clear.thumb` e não há uma
   biblioteca de roupas completa. Não inventar ou substituir esses ativos.
   A validação integral requer exemplos reais licenciados, inclusive cabelos
   recortados e roupas sobrepostas, exercitados nos carregadores originais.
6. **Exportação ampliada:** o smoke valida malha/olhos nos quatro formatos;
   animações, rigs alternativos, proxies/roupas e todas as opções de exportação
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
   de mouse/teclado, poses e todas as
   ferramentas de projeção. `renderSkin` ainda exige testes adicionais de
   formatos, transformação UV e acumulação sobre imagens existentes.

## Critério de entrega

Manter o PR aberto, a `main` intacta e os pacotes identificados como testes.
Os artefatos de diagnóstico conservam logs completos, modelos exportados e
capturas reais; um teste de importação ou uma compilação bem-sucedida não
substitui um quadro Vulkan válido e ferramentas exercitadas.
