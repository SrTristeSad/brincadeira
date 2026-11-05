# MakeHumano — modernização experimental do MakeHuman

Esta pasta é a área de trabalho para atualizar o [MakeHuman](https://github.com/makehumancommunity/makehuman) em **Python**, preservando a lógica e os recursos originais sempre que possível.

> **Estado atual:** fontes originais, malha base, rig, morph targets e outros recursos versionados em `codigo/`; dois erros de sintaxe auxiliares corrigidos; testes de deformação 3D e compatibilidade Python 3.12/3.13 passaram. A sequência de inicialização da GUI passou com Python 3.12 e Xvfb no Linux; aparência visual, interação dos controles e exportação ainda dependem de testes em desktop real.

## O que já existe

- `importar_original.py`: obtém uma cópia do código-fonte oficial para `codigo/`, sem modificar o repositório de origem.
- `diagnostico.py`: identifica versões do Python e das dependências e verifica a sintaxe dos arquivos importados.
- `executar.py`: executa o MakeHuman importado com o Python atual, sem alterar sua lógica.
- `testes/test_morph_targets.py`: testes unitários da aplicação de morph targets do motor original.
- `testes/test_image_qt.py`: testes de carregamento de imagens RGB/RGBA com Qt e NumPy recente.
- `testes/smoke_gui.py`: teste de inicialização real da interface até concluir a carga do modelo, plugins e morph targets, com marcador de prontidão opcional.
- `.github/workflows/smoke-gui-makehumano.yml`: teste gráfico Linux executado sob Xvfb, com renderização por software.
- `DIAGNOSTICO-INICIAL.txt`: resultado histórico do primeiro exame com Python 3.14; mostra os erros encontrados **antes das correções**.
- `.github/workflows/testar-makehumano.yml` (na raiz do repositório): testes de sintaxe, dependências e morph targets com Python 3.12/3.13.
- `.github/workflows/importar-makehuman.yml` (na raiz do repositório): importação inicial automatizada, com proteção contra sobrescrita.
- `.gitignore`: ignora arquivos temporários, mas **não ignora** `codigo/`, para que atualizações possam ser versionadas.

## Primeiros passos

É necessário ter **Python 3** e **Git** instalados.

Para testar **esta versão**, clone `brincadeira`, entre na pasta `makehumano/` e execute:

```bash
python diagnostico.py
```

O código original já faz parte deste repositório; **não é necessário** executar a importação novamente. O script `importar_original.py` serve para preparar outra cópia em uma pasta de trabalho nova.

O importador registra em `codigo/.makehumano-origem.txt` o commit exato que foi copiado. Ao repetir a importação com `python importar_original.py --atualizar`, a versão anterior é preservada em um diretório de backup.

Para preparar o ambiente, siga `codigo/README.md`. Recomendamos começar com **Python 3.12** (versão já testada na inicialização gráfica). As dependências documentadas pelo original podem ser instaladas com:

```bash
python -m pip install -r codigo/requirements.txt
```

Os recursos necessários ao teste de abertura foram incluídos nesta cópia. Para iniciar em um desktop com suporte a OpenGL, tente:

```bash
python executar.py --noshaders
```

**Atenção:** o teste gráfico usa `--noshaders` em um servidor X virtual, portanto **não valida** shaders e aparência final. Malhas, rigs, morph targets e outros recursos **presentes no repositório original** já estão versionados nesta cópia. Recursos **externos** disponibilizados separadamente pelo projeto continuam podendo ser necessários para certas funções. Sintaxe válida não comprova compatibilidade completa com Python, Qt, NumPy ou OpenGL.

## Prévia experimental com wgpu-py / Vulkan

Foi acrescentado um **visualizador independente** em [`motor_wgpu/`](motor_wgpu/README.md). Ele carrega a malha original `base.obj`, mantém as coordenadas UV, possui material WGSL com difuso + reflexão GGX simplificada e permite alterar texturas durante a execução. O painel agora carrega **238 modificadores diretos** das definições oficiais do MakeHuman, agrupados por região do corpo. Os sliders aplicam morph targets positivos e negativos ao vertex buffer Vulkan, recalculando as normais sem alterar UVs. Também existem **oito controles gerais** na prévia — idade, gênero morfológico, peso, musculatura, altura, proporções corporais, volume e firmeza dos seios — que combinam até 564 alvos originais. A sincronização completa dos três controles étnicos e das dependências da GUI principal ainda está pendente.

Execute no diretório `makehumano/`:

```bash
python -m pip install -r motor_wgpu/requirements.txt
python -m motor_wgpu.app
```

O parâmetro `--backend vulkan` obriga o uso de Vulkan. O modo automático tenta escolher a API que funcione na máquina. Os testes em GitHub Actions verificam o processamento da malha e a criação de quadros com Vulkan por software (Mesa/Lavapipe). **Isto ainda não substitui a viewport principal** nem reproduz todas as regras de dependência, poses e plugins do MakeHuman original; também faltam subsurface scattering, picking e revisão visual em uma GPU física.

## Como salvar as atualizações neste repositório

O diretório `codigo/` está versionado no GitHub em `brincadeira/makehumano/codigo/`. Assim, as modificações feitas nos arquivos originais aparecem como diferenças auditáveis. Use commits pequenos e execute os testes antes de alterar a lógica de modelagem.

## Objetivo das próximas alterações

1. [x] Importar o código original com proveniência e licenças.
2. [x] Corrigir os dois erros de sintaxe encontrados em scripts auxiliares legados.
3. [x] Criar testes iniciais para morph targets e verificações de Python 3.12/3.13.
4. [x] Executar a matriz de testes: Python 3.12 e 3.13, importações e deformações passaram.
5. [x] Restaurar malha base, esqueleto, targets e assets ignorados pela primeira importação.
6. [x] Corrigir o uso binário de `numpy.fromstring()` para `numpy.frombuffer()` ao carregar texturas Qt com NumPy 2+.
7. [x] Executar a abertura gráfica com Xvfb no Linux: inicialização, plugins e morph targets concluídos no Python 3.12.
8. [x] Criar visualizador wgpu independente com Vulkan, textura dinâmica e quatro `.target` originais com sliders.
9. [x] Validar deformação, costuras UV, restauração e renderização de novos vértices no backend Vulkan por software.
10. [x] Criar catálogo de 238 sliders diretos a partir dos arquivos oficiais, incluindo controles bidirecionais e cache de targets.
11. [ ] Testar visualmente a interface num desktop real e identificar assets externos necessários.
12. [x] Acrescentar oito macros com interpolação verificada contra `human.py` e aplicação de alvos originais.
13. [ ] Completar os três controles étnicos, as dependências entre modificadores e a integração à GUI principal.
14. [ ] Testar exportação, salvamento, carga e materiais.
15. [ ] Adaptar dependências e interface sem quebrar deformações, arquivos e plugins.

## Licenças e créditos

O código-fonte do **MakeHuman Community** é disponibilizado sob **AGPL-3.0 ou posterior**. Os assets incluídos pelo projeto são **CC0 1.0**. Avisos e arquivos de licença originais devem ser preservados ao importar e modificar o projeto. Consulte o [documento de licenças original](https://github.com/makehumancommunity/makehuman/blob/master/LICENSE.md).

Este trabalho experimental não é uma versão oficial do MakeHuman.
