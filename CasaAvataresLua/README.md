# CASA VIVA — casa 3D com dois avatares e 26 movimentos reais

Projeto **Lua + LÖVR 0.19** para desktop, com uma casa estilo diorama, agentes com necessidades e comunicação opcional. Você **não precisa do Blender para abrir a casa**.

## O que vem DE FATO no pacote

- `assets/avatar1.glb` e `assets/avatar2.glb`: **dois personagens 3D originais**, cada um com **26 clipes nomeados e animados dentro do arquivo**. São modelos estilizados simples, não humanos fotorrealistas do MakeHuman.
- `world.lua`: casa em 3D com jardim, piso, paredes, janelas, cozinha com eletrodomésticos, sala, sofá, tapete, mesa de jantar, escritório e quarto. O cenário é construído por Lua, sem depender de outros assets.
- `hud.lua`: barra de controles e de animações na própria janela, com botões de mouse.
- `agent.lua`, `navigation.lua`, `simulation.lua`: decisões por necessidades, deslocamento A*, um ou dois avatares e comunicação por falas predefinidas.

### Como executar

1. Baixe o **LÖVR 0.19** para Windows ou Linux: <https://lovr.org/downloads>.
2. Extraia o ZIP da Casa Viva ou baixe o projeto inteiro do GitHub.
3. No Windows, arraste a **pasta `CasaAvataresLua`** (que contém `main.lua`) até `lovr.exe`. Também pode arrastar `CasaVivaCorrigida.lovr` para o executável.
4. A casa abre com os dois personagens. Use os botões da tela para navegar e `ENTER` para reproduzir a animação selecionada.

**Não execute `main.lua` isoladamente.** Ele depende do LÖVR e dos arquivos do projeto.

## Controles

| Controle | Ação |
| --- | --- |
| Botões CASA/SALA/COZINHA/QUARTO ou F1–F4 | Ir para ambiente |
| Mouse esquerdo arrastar | Girar câmera |
| Mouse direito arrastar | Mover câmera |
| Roda ou Q/E | Zoom |
| Botões `‹`, `›` ou Z/X | Selecionar animação |
| Botão REPRODUZIR ou ENTER | Tocar animação |
| TAB | Alternar personagem |
| Botões 1 ou 2 | Quantidade de avatares |
| C | Ligar/desligar conversa |
| F | Seguir personagem |
| Espaço | Pausar simulação |
| L | Recarregar catálogo dos GLBs |
| H | Listar atalhos no console |
| M | Mostrar/ocultar painel |

### Os 26 movimentos já instalados

`idle`, `walk`, `run`, `sit`, `sleep`, `dance`, `wave`, `talk`, `read`, `cook`, `eat`, `work`, `stretch`, `exercise`, `think`, `observe`, `clean`, `laugh`, `relax`, `greet`, `explore`, `jump`, `clap`, `nod`, `celebrate`, `point`.

As animações foram criadas proceduralmente para os personagens incluídos. Não são motion capture. A navegação e a animação são independentes: a IA escolhe a tarefa, anda ao local e reproduz o movimento.

## Importar personagens do MakeHuman

Exportar um modelo no formato glTF/GLB, com esqueleto e seus clipes animados já incorporados. Colocar o arquivo em `assets/avatar1.glb` ou `assets/avatar2.glb`, substituindo o personagem de demonstração. O motor procura nomes de clipes como `idle`, `walk`, `dance`, etc. O Blender **não é necessário para usar arquivos GLB prontos**, mas pode ser necessário para adaptar uma animação FBX/BVH a um esqueleto diferente.

Guarde uma cópia dos avatares originais antes de substituir.

## Animações adicionais, inclusive +18

A Casa Viva **não contém cenas sexuais prontas**. O catálogo **não simula que uma cena existe**: só mostra as cenas extras que você colocou nas pastas de animações ou registrou explicitamente.

Para instalar um movimento extra, coloque **um GLB que já contenha o personagem inteiro e a animação** em:

```text
assets/
  animations/
    avatar1/
      extra_dance.glb
      adult_cena_01.glb
      dupla_adult_01.glb
    avatar2/
      dupla_adult_01.glb
```

Abra o projeto pela **pasta editável** (não pelo `.lovr` empacotado), aperte **L**, escolha o arquivo com Z/X ou nos botões de tela e aperte ENTER.

- `adult_...`: marcado como +18, executado **somente mediante comando manual**.
- `dupla_...`: animação para dois personagens, com tentativa de alinhamento e sincronização dos dois arquivos de mesmo nome.
- `dupla_adult_...`: animação para dois personagens, marcada como +18.
- Nomes aceitam letras, números, sublinhado e hífen. **GLB por avatar deve trazer corpo completo e animação**, não apenas dados de movimento.

O sistema **não faz retarget automático**, não converte FBX/BVH e não corrige pares que foram criados com rigs ou posicionamentos incompatíveis. É necessário ter autorização para usar e distribuir os arquivos, e utilizar apenas representações adultas e consensuais.

## Arquivos e manutenção

| Arquivo | Responsabilidade |
|---|---|
| `main.lua` | Loop do jogo, ações e mouse |
| `world.lua` | Arquitetura, paleta e móveis |
| `hud.lua` | Interface gráfica clicável |
| `camera.lua` | Orbitar, zoom e ambientes |
| `agent.lua` | Necessidades, prioridades e rotas |
| `navigation.lua` | Busca A* desviando dos obstáculos cadastrados |
| `simulation.lua` | Diálogos e ações em dupla |
| `avatars.lua` | Renderização e reprodução dos modelos |
| `animation_library.lua` | Descoberta de arquivos GLB |
| `settings.lua` | Nomes, personalidades e opções |
| `tools/gerar_avatares_demo.py` | **Código-fonte dos modelos originais**, editável (requer Python, numpy e trimesh apenas para gerar novamente) |
| `tests/` | Testes Lua sem GPU |

## Limitações reais

Os agentes utilizam regras de decisão, não uma LLM. A casa é um diorama 3D estilizado, não um clone gráfico de The Sims. Os modelos novos têm animações glTF originais, mas a aparência final e a importação no motor **precisam ser verificadas com o LÖVR instalado**; testes sem GPU não bastam para afirmar que tudo é renderizado corretamente.

Referência conceitual (sem copiar o código): [VoxelColony-LOVR](https://github.com/FilthyFrost/VoxelColony-LOVR). Os modelos GLB e código adicionados nesta atualização foram criados especificamente para Casa Viva.
