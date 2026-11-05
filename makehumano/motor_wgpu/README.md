# Motor WGPU experimental — MakeHumano

**Estado:** protótipo isolado. A interface original em PyQt5/OpenGL permanece funcionando e não foi substituída.

O módulo `motor_wgpu/` usa **wgpu-py + WGSL** para visualizar o `codigo/makehuman/data/3dobjs/base.obj` original. A leitura OBJ seleciona o grupo `body`, triangula quads, preserva UV e calcula normais suavizadas. O renderizador suporta depth buffer, rotação/zoom via controles e **troca de textura RGBA em tempo real**, além de tonalidade e rugosidade da pele com iluminação difusa + reflexo GGX básico.

O painel experimental agora usa **as definições oficiais** de `modeling_modifiers.json` e `modeling_sliders.json`: 238 modificadores anatômicos têm `.target` diretos nesta revisão e podem ser selecionados por região. Os sliders têm direção positiva/negativa quando o MakeHuman define ambos os targets. Os arquivos são carregados sob demanda, com cache; o renderizador recalcula normais, preserva UVs e atualiza o vertex buffer da GPU. **Oito macrocontroles anatômicos agora funcionam na prévia:** idade, gênero morfológico, peso, musculatura, altura, proporções corporais, volume e firmeza dos seios. Seus fatores são comparados nos testes aos cálculos originais de `apps/human.py`, e **564 `.target`** participam do catálogo de macroformas. **Os três parâmetros de mistura étnica herdados do MakeHuman agora também possuem sliders interdependentes**, totalizando 11 controles gerais. O ajuste de um parâmetro renormaliza os outros dois para a soma permanecer em 100%, seguindo `Human._setEthnicVals`. Essas categorias correspondem a alvos de deformação herdados, **não a uma medição de identidade étnica**. Ainda não foram integradas todas as relações entre o sistema original de modificadores, a GUI principal, as poses e os plugins. Esta prévia já aceita mapas de normal e rugosidade no shader GGX e um **efeito aproximado de dispersão da pele**, mas ainda não implementa dispersão subsuperficial física, pintura 3D, rigging ou picking. Os presets de cores são exemplos, não texturas oficiais.

## Executar

Use Python 3.12 ou 3.13 e drivers de vídeo atualizados. Na pasta `makehumano/`:

```bash
python -m pip install -r motor_wgpu/requirements.txt
python -m motor_wgpu.app
```

Para solicitar **Vulkan explicitamente**:

```bash
python -m motor_wgpu.app --backend vulkan
```

Sem o argumento, wgpu seleciona automaticamente um backend disponível (Vulkan, Metal ou D3D12, conforme o sistema). Se a GPU/driver não suportar o backend escolhido, o programa pode falhar; nesse caso, execute novamente sem `--backend`. Na janela, escolha uma textura por `Carregar textura da pele…`. Use uma textura UV no layout do `base.obj` original para que corresponda ao modelo. A coluna de controles contém oito parâmetros gerais, três controles de mistura étnica interdependentes e um seletor de região (cabeça, nariz, braços e pernas etc.). Sliders bidirecionais funcionam de -100 a +100; unidirecionais, de 0 a +100. Ao trocar de grupo, os pesos permanecem ativos. **Restaurar todas as deformações** repõe as macrovariáveis iniciais do MakeHuman e zera os sliders anatômicos. O modelo inicial já recebe os macros padrão, não é a malha `.obj` absolutamente neutra.

### Olhos low-poly e high-poly com proxies oficiais

O visualizador Vulkan possui **dois modelos de olhos** com malha, UV e textura próprias: **low-poly (96 vértices canônicos)** e **high-poly (1.064 vértices canônicos)**. A caixa *Mostrar olhos originais* controla a visibilidade, e a lista permite escolher a resolução. Apenas o modelo selecionado é desenhado; os dois compartilham o depth buffer com o corpo.

