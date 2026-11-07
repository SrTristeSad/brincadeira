# Protocolo de paridade visual — MakeHuman OpenGL × MakeHumano Vulkan

**Estado (2026-11-06):** roteiro proposto, **sem pares de referência capturados e sem resultados medidos**. As tolerâncias abaixo são critérios **provisórios**: exigem aprovação do criador e podem precisar de ajuste por análise de imagens reais. Este documento não homologa a migração.

## 1. O que precisa ficar congelado

- **Dois executáveis em ambientes separados:** MakeHuman original com OpenGL (revisão SHA completa a identificar e registrar antes de capturar) e MakeHumano Vulkan (SHA completo da revisão comparada; ponto inicial sugerido: 586c98c6031dbdff4226d94604b1758b34e648c1). O OpenGL só é usado como referência externa, **não** como fallback da aplicação final.
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
| phong.png | Preset phong, AO e material idênticos | Sem par |
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

**Resultado registrado nesta data:** 0 pares OpenGL × Vulkan disponíveis; 0 comparações contra o original executadas; nenhum caso homologado. As 61 capturas idênticas da CI são **Vulkan-fonte × Vulkan-portátil** e não substituem esta campanha.

**Validações externas em separado:** GPU física NVIDIA/AMD/Intel, exportações consumidas em aplicativos externos e campanha manual de plugins/entrada. Sem resultados atribuídos a elas.
