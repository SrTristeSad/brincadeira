# Protocolo de paridade visual — MakeHuman OpenGL × MakeHumano Vulkan

**Estado (2026-11-06):** roteiro proposto com **um par Phong OpenGL × Vulkan produzido fora do repositório e reprovado**; medições e locais dos artefatos foram **informados pelo responsável**, sem acesso direto aos PNGs neste ambiente. As tolerâncias abaixo são critérios **provisórios**, ainda não aprovados. Este documento não homologa a migração.

## 1. O que precisa ficar congelado

- **Dois executáveis em ambientes separados:** primeiro par informado: MakeHuman OpenGL upstream em `a8bc2d54` (SHA completo ainda a registrar), MakeHumano Vulkan `e5c4431` (SHA completo `e5c443154d883cafd4aa28595791afe27fbdc74c`). O OpenGL só é usado como referência externa, **não** como fallback da aplicação final.
- **Mesmo estado da aplicação:** modelo .mhm, modificadores, geometria, pose, rig, acessórios, arquivos .mhmat, mapas, .mhscene e cores/luzes. Guardar SHA-256 e origem/licença de cada asset; não copiar conteúdos sem permissão.
- **Mesmas câmera e projeção:** guardar modo (perspectiva/ortográfica), posição, alvo, rotação, FOV, near/far, matrizes de câmera, orientação, tamanho e enquadramento do objeto. Capturar com os mesmos valores numéricos; registrar qualquer impossibilidade de reproduzi-los como bloqueio.
- **Mesma captura:** render offscreen na interface original, 1024×768, PNG RGBA 8-bit sem redimensionar, recortar, corrigir gama ou aplicar pós-processamento. Registrar fundo RGBA, espaço de cor, exposição e opções de multisampling; inicialmente 1× em ambos. Não misturar screenshot do desktop com framebuffer offscreen. Para máscara alfa, preservar a saída de mh.renderAlphaMask e representar o valor no canal A de um PNG RGBA, documentando a conversão, idêntica nos dois lados.
- **Controle de execução:** registrar OS, Python, Qt, wgpu/driver, resolução lógica/física, commit, checksum dos PNGs, data e parâmetros de execução. Capturar depois de terminar carregamento e renderização; duas capturas repetidas por sistema devem ser iguais ou ter a variação quantificada antes de comparar backends.

A rota Vulkan dispõe de mh.renderToBuffer/mh.renderAlphaMask e capturar_framebuffer. Confirmar no checkout **original específico** a API de exportação e seu tratamento de alfa antes da captura, sem presumir que ambos gerem PNGs idênticos automaticamente. A instrumentação de captura, se necessária, deve ser isolada e não alterar os shaders nem a interface original.

## 2. Matriz obrigatória de cenas

Cada par usa o mesmo material e os mesmos arquivos, no mesmo enquadramento e iluminação. Nomes de arquivo relativos aos diretórios <code>referencia-opengl/</code> e <code>candidato-vulkan/</code>:

| Caso / PNG | Material ou efeito | Situação em 2026-11-06 |
| --- | --- | --- |
| xray.png | Preset xray original / WGSL | Sem par |
| litsphere.png | Preset litsphere, textura idêntica | Sem par |
| phong.png | Preset phong, AO e material idênticos | 1 par local **REPROVADO**, diferenças de cor e textura ainda em investigação |
| toon.png | Preset toon, parâmetros idênticos | Sem par |
| normalmap.png | Preset normalmap, mapa/tangentes controlados | Sem par |
| skin.png | Preset skin, AO e gradiente idênticos | Sem par |
| mascara-alfa.png | Máscara produzida pela API original em ambos | Sem par |
| material-pele.png | Material/texture reais com licença rastreada | Sem par |
| material-roupa.png | Roupa real com alfa/camadas, a obter legalmente | **Bloqueado por asset ausente** |
| material-cabelo.png | Cabelo real com múltiplas camadas, a obter legalmente | **Bloqueado por asset ausente** |
| intersecoes-translucidas.png | Geometria real em interseção/ciclo | **Bloqueado por asset ausente** |

Para sombras, wireframe, textura de transparência e A2C/MSAA, acrescentar pares específicos após os casos básicos; não substituir os seis presets pela comparação Vulkan-fontes × Vulkan-portátil.

## 3. Captura, comparação e evidências

1. Criar dois checkouts fixos e isolados. Registrar SHA do MakeHuman OpenGL e SHA do Vulkan. Salvar o estado da cena, câmera, luz, material, recursos e checksums em um <code>manifesto.json</code> por execução; bloquear o teste se as entradas divergirem.
2. Em cada checkout, carregar exatamente os mesmos arquivos pela GUI **original**, restaurar números de câmera/luz, selecionar o preset correspondente e capturar o framebuffer **offscreen** em RGBA de 1024×768. Salvar em diretórios distintos, usando os nomes da matriz. Para a máscara, preservar o canal alfa da API; não gerar um PNG RGBA opaco a partir da visualização RGB.
3. Gerar o JSON de métricas e o diff PNG com o comparador que já existe (exemplo de um caso, a repetir para todos):

~~~bash
python makehumano/testes/comparar_opengl_vulkan.py referencia-opengl/phong.png candidato-vulkan/phong.png --tolerancia 8 --fracao-maxima 0.02 --json resultados/phong.json --diferenca resultados/phong-diff.png
~~~

4. Para cada PNG, registrar: erro médio RGB, erro máximo RGBA, fração de pixels divergentes, pixels alfa divergentes e IoU de cobertura alfa; guardar PNG original, PNG Vulkan, diff e JSON, com checksums. O comparador não corrige alinhamento ou resolução; divergências no enquadramento invalidam a captura.
5. Classificar cada caso como <code>SEM REFERÊNCIA</code>, <code>CAPTURA INVÁLIDA</code>, <code>REPROVADO</code> ou <code>APROVADO PROVISORIAMENTE</code>. Só a revisão manual e a aprovação dos critérios podem levar à homologação. Registrar falhas por shader, alfa, espaço de cor, textura, geometria, luz/sombra e driver.

## 4. Limites numéricos propostos (a aprovar, não calibrados)

Para os presets e materiais: **tolerância de 8 níveis por canal RGBA** e no máximo **2% de pixels fora da tolerância**, com **erro médio RGB ≤ 3**. Para contornos/alpha, exigir também **IoU de cobertura alfa ≥ 0,995** e **no máximo 0,5% de pixels com alfa acima da tolerância**, contados sobre a imagem inteira.

Para a máscara alfa isolada: **tolerância de 2 níveis por canal e até 0,5% de pixels divergentes**, mantendo IoU ≥ 0,995. Não aceitar diferenças estruturais grosseiras (silhueta, seleção, canais trocados), mesmo com médias dentro do limite. Esses valores são pontos de partida **mais rígidos para alfa**, não estatísticas observadas. Rever somente com evidência visual e aprovação explícita, registrando a justificativa.

O script atual decide seu exit code **somente** por <code>fracao_divergente</code>; a média RGB, IoU e a fração alfa precisam ser conferidas separadamente no JSON. Portanto **exit code 0 não significa aprovação integral** deste protocolo.

## 5. Modelo de registro por caso

~~~json
{
  "caso": "phong",
  "estado": "SEM REFERÊNCIA",
  "sha_opengl": null,
  "sha_vulkan": "586c98c6031dbdff4226d94604b1758b34e648c1",
  "resolucao": [1024, 768],
  "cena_camera_luz_assets_sha256": null,
  "png_opengl_sha256": null,
  "png_vulkan_sha256": null,
  "metricas": null,
  "diff_png": null,
  "ambiente": null,
  "revisor": null,
  "decisao": "PENDENTE"
}
~~~

**Resultado registrado nesta data:** um par `phong.png` informado, comparado fora deste ambiente e **reprovado**; sem PNGs ou manifestos incorporados ao repositório; nenhum caso homologado. As 61 capturas idênticas da CI são **Vulkan-fonte × Vulkan-portátil** e não substituem esta campanha.

**Validações externas em separado:** GPU física NVIDIA/AMD/Intel, exportações consumidas em aplicativos externos e campanha manual de plugins/entrada. Sem resultados atribuídos a elas.

