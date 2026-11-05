# MakeHumano — modernização experimental do MakeHuman

Esta pasta é a área de trabalho para atualizar o [MakeHuman](https://github.com/makehumancommunity/makehuman) em **Python**, preservando a lógica e os recursos originais sempre que possível.

> **Estado atual:** estrutura inicial e ferramentas de importação, diagnóstico e execução. A aplicação **ainda não foi modernizada nem testada** em versões recentes do Python. O código-fonte completo do MakeHuman ainda **não está incluído** neste repositório.

## O que já existe

- `importar_original.py`: obtém uma cópia do código-fonte oficial para `codigo/`, sem modificar o repositório de origem.
- `diagnostico.py`: identifica versões do Python e das dependências e verifica a sintaxe dos arquivos importados.
- `executar.py`: executa o MakeHuman importado com o Python atual, sem alterar sua lógica.
- `.gitignore`: ignora arquivos temporários, mas **não ignora** `codigo/`, para que atualizações possam ser versionadas.

## Primeiros passos

É necessário ter **Python 3** e **Git** instalados.

Abra um terminal dentro de `makehumano/` e execute:

```bash
python importar_original.py
python diagnostico.py
```

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

O diretório `codigo/` foi deixado fora das regras de exclusão do Git para permitir que o código atualizado seja salvo em `brincadeira/makehumano/codigo/`. A importação inicial é uma etapa local; os arquivos só aparecem no GitHub depois de adicionados e registrados em um commit.

## Objetivo das próximas alterações

1. Identificar incompatibilidades reais e documentar o estado inicial.
2. Atualizar gradualmente o ambiente Python e os testes automatizados.
3. Adaptar dependências e interface gráfica sem quebrar o sistema de deformação.
4. Modernizar os módulos mantendo, sempre que possível, os arquivos e os plugins originais.

## Licenças e créditos

O código-fonte do **MakeHuman Community** é disponibilizado sob **AGPL-3.0 ou posterior**. Os assets incluídos pelo projeto são **CC0 1.0**. Avisos e arquivos de licença originais devem ser preservados ao importar e modificar o projeto. Consulte o [documento de licenças original](https://github.com/makehumancommunity/makehuman/blob/master/LICENSE.md).

Este trabalho experimental não é uma versão oficial do MakeHuman.