O arquivo original `low-poly.mhclo` utiliza **referência direta** de cada vértice ao corpo. O `high-poly.mhclo` utiliza **três vértices de referência, três pesos e um deslocamento tridimensional** para cada vértice. Seu deslocamento é ajustado por uma matriz diagonal calculada das distâncias do corpo deformado nos eixos x/y/z, segundo `TMatrix.getMatrix()` do MakeHuman. O código compara os resultados com **`Proxy.getCoords()` e `TMatrix.getMatrix()` originais**, inclusive após deformações. Em cada atualização, as normais são recalculadas e as UVs preservadas.

**Ainda não é um sistema completo de roupas:** a cópia do repositório não inclui peças de vestuário. Já é possível carregar manualmente arquivos `.mhclo` externos compatíveis, com referências diretas/ponderadas, escala/shear, e máscaras `delete_verts` automáticas. Porém não há catálogo próprio, rigs, poses, materiais `.mhmat` completos, transparência de tecido nem resolução de colisões. A resolução selecionada dos olhos também ainda não é persistida no JSON experimental. A verificação de CI usa Vulkan por software; não substitui uma inspeção visual em GPU física.

### Importar acessórios e roupas externos (`.mhclo`)

O botão **Adicionar peça .mhclo…** permite selecionar manualmente um arquivo de proxy MakeHuman externo e, opcionalmente, uma imagem de textura. O **OBJ deve estar na mesma pasta que o `.mhclo`**, como definido em `obj_file`. Se cancelar a escolha manual de textura, o programa tenta usar automaticamente a imagem `diffuseTexture` do material `.mhmat` associado ao proxy; sem material ou sem mapa difuso, usa RGBA branco neutro. A escolha manual substitui apenas a imagem, mantendo a cor e a rugosidade do material. O sistema identifica automaticamente a primeira linha da seção `verts 0`:

- **Uma referência por vértice:** vínculo direto, como os olhos low-poly oficiais.
- **Três referências, três pesos e três offsets:** proxy ponderado, com escala `x_scale/y_scale/z_scale` ou shear compatível.

Ao carregar, a peça recebe uma entrada independente na interface, com **visibilidade** e botão **Remover**. Os vértices da peça seguem os morph targets do corpo; sua máscara `delete_verts`, quando definida, oculta os triângulos correspondentes do corpo **somente enquanto a peça está visível**. É possível carregar várias peças, cada uma com sua malha e textura. O corpo não é modificado permanentemente, e remover uma peça restaura sua parte da máscara.

**Materiais `.mhmat` (parciais):** o leitor reconhece a referência `material` do `.mhclo`, inclusive o padrão `../materials/` dos olhos oficiais, e utiliza `diffuseTexture`, `diffuseColor` e `shininess` (transformada em rugosidade GGX **aproximada**, não física). Os arquivos são resolvidos apenas em diretórios locais permitidos. Opções de shader, mapas adicionais, transparência, animação de material e outras propriedades **não são reproduzidas**; o programa apresenta avisos ao importar uma peça com esses recursos. A renderização ainda é opaca, mesmo que o `.mhmat` declare transparência.

**Ainda é uma importação experimental e parcial:** não interpreta o sistema `.mhmat` completo, ossos/rigs, poses, pesos de skinning, colisões, ajuste físico, transparência de tecido ou oclusão entre camadas de roupa. Alguns proxies oficiais podem ter diretivas que o parser recusa explicitamente; são necessárias adaptações antes de importar esses casos. A seleção e a textura das peças externas **não são persistidas no projeto `.makehumano.json` e não entram na exportação OBJ do corpo**. Por enquanto, carregue novamente os acessórios ao reabrir o visualizador. O teste gráfico exercita uma **peça sintética temporária**, não uma roupa oficial de produção.

### Compatibilidade de roupas: shear e máscaras (infraestrutura)

