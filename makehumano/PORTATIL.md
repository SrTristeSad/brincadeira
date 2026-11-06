# Pacote portátil Vulkan de testes

O workflow `empacotar-makehumano.yml` constrói o **MakeHuman original** em
Windows x64 e Linux x64 com Python 3.12, Qt, NumPy, wgpu-native e rendercanvas.
O pacote continua experimental. Nenhum fallback OpenGL é instalado.

## Executar no Windows

1. Extraia **todo** o ZIP em uma pasta gravável. Não abra o `.exe` dentro do ZIP.
2. Execute `Iniciar-MakeHumano.bat`. Não é necessário instalar Python.
3. É necessário um driver de vídeo com suporte Vulkan. Atualize o driver do
   fabricante se a criação do dispositivo Vulkan falhar.
4. Em caso de falha, envie `MakeHumano-inicializacao.txt` e, quando existir,
   `MakeHumano-erro.txt`, da pasta do executável.

O iniciador captura stdout/stderr para preservar também diagnósticos nativos
Qt/wgpu. Falhas Python não tratadas são registradas mesmo ao abrir o executável
diretamente. Uma falha fatal ao criar a cena Vulkan é informada e encerra a
aplicação com código 1, em vez de manter uma viewport vazia em loop. A CI
Windows também testa intencionalmente um runtime inexistente. Erros ao criar o perfil do usuário retornam falha ao sistema,
em vez de encerrar com sucesso. Os personagens continuam na pasta de usuário
original do MakeHuman; apenas os testes usam um perfil temporário.

Para testar a opção original de suavização, execute no terminal da pasta:

```bat
Iniciar-MakeHumano.bat --multisampling
```

Isso ativa MSAA 4x e permite Alpha to Coverage nos materiais translúcidos.
Sem o argumento, o modo padrão continua sem MSAA. A suavização é independente
das [sombras Vulkan](SOMBRAS-VULKAN.md), controladas pelos materiais e luzes.

## O que a CI exige do executável

O autoteste de importação continua verificando `mhmain` e `cProfile`, mas não
basta para publicar o artefato. O teste completo abre o executável congelado e
exige simultaneamente:

- conclusão da inicialização da GUI, plugins e targets;
- quadro da cena original `G.world` usando um adaptador Vulkan;
- picking, framebuffer offscreen, `renderToBuffer`, `renderAlphaMask`, `renderSkin`;
- projeção UV com coordenadas 3D/4D e matrizes, pintura acumulada e destino luminância/alfa;
- displacement alterando silhueta e picking, intensidade zero, atualização do mapa e preservação da malha;
- ferramenta mapImageGL original na malha real, pintura visível na viewport sem sobrescrever o arquivo;
- execução dos seis presets oficiais WGSL, normal maps e composição alfa;
- alteração real da malha pelo modificador `macrodetails/Age`, undo e redo no histórico original;
- rig oficial e T-pose deformando a malha e a imagem, undo/redo e roundtrip MHM com rig/pose;
- reprodução de dois quadros e parada sem looping, verificando coordenadas do personagem;
- PNG UV 2048x2048 pelo exportador original, sem fallback CPU; índices UV uint32 sem compactação em 16 bits;
- BVH original com animação de dois quadros, recarga e comparação das poses locais dos 163 ossos mesmo após skinning;
- FBX/Collada com esqueleto, leitura independente de ossos, índices, pesos e matrizes;
- mapas especulares, transparência, bump e AO, incluindo intensidade zero, altura constante e prioridade dos normal maps;
- sombras opacas/recortadas, alfa de textura/vértice, opacidade, mapa de transparência e transmissão escalar por camadas;
- penumbra de área, controles originais Cast/Receive e persistência .mhmat;
- foco, ângulo, atenuação e emissão de área, incluindo energia normalizada, tamanho zero e eventos dos widgets originais;
- MSAA 4x, bordas diagonais e controle original Alpha to Coverage;
- salvamento e recarregamento `.mhm`, com comparação das coordenadas;
- exportação OBJ com vértices/faces, FBX binário com cabeçalho, Collada com geometria XML e STL binário com contagem/tamanho dos triângulos;
- carregamento dos plugins de modificadores, materiais, OBJ, FBX, Collada e STL;
- resposta do controle wireframe, com arestas pretas e imagem diferente da superfície sólida;
- processo ainda vivo e ausência de traceback ou erro de render no log;
- segunda abertura do portátil com `--multisampling`, desde a inicialização;
- no Windows, igualdade exata de 53 capturas PNG entre fontes e executável. As
  capturas só são geradas após terminar a carga da iluminação, plugins e targets.

Isso **não** comprova equivalência visual dos shaders, todos os controles da
interface ou todos os formatos/opções de exportação. Os quatro formatos citados
são exportados com a malha original e olhos padrão, e FBX/Collada também
com o rig oficial em repouso. Animações FBX/Collada, outras opções BVH, roupas externas e
importação desses arquivos em outras aplicações ainda exigem validação.

