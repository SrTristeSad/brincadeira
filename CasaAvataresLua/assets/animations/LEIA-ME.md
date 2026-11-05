# Animacoes adicionais (GLB)

Para adicionar uma ação, coloque o arquivo .glb **com o personagem completo e a animacao embutida** em `avatar1/` ou `avatar2/`.

Exemplo:

```
assets/animations/avatar1/dance_extra.glb
assets/animations/avatar2/dance_extra.glb
assets/animations/avatar1/adult_cena_02.glb
assets/animations/avatar2/adult_cena_02.glb
assets/animations/avatar1/dupla_adult_02.glb
assets/animations/avatar2/dupla_adult_02.glb
```

Acoes com `adult_` ou `dupla_adult_` no nome sao tratadas como adultas; `dupla_` exige dois avatares e sincroniza o inicio das acoes.

O catalogo le os arquivos ao iniciar e ao apertar `L` (recarregar). `Z`/`X` escolhem a animacao, `ENTER` executa.

**Importante:** apenas clipes FBX/BVH ou um GLB contendo somente ossos nao bastam: este modo carrega o *modelo completo* por acao. Para reutilizar so o esqueleto de um avatar, primeiro combine e exporte como GLB com rig e animacao compatíveis numa ferramenta de autoria 3D. Este projeto NAO faz retargeting automatico.

Nao suba arquivos comerciais, proprietarios ou modelos sem permissao de redistribuir. Use apenas personagens adultos, cenas consentidas e assets de origem autorizada.