## 6. Primeiro par Phong: observações e triagem (informadas em 2026-11-06)

**Origem das informações:** execução isolada comunicada pelo responsável. Os arquivos permanecem no ambiente externo em `/home/claude/srtristesad/` e **não estavam acessíveis para reexecução nesta revisão**. Não classificar as métricas abaixo como medidas novamente por este PR.

- **Referência OpenGL:** upstream `a8bc2d54`, Mesa **llvmpipe** (GPU por software), NumPy **1.26.4**; NumPy 2 quebrou `np.fromstring` no original.
- **Candidato Vulkan:** `e5c4431`, Mesa **Lavapipe** (GPU por software), `VK_ICD_FILENAMES=/opt/lavapipe/lvp_icd.json`, NumPy **2.5.4**.
- **Mesmo harness isolado em ambos:** `/home/claude/srtristesad/mh-ref/plugins/99_captura_referencia.py` e `/home/claude/srtristesad/mh-cand/plugins/99_captura_referencia.py`. O harness não é parte do repositório.
- **Entradas:** cena padrão, preset `phong`, saída **RGB** a **1024 × 768**, máscara alfa **não testada neste par**.
- **Câmera orbital:** `fov=90`, `center=(0, 0.11924934, 0)`, `radius=12.25118277`. `OrbitalCamera` deriva a matriz de visão de seus parâmetros orbitais e não utiliza os valores de `setEye` da classe base como controle efetivo. O harness deve fixar também orientação, zoom/translação e projeção e registrar as **matrizes de visão/projeção** resultantes. Ver `codigo/makehuman/lib/camera.py`, especialmente `OrbitalCamera.getMatrices` e `updateCamera`: este último pode recalcular centro e raio se `noAutoScale` não estiver ativo.
- **Arquivos externos:** `capturas/referencia-opengl/phong.png`, `capturas/candidato-vulkan/phong.png`, `resultados/phong.json`, `resultados/phong-diff.png` e manifestos JSON nos respectivos diretórios.
- **Métricas informadas:** tolerância por canal **8**, fração máxima **0,02**; fração divergente **0,9986**, erro médio RGB **59,5**, IoU cobertura alfa **1,0**, pixels alfa diferentes **0**; **REPROVADO**. Como o par é RGB, não usar as estatísticas de canal alfa implicitamente opaco como demonstração de equivalência de máscara/transparência.
- **Observações visuais:** fundo OpenGL RGB ~128; fundo Vulkan RGB ~188; pele azul lisa no original versus bege/texturizada no candidato. A causa do segundo achado permanece desconhecida e exige comparação dos estados do material no mesmo instante de captura.

### Hipótese da conversão sRGB — sem alteração de produção

`codigo/makehuman/lib/vulkan_scene.py` configura `self.formato = self.contexto.get_preferred_format(self.adapter)`. Em `framebuffer_offscreen`, o formato padrão é `self.formato`; `capturar_framebuffer` usa esse padrão. Se o contexto retornar `bgra8unorm-srgb` ou `rgba8unorm-srgb`, a escrita do alvo converte linear para sRGB. A função de leitura `ler_framebuffer_rgba` converte a ordem BGRA/RGBA, mas não decodifica sRGB.

A codificação sRGB de linear 0,5 é aproximadamente 0,735356983, ou **188/255** após quantização, versus **128/255** em `rgba8unorm`. Isso é consistente com o fundo observado, mas **não confirma sozinho** que todo o erro de Phong resulte do formato offscreen ou que a saída OpenGL e a matemática do shader tenham mesmo espaço de cor.

**Experimento isolado:** executar `makehumano/testes/diagnosticar_srgb_offscreen.py` em Xvfb/Lavapipe com o mesmo Qt/rendercanvas/wgpu, criando alvos independentes `rgba8unorm`, `rgba8unorm-srgb` e no formato preferido do contexto. Limpar com o valor linear `(0.5,0.5,0.5,1.0)`, ler os bytes e registrar um JSON. O script **não carrega a cena, não altera pipelines nem troca o formato do renderizador**.

~~~bash
git clone --branch makehumano/protocolo-paridade-visual-20261106 \
  https://github.com/SrTristeSad/brincadeira.git /tmp/brincadeira-srgb
cd /tmp/brincadeira-srgb
python -m pip install -r makehumano/codigo/requirements.txt
VK_ICD_FILENAMES=/opt/lavapipe/lvp_icd.json WGPU_BACKEND_TYPE=Vulkan \
xvfb-run -a -s "-screen 0 1280x800x24" \
python makehumano/testes/diagnosticar_srgb_offscreen.py \
  --json /home/claude/srtristesad/resultados/diagnostico-srgb.json
~~~

O script é executado a partir da raiz de um clone isolado; instalar as dependências antes de rodá-lo. O loader/ICD usado aqui é exclusivo da validação com Vulkan por software. **Critério de conclusão do experimento:** observar 128±1 no alvo UNORM e 188±1 no sRGB, identificar o formato preferido do contexto com Qt e confrontar o resultado com o fundo de `phong.png`. Repetir a leitura efetiva de `cena.formato` no harness, se possível; isso diferencia inferência por contexto de medida dentro da cena real.

**Decisão necessária antes de corrigir a produção:** revisar evidência do experimento, escolher se o contrato de captura deve usar linear UNORM ou normalização explícita (preservando o comportamento do original), avaliar as consequências sobre os outros passes e testes de shader que atualmente dependem do formato sRGB. Não alterar `vulkan_scene.py` antes dessa decisão.

### Investigação separada da cor da pele no Phong

A seguir, coletar dos **dois** processos antes da captura os campos `material.shader`, `shaderConfig`, `diffuseColor`, `diffuseTexture`, `shaderParameters`, `ambientColor`, `specularColor`, UVs, identidade/checksum da textura e estado das luzes. Confirmar se o material realmente é o mesmo; comparar pixels do objeto fora da região de fundo **após** controlar o espaço de cor. Não assumir que o shader original ignora textura sem inspecionar o GLSL e demonstrar o efeito.

**Critério de paridade:** gerar novamente o par `phong.png` após cada mudança autorizada, registrar todas as métricas do protocolo e revisar visualmente o diff. `exit code 0` do comparador verifica apenas a fração divergente; **não é aceite integral**.

## 7. Rastreio estático da captura e medição real pendente

**Rastreio confirmado nos arquivos da branch (sem executar o harness):**

1. `codigo/makehuman/lib/mh.py`: `mh.renderToBuffer(1024, 768)` chama `_canvas_vulkan().renderToBuffer(width, height, productionRender)`.
2. `codigo/makehuman/lib/vulkan_canvas.py`: `CanvasVulkan.renderToBuffer()` obtém `cena = self._garantir_cena()`, chama `cena.capturar_framebuffer(G.world, G.cameras, 1024, 768, productionRender=..., cor_fundo=(0.5, 0.5, 0.5, 1.0))` e envolve os pixels num `Image`.
3. `codigo/makehuman/lib/vulkan_scene.py`: `CenaVulkan.capturar_framebuffer()` invoca `self.framebuffer_offscreen(1024, 768)`, chama `desenhar(..., alvo=alvo)` e depois `ler_framebuffer_rgb(alvo)`.
4. `CenaVulkan.framebuffer_offscreen()` usa `formato = self.formato` quando não existe parâmetro explícito, cria a textura com esse formato e a retorna. `self.formato` vem de `self.contexto.get_preferred_format(self.adapter)` na construção da cena.

**Conclusão estritamente estática:** `framebuffer_offscreen()` cria a textura de cor final (ou alvo de resolve com MSAA) do caminho `mh.renderToBuffer`. O observador existente intercepta esse método, não um caminho alternativo. Ele **não** mede separadamente os attachments de profundidade ou a textura multisample auxiliar; não confundir esses buffers com a textura de saída RGB. Só a execução real confirmará o formato efetivo da captura Phong.

### Uso no harness **isolado** do candidato

O harness real está em `/home/claude/srtristesad/mh-cand/plugins/99_captura_referencia.py` e não foi disponibilizado a este ambiente. Não inserimos instrumentação no código de produção, em `mh.py` ou em `vulkan_scene.py`.

