# Sombras Vulkan — etapa separada

A implementação está em `codigo/makehuman/lib/vulkan_shadows.py`, integrada
à cena original `G.world`. Não cria outro editor, personagem ou renderer CPU.

## Usar

Em **Utilities → Material Editor**:

- **Cast shadows**: o objeto pode bloquear a luz que chega a outros objetos.
- **Receive shadows**: sua iluminação direta respeita os objetos oclusores.

Os valores são os campos originais `castShadows` e `receiveShadows` do Material,
preservados em `.mhmat`. O editor pede um redraw após cada alteração.

As luzes pontuais e de foco projetam sombras duras. Os controles originais de
luz **Soft light**, **Softness** e **Samples** integram a oclusão das amostras
do emissor de área e produzem penumbra. A viewport conserva o limite de 16
amostras por emissor e oito emissores; não altera os valores salvos na cena.

Sombras atenuam a contribuição direta difusa e especular, sem apagar a luz
ambiente, o AO do material ou a emissão própria. O material básico e os
presets Phong, Toon, Normalmap e Skin usam essa visibilidade. LitSphere e
Xray preservam a iluminação própria dos presets e não recebem sombras de
luzes da cena. Não há chão ou geometria adicional criada automaticamente.

## Implementação

A CPU coleta os triângulos visíveis do MakeHuman, incluindo máscaras de faces,
transformações e displacement. Constrói uma BVH em pré-ordem com limites,
faixas de triângulos e índices de escape. WGSL percorre os buffers de leitura
na GPU e testa o segmento entre fragmento e amostra de luz, sem extensões de
ray tracing e sem fallback OpenGL. Objetos atrás do receptor ou além da luz
não bloqueiam esse segmento. O viés cresce com a extensão da cena.

A geometria original não é modificada. Assinaturas dos triângulos reutilizam
os buffers quando nada mudou; morphs, poses e transformações reajustam os
limites da árvore por níveis. Alterações da quantidade de triângulos refazem
a partição. Objetos invisíveis, linhas, overlays 2D, `depthless` e exclusões
do render de produção não viram oclusores.

Na base original de 36.972 triângulos, a árvore e os triângulos empacotados
ocupam aproximadamente 2,6 MB. Uma medição CPU local levou cerca de 500 ms
para particionar e 16 ms para reajustar após deformação. Esses valores não
medem FPS nem garantem desempenho em outras máquinas; a consulta GPU por
fragmento também tem custo, sobretudo com várias luzes e Samples altos.

## Escopo e limites

Somente superfícies opacas lançam sombras nesta etapa. Materiais marcados
como transparentes, opacidade abaixo de um, mapa de transparência ativo,
cores de vértice com alfa, texturas com qualquer alfa abaixo de 255 e o preset
Xray são excluídos dos oclusores. Faces translúcidas ao fim das primitivas
originais são excluídas individualmente. Não se projeta uma sombra retangular
opaca para fingir suporte a cabelos recortados.

Faltam sombras com recorte alpha por texel, transmissão por materiais
translúcidos, validação com cabelos/roupas reais e GPUs Windows físicas,
medição interativa de desempenho e avaliação de acne/viés em escalas extremas.
Sombras de área usam amostras discretas determinísticas, portanto podem
apresentar faixas com poucos Samples. Não se afirma paridade com renderizadores
externos, iluminação global ou paridade visual completa com o MakeHuman antigo.

## Validação

Os testes CPU verificam layout dos buffers, cobertura da árvore, limites e
escapes, índices degenerados, reajuste após deformação, cache e os filtros dos
materiais originais. O smoke GPU usa duas superfícies temporárias na câmera
original e exige: escurecimento por oclusão, penumbra, alpha preservado,
`castShadows`/`receiveShadows`, objeto atrás do receptor sem oclusão, exclusão
de produção e geometria intacta. Também aciona os controles do editor original
e salva/reabre um `.mhmat`. Os estados do personagem e da iluminação são
restaurados após o teste.

Os diagnósticos contêm `shadows.json`, `shadow-off.png`, `shadow-point.png` e
`shadow-area.png`; as três imagens entram na comparação entre fontes Windows
e executável. O teste portátil completo é repetido com MSAA 4x.


## Evidências da revisão

Código empacotado: `dc3ec040c5305cfa764d13093614ad7e5afb6926`.

- [Windows/Linux: GUI real, ferramentas e MSAA](https://github.com/SrTristeSad/brincadeira/actions/runs/42257728380)
- [CPU, Vulkan e GUI original sem PyOpenGL](https://github.com/SrTristeSad/brincadeira/actions/runs/42257728593)
- [ZIP Windows de testes](https://github.com/SrTristeSad/brincadeira/actions/runs/42257728380/artifacts/13524435592)
- [Diagnóstico Windows com PNGs e JSON](https://github.com/SrTristeSad/brincadeira/actions/runs/42257728380/artifacts/13523971123)

Os portáteis Windows e Linux concluíram os testes padrão e MSAA. Os três
relatórios Windows (fontes, portátil e portátil MSAA) confirmam oclusão,
penumbra, controles, persistência, exclusão de produção e geometria preservada.
A fixture tem 271 pixels de penumbra parcial. São 50 capturas idênticas entre
fontes e executável Windows, comparação repetida após baixar os diagnósticos.
O reajuste da BVH conservou as 50 capturas Linux da primeira implementação
nos modos padrão e MSAA. A suíte local contém 321 casos sem falhas, com um
caso exclusivo de separadores Windows excluído no Linux.

O ZIP Windows foi baixado e auditado (integridade, Python, Qt, wgpu-native,
recursos e módulos de sombras; sem drivers da CI). SHA-256:
`009235138da66f17554adbbe2f23bd67fee11eedb52928fc6123b6e5424b520f`.
A CI usa Vulkan por software, não GPU Windows física.
