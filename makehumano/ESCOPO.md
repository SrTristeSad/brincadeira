# Escopo oficial do projeto MakeHumano

## Objetivo

**Modernizar o MakeHuman existente**, mantendo o programa original e suas
funcionalidades. As alterações solicitadas são **somente**:

1. **Atualizar o MakeHuman para versões modernas do Python** e as dependências
   necessárias à execução, corrigindo incompatibilidades sem mudar seu
   comportamento.
2. **Substituir a renderização OpenGL por Vulkan no próprio MakeHuman**, usando
   sua interface original e preservando o funcionamento das ferramentas.

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
- Identificar as chamadas e dependências de OpenGL do MakeHuman e adaptar
  apenas o caminho de renderização necessário para usar Vulkan.
- Integrar o backend Vulkan à **janela, ao ciclo de atualização e à viewport
  do MakeHuman original**, sem substituir seus controles por uma interface
  independente.
- Fazer testes de regressão e comparações necessárias para garantir que o
  programa continue funcionando, inclusive testes gráficos reais quando
  possíveis.
- Preservar o código original, os avisos de licença e mudanças pequenas,
  rastreáveis e reversíveis durante a migração.

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
- Existe um protótipo de Vulkan isolado em `motor_wgpu/`. Ele pode servir como
  **referência técnica para a migração**, mas **não substitui** o renderizador
  OpenGL da interface original.
- Recursos experimentais já desenvolvidos no protótipo são **histórico de
  pesquisa, não novos requisitos**. Não devem comandar os próximos trabalhos
  nem ser apresentados como conclusão do objetivo principal.
- Nenhum código existente deve ser apagado apenas para corrigir o planejamento.

## Ordem de execução

1. Verificar a inicialização e o uso do MakeHuman original com o Python-alvo,
   corrigindo incompatibilidades necessárias.
2. Mapear os pontos do OpenGL original, implementar o backend Vulkan e
   conectá-lo à viewport existente, por etapas verificáveis.
3. Validar as funções originais, arquivos e plugins no MakeHuman com Vulkan,
   corrigindo regressões causadas pela migração.
4. Preparar a execução e as instruções finais sem exigir o aplicativo
   experimental separado.

## Critério de conclusão

O pedido estará concluído **quando o MakeHuman original puder ser aberto e
utilizado com Python moderno, mantendo sua interface e funcionalidades, com
a viewport renderizada por Vulkan no lugar de OpenGL**. Testes de um
visualizador paralelo, sozinhos, não satisfazem esse critério.

Uma eventual ponte temporária, feature flag ou modo de contingência para
diagnóstico não altera a meta: **a renderização normal da interface original
deve funcionar por Vulkan**.

Este documento é a referência de escopo para as próximas alterações.
Qualquer ampliação exige decisão explícita do criador.