Antes de editar, verificar que a função que gera `phong.png` já concluiu a configuração da cena, da câmera e do material. Naquele ponto, **substituir exatamente a chamada `mh.renderToBuffer(1024, 768)` existente** pela mesma chamada dentro do bloco abaixo, preservando o nome da variável de resultado e o salvamento PNG que já existe no harness:

~~~python
import sys
from core import G

sys.path.insert(0, '/tmp/brincadeira-observador/makehumano/testes')
from observar_formato_cena_vulkan import observar_captura_offscreen

# É o método real chamado por CanvasVulkan.renderToBuffer,
# não presumimos que a primeira renderização já criou G.canvas._cena.
cena = G.canvas._garantir_cena()
with observar_captura_offscreen(
    cena,
    '/home/claude/srtristesad/resultados/formato-real-phong.json',
):
    imagem = mh.renderToBuffer(1024, 768)

# Prosseguir com o mesmo código do harness que salva imagem como phong.png.
~~~

`imagem` é apenas o nome demonstrativo: conservar o identificador original do harness. **Não duplicar a captura**, mudar parâmetros, alterar os shaders ou repetir o método de configuração da cena. `G.canvas._garantir_cena()` é o mesmo método invocado internamente por `CanvasVulkan.renderToBuffer()`; retorna a mesma instância (ou cria a primeira antes da captura). Usar o observador apenas no checkout isolado do **candidato Vulkan**, não no MakeHuman OpenGL de referência.

### Validação e interpretação

~~~bash
# Com o clone do PR #11 disponível em /tmp/brincadeira-observador:
cd /tmp/brincadeira-observador
python -m unittest discover -s makehumano/testes -p 'test_observar_formato_cena_wgpu.py' -v

# No ambiente do harness, após refazer a captura:
cat /home/claude/srtristesad/resultados/formato-real-phong.json
~~~

**Critério de observação:** `captura_concluida_sem_excecao=true`, `captura_1024x768_observada=true` e `estado="OBSERVADO"`, com pelo menos uma entrada em `texturas_offscreen_observadas` cujos `largura` e `altura` sejam `1024` e `768`. Validar `formato_preferido_superficie`, `formato_cena_no_instante` e `formato_real_da_textura`, além de preservar o PNG e seu checksum no manifesto. Se não houver textura 1024×768, o relatório fica `estado="NAO_OBSERVADO"`, ainda que outra dimensão tenha sido interceptada e o bloco termine normalmente.

**Depois da leitura:** se o alvo real estiver em `*-srgb`, o fato de a cor linear 0,5 produzir cerca de 188 corrobora a hipótese de conversão do fundo. Caso esteja em `*unorm`, a causa exata do fundo 188 permanece em aberto. Em ambos os casos, isso não explica sozinho as diferenças de pele/textura nem comprova paridade OpenGL × Vulkan.

**Limitações:** testes unitários com objetos simulados não substituem execução da GUI original; a execução não foi feita aqui porque o harness externo não está montado. Nenhuma mudança de renderização de produção está autorizada. Plataformas-alvo: **Windows e Linux**; macOS fora do escopo por decisão do criador.

## 8. Captura real da GUI na CI (harness efêmero e independente do par Phong)

O script `testes/executar_harness_formato_gui.py` copia **temporariamente** `testes/harness_plugin_formato_gui.py` para a árvore de plugins da cópia de trabalho do runner Linux. Ele inicia o **MakeHuman original modernizado** numa pasta HOME isolada, espera o fim da inicialização e chama `mh.renderToBuffer(1024, 768)` dentro do mesmo observador de formato da seção 7. Registra JSON, PNG e log, e remove o plugin transitório em `finally`.

Essa injeção só ocorre durante o teste e não faz parte do código distribuído. Não adiciona interface, controles, backend ou funcionalidade ao produto. O teste não altera formatos da GPU nem shaders. O artefato GitHub Actions chama-se `formato-real-gui-ci`.

O runner observa o formato efetivo da textura de cor, `CenaVulkan.formato`, o formato preferido do contexto, a forma [largura, altura] dos pixels RGB e seu hash SHA-256. Registra também o pixel superior esquerdo, não presumindo que seja sempre fundo. Reprova se a cena não produzir uma textura de **1024×768**, se o registro estiver incompleto ou se a execução falhar.

**Limite metodológico:** esta é uma **nova captura Vulkan do estado padrão da GUI na CI**, não reproduz necessariamente o material/câmera do harness externo e **não** produz imagem de referência OpenGL. Portanto ela poderá comprovar a escolha de formato numa execução real da CenaVulkan sob Linux/Lavapipe, mas não comprova paridade Phong nem o formato exato da execução externa anterior. Esse par continua exigindo o procedimento da seção 7 e os arquivos externos reais.

**Windows e Linux** são as plataformas-alvo do projeto; o harness novo exercita somente o runner Linux e não homologa GPUs físicas. A política de alteração do framebuffer de produção continua dependente de decisão explícita do criador.

## 9. Evidência obtida na GUI real da CI — formato sRGB

