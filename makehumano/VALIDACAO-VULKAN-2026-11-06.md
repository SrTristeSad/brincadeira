# Validação do Vulkan — MakeHumano original

**Data da verificação:** 2026-11-06  
**Branch e commit verificados:** `main` — `586c98c6031dbdff4226d94604b1758b34e648c1`  
**Objeto:** MakeHuman original modernizado em `codigo/makehuman/`; o editor `motor_wgpu/` independente não existe mais.

## Resumo de aceite

**Resultado: aprovado para continuar o desenvolvimento sobre o backend Vulkan, mas NÃO aprovado como migração 100% compatível / lançamento final.**

A CI confirma o backend Vulkan funcional na interface original, sem exigir PyOpenGL, com testagem de executáveis para Windows e Linux. Compatibilidade integral com o MakeHuman antigo, shaders arbitrários, plugins externos e hardware físico **não foi demonstrada**. As falhas já conhecidas abaixo não podem ser convertidas em "aprovadas" pelo simples fato de os smokes terminarem com sucesso.

## Verificações efetivamente executadas

| Verificação | Resultado | Evidência |
| --- | --- | --- |
| Regressões Python 3.12 | **PASSOU:** 264 testes, 1 ignorado | [Actions — testes Python](https://github.com/SrTristeSad/brincadeira/actions/runs/42314562203) |
| Regressões Python 3.13 | **PASSOU:** 264 testes, 1 ignorado | [Actions — testes Python](https://github.com/SrTristeSad/brincadeira/actions/runs/42314562203) |
| GUI original em Vulkan | **PASSOU:** abertura, primeiro frame, FaceGroup picking, framebuffer offscreen, máscara alfa, UV bake e smokes de materiais | [Actions — Vulkan](https://github.com/SrTristeSad/brincadeira/actions/runs/42314562191) |
| GUI original sem PyOpenGL instalado | **PASSOU:** backend Vulkan com renderização sob Xvfb | [Actions — Vulkan](https://github.com/SrTristeSad/brincadeira/actions/runs/42314562191) |
| Abertura da GUI Linux | **PASSOU:** smoke gráfico com Xvfb | [Actions — GUI](https://github.com/SrTristeSad/brincadeira/actions/runs/42314562197) |
| Executável portátil Windows | **PASSOU:** build, importações, GUI congelada, operações gráficas e upload de ZIP | [Actions — portáteis](https://github.com/SrTristeSad/brincadeira/actions/runs/42314562245) |
| Executável portátil Linux | **PASSOU:** build, importações e GUI congelada com Vulkan | [Actions — portáteis](https://github.com/SrTristeSad/brincadeira/actions/runs/42314562245) |
| Capturas Windows fontes × portátil | **PASSOU:** 61 capturas Vulkan idênticas entre fontes e binário | [Logs Windows do empacotamento](https://github.com/SrTristeSad/brincadeira/actions/runs/42314562245) |

Os logs registram `Forcing backend: Vulkan (6)`, renderização dos presets nativos WGSL, `GL_POINTS` e picking, além do funcionamento dos smokes de rig, pose, olhos, textura e exportação nos cenários exercitados.

**Importante:** as 61 capturas idênticas comparam **Vulkan-fonte × Vulkan-portátil**; **não** são imagens pareadas OpenGL × Vulkan. A CI utiliza Mesa/Lavapipe/llvmpipe (Vulkan por software), inclusive no Windows: não representa GPU física do usuário. Os testes de erro intencional podem emitir mensagens `ERROR` nos logs apesar de o teste correspondente passar; interpretar resultado do teste e contexto.

## Incompatibilidades reais confirmadas pela inspeção do código

1. **Shaders GLSL personalizados:** `lib/vulkan_shader.py` declara `Shader.supported() == False` e sua construção gera `NotImplementedError`. Há seis presets nativos WGSL reconhecidos; materiais externos com GLSL não estão automaticamente portados. **Estado: incompatibilidade conhecida.**
2. **Plugins externos com desenho imediato:** `lib/object3d.py`, métodos `Object3D.draw()` e `Object3D.pick()`, geram `NotImplementedError`. O rendering interno normal usa `CenaVulkan` e `mh.getPickedColor()`, mas extensões antigas que chamem essas APIs podem quebrar. **Estado: incompatibilidade conhecida.**
3. **Transparência de malhas entrelaçadas:** ordenação de objetos/triângulos e alpha blending foram implementados e exercitados para casos sintéticos, mas uma ordenação por centro não resolve interseções cíclicas, cabelo com camadas cruzadas ou todos os efeitos do OpenGL original. **Estado: paridade complexa não comprovada.**
4. **Recursos externos para casos realistas:** a árvore verificada tem `data/hair/clear.thumb` e nenhum arquivo versionado em `data/clothes/`. Não é possível homologar cabelo/roupa realistas apenas com os assets presentes. **Estado: teste não realizado por falta de caso representativo.**

## Validações que não foram executadas e bloqueiam o aceite final

- Executar em GPUs físicas e drivers NVIDIA/AMD/Intel sob Windows/Linux, inclusive desempenho, VRAM, resize e erros de dispositivo.
- Capturar cenas equivalentes no **MakeHuman original OpenGL** e no Vulkan para medir diferença de cor/alfa/picking/sombras sob a mesma câmera, modelo, material e luz.
- Testar plugins reais de terceiros, inclusive uso de `Object3D.draw/pick` e shaders GLSL personalizados; decidir se serão portados ou explicitamente excluídos do contrato de compatibilidade.
- Carregar roupas/cabelos reais licenciados com transparência complexa, poses, deformações e sobreposições; reproduzir defeitos e corrigir os comprovados.
- Validar exportações com aplicações consumidoras externas e uma campanha manual representativa de ferramentas do editor.

## Decisão técnica

A infraestrutura Vulkan pode ser usada como base da **próxima etapa de desenvolvimento**, preservando o código original e os testes verdes. Entretanto, o critério de conclusão de [ESCOPO.md](ESCOPO.md) (equivalência da interface e funcionalidades, exclusivamente Vulkan) **ainda não foi alcançado**. Não apresentar a migração como 100% compatível ou versão final, nem confundir lacunas de validação com funcionalidade comprovadamente ausente.

Este documento registra resultados reais de CI e inspeção de código, sem alegar testes manuais em GPU física.