O leitor de acessórios `.mhclo` ponderados agora reconhece as transformações `shear_x/y/z`, `l_shear_x/y/z` e `r_shear_x/y/z`. O cálculo constrói os oito cantos das caixas de referência usadas em `TMatrix.matrixFromShear()` e ajusta uma transformação afim 3×3 para os offsets. O caminho existente `x_scale/y_scale/z_scale` continua prioritário, como no MakeHuman original. Valores e combinações incompletos são rejeitados explicitamente.

Também foram acrescentadas as seções `delete_verts` com índices e intervalos inclusivos (`10 - 25`), a transferência de visibilidade entre malha-base e proxy segundo `transferVertexMaskToProxy()` e a filtragem dos triângulos da malha-base usando o index buffer Vulkan. Isso **não altera a topologia canônica ou os morph targets**; o índice ativo pode ser restaurado integralmente.

**Integração automática com os acessórios:** cada malha adicional pode registrar a máscara `delete_verts` ao ser criada. O gerenciador combina, por OU lógico, somente as máscaras de acessórios **visíveis**; ao esconder ou remover uma peça, seus triângulos ocultos reaparecem automaticamente. Se várias máscaras estiverem ativas, elas se somam. A máscara manual de diagnóstico continua independente, e o índice GPU só é reenviado quando a combinação efetiva muda. O corpo, os morph targets e as UVs permanecem inalterados.

**Escopo:** não há roupas reais nesta cópia do repositório. Os olhos oficiais têm máscaras vazias, portanto não ocultam o rosto. Os testes exercitam máscaras sintéticas temporárias vinculadas aos olhos e a um acessório de teste, e restauram tudo antes de encerrar; **isso não significa que roupas reais já estejam disponíveis**. Ainda faltam catalogar/adicionar peças, tratar oclusão entre camadas, colisões, rigging, transparência e materiais de tecido.

### Mapas de normal e rugosidade

O painel **Mapas de detalhe da pele** permite **carregar/remover** dois mapas diretamente na GPU, sem alterar a malha, os modificadores ou as UVs:

- **Normais:** textura RGB/RGBA em espaço tangente, convenção OpenGL (+Y). O shader constrói uma base tangente com derivadas das posições e UVs em cada fragmento; regiões sem derivadas UV válidas usam a normal geométrica.
- **Rugosidade:** o **canal vermelho**, lido linearmente, multiplica a rugosidade base escolhida no slider, com limite mínimo de 0,05. Um mapa branco não altera o material.

O mapa neutro/ausência de mapas mantém a apresentação anterior. Um normal map não é um height/bump map, e o resultado exige um UV layout compatível com o `base.obj`. Como o WGSL usa iluminação GGX simplificada, a aparência ainda não é equivalente ao sistema avançado de materiais do MakeHuman original.

### Dispersão da pele (aproximação, não SSS físico)

O slider **Dispersão da pele (aproximada)** vai de 0 a 100%. Em 0%, a iluminação difusa preserva o resultado anterior; valores maiores acrescentam um componente difuso suavizado e levemente avermelhado nas regiões próximas às bordas de iluminação. O cálculo ocorre em **um único fragment shader**, sem texturas novas, passagens adicionais ou alteração da malha. A intensidade inicial para personagens novos é 25%.

Este efeito é **artístico**, não um cálculo físico de `subsurface scattering`: não calcula espessura, iluminação transmitida, distância percorrida sob a superfície, dispersão espacial ou sombras translúcidas. Não espere comportamento realista de orelhas retroiluminadas. Ele serve para avaliar a direção visual com baixo custo antes de implementar um SSS mais completo.

### Salvar e reabrir um personagem (versão 3)

Use **Salvar personagem…** e **Abrir personagem…** na coluna de controles. O projeto experimental `.makehumano.json` versão **3** salva os parâmetros anatômicos, a cor, rugosidade e dispersão da pele e agora também **guarda os pixels das três texturas** em PNGs locais.