**Executado e verificado:** GitHub Actions [run 42325773604](https://github.com/SrTristeSad/brincadeira/actions/runs/42325773604), commit `54ccb9e8adcd4cb08ecd21dfa648e427277c2e2f`, no job `vulkan-gui-original`. Artefato `formato-real-gui-ci` (`formato-cena-gui.json`, PNG e log). O plugin do harness foi colocado temporariamente na instalação de CI e removido ao encerrar; nenhum arquivo de produção versionado foi modificado.

| Campo observado | Resultado |
| --- | --- |
| `formato_preferido_superficie` | `rgba8unorm-srgb` |
| `formato_cena_inicial` e final | `rgba8unorm-srgb` |
| `formato_real_da_textura` | `rgba8unorm-srgb` |
| Dimensões e conclusão | 1024 × 768, `estado=OBSERVADO`, sem exceção |
| Pixel superior esquerdo | RGB `(188, 188, 188)` |
| Shader do material capturado | LitSphere (não Phong) |
| SHA-256 pixels RGB | `7580e785c691e3c27e031474e6d054e42d9bc18313637bfdd6fcfa932fecb949` |
| SHA-256 PNG | `501e253559034b83756b57bc974ed9efc56eca764b2795818fce7f6948c63fb8` |

**Interpretação:** a GUI real no runner Linux com driver Vulkan por software herdou `rgba8unorm-srgb` e renderizou o fundo 0,5 como byte 188. Isso comprova o mecanismo nessa execução da CenaVulkan, mas **não** prova o formato do processo Phong externo anterior nem paridade OpenGL × Vulkan. Nenhuma alteração de produção é autorizada por esta medição, isoladamente.

### Estado do material: diagnóstico que falta antes de corrigir Phong

O shader GLSL **do próprio upstream `a8bc2d54ff0ac92e78ff71431b1023eda42bf482`** contém `#ifdef DIFFUSE` e só amostra `diffuseTexture` quando o define está ativo. Sem ele, a variável do shader usa branco. Portanto a hipótese de que o Phong original sempre ignora textura é incorreta; o estado efetivo `shaderDefines`, `shaderConfig`, mapas e material precisa ser medido.

Foi adicionado `testes/registrar_estado_material.py` (stdlib, sem imports de OpenGL/Vulkan), com regressões em `testes/test_registrar_estado_material_wgpu.py`. O módulo registra `shader`, `shaderDefines` (incluindo DIFFUSE efetivo), `shaderConfig`, parâmetros, cores, mapas e seus SHA-256 quando arquivos, além das entradas de iluminação. Ele **não** altera a aplicação e pode ser copiado para os dois ambientes de captura isolados.

Para preservar correspondência com o mesmo `phong.png`, inserir **imediatamente antes da chamada de render já existente** em cada uma das duas cópias externas do harness:

~~~python
import sys
from pathlib import Path
from registrar_estado_material import salvar_estado  # disponibilizar o módulo via sys.path da cópia isolada
from core import G

lado = 'opengl'  # na cópia Vulkan usar 'vulkan'
material = G.app.selectedHuman.material
salvar_estado(
    Path('/home/claude/srtristesad/resultados') / ('estado-material-' + lado + '.json'),
    material, G.app.scene, referencia=lado,
)
# A seguir, manter mh.renderToBuffer(1024, 768) e o mesmo salvamento PNG.
~~~

**Preparação:** copiar `registrar_estado_material.py` para um diretório de diagnóstico importável pelas duas cópias isoladas do harness; não instalá-lo como plugin nem alterar código de produção. O snippet pressupõe que essa importação já está disponível (configurar `sys.path` para o diretório externo, se necessário).

**Critério:** arquivos `estado-material-opengl.json` e `estado-material-vulkan.json` do mesmo par, com checksums de textura, shader, defines, material e iluminação. Comparar nomes lógicos e hashes, não presumir igualdade de caminhos absolutos entre diferentes instalações. Só depois de uma diferença controlada no material, medir novos PNGs e todas as métricas do protocolo. Ainda **não** há snapshots dos dois processos nesta revisão.

**Limite:** a campanha e o código do produto continuam restritos a Windows e Linux, sem alterações visuais ou de backend nesta fase.

## 10. Experimento controlado de textura Phong na GUI Vulkan (ainda não executado no momento da escrita)

**Objetivo:** distinguir uma configuração DIFFUSE habilitada/desabilitada do estado de textura efetivamente usado no renderizador, sem modificar shaders ou framebuffers de produção. O plugin diagnóstico `testes/harness_plugin_material_phong_gui.py` é copiado apenas para um processo transitório pelo runner de CI. A própria instalação de CI remove o plugin ao terminar.

A sequência ocorre dentro de um único processo MakeHumano e com a mesma câmera e cena: atribuir o preset existente `shaders/glsl/phong`, habilitar `material.configureShading(diffuse=True)`, registrar o estado do material e capturar `mh.renderToBuffer(1024,768)`; desabilitar `diffuse=False`, registrar novamente e fazer a segunda captura. A câmera é comparada pelas matrizes de view/projeção antes e depois. O ambiente de teste é destruído, e o estado do material é restaurado em `finally`.

O relatório registra `formato_cena_inicial`, duas texturas 1024×768, `shaderConfig`, `shaderDefines`, `diffuseTexture` e hashes, `isTextured` real do objeto, iluminação, RGB do canto da imagem, hashes RGB/PNG, fração de pixels diferentes acima de 8 níveis, erro médio RGB, erro máximo RGB e estabilidade de câmera. Os PNGs e o JSON são anexados ao artefato `phong-diffuse-on-off-ci` no workflow Vulkan.

**Aceitação restrita:** a CI só confirma se o runner/câmera funcionaram e se o controle `isTextured` acompanhou `diffuse=True/False`. Se não houver asset difuso, a imagem não mudar não prova erro; os campos de textura devem ser inspecionados. Uma diferença de pixels neste experimento **não equivale** a paridade com OpenGL, nem demonstra a causa exata do contraste pele azul/bege no par externo. Não usar o exit code, sozinho, como aprovação de qualquer tolerância do protocolo.

**Fonte de referência:** `Object3D.isTextured` devolve `self.object.shaderConfig['diffuse']` no código do candidato. O WGSL usa esse valor em `dados.flags.y`; o GLSL original só lê `diffuseTexture` com `#ifdef DIFFUSE`. Assim, a hipótese de que Vulkan sempre ignora `shaderConfig.diffuse` não é sustentada por leitura estática — exige observação dos dados reais e do par externo.

Este trabalho continua exclusivo de diagnóstico. Não altera Python de produção, materiais de usuários, interface, drivers, fallback ou escopo (apenas Windows/Linux).

### Resultado do controle real sem textura difusa (CI `e122df2`)

Executado na [CI 42326489708](https://github.com/SrTristeSad/brincadeira/actions/runs/42326489708), com artefato `phong-diffuse-on-off-ci`. A GUI Vulkan usou o material `DefaultSkin`, shader `phong`, textura difusa **ausente (`null`)**, `shaderDefines=[]` em ambos os estados, apesar de `shaderConfig.diffuse` mudar de `true` para `false`. O controle `Object3D.isTextured` acompanhou as duas opções; a câmera permaneceu igual.

As duas imagens Phong 1024×768 foram **pixel a pixel idênticas**: fração divergente na tolerância 8 = **0**, erro médio RGB **0**, erro máximo RGB **0**, hashes de PNG iguais. A textura de cor tinha formato `rgba8unorm-srgb` e o fundo RGB 188. Este resultado **não** prova que há regressão; é compatível com um material sem textura difusa e com ausência da macro `DIFFUSE` no shader original.

### Controle positivo executado (textura sintética exclusivamente em memória)

O harness foi estendido para criar uma imagem RGBA xadrez 16×16 no próprio processo CI, atribuí-la temporariamente a `material.diffuseTexture`, registrar `shaderDefines` e capturar duas imagens Phong adicionais (com difusa ligada/desligada), sem modificar arquivo de material nem adicionar asset ao produto. Registra métricas próprias de diferença dos dois estados, hashes e tipo de `corpo.texture`. O controle foi executado em CI; os resultados medidos estão registrados abaixo.

Se as imagens sintéticas diferirem, teremos evidência de que a rota Vulkan responde ao vínculo da textura e ao flag DIFFUSE na mesma cena. Se não diferirem, precisamos olhar a fonte `corpo.texture` e a amostragem do WGSL antes de concluir regressão. Em nenhum caso o experimento equivale à comparação com a referência OpenGL `a8bc2d54`.

### Resultado do controle positivo xadrez no Phong Vulkan

Execução: [GitHub Actions 42326878096](https://github.com/SrTristeSad/brincadeira/actions/runs/42326878096), commit `ccfbd0e0a16c3a4dee5577fc7a9b8bee9ee4130c`, artefato `phong-diffuse-on-off-ci` com quatro PNGs, JSON e log. Mesma câmera, shader Phong e alvo 1024×768 no processo temporário Linux/Lavapipe.

| Controle | Define `DIFFUSE` | Pixels RGB diferentes acima de 8 níveis | Erro médio RGB | Erro máximo RGB |
| --- | --- | ---: | ---: | ---: |
| DefaultSkin sem textura, `diffuse=True` vs `False` | ausente/ausente | 0 / 786.432 | 0 | 0 |
| Textura sintética RGBA 16×16, `diffuse=True` vs `False` | presente/ausente | **45.400 / 786.432** (**5,7729%**) | **2,4142** | **141** |

Com a imagem sintética, `corpo.texture` expôs um objeto `Image`. O shader/pipeline Vulkan respondeu à mudança de textura difusa e ao estado `isTextured` nesse caso. As estatísticas de comparação interna são **medidas de sensibilidade**, não limiares de paridade OpenGL × Vulkan. Não classificar 5,77% como reprovação contra o original: as duas imagens têm entradas diferentes por desenho do teste.

Foi acrescentada validação de regressão no harness: exigir define DIFFUSE ativo/inativo nos respectivos controles, ao menos um pixel Phong alterado pela textura sintética, matrizes idênticas e quatro texturas 1024×768 observadas. Resultado de CI da revisão com a nova asserção deve ser consultado separadamente.

**Conclusão limitada:** a diferença de pele azul lisa (referência OpenGL) versus bege/texturizada (par externo) ainda não está explicada. Nesta CI a pele `DefaultSkin` não tinha `diffuseTexture`. A comparação pareada dos dois estados de material e do original segue necessária. Não houve autorização ou modificação do renderizador de produção.

## 11. Referência OpenGL upstream em ambiente CI isolado — execução pendente

Para não depender somente dos arquivos no ambiente externo `/home/claude/srtristesad/`, foi preparado um segundo harness de referência em `testes/harness_plugin_opengl_referencia.py`, que só é **copiado para um clone temporário** do MakeHuman upstream, fixado no commit completo `a8bc2d54ff0ac92e78ff71431b1023eda42bf482`. O MakeHumano modernizado não incorpora esse plugin nem passa a aceitar OpenGL.

O runner `testes/executar_harness_opengl_referencia.py` inicia um processo independente no Xvfb com Mesa llvmpipe e um ambiente Python virtual exclusivo com **NumPy 1.26.4 + PyQt5 + PyOpenGL**. A captura usa a GUI original e `mh.renderToBuffer(1024,768)` e registra PNG/JSON/log; remove o plugin transitório no encerramento.

Ambos os harnesses de diagnóstico, OpenGL e Vulkan, agora usam os mesmos números de câmera de `testes/configurar_camera_paridade.py`: FOV 90, centro `(0, 0.11924934387207031, 0)`, raio `12.251182769327169`, inclinações/rotações nulas, zoom 1 e sem reescala automática; **projeção original preservada e registrada**, com matrizes, near/far e dimensões de viewport. Se o checkout/estado de câmera divergir, a comparação deve ser considerada inválida.

**Primeiro objetivo restrito:** verificar que o upstream inicia e produz um PNG Phong com seu material e iluminação registrados, no Windows/Linux visados (runner desta fase: Linux). Não declarar equivalência até conferir que câmera, modelo, shaders, assets, iluminação e métodos de captura estão alinhados e então executar o comparador com todas as métricas. A CI de referência é teste externo; não é fallback no produto final.

**Status inicial:** scripts preparados na branch, execução do original na CI e inspeção dos resultados ainda pendentes. Nenhuma alteração de produção autorizada ou executada.

## 12. Matriz diagnóstica de canais Phong (aguardando execução do original)

Foi acrescentado `testes/diagnosticar_pareamento_phong.py`, que, SOMENTE se ambas as capturas existirem, executa quatro comparações de imagens reais sem alterar os PNGs de origem: OpenGL bruto versus Vulkan bruto; OpenGL com R/B trocados; Vulkan com sRGB decodificado para linear; e as duas transformações combinadas. Gera quatro conjuntos separados de métricas e dois mapas de diferença, e registra as divergências de matrizes de câmera, shader, defines, textura difusa e iluminação. Os testes CPU de transformações de canal ficam em `test_diagnosticar_pareamento_phong_wgpu.py`.

**Justificativa de canal:** o upstream `glmodule.renderToBuffer` lê `GL_RGBA` e depois aplica `surface[::-1, :, [2,1,0]]`. Em `image_qt.save`, a primeira componente é interpretada como R no RGB empacotado; assim não há cancelamento da troca no salvamento via `Image.save`. Esse tratamento pode explicar parte da pele azul no PNG de referência, mas o resultado precisa ser medido nas capturas reais.

**Justificativa de gama:** a textura Vulkan offscreen foi medida como `rgba8unorm-srgb`, com cor linear 0,5 gravada como byte 188. Decodificar sRGB no PNG Vulkan é aqui só experimento analítico, NÃO proposta automaticamente aprovada para o contrato do produto.

**Condição de validade:** o JSON distingue `PAR_COMPARAVEL_PARA_DIAGNOSTICO` de `ENTRADAS_NAO_COMPROVADAS_EQUIVALENTES`, com base em números da câmera, shader, defines, difusa e iluminação. Os outros assets e parâmetros, além da qualidade da projeção offscreen, ainda precisam de conferência; qualquer `limites_propostos_todos_satisfeitos` é meramente estatístico e não homologação. Como PNGs são RGB, a IoU alfa 1,0 é trivial e não confirma máscara/transparentes. A decisão sobre como interpretar a troca histórica R/B deve ser discutida com o criador antes de propor correção da produção.

**Status:** ferramenta preparada; resultados da CI dependerão de a referência OpenGL upstream executar com sucesso no checkout isolado.

## 13. Primeiro PNG de referência OpenGL recuperado; manifesto falhou no coletor

Execução [GitHub Actions 42327430376](https://github.com/SrTristeSad/brincadeira/actions/runs/42327430376), upstream em commit exato `a8bc2d54ff0ac92e78ff71431b1023eda42bf482`, NumPy 1.26.4, OpenGL llvmpipe. **A GUI abriu, renderizou Phong e salvou `phong-referencia-opengl-ci.png` de 1024×768.** O job foi marcado falho **depois do PNG**, ao montar o manifesto de iluminação: o `SceneObject.__getattr__` legado usa `hasattr(self, attr)` para um atributo inexistente, entrando em `RecursionError`. A captura existe, mas o manifesto dessa execução é `ERRO` e não permite homologação.

O helper de diagnóstico `registrar_estado_material.py` foi corrigido para consultar `_attributes` dos objetos de cena legados sem chamar `__getattr__` em campos ausentes; incluiu-se o campo real `color` das luzes, além de `diffuse` opcional. Há teste de regressão que simula o comportamento recursivo do upstream. Não se alterou `scene.py` nem qualquer arquivo de produção.

### Exploração das imagens recuperadas antes de validar os manifestos

Os artefatos dos mesmos jobs permitem examinar o PNG OpenGL e o PNG Vulkan com câmera fixada e shader Phong, mesmo antes do manifesto corrigido. Esta comparação exploratória foi reproduzida fora da CI, usando PNGs exatos baixados do run acima e Pillow+NumPy; **ainda não serve como homologação**, pois o primeiro manifesto OpenGL falhou:

| Tratamento analítico (sem alterar PNG original) | Fração de pixels fora da tolerância 8 | Erro médio RGB |
| --- | ---: | ---: |
| Ambos brutos | **99,8633%** | **59,5175** |
| Apenas inverter R/B da referência OpenGL | 99,8533% | 59,5025 |
| Apenas decodificar sRGB do PNG Vulkan | **5,3987%** | **1,7432** |
| Inverter R/B OpenGL + decodificar sRGB Vulkan | **4,1879%** | **0,7998** |

O conteúdo de silhueta após os dois tratamentos teve interseção sobre união aproximada **0,9992** ao comparar máscaras RGB contra o fundo 128 com limiar 8. Essas máscaras de silhueta diagnósticas **não são a máscara alfa do produto** e o IoU não deve ser interpretado como validação alfa. **Mesmo as métricas combinadas não atingem o limite provisório de 2% de pixels divergentes.** Portanto há divergências restantes na iluminação/cor do personagem ou bordas, que requerem investigação após validar as entradas.

Este achado separa dois efeitos: o sRGB explica quase toda a diferença global de fundo e a troca de canais do GL explica parte da aparência azul. Nada disso autoriza automaticamente correção do framebuffer de produção ou mudança de contrato de cores; os resultados são diagnósticos, com artefatos de origem preservados.

## 14. Paridade de entrada validada; experimento especular sem alterar produção

**Manifestos completos obtidos:** [GitHub Actions 42328007217](https://github.com/SrTristeSad/brincadeira/actions/runs/42328007217), upstream original `a8bc2d54ff0ac92e78ff71431b1023eda42bf482` e candidato Vulkan `e5c443154d883cafd4aa28595791afe27fbdc74c`, ambos em software Mesa (llvmpipe e Lavapipe) e NumPy 1.26.4 / 2.5.4. Todos os jobs do workflow Vulkan passaram; artefatos `phong-referencia-opengl-ci`, `phong-diffuse-on-off-ci` e `phong-pareamento-ci`. A classe do comparador marcou `PAR_COMPARAVEL_PARA_DIAGNOSTICO`, com câmera (FOV, projeção, raio, centro, near/far, zoom e matrizes), shader Phong, ausência de DIFFUSE e de textura difusa, e iluminação registrada coincidentes.

A comparação bruta ficou em 99,8633067% de pixels fora de tolerância 8 e erro médio RGB 59,51750; os dois tratamentos diagnósticos (inversão R/B da captura OpenGL e decodificação sRGB da captura Vulkan) ficaram em 4,1879018% e RGB médio 0,799804. **Aprovação visual: NÃO**; limite provisório de fração 2% não atingido e alpha real não testado.

Análise de região **heurística** sobre os PNGs validados, após as duas normalizações: 45.198 pixels na união dos candidatos a silhueta por contraste com o fundo 128 (limiar de 8), erro médio RGB nessa região **13,9164**, e aproximadamente **72,87%** dos pixels regionais com ao menos um canal acima de 8. O contraste regional revela divergência de iluminação/material que a média global 0,80 oculta. Esta região não é uma máscara alfa nem prova identidade topológica.

Para investigar o brilho sem modificar o produto, ambos os harnesses efêmeros foram estendidos com um **segundo par Phong sem especular**: o material original é capturado como antes, e em seguida `material.specularColor=(0,0,0)` só temporariamente no processo de teste, com restauro em `finally`; câmera, geometria e shader são preservados. Os manifestos registram estado `specularColor`, PNGs/hashes; o comparador mede variantes com e sem as duas normalizações. O objetivo é determinar se remover a parcela especular reduz os **4,19% restantes**; nenhuma correção de shader ou framebuffer está autorizada. As medidas desse controle dependem da nova execução de CI e não podem ser presumidas.

**Risco de interpretação:** uma melhora após desligar reflexos não identifica por si só se a causa é half-vector, normal, intensidade ou espaço de cor. Uma piora tampouco prova o shader correto. Somente o par integral e as métricas do protocolo poderão sustentar conclusão.

## 15. Resultado sem especular e novo controle sem recepção de sombras

**Controle sem especular medido na CI:** [run 42328539078](https://github.com/SrTristeSad/brincadeira/actions/runs/42328539078), commit `6def4ed14f7fd381fd92d24f044c465b540df3f4`. Capturas OpenGL × Vulkan em Phong com `material.specularColor=(0,0,0)` nos dois harnesses temporários. Após inverter R/B da referência e decodificar sRGB apenas para análise, a fração fora de 8 foi **4,1475932%**, RGB médio **0,766646**; Phong normal no mesmo run foi **4,1879018%** e **0,799804**. Ambos falham o limite provisório de 2%, e alfa real não foi medido. O especular tem efeito, mas sua remoção quase não elimina a divergência.

**Nova hipótese restrita:** GLSL `phong_fragment_shader.txt` original não avalia sombra por pixel; Vulkan inclui `shadow_visibility()` no `fator_luz` do preset Phong, a depender de `material.receiveShadows`. Não assumir que isto explica o desvio sem medir. Para o controle seguinte, cada harness descartável captura outro PNG com a propriedade preexistente `receiveShadows=False` no mesmo material/câmera e restaura o estado em `finally`; a ferramenta de comparação registra versões bruta e normalizada. Não há mudança em produção ou na interface.

**Critério do controle:** os manifestos devem confirmar `receiveShadows=False`, shader Phong e dimensões idênticas, e as métricas serem comparadas ao par normal da mesma execução. O experimento **não altera o contrato final de sombras** e não homologa equivalência. Esta etapa está apenas implementada, aguardando CI na revisão subsequente.

### Resultado medido do controle de sombras

**Execução:** [GitHub Actions 42328823083](https://github.com/SrTristeSad/brincadeira/actions/runs/42328823083), commit `cfe535f8472d575f37be95569fb70809b4f3c92b`, jobs Vulkan concluídos com sucesso, artifacts `phong-referencia-opengl-ci`, `phong-diffuse-on-off-ci`, `phong-pareamento-ci`. A comparação usou OpenGL e Vulkan pareados com os parâmetros originais de câmera e material, modificando apenas `receiveShadows=False` nos dois harnesses efêmeros e restaurando o estado em seguida.

| Cenário (após correções de R/B na referência e decodificação sRGB Vulkan, **somente para diagnóstico**) | Pixels >8 | Fração | Erro médio RGB global | Erro médio RGB na região heurística do corpo | Máximo RGBA |
| --- | ---: | ---: | ---: | ---: | ---: |
| Phong original | 32.935 / 786.432 | **4,1879%** | **0,799804** | **13,9164** | 203 |
| Phong com especular zerado | 32.618 / 786.432 | **4,1476%** | **0,766646** | Não calculado | 149 |
| Phong com `receiveShadows=False` | 32.786 / 786.432 | **4,1690%** | **0,763142** | **13,2785** | 128 |

A referência OpenGL Phong com `receiveShadows=False` gerou bytes PNG idênticos aos do controle original (mesmo SHA-256 `7e5c444966a3ad3bc3c11a1710150a62b0a423a9782e092d79d8ad9248ac4c87`); no candidato Vulkan os PNGs **não** são idênticos (SHA-256 normal `df03b154b8a747f8edb9383cbe7d98e49e3435c6216ede981ef666d33563b63c`, sem sombras `9485b516060b89977d9a9cee7e60d9836c5e999b3f0c0e431bda42a036f422f9`). Esse controle demonstra uma diferença de comportamento de recepção de sombras na rota Phong, mas explica apenas parte pequena da divergência RGB do par.

A região heurística de corpo foi formada por união dos pixels que diferiam do fundo cinza 128 em mais de 8 níveis em ao menos um canal, após normalizações de canal/gama. Nos dois pares foram 45.198 pixels; esse procedimento **não é uma medição de alpha mask**. Foram rechecados os dados dos artefatos completos com Pillow+NumPy, não apenas códigos de saída.

**Decisão técnica desta fase:** nem o especular nem a sombra são a principal causa dos **~4,17% restantes**. A investigação deve prosseguir pelas transformações de normais, direções de luz, contribuição difusa, interpolação e equações GLSL/WGSL. **Não alterar** `vulkan_scene.py`, shaders ou framebuffer de produção enquanto não houver autorização expressa do criador. Não tentar aprovar o shader apenas porque `erro_medio_rgb` global fica abaixo de 3.

## 16. Diagnóstico CPU da geometria e controle de iluminação puramente difusa (execução pendente)

Dois controles adicionais em harnesses efêmeros, sem alterações em shaders/framebuffers de produção:

**(1) Identidade dos buffers:** novo `testes/registrar_geometria_paridade.py` toma o corpo selecionado de `G.world` no original e no candidato e calcula SHA-256 dos arrays de posições e normais (`float32 little-endian`) e índices de quadriláteros (`uint32 little-endian`), número de vértices/faces, BBox e comprimentos das normais. O comparador só marca as entradas `PAR_COMPARAVEL_PARA_DIAGNOSTICO` quando as três assinaturas são iguais. Testes CPU verificam normalização entre NumPy/endianness, divergências e rejeição de NaN.

**(2) Difusa isolada:** nos dois processos, a partir do estado Phong original, o harness gera uma captura adicional com `ambientColor=(0,0,0)`, `specularColor=(0,0,0)` e `receiveShadows=False`, preservando `diffuseColor`, luz, geometria e a câmera. As três propriedades são restauradas em `finally`. O par é medido bruto e após as duas transformações *somente analíticas* R/B e sRGB; calcula também erro por canal na região heurística do corpo, não alfa.

**(3) Posição da luz GL efetiva:** o harness upstream consulta `glGetLightfv(GL_LIGHT0, GL_POSITION)` em contexto real e registra a posição em espaço de câmera, comparando-a numericamente com `view @ light.position` do cenário. A leitura é opcional e registra um erro explícito se o driver não a fornecer; não substitui as métricas visuais. O GLSL Phong opera em espaço de câmera (`gl_NormalMatrix`, `gl_LightSource[0].position`), enquanto a versão WGSL usa normais e luzes em espaço de mundo. É essencial verificar que as transformações preservam o vetor de iluminação.

**Critério:** validar captura só difusa nos dois backends, hashes idênticos de geometria/normais e posição real da luz; interpretar redução/aumento das diferenças com máscara RGB e todos os limites existentes. Resultados desta etapa não estão medidos na documentação inicial; CI deve ser consultada. Nenhuma paridade será homologada por teste de saída 0, nem qualquer correção visual aplicada sem decisão do criador.

## 17. Contraprova da posição efetiva da luz GLSL no Phong (sem alteração de produção)

**Evidência medida na CI [42330326816](https://github.com/SrTristeSad/brincadeira/actions/runs/42330326816):** as assinaturas SHA-256 dos arrays do corpo `base.obj` são *exatamente iguais* entre o upstream OpenGL `a8bc2d54` e o candidato Vulkan `e5c4431`: 21.833 vértices, 13.378 quads, posições `cbabd33760a51a1e7509a291e4426a5312b58e5819ac3822dbd747ab5e1f1e6f`, normais `b5537c0dc6306d2aa13f2caa6a48b350d89e5e2523ddde5352441e2887b423c8`, faces `b0d244b6a6a2151ee4db2b3e49c727f6d4ba1f76c8881b8e7cb9abcdd4765bd3`. Normais de módulo ~1.0. O comparador só marca o par comparável com os três hashes iguais.

**Contradição de iluminação encontrada:** a consulta real `glGetLightfv(GL_LIGHT0,GL_POSITION)` do upstream após renderizar Phong retornou a posição *eye-space* `[-10.98999977, 20.0, 20.0, 1.0]` (Mesa llvmpipe). A posição que corresponderia à luz da cena transformada por `view @ light.position` é `[-10.99, 19.88075066, 7.74881723, 1.0]`; diferença `y=+0.11924934`, `z=+12.25118277`. Isso sugere que o GL original guardou a luz antes de aplicar a transformação de câmera, enquanto o Vulkan a usa como luz em mundo, alterando a direção difusa efetiva. Não alterar a fórmula de produção por causa de um provável comportamento legado sem validá-lo.

**Controle só difuso:** com `ambientColor=(0,0,0)`, `specularColor=(0,0,0)`, `receiveShadows=False` nos dois processos, a fração divergente após normalizações diagnósticas foi **4,2063%** (RGB médio global **0,7663**, erro RGB médio sobre região heurística **13,3335**). O resíduo permanece essencialmente na componente difusa.

**Contraprova agora preparada:** o script CPU `testes/compensar_luz_eye_legacy.py` resolve `view @ P_world = GL_LIGHT0_eye` sem alterar o renderer. Dentro do harness Vulkan **efêmero**, a única luz é temporariamente reposicionada para essa `P_world` compatível com o estado GLSL medido (esperada aproximadamente `[-10.99, 20.11924934, 32.25118277]`). São gerados dois PNGs adicionais (Phong normal e só difuso), os valores e hashes são registrados, a posição original da luz é restaurada sempre. O comparador verifica `view @ P_world` contra o GL real antes de calcular as métricas. Outros testes CPU cobrem identidade, translação e matriz singular.

**Critério e restrição:** essa posição modificada serve APENAS para entender a fonte do erro, não é material da cena oficialmente alterado, nem aprovação de portar uma peculiaridade OpenGL. Verificar se cai a fração de pixels fora de 8 e o erro regional, além de inspecionar os PNGs. Qualquer decisão sobre reproduzir ou não a semântica legada em Vulkan fica com o criador. Resultados deste controle ainda pendentes na revisão inicial.

## 18. Contraprova concluída — incompatibilidade de espaço de luz é dominante

**Execução pareada da mesma revisão:** [GitHub Actions 42330678073](https://github.com/SrTristeSad/brincadeira/actions/runs/42330678073), commit `7aa8b293085a9042ef5828f30ee2f51a25790e86`. Quatro workflows concluídos com sucesso (CI Vulkan PR e push, smoke GUI, deformações Python). JSONs e capturas originais nos artefatos `phong-referencia-opengl-ci`, `phong-diffuse-on-off-ci`, `phong-pareamento-ci`. Os três hashes de geometria são idênticos; iluminação e material coincidem antes do controle; os nove alvos 1024×768 foram realmente observados na GUI Vulkan. O controle foi aplicado **somente no processo temporário Vulkan**.

### Posição de luz medida, sem inferência

GL `glGetLightfv(GL_LIGHT0, GL_POSITION)` observou luz em espaço de câmera `(-10,98999977; 20,0; 20,0; 1,0)`. O cálculo padrão de Vulkan a partir de uma luz em mundo `(-10,99; 20; 20)` resulta em posição de câmera `(-10,99; 19,88075066; 7,74881723; 1)`. A contraprova converte a luz *eye-space* realmente armazenada no GL para mundo usando `P_world = inverse(view) @ GL_LIGHT0_eye`, produzindo `(-10,99; 20,11924934; 32,25118277)` para o cenário pareado. O comparador valida `view @ P_world == GL_LIGHT0_eye` dentro da tolerância e rejeita qualquer controle sem correspondência. Nada está hardcoded no renderizador de produção.

| Cenário, somente depois das duas normalizações analíticas R/B no GL e sRGB→linear no Vulkan | Fração >8 antes da compensação | Fração >8 com luz compensada | Pixels divergentes com compensação | Erro médio RGB com compensação | Erro RGB médio na região heurística do corpo |
| --- | ---: | ---: | ---: | ---: | ---: |
| Phong completo | **4,1879018%** | **0,2314250%** | **1.820 / 786.432** | **0,1354811** | **2,3573** |
| Phong apenas difuso (ambiente/especular/sombras zerados) | **4,2063%** | **0,0261943%** | **206 / 786.432** | **0,0398670** | **0,6937** |

Os controles compensados passam os dois *limites RGB provisórios* (fração até 2%, erro médio RGB até 3) neste par Phong. A contraprova confirma fortemente que a transformação da posição efetiva da luz é a fonte dominante da divergência de iluminação. Os pixels residuais do Phong completo se concentram principalmente em especular, bordas e diferenças de rasterização; a causa pixel a pixel dessas sobras NÃO foi definitivamente isolada.

**Isto NÃO é paridade visual homologada:** o teste exige reinterpretação de R/B da referência OpenGL, decodificação sRGB do Vulkan e compensação de luz aplicada fora da produção. A máscara alfa real não foi capturada (os PNGs são RGB; IoU alfa 1 é trivial). Não houve decisão do criador sobre reproduzir a posição eye-space legada versus preservar iluminação mundial semanticamente corrigida. LitSphere, skin, toon, normalmap e demais configurações ainda exigem suas próprias capturas pareadas.

Foi corrigida a nomenclatura do JSON de diagnósticos: `limites_rgb_propostos_satisfeitos` pode ser true, mas `limites_propostos_todos_satisfeitos` permanece **false** e `alfa_real_avaliado=false`, precisamente para impedir homologação acidental por RGBA opaco sintético. O campo legado `aprovado` do comparador significa apenas a fração de pixels dentro do limiar escolhido.

**Próxima decisão reservada ao criador:** (A) preservar a aparência/captura histórica do GLSL, modelando explicitamente a semântica de luz eye-space na compatibilidade Vulkan, com patch separado e regressões pré/pós; ou (B) manter a semântica mundo do backend moderno e documentar a diferença visual deliberada. Independentemente disso, decidir em separado o contrato de cor offscreen e a conversão de canais da ferramenta de referência. Não modificar shaders/viewport/offscreen/câmera de produção nem fazer merge sem aprovação.

## 19. Captura da máscara alfa REAL do Phong pela API original

**Motivo:** todos os PNGs Phong anteriores são RGB. A comparação via `compare_portable_frames.pixels` os convertia em RGBA opaco, fazendo IoU alfa=1 por construção. Isso **não** prova a cobertura do modelo. Esta etapa exige a saída de `mh.renderAlphaMask(1024,768)` nos dois processos e não depende da decisão pendente sobre a luz em eye-space.

**Rastreio das APIs sem modificar produção:** o upstream `a8bc2d54` executa uma renderização específica com `G.clearColor=(0.5,0.5,0.5,0)` e `glBlendFunc(GL_ONE,GL_ONE)`, desativa multisampling, lê `GL_RGBA` e retorna o canal A repetido como cinza RGB. O Vulkan chama `CenaVulkan.capturar_framebuffer(... incluir_alfa=True, cor_fundo=(0.5,0.5,0.5,0))`, lê RGBA da GPU e replica o canal A como cinza RGB. São contratos distintos e precisam de medição, nunca de equivalência presumida.

**Implementação somente em harnesses isolados:** novo `testes/registrar_mascara_paridade.py` valida que a saída da API é RGB uint8 em escala de cinza com cobertura não trivial; grava exatamente esses valores no canal A de PNG RGBA, com RGB=0. Registra SHA-256 dos bytes do canal A e do PNG final. O harness de referência OpenGL e o do candidato Vulkan fazem a chamada depois das capturas Phong, com estado de material e câmera restaurados. A observação Vulkan agora exige **10** texturas offscreen de 1024×768, incluindo o passe alfa. Nenhum arquivo do produto foi alterado.

**Verificação quantitativa:** `testes/comparar_mascara_paridade.py` valida modo PNG RGBA, resolução, canal RGB=0, hash da API, e cobertura não trivial antes de medir IoU dos pixels `A>0`, pixels fora da tolerância alfa=8, fração divergente, erro médio/máximo A e quantidade de pixels com alfa intermediário em cada backend. Os limites sugeridos, **ainda não aprovados pelo criador**, são IoU ≥0,995 e fração alfa divergente ≤0,5%. Saída `phong-alfa-api-ci.json` e `phong-alfa-api-diff-ci.png` acompanha o artefato `phong-pareamento-ci`; os PNGs alfa canônicos integram os artefatos individuais.

**Critérios de interpretação:** se o teste registrar PNG válido, a máscara alfa da **API Phong** foi realmente avaliada. A CI pode concluir `success` mesmo que os limiares de paridade alfa sejam reprovados; usar os números, não o exit code. Mesmo que a máscara passe, isso não homologa transparência de outros materiais/presets, blending e alpha-to-coverage, nem dispensa corrigir/decidir contrato de cor e luz da produção.

**Status:** instrumentação implementada e cinco testes CPU aprovados localmente; execução real da GUI e métricas ainda pendentes para esta revisão. **Windows e Linux** no escopo, sem macOS.

### Resultado efetivo da primeira execução pareada de alfa

**Fonte:** [GitHub Actions 42333196092](https://github.com/SrTristeSad/brincadeira/actions/runs/42333196092), commit `91a548a957e16e2f43e241bac851c25422d5cd1f`. Os dois harnesses produziram máscaras RGBA 1024×768 via `mh.renderAlphaMask`, com checksums de canal A e PNG conferidos manualmente após baixar os artefatos `phong-referencia-opengl-ci` e `phong-diffuse-on-off-ci`. O step automático da comparação falhou **por ausência de Pillow no ambiente de CI**, não por divergência visual; os PNGs e manifestos são válidos.

A análise local independente com Pillow e NumPy, lendo os arquivos **exatos** publicados pelos dois harnesses e verificando os hashes, calculou:

| Métrica de alfa da API | Valor |
| --- | ---: |
| Pixels totais | 786.432 |
| Pixels divergentes além de 8 níveis | **36** (**0,00457764%**) |
| IoU real de cobertura `A>0` | **0,9992035046** |
| Erro médio absoluto de alfa | **0,01167297** |
| Erro máximo de alfa | **255** |
| Cobertura OpenGL / Vulkan | **45.178 / 45.182** |
| Interseção / união | **45.162 / 45.198** |
| Alfa intermediário OpenGL / Vulkan | **0 / 0** |
| Limiares provisórios alfa (IoU ≥0,995; até 0,5% divergente) | **Atendidos neste caso** |

SHA-256 alfa OpenGL `9bdb92051bc6ddd683186daf2af842bb3e3b5df191af292b6a2548a45b430006`; Vulkan `a11aee4ad9768515228efa83cf7301f90e4133cbf5ce6aae64c5fc5cafbfaf8c`. A diferença máxima de 255 representa cobertura diversa em parte dos 36 pixels, e as máscaras NÃO são idênticas. Os dois backends não produziram alfa parcial neste Phong de corpo sem material transparente.

**Acompanhamento:** somente a ação CI foi atualizada para instalar `Pillow>=10,<13` antes do teste Python/relatório, sem alterar requirements de produção. A nova execução deve confirmar essas métricas e anexar `phong-alfa-api-ci.json` e `phong-alfa-api-diff-ci.png`. Mesmo quando o teste automático passar, não equivale à homologação dos demais shaders, materiais transparentes ou blending.

## 20. Controle de alfa parcial por textura RGBA (execução pendente)

**Motivação:** o Phong GLSL original define `final_color.a = tex_color.a` independentemente de `material.opacity`, enquanto o WGSL multiplica o alfa por `material.opacity`. Para isolar a semântica da textura, os dois harnesses usam **opacity=1.0** e NÃO alteram a produção. O resultado do corpo opaco anterior foi IoU 0,9992035 e 36/786.432 pixels alfa divergentes; nenhum alfa intermediário.

**Teste reproduzível:** `testes/textura_alpha_controle.py` constrói no processo uma textura RGBA 32×32, xadrez RGB com alfa **128 em todos os texels**, com `sha256_rgba` registrado. Temporariamente, em cada cópia isolada da GUI original: `material.diffuseTexture=Image(data=...)`, `configureShading(diffuse=True)`, `opacity=1`, `transparent=True`, `alphaToCoverage=False` e shader Phong existente. Captura `mh.renderToBuffer(1024,768)` e `mh.renderAlphaMask(1024,768)`; guarda PNG RGB, PNG da máscara A real, estado do material e hashes; restaura todos os atributos em `finally`. O comparador exige flags e hash idênticos dos pixels da textura.

**Métricas novas:** além do controle opaco, o comparador de alfa registra IoU, erro absoluto médio/máximo e pixels fora da tolerância 8 para o par parcial; pixels com `0<A<255` nos dois, médias de A na interseção de cobertura, e `limiares_parciais_propostos_atendidos` (true SOMENTE quando alfa parcial foi realmente observado em ambos). O resultado não homologa outros shaders, materiais ou blending geral; a função de captura OpenGL utiliza acumulação de alfa distinta da composição Vulkan.

**Artefatos:** PNGs `*-alpha-parcial-rgb.png` e `*-alpha-parcial-api.png` nos artefatos individuais; `phong-alfa-parcial-diff-ci.png` no artefato `phong-pareamento-ci`. Contagem Vulkan prevista: **12** alvos offscreen 1024×768, sendo 10 já verificados e mais duas capturas com controle parcial. Três testes CPU de textura verificaram RGBA, padrão e parâmetros; duas regressões numéricas avaliam alfa parcial.

**Status inicial:** instrumentação somente preparada; execução real da GUI pendente. Não inferir resultados nem interpretar sucesso do job como aprovação visual. Mudanças limitadas a harnesses efêmeros, comparador, testes, workflow e protocolo. `main`, shaders, framebuffer e API de produção permanecem intactos.

## 21. Reavaliação crítica do primeiro controle parcial — textura em memória sem cache

**Run 42335541126 / commit `4771fba`:** a CI dos dois processos e o comparador foram bem-sucedidos operacionalmente e encontraram IoU de cobertura 0,9992035, mas **45.058 pixels alfa divergentes acima de 8** (5,7294% da imagem), com alfa intermediário **0 pixels no OpenGL** e **45.042 no Vulkan**. Alfa médio na interseção: 255 (OpenGL) versus 129,72 (Vulkan). O PNG original com xadrez em memória ficou **quase preto**, enquanto o Vulkan apresentou textura e alfa parcial. Esse primeiro controle não constitui evidência limpa de divergência intrínseca entre os renderizadores: a entrada GLSL não foi demonstrada efetivamente vinculada ao sampler.

**Pista reproduzível no upstream:** `texture.getTexture(Image)` para `Image` sem `sourcePath` emite o aviso `Image used as texture does not contain a "sourcePath" attribute, making it impossible to cache it` no log original. O método retorna um `Texture(img)` temporário e a classe `Texture.__del__` chama `glDeleteTextures(textureId)`; o sampler recebe um identificador, mas o objeto Python pode ser liberado antes do desenho. Isso é coerente com amostragem GLSL preta e alfa=1, mas permanece hipótese de ciclo de vida até a contraprova com textura válida. **Não é justificativa para modificar produção.**

**Contraprova preparada em harnesses apenas:** `testes/textura_alpha_controle.py` passou a serializar os mesmos pixels RGBA de 32×32 e alfa 128 em um **PNG determinístico escrito exclusivamente em `RUNNER_TEMP`**, usando apenas stdlib (`struct`, `zlib`), sem depender de Pillow ou do salvamento Qt. Atribui-se `material.diffuseTexture` ao **caminho absoluto do PNG** em ambos os processos, permitindo cache por caminho no OpenGL legado. Os arquivos `phong-referencia-opengl-ci-textura-parcial.png` e `phong-diffuse-ci-textura-parcial.png` acompanham os artifacts; o comparador exige **SHA-256 idêntico do arquivo**, `opacity=1`, `DIFFUSE` ligado, `transparent=True`, `alphaToCoverage=False`. Nenhum asset de produção foi criado ou alterado.

**Status deste novo controle:** ainda não executado nesta revisão do documento. O primeiro resultado de 5,73% não deve ser apresentado como reprovação definitiva do *suporte à transparência parcial*: pode ser causado pelo teste em memória não cacheado. A execução com arquivo de textura será necessária para confirmar o grau de equivalência da API e separar o passe aditivo OpenGL do blend alfa Vulkan.
