# Escopo oficial do projeto MakeHumano

## Objetivo

**Modernizar o MakeHuman existente**, mantendo o programa original e suas
funcionalidades. As alterações solicitadas são **somente**:

1. **Atualizar o MakeHuman para versões modernas do Python** e as dependências
   necessárias à execução, corrigindo incompatibilidades sem mudar seu
   comportamento.
2. **Remover por completo o motor gráfico OpenGL e substituí-lo por Vulkan**
   no próprio MakeHuman, preservando a interface original e suas ferramentas.
   Vulkan será o **único backend gráfico** do programa final: sem engine
   OpenGL paralela, modo de compatibilidade ou fallback permanente.

**Não é objetivo criar um novo editor, reescrever o MakeHuman nem acrescentar
funcionalidades.** O MakeHumano é uma modernização técnica do programa
existente, não um produto separado.

## O que deve ser preservado

A interface, a experiência de uso e o comportamento já existentes:
modelagem e controles anatômicos, personagens, morph targets, materiais e
texturas, acessórios/roupas, esqueleto, poses, arquivos, exportações e plugins,
na medida em que a aplicação original os suporta.

Uma diferença de comportamento introduzida pela modernização é **regressão
a corrigir**, não oportunidade para redesenhar a funcionalidade. Compatibilidade
com arquivos e plugins deve ser verificada, não presumida.

## Trabalho autorizado

- Diagnosticar e corrigir problemas de Python, Qt, NumPy e dependências que
  impeçam o MakeHuman original de executar nas versões modernas de Python.
- Auditar todas as dependências de OpenGL do MakeHuman original e
  **substituir a infraestrutura gráfica inteira**, não apenas a viewport:
  canvas/contexto, renderização de malhas e sobreposições, buffers, texturas,
  shaders, iluminação, picking/seleção, depth, capturas de tela,
  renderização fora da tela e integrações gráficas dos plugins.
- Migrar shaders GLSL e recursos específicos de OpenGL para implementações
  Vulkan equivalentes, preservando resultados e operações do aplicativo.
- Eliminar PyOpenGL das dependências, remover imports/chamadas OpenGL do
  caminho de execução e desativar/substituir recursos e plugins exclusivos
  de OpenGL. Após verificar a equivalência funcional, retirar os módulos
  obsoletos da árvore ativa, preservando o histórico no Git.
- Integrar o backend Vulkan à **janela, ao ciclo de atualização e à viewport
  do MakeHuman original**, sem substituir seus controles por uma interface
  independente.
- Fazer testes de regressão e comparações necessárias para garantir que o
  programa continue funcionando, inclusive testes gráficos reais quando
  possíveis.
- Preservar os recursos, o comportamento original e os avisos de licença.
  Durante a migração, manter alterações rastreáveis e reversíveis; **após
  equivalência comprovada**, eliminar o motor OpenGL em vez de mantê-lo
  permanentemente instalado ou disponível como alternativa.

## Fora do escopo

Salvo nova autorização explícita do criador, **não desenvolver**:

- Um aplicativo ou editor paralelo para substituir a interface do MakeHuman.
- Novos controles corporais, recursos artísticos ou ferramentas de edição.
- Novos sistemas de roupas, materiais, rigging, poses, animação, exportação
  ou formatos próprios não necessários à migração.
- Melhorias cosméticas, remodelagem da interface ou funcionalidades extras.
- Uma reconstrução manual de recursos que já existem no MakeHuman.

## Situação do trabalho já feito

- A cópia do MakeHuman original está em `codigo/makehuman/`.
- Foram feitos ajustes e testes iniciais de compatibilidade com Python moderno,
  mas a compatibilidade completa do aplicativo precisa ser verificada.
- O antigo editor Vulkan independente foi removido da árvore ativa por decisão
  do criador. Seu histórico permanece no Git.
- A implementação atual usa Vulkan como backend da janela original e não
  requer PyOpenGL. Isso ainda **não comprova equivalência funcional**:
  shaders GLSL personalizados, plugins externos, seleção e transparência
  complexa, além de operações legadas como `Object3D.draw/pick`, exigem
  migração ou validação adicional. O trabalho permanece em desenvolvimento.
- Auditoria inicial encontrou dependências diretas em `lib/qtui.py`
  (`QOpenGLWidget`), `lib/glmodule.py`, `lib/shader.py`,
  `lib/texture.py`, `lib/mh.py`, shaders GLSL, no plugin
  `plugins/4_rendering_opengl/` e em `codigo/requirements.txt`
  (`PyOpenGL`). Isso não é uma lista exaustiva.
- Recursos do antigo editor independente são **histórico de pesquisa, não novos
  requisitos**. Não devem comandar os próximos trabalhos nem ser apresentados
  como conclusão do objetivo principal.
- O código da aplicação original não deve ser apagado apenas para corrigir o
  planejamento; remoções do motor OpenGL dependem de equivalência validada.

## Ordem de execução

1. Verificar o MakeHuman original com o Python-alvo e corrigir as
   incompatibilidades necessárias à execução.
2. Mapear integralmente as dependências do motor OpenGL, incluindo interfaces
   de renderização utilizadas por `mh.py`, pela GUI e por plugins.
3. Implementar o motor Vulkan e conectá-lo à interface **original**,
   preservando renderização, seleção, texturas, shaders, capturas e plugins.
4. Validar as funções, arquivos e plugins originais com Vulkan e corrigir
   regressões. OpenGL pode existir **apenas transitoriamente** durante
   a migração em desenvolvimento, nunca como backend do produto final.
5. Eliminar os módulos OpenGL obsoletos, referências ativas ao PyOpenGL,
   shaders exclusivamente GLSL e plugins de OpenGL substituídos. Validar que
   a aplicação inicia e opera **sem PyOpenGL nem contexto OpenGL**.
6. Documentar a execução do próprio MakeHuman atualizado, sem editor
   experimental separado.

## Critério de conclusão

O pedido estará concluído **quando o MakeHuman original puder ser aberto
e utilizado com Python moderno, mantendo sua interface e funcionalidades
com o motor gráfico inteiro executado exclusivamente por Vulkan**.

A validação de conclusão exige demonstrar que:
- Não há dependência obrigatória de `PyOpenGL`, `QOpenGLWidget` ou contexto
  OpenGL para iniciar, modelar, selecionar, usar plugins ou exportar.
- O caminho gráfico normal usa exclusivamente Vulkan, sem fallback OpenGL.
- As funcionalidades gráficas equivalentes existentes foram verificadas.
- O OpenGL obsoleto foi retirado do código ativo após a migração; a história
  original permanece acessível pelo Git e com seus créditos/licenças.
- O MakeHuman atualizado funciona **na interface original**, não em um editor
  separado.

Testes isolados do piloto Vulkan **não satisfazem**, por si sós, esses critérios.

Este documento é a referência de escopo para as próximas alterações.
Qualquer ampliação exige decisão explícita do criador.
