# DragonBones — núcleo JavaScript/TypeScript

Código-base original: [DragonBonesJS](https://github.com/DragonBones/DragonBonesJS), versão 5.7.0. Esta cópia permanece sob a licença MIT, com os avisos de autoria originais.

## Desenvolvimento

Requer Node.js 22+ para as ferramentas de compilação.

```sh
cd DragonBonesJS/DragonBones
npm install
npm test
```

`npm test` compila, minifica e executa os testes de regressão. Para gerar somente os artefatos:

```sh
npm run build
```

## Artefatos gerados

- `out/dragonBones.js`: biblioteca JavaScript, exportada pelo ponto de entrada principal do pacote.
- `out/dragonBones.d.ts`: declarações TypeScript geradas junto ao JavaScript.
- `out/dragonBones.min.js`: versão minificada.

Os comandos de build de Egret, PixiJS, Phaser, Hilo e Cocos foram retirados **apenas deste pacote isolado**, porque as integrações correspondentes não estão presentes nesta cópia. Isso não altera nenhum dos projetos ou motores existentes no repositório original.

**Estado de validação:** as configurações foram verificadas com um projeto TypeScript mínimo, mas o núcleo inteiro ainda precisa ser compilado e testado com todas as dependências. Não presuma que um `npm install` ou `npm test` já tenha passado nesta cópia.
