# MakeHumano — modernização do MakeHuman

Este diretório contém o trabalho de **modernização do MakeHuman original**. O objetivo é atualizar a compatibilidade com Python e suas dependências e substituir **integralmente o motor OpenGL por Vulkan**, preservando a interface e as funcionalidades existentes. Não se trata de criar outro editor.

**Referência para qualquer alteração:** [ESCOPO.md](ESCOPO.md).

## Estado atual

A migração **não está concluída**. A aplicação original continua dependendo de componentes OpenGL em parte do caminho de execução. Há uma integração Vulkan **piloto** na janela original, ativada por `MAKEHUMANO_VULKAN_PILOT=1`: ela renderiza objetos de `G.world` e possui seleção inicial de FaceGroups pelo contrato `mh.getPickedColor()`, sem `glReadPixels` nessa seleção. O picking do piloto é calculado na CPU e ainda tem limitações.

Ainda faltam migração e validação da infraestrutura gráfica completa (materiais, transparência, shaders, recursos offscreen, plugins, seleção e equivalência visual). Só depois de demonstrar a equivalência será seguro eliminar `PyOpenGL`, `QOpenGLWidget` e os demais componentes OpenGL legados.

## Organização

| Caminho | Função |
| --- | --- |
| `codigo/` | Cópia versionada do MakeHuman original, com recursos, licenças e alterações em desenvolvimento. **Não excluir** arquivos originais sem verificar dependências. |
| `testes/` | Testes de regressão da modelagem e da integração Vulkan na janela original, além do smoke test gráfico. |
| `diagnostico.py` | Verifica dependências disponíveis e sintaxe dos arquivos Python. |
| `executar.py` | Inicia a aplicação original presente em `codigo/makehuman/`. |
| `importar_original.py` | Ferramenta de reimportação do upstream, **não necessária para uso normal desta cópia**. |
| `requirements-vulkan-piloto.txt` | Dependências adicionais do Vulkan piloto na interface original. |
| `ESCOPO.md` | Objetivos, limites e critérios de conclusão do projeto. |

## Executar a aplicação original

Use preferencialmente Python **3.12** para reproduzir o ambiente do smoke test em CI. Uma parte dos testes também é executada com Python 3.13, mas isso não comprova compatibilidade completa da interface.

Na pasta `makehumano/`:

```bash
python -m pip install -r codigo/requirements.txt
python diagnostico.py
python executar.py --noshaders
```

A execução comum ainda utiliza OpenGL durante a migração e requer ambiente gráfico com as bibliotecas Qt e drivers apropriados. O parâmetro `--noshaders` facilita o teste inicial, mas **não representa a renderização final**.

Para experimentar a integração Vulkan na **janela original**, instale as dependências adicionais do próprio piloto. Exemplo de shell Linux/macOS:

```bash
python -m pip install -r requirements-vulkan-piloto.txt
MAKEHUMANO_VULKAN_PILOT=1 WGPU_BACKEND_TYPE=Vulkan python executar.py --noshaders
```

Esse modo é **experimental**; ele ainda necessita de dependências legadas e não deve ser tratado como substituição concluída do OpenGL.

## Testes

Com as dependências adequadas instaladas, execute na pasta `makehumano/`:

```bash
python -m unittest discover -s testes -p "test_*.py" -v
```

O teste gráfico da GUI precisa de ambiente com suporte a Qt e renderização; o CI utiliza Xvfb e renderização por software. Os workflows ficam na raiz do repositório, em `.github/workflows/`:

- `testar-makehumano.yml`: Python 3.12/3.13, sintaxe e regressões.
- `smoke-gui-makehumano.yml`: abertura da interface original.
- `testar-vulkan-makehumano.yml`: testes do Vulkan conectado à GUI original, sem editor independente.

**Atenção à reimportação:** `codigo/` já está versionado e contém alterações próprias. Executar `python importar_original.py --atualizar` troca a cópia de trabalho por outra do upstream e move a anterior para um backup local. Não use esse comando para atualizar uma instalação existente sem primeiro revisar suas alterações.

## Próximas etapas dentro do escopo

1. Completar a compatibilidade da aplicação original com Python moderno e suas dependências.
2. Migrar todos os caminhos gráficos da janela e dos plugins originais para Vulkan.
3. Comprovar equivalência funcional e visual com testes de regressão.
4. Remover o motor OpenGL **somente após** a substituição e a validação.

O editor experimental independente foi removido da árvore ativa. Seu histórico continua disponível nos commits antigos do Git. O trabalho futuro é exclusivamente na aplicação original.

## Licenças e proveniência

As informações da revisão upstream ficam em `codigo/.makehumano-origem.txt`. Os avisos e licenças originais estão em `codigo/LICENSE.md`, `codigo/LICENSE.CODE.md` e `codigo/LICENSE.ASSETS.md`. Eles devem ser preservados.

Este trabalho experimental **não é uma versão oficial do MakeHuman**.
