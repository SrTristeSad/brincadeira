# MyPaint-Ibis-Lua

Protótipo **independente** de um editor de pintura em LÖVE 11.5, com interface inspirada no projeto [Ibis-Lua](https://github.com/SrTristeSad/Ibis-Lua) e seleção de ferramentas que também existem no MyPaint.

> **Estado real:** não é um fork do MyPaint e **não utiliza libmypaint**. O Ibis-Lua original é um projeto visual sem motor de pintura; aqui há um motor raster simples próprio para tornar o protótipo utilizável. Não representa equivalência de fidelidade ou desempenho do MyPaint. O código foi colocado isoladamente nesta pasta, sem alterar nenhum outro projeto de `brincadeira`.

## O que funciona nesta etapa

- Desenho livre com pincel circular, borracha e conta-gotas.
- Cor RGB, tamanho e opacidade do pincel.
- Camadas raster: adicionar, remover, selecionar, ocultar e alterar opacidade.
- Desfazer/refazer **pinceladas** (até 12 passos; ações de camada não entram no histórico).
- Zoom com roda do mouse, deslocamento com Espaço+arrastar ou ferramenta Mão.
- Nova tela com largura/altura personalizadas.
- Exportar o resultado composto em **PNG** para a pasta de dados do LÖVE.
- Abrir PNG/JPEG arrastando o arquivo para a janela (substitui a tela atual).

**Não incluídos:** texto, vetor, animação, filtros, seleção mágica, loja de pincéis, galerias e outras ferramentas de ibisPaint que não foram implementadas aqui. Recursos mais avançados do próprio MyPaint também **não** são reproduzidos; não confundir “ferramentas que existem no MyPaint” com “todas as funções do MyPaint”.

## Execução

1. Instale [LÖVE 11.5](https://love2d.org/).
2. Execute `love MyPaint-Ibis-Lua` na raiz do repositório ou abra esta pasta com o LÖVE.
3. Para salvar, use **Export PNG** ou **Ctrl+S**. O caminho absoluto de exportação aparece na barra inferior.

### Atalhos
- **B** pincel · **E** borracha · **I** conta-gotas · **H** mão
- **C** painel de cores · **L** painel de camadas
- **Ctrl+Z** desfazer · **Ctrl+Y** refazer
- **Ctrl+N** nova tela · **Ctrl+S** exportar PNG
- **Espaço + arrastar** mover a tela · **Roda do mouse** zoom

## Estrutura

- `main.lua`: interface, mouse, teclado e controle do editor.
- `src/document.lua`: camadas, desenho raster e exportação.
- `src/tools.lua`: catálogo **restrito** de ferramentas.
- `src/ui_theme.lua`: tokens visuais reaproveitados do Ibis-Lua original.
- `conf.lua`: configuração da janela LÖVE.
- `tests/test_tools.lua`: teste puro de catálogo, sem depender de LÖVE.

## Referências e autoria

O esquema de cores vem de `SrTristeSad/Ibis-Lua/src/ui_theme.lua`; os demais componentes foram reimplementados aqui para manter a nova pasta autônoma. Não foram incluídos arquivos proprietários do ibisPaint nem se afirma afiliação à ibis inc. ou ao projeto MyPaint.

## Limitações conhecidas

O app usa uma tela raster de tamanho fixo (máximo 4096 × 4096 nesta versão), não implementa o canvas infinito do MyPaint, não abre arquivos .ora/.ora nativos e não guarda um projeto editável entre execuções. O PNG exportado mantém a composição, mas não as camadas. Trabalhos não exportados são perdidos ao fechar, trocar de tela ou importar outra imagem.

O objetivo é validar a experiência visual e o recorte de ferramentas **antes** de substituir esta camada raster pela arquitetura real do MyPaint/libmypaint.
