# DragonBones — núcleo JavaScript/TypeScript

Código-base original: [DragonBonesJS](https://github.com/DragonBones/DragonBonesJS), versão 5.7.0. Esta cópia permanece sob a licença MIT, com os avisos de autoria originais.

## Desenvolvimento

Requer Node.js 22+ para as ferramentas de desenvolvimento. Para verificar a
estrutura dos arquivos, entradas do pacote, licença e sintaxe dos testes **sem
instalar dependências**, execute:

```sh
cd DragonBonesJS/DragonBones
npm run test:preflight
```

Esse comando é uma pré-verificação e **não** compila nem executa o motor de animações.

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

## Dicionários internos de animação

`Animation.getBlendState()` agora cria também seus mapas aninhados com `Object.create(null)`, impedindo conflitos entre nomes de bones/slots e propriedades herdadas como `constructor` ou `__proto__`. O setter `animations` passou a copiar apenas as entradas próprias e enumeráveis da origem com `Object.keys()` (disponível em ES5), evitando importar propriedades herdadas. API pública, estrutura de animações e compatibilidade com ES5 preservadas.

Foram adicionados dois testes de regressão ao pacote. A compilação integral permanece pendente.

## Substituição de animações na fábrica

`BaseFactory.replaceAnimation()` agora copia somente as entradas próprias de cada catálogo de animações ao mesclar dados, usando `Object.keys()` (ES5). Isso evita propagar propriedades herdadas de objetos externos para o conjunto de animações do esqueleto. O modo de substituição total e a precedência das animações recebidas continuam iguais.

Foram acrescentados três testes de regressão. A compilação completa do motor permanece pendente.
