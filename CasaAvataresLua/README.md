# CASA VIVA — Casa 3D com 1 ou 2 agentes em Lua

Um protótipo **editável** que usa [LÖVR](https://lovr.org/), um motor 3D gratuito baseado em Lua.
Ele abre uma casa mobiliada e põe nela **um ou dois personagens que agem automaticamente**.
Não precisa de Blender nem de arquivos de avatar para testar o cenário.

## Como executar no Windows

1. Baixe e extraia o LÖVR em https://lovr.org/ (versão atual 0.19+ recomendada).
2. Extraia o arquivo `CasaAvataresLua.zip`.
3. **Arraste a pasta `CasaAvataresLua` para cima do arquivo `lovr.exe`**. Alternativamente, use o terminal:

   ```bat
   lovr.exe "C:\CAMINHO\CasaAvataresLua"
   ```

No Linux e macOS, passe o caminho da pasta como argumento para o executável LÖVR.
**Não tente abrir `main.lua` sozinho**: é preciso abrir o projeto com LÖVR.

## Teclas

| Tecla | Ação |
|:---|:---|
| `1` | Mostrar somente um avatar; não há comunicação |
| `2` | Mostrar dois avatares |
| `C` | Ligar/desligar diálogo automático quando há 2 avatares |
| `TAB` | Escolher avatar 1 ou 2 |
| `T` | Executar a próxima ação/animação do avatar selecionado (teste de 7 s) |
| `ESPAÇO` | Pausar/continuar a simulação |
| `A` e `D`, ou setas esquerda/direita | Girar a câmera |
| `W` e `S`, ou setas cima/baixo | Inclinar a câmera |
| `Q` e `E`, ou rodinha do mouse | Afastar/aproximar |
| `H` | Imprimir controles no terminal |
| `R` | Reiniciar agentes |
| `ESC` | Sair |

## Ações e animações

Há **21 ações reconhecidas**:

`idle`, `walk`, `run`, `sit`, `sleep`, `dance`, `wave`, `talk`, `read`, `cook`,
`eat`, `work`, `stretch`, `exercise`, `think`, `observe`, `clean`, `laugh`,
`relax`, `greet` e `explore`.

Os **bonecos provisórios** se movimentam por animações geradas por código (poses e
movimento de braços, pernas e corpo). Algumas ações compartilham variações de pose.

Os modelos **GLB próprios não recebem automaticamente 21 animações esqueléticas**.
O motor utiliza os clipes que JÁ vierem no GLB; encontra nomes aproximados como
`Walking`, `Run`, `Idle`, `Dance`, etc. Para ações sem clipe compatível, usa
`Idle`, se existir, ou deixa o personagem na pose original. Assim, por exemplo,
para um MakeHuman realizar animações de dança com os braços, você precisará
importar um arquivo GLB *já animado*.

## Como substituir os bonecos pelos avatares do MakeHuman

1. Prepare/exporte o personagem do MakeHuman com esqueleto (rig).
2. No Mixamo, Blender ou outra ferramenta, associe animações compatíveis ao
   esqueleto. Dependendo do arquivo, isso exigirá **retargeting** (transferência
   de animações entre rigs). Não existe compatibilidade garantida entre todos
   os rigs ou pacotes.
3. Exporte o resultado como **GLB (.glb), com as animações incorporadas**.
   O motor não aceita FBX/BVH diretamente.
4. Coloque os arquivos nesta pasta:

   ```text
   CasaAvataresLua/
     assets/
       avatar1.glb
       avatar2.glb
   ```

5. Abra/reinicie o projeto. Para ajustar nome, personagem, roupa, orientação
   ou altura, modifique `settings.lua`.
6. Se o personagem estiver olhando para trás, altere `rotacao = math.pi` em
   `settings.lua`. A escala é calculada automaticamente para 1,72 m por padrão.

> Atenção: dependendo da origem do GLB e dos movimentos disponíveis, algumas
> poses de interação com móveis ainda precisarão de ajustes de posicionamento.
> O projeto não vem com modelos MakeHuman ou bibliotecas comerciais/NSFW.

## Como os agentes funcionam

São **agentes locais baseados em regras** (sem LLM, sem acesso à internet):

- Cada agente acompanha energia, fome, socialização e diversão.
- Escolhe uma ação e caminha até o local adequado; o caminho desvia de móveis
  cadastrados na grade de navegação.
- Quando há 2 agentes e a opção de comunicação está ligada, os dois podem se
  encontrar e trocar falas predefinidas. As falas ficam perto dos personagens;
  o histórico de até 8 falas é mantido em `sim.historico`.
- Com um só agente, **não existe diálogo entre agentes**.
- Sem modelos externos, tudo funciona em modo demonstrativo.

Para integrar uma IA real no futuro, é possível substituir a rotina de decisão
em `agent.lua` e a comunicação em `simulation.lua` por um serviço externo. Isso
**não está incluído** nesta versão.

## Arquivos do projeto

| Arquivo | Responsabilidade |
|:---|:---|
| `main.lua` | Câmera, controles, inicialização e renderização |
| `conf.lua` | Janela e configurações do motor 3D |
| `settings.lua` | Preferências, personagens, quantidade e comunicação inicial |
| `world.lua` | Desenha a casa e os móveis |
| `navigation.lua` | Busca de caminhos por grade para evitar móveis |
| `agent.lua` | Estados, necessidades, objetivos e comportamento |
| `simulation.lua` | Coordena os agentes e o diálogo entre eles |
| `avatars.lua` | Bonecos 3D provisórios e reprodução de GLBs animados |
| `assets/` | Lugar reservado para seus personagens 3D |
| `tests/` | Verificações de comportamento em Lua |

## Limitações honestas

- Protótipo, não jogo completo: não há colisões físicas entre os dois agentes.
- Móveis são construídos com primitivas geométricas, não modelos realistas.
- As conversas são predefinidas e não representam inteligência geral.
- Não há sincronização automática de animações de dois humanos nem interação
  física sofisticada entre eles.
- Os arquivos dos seus personagens 3D precisam ser fornecidos por você.
- Não há uma validação visual no LÖVR neste ambiente; a lógica Lua tem testes
  automatizados separados.

**Fontes técnicas:** https://lovr.org/docs/Model ;
https://lovr.org/docs/Model:animate ; https://lovr.org/docs/lovr.conf
