# DragonBonesJS — área isolada de atualização

Esta pasta foi criada para trabalhar na atualização do [DragonBonesJS](https://github.com/DragonBones/DragonBonesJS), sem alterar arquivos ou diretórios fora de `DragonBonesJS/` neste repositório.

## Origem

- **Repositório original:** https://github.com/DragonBones/DragonBonesJS
- **Branch de referência:** `master`
- **Commit de referência verificado em 06/11/2026:** `64b6c69ae35777c2404be68c9192e2c56906079e`
- **Versão indicada no `package.json` original:** `5.7.0`
- **Licença do projeto original:** MIT (veja `LICENSE`).

## Situação atual

A pasta de trabalho está preparada. **O código do DragonBonesJS ainda não foi importado ou modernizado**; nenhum funcionamento foi reivindicado como testado.

O projeto original inclui um núcleo TypeScript e integrações distintas com PixiJS, Phaser, Egret, Cocos, Hilo e outros ambientes. A escolha das integrações e do objetivo da modernização deve ser definida antes de alterar o código.

## Regra de isolamento

Toda nova alteração deste trabalho deverá permanecer dentro de `DragonBonesJS/`. Não modificar `.github/`, `CasaAvataresLua/`, `MyPaint-Ibis-Lua/`, `makehumano/` ou quaisquer outros arquivos/diretórios fora desta pasta.

## Próxima etapa

Importar o código-fonte relevante preservando avisos de licença e autoria, levantar incompatibilidades atuais, atualizar o conjunto de ferramentas e validar o comportamento por meio de testes. A abrangência (biblioteca central ou integrações específicas) será definida antes da migração.
