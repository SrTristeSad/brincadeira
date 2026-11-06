# Sombras Vulkan — etapa separada

A implementação está em `codigo/makehuman/lib/vulkan_shadows.py` e
`vulkan_shadow_alpha.py`, integrada
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
ray tracing e sem fallback OpenGL. A cobertura é amostrada pelas UVs do ponto
atingido: alfa da textura, opacidade, alfa dos vértices e mapa de transparência
com sua intensidade/configuração, respeitando o contrato de cada preset.
Máscaras usam filtro bilinear, clamp-to-edge e origem superior das imagens,
sem redimensionamento. Cada interseção transmite a fração `1 - alfa`; as
frações das camadas são multiplicadas, independentemente da ordem dos objetos.
Arestas compartilhadas têm uma regra semiaberta para não contar duas vezes
a diagonal de um quad. Objetos atrás do receptor ou além da luz
não bloqueiam esse segmento. O viés cresce com a extensão da cena.

A geometria original não é modificada. Assinaturas dos triângulos reutilizam
os buffers quando nada mudou; morphs, poses e transformações reajustam os
limites da árvore por níveis. Alterações da quantidade de triângulos refazem
a partição. Objetos invisíveis, linhas, overlays 2D, `depthless` e exclusões
do render de produção não viram oclusores.

Na base original de 36.972 triângulos, a árvore e os triângulos empacotados
ocupam aproximadamente 2,6 MB. Uma medição CPU local levou cerca de 500 ms
para particionar e 16 ms para reajustar após deformação; a medição isola a
árvore, sem upload de texturas, e não mede FPS. O total de memória citado não
inclui os novos descritores de cobertura (80 bytes por triângulo) e pixels RGBA8. Os buffers de cobertura têm cache separado: alterar
textura/opacidade não exige reenviar geometria. Texturas usadas somente pelo
alfa e inteiramente opacas não ocupam o buffer de pixels. O tamanho dos
buffers de cobertura é validado contra o limite do dispositivo, com erro explícito em
vez de truncamento. Não há garantia de desempenho em outras máquinas; a consulta GPU por
fragmento também tem custo, sobretudo com várias luzes e Samples altos.

## Escopo e limites

Superfícies opacas, recortadas e parcialmente transparentes lançam sombras.
Faces translúcidas originais permanecem na BVH: suas UVs e cobertura decidem
quanto da luz passa, em vez de excluir o objeto inteiro ou projetar um
retângulo opaco. A transmissão é escalar, sem refração nem filtragem de cor.
Cada superfície atravessada contribui; uma malha fechada pode ser atravessada
na entrada e na saída, diferentemente de um cartão de cabelo de uma só camada.

Xray continua excluído dos oclusores: sua transparência de contorno depende
da direção de visão e não foi convertida para um material físico de sombra.
LitSphere/Xray conservam a iluminação própria ao receber luz. Faltam
validação com cabelos/roupas reais licenciados, GPUs Windows físicas,
medição interativa de desempenho e avaliação do viés em escalas extremas.
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

A extensão alpha verifica recorte assimétrico com orientação UV, edição da
Texture CPU em memória, intensidade zero/configuração desligada, alfa dos
vértices, opacidade e duas camadas de 50% transmitindo 25%. A referência
quantitativa interpola luz linear e a converte para sRGB quando o framebuffer
usa esse formato; não interpola diretamente os bytes sRGB. A tolerância
continua em três níveis de canal para quantização/interpolação. Capturas e
arrays de diagnóstico são preservados se essa comparação falhar.

Os diagnósticos contêm `shadows.json`, `shadow-off.png`, `shadow-point.png` e
`shadow-area.png`, `shadow-cutout.png`, `shadow-opacity.png` e
`shadow-layers.png`; as seis imagens entram na comparação entre fontes Windows
e executável. O teste portátil completo é repetido com MSAA 4x.


## Evidências da revisão

Código empacotado: `bceafdc6d0d743525f02813612e68a632979de87`.

- [Windows/Linux: GUI real, ferramentas e MSAA](https://github.com/SrTristeSad/brincadeira/actions/runs/42262233631)
- [CPU, Vulkan e GUI original sem PyOpenGL](https://github.com/SrTristeSad/brincadeira/actions/runs/42262233526)
- [ZIP Windows de testes](https://github.com/SrTristeSad/brincadeira/actions/runs/42262233631/artifacts/13526285898)
- [Diagnóstico Windows com PNGs e JSON](https://github.com/SrTristeSad/brincadeira/actions/runs/42262233631/artifacts/13526325846)

Os portáteis Windows e Linux concluíram os testes padrão e MSAA. Os três
relatórios Windows (fontes, portátil e portátil MSAA) confirmam oclusão,
penumbra, controles, persistência, exclusão de produção e geometria preservada.
A fixture tem 271 pixels de penumbra parcial. São 53 capturas idênticas entre
fontes e executável Windows, comparação repetida após baixar os diagnósticos.
A extensão alpha conservou as 50 capturas da revisão anterior, no Windows
e no Linux, nos modos padrão e MSAA. Os relatórios também confirmam recorte
UV, edição de textura, alfa de vértice, opacidade, mapa de transparência e
transmissão por camadas sem dependência da ordem. A suíte local contém 326 casos sem falhas, com um
caso exclusivo de separadores Windows excluído no Linux.

O ZIP Windows foi baixado e auditado (integridade, Python, Qt, wgpu-native,
recursos e módulos de sombras; sem drivers da CI). SHA-256:
`3bb1e94a9540781e6b86913ce12d5c42d37f0f8fcf186acc9e95dc2f811122f6`.
A CI usa Vulkan por software, não GPU Windows física.