Exemplo de arquivos salvos:

```text
personagem.makehumano.json
personagem.makehumano.json.assets/
  cor-<hash>.png
  normal-<hash>.png
  rugosidade-<hash>.png
```

Os nomes são gerados a partir do conteúdo, não de caminhos fornecidos pelo usuário. Apenas os mapas ativos recebem PNGs; a textura difusa é sempre salva. Ao abrir, os PNGs são decodificados, validados e comparados com o hash de cada arquivo **antes** de atualizar os materiais da GPU. Mapas ausentes no projeto voltam ao padrão neutro. Se a pasta de imagens estiver faltando ou algum PNG estiver corrompido, o projeto não será aplicado.

**Compatibilidade:** os JSONs de versão **1 e 2** continuam sendo aceitos e atualizados para versão 3 em memória; eles não contêm imagens salvas, portanto usam texturas neutras. A versão 1 também mantém a dispersão desativada (0%) para preservar a aparência antiga. Para mover ou fazer backup de um projeto versão 3, copie **o JSON e a pasta `.assets` juntos**. PNGs de versões anteriores não são apagados automaticamente; isso evita invalidar backups.

O formato ainda **não é o `.mhm`** do MakeHuman e não preserva roupas, poses, plugins ou câmera.

### Importar um personagem do MakeHuman original (`.mhm`)

O botão **Importar MHM original…** lê o formato textual do editor legado **somente para recuperar a forma corporal**. Ele reconhece os nomes de **249 controles** definidos em `data/modifiers/modeling_modifiers.json`: 238 modificadores diretos e 11 macrocontroles (incluindo os três parâmetros étnicos). Valores dos sliders diretos são convertidos de [-1, 1] para percentuais inteiros, avisando se houver arredondamento. As três proporções étnicas são normalizadas como no fim de `Human.load()`.

Antes de alterar o personagem, a janela apresenta um resumo da importação e **pede confirmação**. O leitor sinaliza propriedades não suportadas, como `clothes`, `material`, `camera`, `subdivide` e modificadores definidos por outros plugins. Isso significa que **um `.mhm` completo não é reconstituído com fidelidade**: roupas, cabelos, poses, subdivisão, materiais, câmera, UUID, tags e dados de plugins não são importados. A prévia usa o material padrão e as texturas neutras. Arquivos antigos podem requerer `compat.loadMHM`, que este leitor não executa; nesses casos, verifique o resultado na aplicação original.

O arquivo `.mhm` **não é modificado**. Depois de importar a parte anatômica, salve no formato experimental `.makehumano.json` para continuar a edição e guardar as texturas. **Ainda não há exportação de volta para `.mhm`**. Os testes de compatibilidade usam amostras textuais representativas de `Human.save()`; não equivalem a uma bateria de personagens históricos reais.

### Exportação OBJ com mapas de pele

O botão **Exportar OBJ com mapas de pele…** cria **cinco arquivos** com o mesmo nome-base, por exemplo:

- `personagem.obj`: malha corporal deformada, UVs, normais e referência ao MTL.
- `personagem_pele.mtl`: tonalidade da pele, rugosidade convertida aproximadamente para Phong e referência à textura difusa.
- `personagem_pele.png`: cópia da última textura RGBA da pele.
- `personagem_pele_normal.png`: cópia do normal map usado ou um mapa neutro.
- `personagem_pele_rugosidade.png`: cópia do mapa de rugosidade usado ou um mapa neutro.

**O MTL clássico só referencia a textura difusa e não armazena o efeito aproximado de dispersão.** Os dois últimos PNGs são arquivos auxiliares não conectados automaticamente. Para obter o efeito em Blender e outros editores, é necessário atribuir manualmente o normal map como **Non-Color**, usar um nó **Normal Map** e conectar o canal de rugosidade ao material apropriado. Os PNGs preservam os dados RGBA sem conversão de gama.

