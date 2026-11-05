# Motor WGPU experimental — MakeHumano

**Estado:** protótipo isolado. A interface original em PyQt5/OpenGL permanece funcionando e não foi substituída.

O módulo `motor_wgpu/` usa **wgpu-py + WGSL** para visualizar o `codigo/makehuman/data/3dobjs/base.obj` original. A leitura OBJ seleciona o grupo `body`, triangula quads, preserva UV e calcula normais suavizadas. O renderizador suporta depth buffer, rotação/zoom via controles e **troca de textura RGBA em tempo real**, além de tonalidade e rugosidade da pele com iluminação difusa + reflexo GGX básico.

Os controles de demonstração agora aplicam **quatro arquivos .target oficiais** diretamente à malha canônica. O renderizador recalcula as normais, preserva as UVs e atualiza o vertex buffer da GPU. Isso **ainda não é a integração do sistema completo de modificadores** (idade, gênero, dependências entre macroalvos etc.) com a GUI principal. Também não há subsurface scattering, normal/roughness maps, pintura 3D, rigging ou picking. Os presets de cores são exemplos editáveis, não modelos oficiais de tons de pele.

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

Sem o argumento, wgpu seleciona automaticamente um backend disponível (Vulkan, Metal ou D3D12, conforme o sistema). Se a GPU/driver não suportar o backend escolhido, o programa pode falhar; nesse caso, execute novamente sem `--backend`. Na janela, escolha uma textura por `Carregar textura da pele…`. Use uma textura UV no layout do `base.obj` original para que corresponda ao modelo. A coluna de controles possui rolagem; os sliders **Nariz**, **Torso**, **Abdômen** e **Mão esquerda** aplicam morph targets originais com peso de 0 a 100%, e **Restaurar deformações** volta à malha base.

O arquivo de requisitos do novo motor é separado dos requisitos do editor antigo. **Não misture** as duas viewports na mesma janela por enquanto.

## Testes

- CPU, leitura OBJ, UV, morph targets e materiais: `python -m unittest discover -s testes -p 'test_*wgpu.py' -v`
- Interface com Vulkan por software, no Linux com Mesa/Lavapipe e Xvfb:
  `xvfb-run -a python -m motor_wgpu.app --backend vulkan --smoke`

O GitHub Actions executa esses testes em `.github/workflows/testar-wgpu.yml`.

## Arquitetura

- `malha.py`: formato OBJ → buffers CPU (posição, normal, UV, índices)
- `materiais.py`: parâmetros da pele e validação de pixels
- `morphs.py`: leitura dos arquivos `.target`, combinação de pesos e recomputação de normais
- `shaders/pele.wgsl`: material difuso + GGX simplificado
- `gpu.py`: device, pipeline, texturas, uniforms, depth, vertex buffer mutável e draw
- `app.py`: widget Qt e controles de demonstração

## Próximos marcos (não implementados)

1. Integrar o sistema **completo** de modificadores anatômicos e suas dependências, além dos quatro `.target` de demonstração.
2. Converter os materiais atuais para mapas base-color, normal e roughness.
3. Implementar câmera e picking equivalentes à viewport antiga.
4. Testar shaders com várias GPUs/drivers e qualidade visual.
5. Migrar o canvas oficial quando houver paridade de recursos.

A pasta `codigo/` preserva avisos e licenças do [MakeHuman Community](https://github.com/makehumancommunity/makehuman). O novo protótipo é parte do experimento MakeHumano; manter atribuições e termos AGPL pertinentes.
