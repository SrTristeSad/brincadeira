# MakeHumano — modernização experimental do MakeHuman

Esta pasta é a área de trabalho para atualizar o [MakeHuman](https://github.com/makehumancommunity/makehuman) em **Python**, preservando a lógica e os recursos originais sempre que possível.

> **Estado atual (primeira iteração):** fontes originais do MakeHuman **já importadas** em `codigo/`; dois erros de sintaxe nos scripts auxiliares identificados e corrigidos; testes automatizados de deformação 3D e compatibilidade Python 3.12/3.13 adicionados. **Ainda não foi verificado que o aplicativo completo funciona.**

## O que já existe

- `importar_original.py`: obtém uma cópia do código-fonte oficial para `codigo/`, sem modificar o repositório de origem.
- `diagnostico.py`: identifica versões do Python e das dependências e verifica a sintaxe dos arquivos importados.
- `executar.py`: executa o MakeHuman importado com o Python atual, sem alterar sua lógica.
- `testes/test_morph_targets.py`: testes unitários da aplicação de morph targets do motor original.
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

Para preparar o ambiente, siga `codigo/README.md`. Por exemplo, as dependências documentadas pelo original podem ser instaladas com:

```bash
python -m pip install -r codigo/requirements.txt
```

Depois de baixar os assets conforme as instruções oficiais, tente iniciar com:

```bash
python executar.py
```

**Atenção:** a importação do código não baixa automaticamente todos os assets externos. A sintaxe válida não garante compatibilidade com versões recentes do Python, Qt, NumPy ou OpenGL.

## Como salvar as atualizações neste repositório

O diretório `codigo/` está versionado no GitHub em `brincadeira/makehumano/codigo/`. Assim, as modificações feitas nos arquivos originais aparecem como diferenças auditáveis. Use commits pequenos e execute os testes antes de alterar a lógica de modelagem.

## Objetivo das próximas alterações

1. [x] Importar o código original com proveniência e licenças.
2. [x] Corrigir os dois erros de sintaxe encontrados em scripts auxiliares legados.
3. [x] Criar testes iniciais para morph targets e verificações de Python 3.12/3.13.
4. [ ] Conferir o resultado da execução da matriz de testes e corrigir possíveis falhas.
5. [ ] Testar a inicialização com os assets externos e ambiente gráfico real.
6. [ ] Adaptar dependências e interface sem quebrar deformações, arquivos e plugins.

## Licenças e créditos

O código-fonte do **MakeHuman Community** é disponibilizado sob **AGPL-3.0 ou posterior**. Os assets incluídos pelo projeto são **CC0 1.0**. Avisos e arquivos de licença originais devem ser preservados ao importar e modificar o projeto. Consulte o [documento de licenças original](https://github.com/makehumancommunity/makehuman/blob/master/LICENSE.md).

Este trabalho experimental não é uma versão oficial do MakeHuman.
