# Casa Viva — simulador de vida 3D com Lua

Casa virtual mobiliada com **um ou dois agentes autônomos** no [LÖVR](https://lovr.org/). A casa, a navegação, os comportamentos e o catálogo de animações são editáveis em Lua. Usa bonecos 3D provisórios se você ainda não tiver avatares do MakeHuman.

## Executar

1. Baixe o LÖVR para seu sistema (desktop; LÖVR 0.19+): https://lovr.org/downloads
2. Baixe a pasta `CasaAvataresLua` do GitHub ou extraia o ZIP.
3. Windows: arraste a **pasta** para cima do `lovr.exe`, ou rode `lovr.exe "C:\caminho\CasaAvataresLua"`.
4. Aperte **F1** para ver a casa toda, **F2** sala, **F3** cozinha ou **F4** quarto.

Não execute `main.lua` diretamente: o programa precisa do motor LÖVR.

## Controles simples

| Controle | Função |
|---|---|
| **Arrastar mouse esquerdo** | Girar câmera |
| **Arrastar mouse direito** | Deslocar foco da câmera |
| **Roda do mouse**, Q/E | Aproximar / afastar |
| **F1 / F2 / F3 / F4** | Casa / sala / cozinha / quarto |
| **F** | Seguir / deixar de seguir avatar |
| **TAB** | Selecionar avatar |
| **1 / 2** | Usar um ou dois avatares |
| **Z / X** | Escolher animação anterior / próxima |
| **ENTER** | Executar animação escolhida |
| **L** | Recarregar catálogo e arquivos GLB |
| **T** | Executar animação e avançar (compatibilidade) |
| **C** | Ligar / desligar conversa automática |
| **ESPAÇO** | Pausar / continuar |
| **M** | Mostrar / ocultar painel |
| **H** | Ajuda no terminal e lista das animações |
| **R / ESC** | Reiniciar / sair |

As teclas **W/A/S/D** ou setas também giram a câmera.

## Adicionar muitos movimentos e animações adultas (+18)

**Método mais fácil do projeto:** importe um arquivo `.glb` por ação, contendo **o corpo inteiro do seu personagem com a animação embutida**. Coloque na pasta correspondente:

```text
CasaAvataresLua/
  assets/
    avatar1.glb                       <- corpo principal opcional
    avatar2.glb
    animations/
      avatar1/
        extra_dance.glb               <- ação extra de um avatar
        adult_cena_02.glb             <- ação adulta individual
        dupla_adult_02.glb            <- ação adulta em dupla
      avatar2/
        extra_dance.glb
        dupla_adult_02.glb            <- mesmo nome para a segunda pessoa
```

1. Coloque um ou quantos arquivos `.glb` quiser nessas duas pastas (IDs somente letras, números, `_` e `-`).
2. Aperte **L** dentro da casa para descobrir as animações. **Z/X** percorrem o catálogo; **ENTER** executa.
3. O prefixo `adult_` identifica ações +18. O prefixo `dupla_` identifica uma cena sincronizada para dois avatares. `dupla_adult_` combina ambos.
4. Para cadastrar nomes bonitos, duração e regras, edite **`settings.lua` → `animacoesExtra`**. Para esconder as entradas +18, defina `animacoesAdultas = false`.

Para uma cena em dupla, os dois agentes se aproximam e iniciam os clipes sincronizados quando ambos chegam. Os GLBs devem conter movimentos pareados e sincronizáveis; **a sincronização por si só não corrige poses, rigs, alinhamento ou colisão**. A ação é somente manual: os agentes não escolhem espontaneamente cenas adultas.

**Limitações reais:** não existe conversão automática de FBX/BVH ou retargeting entre esqueletos; um GLB que contenha apenas os ossos e animação não substitui um personagem completo neste método. A importação direta de um pacote Mixamo feito para outro esqueleto **não é garantida**. Em geral, é preciso exportar cada personagem já animado em GLB a partir de software compatível (por exemplo Blender). Modelos e animações não acompanham o projeto.

Use somente modelos de **personagens adultos**, animações **consensuais** e arquivos para os quais tenha direito de uso. Não coloque assets proprietários no repositório público sem licença de redistribuição.

### Se os movimentos já estiverem no avatar principal

`assets/avatar1.glb` e `assets/avatar2.glb` também podem conter vários clipes internos. A Casa Viva procura nomes como `walk`, `idle`, `dance` etc. Para associar nomes diferentes, adicione `aliases = {'Nome do clipe'}` na ação correspondente em `settings.lua`.

## Como os agentes funcionam

- Os NPCs avaliam fome, energia, diversão, personalidade e penalizações para ações repetidas.
- A navegação usa **A*** em uma grade 2D, desviando dos móveis cadastrados.
- Cada um pode agir sozinho; se houver dois e a comunicação estiver ligada, eles podem se encontrar e trocar falas predefinidas.
- Essa é uma **simulação por regras**, não uma LLM nem um clone completo de The Sims.

Inspirado conceitualmente pelos agentes de utilidade e navegação do projeto [VoxelColony-LOVR](https://github.com/FilthyFrost/VoxelColony-LOVR). **O código da Casa Viva foi escrito separadamente**: o código do VoxelColony não foi copiado, pois não localizamos uma licença de reutilização explícita no repositório consultado.

## Arquivos

- `main.lua`: entrada, câmera, painel e teclado/mouse.
- `camera.lua`: vistas e acompanhamento do personagem.
- `navigation.lua`: algoritmo A* e obstáculos.
- `agent.lua`: regras de decisão e necessidades dos personagens.
- `simulation.lua`: encontro, comunicação, ações em dupla.
- `animation_library.lua`: reconhecimento automático e catálogo de GLB.
- `avatars.lua`: importação, animação e bonecos provisórios.
- `world.lua`: casa e móveis em formas geométricas.
- `settings.lua`: nome, quantidade, personagens e cenas adicionais.
- `tests/*.lua`: testes de lógica independentes de GPU.

## Testes e compatibilidade

Os testes Lua podem rodar sem LÖVR: `lua tests/test_sim.lua`, `lua tests/test_navigation.lua`, `lua tests/test_pair.lua`, `lua tests/test_library.lua`, `lua tests/test_camera.lua`, `lua tests/test_glb_mock.lua` e `lua tests/test_render_mock.lua`. O último testa uma **interface gráfica simulada**, não uma renderização GPU real.

**Importante:** o projeto não é uma integração direta do jogo VoxelColony. Ele aproveita as ideias de pathfinding A* e prioridades dos NPCs para uma casa com dois avatares. A biblioteca de GLBs serve para *avatares completos já animados*; não converte automaticamente pacotes FBX de terceiros.
