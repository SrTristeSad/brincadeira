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

## Carregamento em módulos (AMD / exports)

O adaptador legado agora registra a saída AMD **sem uma dependência circular sobre `dragonBones`** e preenche o objeto fornecido em ambientes que expõem apenas `exports`, em vez de simplesmente reatribuir uma variável local. O caminho CommonJS (`module.exports`) e o fallback global continuam preservados. O alvo da compilação permanece ES5.

O defeito e a correção foram reproduzidos num módulo TypeScript mínimo compilado com TypeScript 5.8.3 e executado em Node.js 22. Os quatro novos testes de distribuição exercitam os dois artefatos do projeto, após o build completo.

### Ordem de inicialização das exportações

O adaptador AMD/CommonJS/`exports` foi extraído de `core/DragonBones.ts` para `core/ModuleExports.ts` e adicionado **por último** ao `tsconfig.json`. Assim, todos os membros de `dragonBones` já existem quando a distribuição os exporta. Isso corrige especialmente o caminho `exports` sem módulo CommonJS, que antes recebia somente classes declaradas no primeiro arquivo. A interface pública e o formato ES5 continuam preservados. O verificador estrutural impede que o adaptador volte a ser compilado antes do núcleo.

Validado em reprodução TypeScript 5.8.3 (`outFile`, ES5) com três arquivos de classes e adaptador ao final: AMD, CommonJS e `exports` receberam todas as classes no Node 22. A execução do projeto completo permanece pendente.

## Ordenação de ossos e referências inválidas

`ArmatureData.sortBones()` agora verifica se uma volta completa na lista não conseguiu ordenar nenhum osso. Em esqueletos válidos, preserva a ordem determinada pelas relações entre pais e restrições; em dados inválidos (ciclos ou referências ausentes), lança um erro identificável e **restaura a ordem original dos ossos** antes de interromper. Isso substitui um laço potencialmente infinito sem alterar a API. Quatro testes foram adicionados para hierarquias válidas e dependências impossíveis.

## Limpeza reentrante de WorldClock

`WorldClock.clear()` agora mantém os índices estáveis enquanto desconecta objetos, mesmo com setters de relógio reentrantes. O método remove entradas desconectadas por compactação em `finally`, sem perder objetos novos registrados durante a própria limpeza. Uma exceção em um setter não deixa lacunas permanentes nem exclui automaticamente os outros objetos pendentes. A compactação também foi centralizada em um método privado compartilhado com `advanceTime()`.

Cinco cenários de regressão foram adicionados. A lógica correspondente foi compilada isoladamente para ES5 com TypeScript 5.8.3 e passou em 5/5 testes Node.js 22. A suíte completa do motor continua pendente.

## Fila de ações em Armature.advanceTime()

A execução das ações pendentes da armadura agora retira cada ação da fila **antes** de chamar `fadeIn()`. Ações adicionadas por callbacks (no início ou no fim) são executadas em sequência sem repetir uma entrada já processada. A devolução ao pool ocorre em `finally`: se o callback falhar, a ação já consumida não é repetida, e as demais permanecem disponíveis para o frame seguinte. O tratamento de tipos, a API e o formato original das animações são preservados. Cinco testes de regressão foram adicionados em `armature-update.test.cjs`. Uma reprodução isolada compilada para ES5 com TypeScript 5.8.3 passou em 5/5 testes; o build completo permanece pendente.

## Limites de objetos em pool

`BaseObject.setMaxCount()` normaliza capacidades fracionárias para o inteiro inferior com `Math.floor()` (ES5). Antes, reduzir um pool já preenchido para uma capacidade como `1.5` lançava `RangeError` ao atribuir um número fracionário a `Array.length`. Limites inteiros continuam iguais; valores negativos e `NaN` continuam equivalentes a zero, enquanto `Infinity` continua permitindo capacidade sem limite explícito. Quatro testes de regressão foram adicionados.

Uma reprodução isolada desse gerenciamento de pools foi compilada para ES5 com TypeScript 5.8.3 e executada com Node.js 22.16.0: **2/4 testes passavam antes da correção e 4/4 depois**. A compilação integral do DragonBonesJS e a execução dos testes reais seguem pendentes.

## Inicialização do cache de animações

`AnimationData.cacheFrames()` inicializa explicitamente **todas** as posições de `cachedFrames` com `false`. A versão anterior consultava `this.cacheFrames.length` (quantidade de parâmetros do método) em vez de `this.cachedFrames.length` (tamanho do array), deixando a maioria dos flags como lacunas. A mudança não altera o layout, a taxa de cache, os índices de ossos/slots nem os formatos de animação.

Quatro testes de regressão foram adicionados em `tests/animation-cache.test.cjs`. Uma reprodução isolada da lógica existente, compilada para ES5 com TypeScript 5.8.3, apresentou **2/4 testes aprovados antes** e **4/4 depois** no Node.js 22.16.0. O build integral do projeto continua pendente.
