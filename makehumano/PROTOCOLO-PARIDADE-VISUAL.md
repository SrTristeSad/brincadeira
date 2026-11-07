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
