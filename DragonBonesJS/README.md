# DragonBonesJS — modernização isolada (2026)

Este diretório é a única área autorizada de trabalho no repositório [SrTristeSad/brincadeira](https://github.com/SrTristeSad/brincadeira).

## Origem e licença

- Projeto original: [DragonBones/DragonBonesJS](https://github.com/DragonBones/DragonBonesJS)
- Fonte copiada: subprojeto `DragonBones/` do branch `master`, commit `64b6c69ae35777c2404be68c9192e2c56906079e` (24/05/2025)
- Versão declarada pelo projeto original: 5.7.0
- Licença MIT preservada em [LICENSE](./LICENSE) e nos cabeçalhos existentes.

## Primeira etapa — núcleo original com correções controladas

Foi importado apenas o núcleo `DragonBones/` em TypeScript, sem adicionar novas funcionalidades ou alterar deliberadamente os formatos de animação e a API pública. As integrações com motores gráficos ainda não foram copiadas nem atualizadas.

Alterações iniciais:

1. Protegidas hierarquias de `WorldClock` contra ciclos em `add()` e no setter `clock`.
2. Corrigido `WorldClock.clear()` para soltar referências sem interromper de forma insegura uma atualização em andamento.
3. Protegido o pool de `BaseObject` contra limpeza dupla e colisões com propriedades herdadas do JavaScript.
4. Corrigida a sequência de compilação do núcleo (`tsc` antes de `uglifyjs`) e atualizado o ambiente de compilação para TypeScript 5.8.3 e UglifyJS 3.19.3.
5. Removida a opção de compilação `watch` do `tsconfig.json`, rejeitada pelo TypeScript moderno.
6. Adicionados testes para manter a API pública tanto no build normal quanto no minificado, além de verificações da matemática original de matrizes.
7. Mantidos e ampliados os testes de regressão de `WorldClock` e `BaseObject`.
8. Corrigidos mapas internos indexados por nomes de ossos, slots, skins, animações, texturas e armaduras: agora usam dicionários sem protótipo para evitar colisões com chaves como `constructor` e `__proto__`.
9. Adicionados testes de regressão para preservar nomes válidos de elementos que colidem com propriedades herdadas.

## Compilar e testar

Requer Node.js 22+ para compilar e executar os testes, com acesso às dependências locais. O projeto de origem foi feito para ES5; a versão de Node.js especificada aqui se refere **somente às ferramentas de desenvolvimento**, não ao runtime do usuário final:

```sh
cd DragonBonesJS/DragonBones
npm install
npm test
npm run build
```

**Validação pendente:** um projeto mínimo com a configuração equivalente foi compilado com TypeScript 5.8.3 após remover `watch`, mas os testes e a compilação **do núcleo completo** ainda não foram executados com todas as dependências deste projeto. A revisão de código e verificações estáticas não substituem os testes de execução. A compatibilidade com versões atuais de TypeScript, PixiJS, Phaser e Cocos ainda não foi validada.

## Próximos passos

- Executar e estabilizar o build e os testes do núcleo.
- Executar o build completo com TypeScript 5.8.3 e ajustar eventuais erros sem alterar a API pública.
- Refatorar código legado e melhorar segurança de memória e desempenho, sem alterar o comportamento público esperado.
- Avaliar integrações com motores gráficos somente depois da estabilização do núcleo.

**Regra:** todos os arquivos alterados ou adicionados neste trabalho devem permanecer dentro de `DragonBonesJS/`. Não modificar outras pastas do repositório.

## Etapa de empacotamento (em revisão)

- `DragonBones/package.json` passa a declarar caminhos reais de entrada JavaScript e de tipos TypeScript, mantendo a saída ES5 existente.
- O pacote inclui a própria cópia da licença MIT e declara os artefatos gerados como conteúdo distribuível.
- Comandos antigos para integrações gráficas ausentes são removidos apenas do subpacote `DragonBones/`.
- Testes adicionais verificam, após o build, se os pontos de entrada existem e se o pacote pode ser carregado pelo Node.
- **Não há execução confirmada do build integral**: qualquer falha remanescente do TypeScript 5.8.3 precisa ser corrigida antes de considerar o núcleo estável.

## Compatibilidade da herança TypeScript (em revisão)

O código original sobrescrevia a variável global `__extends` com um helper antigo para Weixin. Ao compilar com TypeScript 5.8 para ES5, essa implementação substituía a versão gerada pelo compilador e perdia a ligação entre construtores usados na herança estática. Removemos somente esse helper legado, permitindo que o compilador forneça sua implementação, e adicionamos dois testes de regressão de herança, sem alterar as classes nem a API pública.

Uma reprodução isolada com TypeScript 5.8.3 e Node.js 22 confirmou a diferença entre o helper antigo e o helper gerado pelo compilador. **Os testes do núcleo completo ainda não foram executados.**

## Estabilidade do relógio de animação (em revisão)

O `WorldClock` agora libera referências imediatamente em `remove()` e `clear()` quando não há atualização em andamento, reduzindo o acúmulo de posições vazias entre quadros. Durante `advanceTime()`, as remoções continuam sendo adiadas até o término da atualização mais externa. O bloco `finally` também libera posições após exceções em callbacks. Não há alteração intencional da API pública ou do formato de animações.

Foram acrescentados cinco testes de regressão, totalizando **31 testes definidos** no núcleo. Em uma reprodução **isolada** do relógio, compilada com TypeScript 5.8.3 e executada com Node 22, sete casos de referência passaram; **isso não substitui a execução de `npm test` no projeto DragonBonesJS completo**, que segue pendente.

## Correção de identificação do pool (em revisão)

O pool de `BaseObject` não usa mais `String(constructor)` como chave. Duas classes distintas podem ter o mesmo `toString()`, especialmente após minificação, e acabavam recebendo objetos uma da outra. Agora os identificadores internos são atribuídos pela **identidade do construtor**, sem alterar métodos públicos nem exigir APIs novas de runtime. A troca usa um registro de construtores em memória e mantém o alvo ES5. Foram acrescentados três testes de regressão.

O defeito foi reproduzido em JavaScript isolado; o build completo e a suíte completa do núcleo ainda precisam ser executados.

## Correção de troca de relógio (em revisão)

Ao transferir um objeto que implementa `IAnimatable` com `clock` como propriedade simples, o `WorldClock.add()` agora o remove explicitamente do relógio anterior antes de associá-lo ao novo. Sem isso, o objeto podia receber atualizações duas vezes (uma de cada relógio). Foram adicionados três testes de regressão para transferências normais, transferências durante a atualização e adições repetidas. A interface pública permanece igual.

O comportamento anterior e a correção foram reproduzidos num caso JavaScript isolado. A suíte completa do DragonBonesJS ainda não foi executada.
