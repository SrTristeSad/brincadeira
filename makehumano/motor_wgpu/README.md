# Motor WGPU experimental — MakeHumano

**Estado:** protótipo isolado. A interface original em PyQt5/OpenGL permanece funcionando e não foi substituída.

O módulo `motor_wgpu/` usa **wgpu-py + WGSL** para visualizar o `codigo/makehuman/data/3dobjs/base.obj` original. A leitura OBJ seleciona o grupo `body`, triangula quads, preserva UV e calcula normais suavizadas. O renderizador suporta depth buffer, rotação/zoom via controles e **troca de textura RGBA em tempo real**, além de tonalidade e rugosidade da pele com iluminação difusa + reflexo GGX básico.

O painel experimental agora usa **as definições oficiais** de `modeling_modifiers.json` e `modeling_sliders.json`: 238 modificadores anatômicos têm `.target` diretos nesta revisão e podem ser selecionados por região. Os sliders têm direção positiva/negativa quando o MakeHuman define ambos os targets. Os arquivos são carregados sob demanda, com cache; o renderizador recalcula normais, preserva UVs e atualiza o vertex buffer da GPU. **Oito macrocontroles anatômicos agora funcionam na prévia:** idade, gênero morfológico, peso, musculatura, altura, proporções corporais, volume e firmeza dos seios. Seus fatores são comparados nos testes aos cálculos originais de `apps/human.py`, e **564 `.target`** participam do catálogo de macroformas. **Os três parâmetros de mistura étnica herdados do MakeHuman agora também possuem sliders interdependentes**, totalizando 11 controles gerais. O ajuste de um parâmetro renormaliza os outros dois para a soma permanecer em 100%, seguindo `Human._setEthnicVals`. Essas categorias correspondem a alvos de deformação herdados, **não a uma medição de identidade étnica**. Ainda não foram integradas todas as relações entre o sistema original de modificadores, a GUI principal, as poses e os plugins. Esta prévia não implementa ainda subsurface scattering, normal/roughness maps, pintura 3D, rigging ou picking. Os presets de cores são exemplos, não texturas oficiais.

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

Sem o argumento, wgpu seleciona automaticamente um backend disponível (Vulkan, Metal ou D3D12, conforme o sistema). Se a GPU/driver não suportar o backend escolhido, o programa pode falhar; nesse caso, execute novamente sem `--backend`. Na janela, escolha uma textura por `Carregar textura da pele…`. Use uma textura UV no layout do `base.obj` original para que corresponda ao modelo. A coluna de controles contém oito parâmetros gerais, três controles de mistura étnica interdependentes e um seletor de região (cabeça, nariz, braços e pernas etc.). Sliders bidirecionais funcionam de -100 a +100; unidirecionais, de 0 a +100. Ao trocar de grupo, os pesos permanecem ativos. **Restaurar todas as deformações** repõe as macrovariáveis iniciais do MakeHuman e zera os sliders anatômicos. O modelo inicial já recebe os macros padrão, não é a malha `.obj` absolutamente neutra.

### Salvar e reabrir um personagem

Use **Salvar personagem…** e **Abrir personagem…** na coluna de controles. A prévia usa arquivos **`.makehumano.json`** legíveis e editáveis; o arquivo guarda os onze parâmetros gerais, os modificadores anatômicos alterados e a cor/rugosidade da pele. A aplicação valida a versão e os valores antes de reconstituir a malha e reenviar os vértices à GPU.

**Importante:** não é o formato `.mhm` do MakeHuman original. Texturas externas carregadas por arquivo, roupas, poses, animações, plugins e câmera não são armazenados nesse JSON. A textura UV pode ser selecionada novamente ao abrir o projeto.

### Exportação OBJ com material e textura

O botão **Exportar OBJ com pele…** cria três arquivos lado a lado, usando o mesmo nome-base: `personagem.obj`, `personagem_pele.mtl` e `personagem_pele.png`. O OBJ contém as posições deformadas (`v`), UVs (`vt`), normais (`vn`) e faces (`f`), referenciando o MTL com `mtllib` e `usemtl`. A malha original de referência mantém os índices de vértices nas costuras.

O **PNG copia os pixels RGBA da última textura enviada à GPU**; se nenhuma imagem externa tiver sido carregada, usa uma textura branca neutra. O MTL define `Kd` pela tonalidade atual e `Ns` como **aproximação** da rugosidade do shader. Para transferir os arquivos a outro programa, **mantenha os três arquivos na mesma pasta**. Se os arquivos já existirem, a interface solicita confirmação antes de substituí-los.

**Limites:** a exportação cobre somente o corpo (`body`), triangulado, sem roupas, cabelo, rig, poses ou animações. MTL/OBJ não representam fielmente GGX, subsurface scattering, transparência complexa ou o pipeline PBR. O PNG preserva o canal alfa, mas seu uso depende do programa importador. **Os arquivos auxiliares e o OBJ são substituídos individualmente**, não numa transação atômica entre os três. Para manter os sliders editáveis, salve também o projeto `.makehumano.json`; o projeto JSON ainda não persiste a imagem externa.

O arquivo de requisitos do novo motor é separado dos requisitos do editor antigo. **Não misture** as duas viewports na mesma janela por enquanto.

## Testes

- CPU, leitura OBJ, UV, morph targets, macros, formato de projetos e comparação com `algos3d.Target.apply` original: `python -m unittest discover -s testes -p 'test_*wgpu.py' -v`
- Interface com Vulkan por software, no Linux com Mesa/Lavapipe e Xvfb:
  `xvfb-run -a python -m motor_wgpu.app --backend vulkan --smoke`

O GitHub Actions executa esses testes em `.github/workflows/testar-wgpu.yml`.

## Arquitetura

- `malha.py`: formato OBJ → buffers CPU (posição, normal, UV, índices)
- `materiais.py`: parâmetros da pele e validação de pixels
- `morphs.py`: leitura dos arquivos `.target`, combinação atômica de pesos e recomputação de normais
- `modificadores.py`: catálogo de sliders a partir dos JSON oficiais do MakeHuman
- `projetos.py`: serialização JSON versionada e validação antes de restaurar parâmetros
- `exportar.py`: gravação OBJ e vínculo opcional com MTL/PNG, preservando posições canônicas e UVs
- `materiais_obj.py`: geração de MTL e PNG RGBA8 com Python/NumPy, sem depender de Qt para exportar
- `macro.py`: interpolação de oito macrovariáveis e normalização dos três controles étnicos seguindo as fórmulas originais, combinando os 564 `.target`
- `shaders/pele.wgsl`: material difuso + GGX simplificado
- `gpu.py`: device, pipeline, texturas, uniforms, depth, vertex buffer mutável e draw
- `app.py`: widget Qt e controles de demonstração

## Próximos marcos (não implementados)

1. Avançar da comparação CPU com `algos3d` para os eventos, poses e dependências completos da GUI original; ainda não há teste de equivalência visual entre as duas interfaces.
2. Evoluir de MTL com textura difusa para mapas de normal e rugosidade, sem confundir o shader GGX com o material Phong do MTL.
3. Implementar câmera e picking equivalentes à viewport antiga.
4. Testar shaders com várias GPUs/drivers e qualidade visual.
5. Migrar o canvas oficial quando houver paridade de recursos.

A pasta `codigo/` preserva avisos e licenças do [MakeHuman Community](https://github.com/makehumancommunity/makehuman). O novo protótipo é parte do experimento MakeHumano; manter atribuições e termos AGPL pertinentes.
