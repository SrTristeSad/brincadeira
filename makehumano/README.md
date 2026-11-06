# MakeHumano — modernização do MakeHuman original

O projeto moderniza **o MakeHuman existente**, preservando sua janela e ferramentas. As metas são compatibilidade com Python moderno e substituição completa de OpenGL por Vulkan. Não há editor ou visualizador separado.

**Escopo e critérios de conclusão:** [ESCOPO.md](ESCOPO.md).

## Estado da integração

O backend **Vulkan é o padrão** na janela original, via `wgpu` e `rendercanvas`, sem chave `MAKEHUMANO_VULKAN_PILOT` e sem dependência de `PyOpenGL`. O módulo legado `lib/glmodule.py` foi retirado; `shader.py` e `texture.py` encaminham as APIs compatíveis à infraestrutura Vulkan. A seleção das FaceGroups, canvas, buffers, texturas, renderização offscreen, UV baking, materiais, sombras e parte do fluxo de animação/exportação possuem implementações e testes.

**Ainda é uma versão de desenvolvimento.** A migração não comprova paridade visual ou funcional completa. Shaders GLSL personalizados não são executados diretamente; os métodos legados `Object3D.draw/pick` não têm substitutos equivalentes; transparência complexa, roupas e cabelos externos, plugins de terceiros e drivers Vulkan de GPUs físicas exigem validação.

Consulte [MIGRACAO-VULKAN.md](MIGRACAO-VULKAN.md) e [AUDITORIA-VERIFICADA-2026-11-06.md](AUDITORIA-VERIFICADA-2026-11-06.md) para detalhes técnicos e limitações. A auditoria registra a revisão de desenvolvimento de origem e os limites dos testes, não uma certificação de produto final.

## Pastas e arquivos

| Caminho | Função |
| --- | --- |
| `codigo/` | Fontes e recursos originais modificados, com créditos e licenças. |
| `codigo/makehuman/lib/vulkan_*.py` | Infraestrutura Vulkan usada pela GUI original. |
| `testes/` | Regressões e smokes do MakeHuman original. |
| `diagnostico.py` | Verificação de sintaxe e dependências Python. |
| `executar.py` | Inicia a aplicação original. |
| `importar_original.py` | Reimportação opcional do upstream. **Não executar numa cópia modificada sem backup/revisão.** |
| `empacotamento/` | Recursos usados na geração dos pacotes portáteis de teste. |

O antigo `motor_wgpu/` separado foi removido por decisão do criador. Nenhuma dependência ou teste ativo exige esse editor. Seu histórico permanece no Git.

## Execução

Use preferencialmente Python 3.12 em Windows ou Linux com Qt e driver Vulkan:

```bash
cd makehumano
python -m pip install -r codigo/requirements.txt
python diagnostico.py
python executar.py
```

Para verificar os testes Python:

```bash
python -m unittest discover -s testes -p "test_*.py" -v
```

Os testes gráficos precisam de uma sessão de GUI e dispositivo Vulkan. O GitHub Actions usa Xvfb e Lavapipe como driver Vulkan por software. Consulte `testes/smoke_gui.py` e os workflows:

- `.github/workflows/testar-makehumano.yml`: Python 3.12/3.13, sintaxe e regressões.
- `.github/workflows/testar-vulkan-makehumano.yml`: GUI original com Vulkan, inclusive sem PyOpenGL.
- `.github/workflows/smoke-gui-makehumano.yml`: abertura e funcionalidades da GUI original.
- `.github/workflows/empacotar-makehumano.yml`: criação e validação de ZIPs de teste para Windows e Linux.

Os pacotes portáteis e suas limitações estão em [PORTATIL.md](PORTATIL.md). Testes em CI não substituem testes reais em hardware e plugins externos.

## Licenças

A revisão original importada está identificada em `codigo/.makehumano-origem.txt`. Preservar os avisos de `codigo/LICENSE.md`, `codigo/LICENSE.CODE.md` e `codigo/LICENSE.ASSETS.md`. Este projeto **não é uma versão oficial do MakeHuman**.
