# MakeHumano — modernização experimental do MakeHuman

Este diretório é a área de trabalho para atualizar o [MakeHuman](https://github.com/makehumancommunity/makehuman) em **Python**, preservando a lógica e os recursos originais sempre que possível.

> **Estado atual:** estrutura inicial e ferramentas de importação/diagnóstico. A aplicação **ainda não foi modernizada ou validada** para versões recentes do Python. Os arquivos originais do MakeHuman ainda não foram importados neste repositório.

## Estrutura

- `importar_original.py`: importa uma cópia do código-fonte oficial para `makehumano/codigo/`, sem modificar o repositório original.
- `diagnostico.py`: verifica a versão do Python, dependências, presença dos arquivos e sintaxe dos módulos importados.
- `.gitignore`: evita versionar arquivos temporários e ambientes virtuais.

## Como começar

É necessário ter **Python 3** e **Git** instalados.

A partir da pasta `makehumano/`:

```bash
python importar_original.py
python diagnostico.py
```

O importador copia a versão do repositório original fixada por um commit, para que a experiência seja reproduzível. Para importar uma versão mais nova, use `python importar_original.py --atualizar` (a cópia anterior é mantida até a nova estar pronta).

Depois, consulte `codigo/README.md` para as instruções oficiais de instalação, obtenção de assets e execução do MakeHuman. A importação do código-fonte não baixa automaticamente todos os assets externos. Não presuma que o aplicativo funcionará com um Python recente sem correções adicionais.

## Objetivo das próximas alterações

1. Identificar incompatibilidades reais sem alterar o comportamento do programa.
2. Atualizar a infraestrutura de testes e o ambiente Python.
3. Adaptar dependências e interface gráfica em etapas pequenas.
4. Modernizar o código preservando o sistema de deformação 3D, arquivos e plugins.

## Licenças e créditos

**MakeHuman Community** é o projeto original. Seu código é disponibilizado sob **AGPL-3.0 ou posterior** e os assets incluídos no projeto são disponibilizados sob **CC0 1.0**. Os arquivos e avisos de licença do projeto original devem ser preservados na importação. Ver [licenças originais](https://github.com/makehumancommunity/makehuman/blob/master/LICENSE.md).

Este diretório não representa uma versão oficial do MakeHuman.
