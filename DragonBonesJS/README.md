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

1. Corrigido o risco de recursão infinita em `WorldClock` ao tentar criar ciclos entre relógios via `add()` ou pelo setter `clock`.
2. Corrigido o script `build` para compilar antes de minificar, com execução sequencial via `&&`, mantendo as dependências de origem nesta primeira etapa.
3. Adicionados testes de regressão para avanço de tempo, remoção, limpeza e ciclos em `WorldClock`.

## Compilar e testar

Requer Node.js 18+ para executar os testes, com acesso às dependências locais:

```sh
cd DragonBonesJS/DragonBones
npm install
npm test
npm run build
```

**Validação pendente:** os testes e a compilação ainda não foram executados com todas as dependências deste projeto. A compatibilidade com versões atuais de TypeScript, PixiJS, Phaser e Cocos ainda não foi validada.

## Próximos passos

- Executar e estabilizar o build e os testes do núcleo.
- Modernizar dependências e TypeScript de forma incremental e testada.
- Refatorar código legado e melhorar segurança de memória e desempenho, sem alterar o comportamento público esperado.
- Avaliar integrações com motores gráficos somente depois da estabilização do núcleo.

**Regra:** todos os arquivos alterados ou adicionados neste trabalho devem permanecer dentro de `DragonBonesJS/`. Não modificar outras pastas do repositório.