No Windows, a CI instala Mesa/Lavapipe e seu loader Vulkan para renderizar por
CPU no runner sem GPU física. O driver de teste Lavapipe MSVC 26.2.6 é baixado com SHA-256 verificado;
o loader vem do MSYS2. O ICD é registrado temporariamente na VM de CI,
porque o loader ignora a seleção por variável de ambiente em processos elevados. Esse driver é **exclusivo do ambiente de teste**;
o ZIP usa o driver Vulkan instalado pelo usuário. A aplicação pré-carrega o
loader de `System32` com seu diretório de dependências registrado, evitando
que a busca de DLLs do PyInstaller esconda o runtime. `MAKEHUMANO_VULKAN_LOADER`
permite selecionar um caminho absoluto para diagnóstico e testes controlados. O teste de software não
substitui a validação em GPUs Windows reais.

## Reproduzir o smoke

Windows, em um desktop com driver Vulkan:

```powershell
python makehumano/testes/smoke_gui.py --executable dist/MakeHumano/MakeHumano.exe --log-dir portable-logs
```

Linux, com Xvfb e Lavapipe instalados:

```bash
xvfb-run -a -s "-screen 0 1280x800x24" \
  python makehumano/testes/smoke_gui.py \
    --executable dist/MakeHumano/MakeHumano --log-dir portable-logs
```

O Python deste comando é somente o controlador do teste. O processo testado é
o executável independente. `portable-logs` conserva o log completo, marcadores,
perfil temporário, personagem e OBJ gerados. Não use seu perfil pessoal para
esse teste. O relatório `functional.json` lista os plugins carregados. Capturas PNG dos seis
presets, normal maps, cores especulares, camadas alpha e wireframe permitem
inspeção visual; elas ainda não são referências de equivalência com o render
original.

## Módulos carregados dinamicamente

O hook `empacotamento/hooks/hook-mhmain.py` enumera os módulos originais e os
plugins sem executá-los. Isso permite que o PyInstaller analise dependências
dos arquivos que a aplicação importa por nome ou `spec_from_file_location`.
Os fontes e recursos também são copiados, preservando o carregador de plugins
original e a possibilidade de manutenção. Plugins de terceiros com novas
dependências nativas ou Python ainda precisam de análise de empacotamento.

O artefato `Diagnostico-portatil-*` inclui os logs do smoke e a lista de imports
não resolvidos do PyInstaller. Essa lista também contém imports opcionais e
específicos de outros sistemas: cada aviso precisa ser interpretado, sem tratar
uma build bem-sucedida como prova de compatibilidade completa.

## Evidências desta etapa

- [CI e pacotes da revisão funcional](https://github.com/SrTristeSad/brincadeira/actions/runs/42262233631)
- [CPU, Vulkan e GUI com/sem PyOpenGL](https://github.com/SrTristeSad/brincadeira/actions/runs/42262233526)
- [Suíte de testes em Python 3.12 e 3.13](https://github.com/SrTristeSad/brincadeira/actions/runs/42262233800)

As builds acima correspondem ao código `bceafdc6d0d743525f02813612e68a632979de87`.

Windows e Linux concluíram a abertura real e os testes funcionais, tanto no
modo padrão quanto com `--multisampling`. As 53 capturas Windows foram
comparadas novamente após baixar os diagnósticos: igualdade exata entre
fontes e executável. A extensão alpha preservou as 50 capturas
da revisão anterior no Windows e no Linux, nos dois modos. A suíte local de
326 casos passou (um caso específico de Windows excluído no Linux). A CI
também verifica Python 3.12/3.13; os links acima identificam o código dos pacotes.

- [ZIP Windows desta revisão](https://github.com/SrTristeSad/brincadeira/actions/runs/42262233631/artifacts/13526285898)
- [ZIP Linux desta revisão](https://github.com/SrTristeSad/brincadeira/actions/runs/42262233631/artifacts/13524789440)
- [Diagnóstico Windows](https://github.com/SrTristeSad/brincadeira/actions/runs/42262233631/artifacts/13526325846)

SHA-256 do ZIP Windows:
`3bb1e94a9540781e6b86913ce12d5c42d37f0f8fcf186acc9e95dc2f811122f6`.
O ZIP foi baixado e verificado: integridade, executável, Python 3.12, Qt,
wgpu-native, malha base, rig oficial e módulos novos (UV/BVH/sombras) presentes; nenhum driver
de CI incluído. A validação Windows usa Vulkan por software e ainda não
comprova compatibilidade com GPUs físicas.

Consultar a conclusão dos jobs antes de aprovar outro ZIP. O teste pelos fontes
usa diretamente `codigo/makehuman/makehuman.py`, evitando deixar processos
filhos abertos ao encerrar o iniciador `executar.py` durante o smoke Windows.
