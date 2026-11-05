# Motor WGPU experimental — MakeHumano

**Estado:** protótipo isolado. A interface original em PyQt5/OpenGL permanece funcionando e não foi substituída.

O módulo `motor_wgpu/` usa **wgpu-py + WGSL** para visualizar o `codigo/makehuman/data/3dobjs/base.obj` original. A leitura OBJ seleciona o grupo `body`, triangula quads, preserva UV e calcula normais suavizadas. O renderizador suporta depth buffer, rotação/zoom via controles e **troca de textura RGBA em tempo real**, além de tonalidade e rugosidade da pele com iluminação difusa + reflexo GGX básico.

O painel experimental agora usa **as definições oficiais** de `modeling_modifiers.json` e `modeling_sliders.json`: 238 modificadores anatômicos têm `.target` diretos nesta revisão e podem ser selecionados por região. Os sliders têm direção positiva/negativa quando o MakeHuman define ambos os targets. Os arquivos são carregados sob demanda, com cache; o renderizador recalcula normais, preserva UVs e atualiza o vertex buffer da GPU. **Os 11 macro-modificadores** (como idade, peso, musculatura e gênero) não estão integrados: dependem de interpolação e regras especiais do MakeHuman. Esta prévia não implementa ainda subsurface scattering, normal/roughness maps, pintura 3D, rigging ou picking. Os presets de cores são exemplos, não texturas oficiais.

## Executar

Use Python 3.12 ou 3.13 e drivers de vídeo atualizados. Na pasta `makehumano/`:

```bash
python -m pip install -r motor_wgpu/requirements.txt
python -m motor_wgpu.app
```

Para solicitar **Vulkan explicitamente**:

```bash
python -m motor_wgpu.app --backend vulkan
```

Sem o argumento, wgpu seleciona automaticamente um backend disponível (Vulkan, Metal ou D3D12, conforme o sistema). Se a GPU/driver não suportar o backend escolhido, o programa pode falhar; nesse caso, execute novamente sem `--backend`. Na janela, escolha uma textura por `Carregar textura da pele…`. Use uma textura UV no layout do `base.obj` original para que corresponda ao modelo. A coluna de controles possui rolagem e um seletor de região (cabeça, nariz, braços e pernas etc.). Sliders bidirecionais funcionam de -100 a +100; unidirecionais, de 0 a +100. Ao trocar de grupo, os pesos permanecem ativos. **Restaurar todas as deformações** volta à malha base.

O arquivo de requisitos do novo motor é separado dos requisitos do editor antigo. **Não misture** as duas viewports na mesma janela por enquanto.

## Testes

- CPU, leitura OBJ, UV, morph targets e materiais: `python -m unittest discover -s testes -p 'test_*wgpu.py' -v`
- Interface com Vulkan por software, no Linux com Mesa/Lavapipe e Xvfb:
  `xvfb-run -a python -m motor_wgpu.app --backend vulkan --smoke`

O GitHub Actions executa esses testes em `.github/workflows/testar-wgpu.yml`.

## Arquitetura

- `malha.py`: formato OBJ → buffers CPU (posição, normal, UV, índices)
- `materiais.py`: parâmetros da pele e validação de pixels
- `morphs.py`: leitura dos arquivos `.target`, combinação atômica de pesos e recomputação de normais
- `modificadores.py`: catálogo de sliders a partir dos JSON oficiais do MakeHuman
- `shaders/pele.wgsl`: material difuso + GGX simplificado
- `gpu.py`: device, pipeline, texturas, uniforms, depth, vertex buffer mutável e draw
- `app.py`: widget Qt e controles de demonstração

## Próximos marcos (não implementados)

1. Integrar os 11 macro-modificadores e suas dependências (idade, peso, gênero, musculatura etc.) usando as mesmas regras da aplicação original, em vez de copiar aproximações.
2. Converter os materiais atuais para mapas base-color, normal e roughness.
3. Implementar câmera e picking equivalentes à viewport antiga.
4. Testar shaders com várias GPUs/drivers e qualidade visual.
5. Migrar o canvas oficial quando houver paridade de recursos.

A pasta `codigo/` preserva avisos e licenças do [MakeHuman Community](https://github.com/makehumancommunity/makehuman). O novo protótipo é parte do experimento MakeHumano; manter atribuições e termos AGPL pertinentes.