A exportação cobre apenas o corpo, sem roupas, rig, poses e animações. Os quads originais são triangulados. Os arquivos são substituídos individualmente, não numa transação atômica conjunta; a interface pede confirmação antes de sobrescrever. Para preservar sliders e texturas em formato editável, salve também o projeto `.makehumano.json` versão 3 e sua pasta `.assets`.

O arquivo de requisitos do novo motor é separado dos requisitos do editor antigo. **Não misture** as duas viewports na mesma janela por enquanto.

## Testes

- CPU, leitura OBJ, UV, morph targets, macros, formato de projetos e comparação com `algos3d.Target.apply` original: `python -m unittest discover -s testes -p 'test_*wgpu.py' -v`
- Interface com Vulkan por software, no Linux com Mesa/Lavapipe e Xvfb:
  `xvfb-run -a python -m motor_wgpu.app --backend vulkan --smoke`

O GitHub Actions executa esses testes em `.github/workflows/testar-wgpu.yml`.

## Arquitetura

- `malha.py`: formato OBJ → buffers CPU (posição, normal, UV, índices)
- `materiais.py`: parâmetros da pele e validação de pixels
- `morphs.py`: leitura dos arquivos `.target`, combinação atômica de pesos e recomputação de normais
- `modificadores.py`: catálogo de sliders a partir dos JSON oficiais do MakeHuman
- `projetos.py`: serialização JSON versionada, migração v1/v2 e persistência local de texturas PNG com verificação de integridade
- `mhm.py`: importação parcial de `.mhm` original e relatório de propriedades ignoradas
- `exportar.py`: gravação OBJ e vínculo opcional com MTL/PNG, preservando posições canônicas e UVs
- `materiais_obj.py`: geração de MTL e PNGs RGBA8 (difuso, normal e rugosidade), sem depender de Qt para exportar
- `macro.py`: interpolação de oito macrovariáveis e normalização dos três controles étnicos seguindo as fórmulas originais, combinando os 564 `.target`
- `shaders/pele.wgsl`: material difuso + GGX simplificado
- `gpu.py`: device, pipeline, texturas, uniforms, depth, vertex buffer mutável e draw
- `acessorios.py`: vínculos `.mhclo` diretos e ponderados com escala ou shear (olhos low/high-poly), leitura de `delete_verts`
- `roupas.py`: identificação e validação de arquivos `.mhclo` selecionados pelo usuário (importação experimental de peça externa)
- `materiais_mhmat.py`: parser seguro e parcial de `.mhmat` para textura difusa, RGB e rugosidade aproximada
- `transformacoes_proxy.py`: matriz de shear dos oito cantos, sem importar a GUI original
- `mascaras.py`: filtragem de triângulos, transferência de máscara conforme `transferVertexMaskToProxy()` e gerenciador de `delete_verts` por visibilidade
- `app.py`: widget Qt e controles de demonstração

## Próximos marcos (não implementados)

1. Ampliar a importação `.mhm` com ensaios sobre arquivos reais históricos e avançar da comparação CPU para poses, eventos e dependências da GUI original; ainda não há teste de equivalência visual entre as interfaces.
2. Evoluir da dispersão visual aproximada para SSS fisicamente mais fiel (espessura e difusão), depois avaliar exportação PBR como glTF.
3. Validar a importação manual de `.mhclo` com roupas históricas reais, ampliar propriedades `.mhmat` ainda não suportadas, sobreposição entre camadas e persistência no projeto. Máscaras por peça e material básico já funcionam.
4. Implementar câmera e picking equivalentes à viewport antiga.
5. Testar shaders com várias GPUs/drivers e qualidade visual.
6. Migrar o canvas oficial quando houver paridade de recursos.

A pasta `codigo/` preserva avisos e licenças do [MakeHuman Community](https://github.com/makehumancommunity/makehuman). O novo protótipo é parte do experimento MakeHumano; manter atribuições e termos AGPL pertinentes.
