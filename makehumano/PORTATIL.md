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

## O que a CI exige do executável

O autoteste de importação continua verificando `mhmain` e `cProfile`, mas não
basta para publicar o artefato. O teste completo abre o executável congelado e
exige simultaneamente:

- conclusão da inicialização da GUI, plugins e targets;
- quadro da cena original `G.world` usando um adaptador Vulkan;
- picking, framebuffer offscreen, `renderToBuffer`, `renderAlphaMask`, `renderSkin`;
- execução dos seis presets oficiais WGSL, normal maps e composição alfa;
- alteração real da malha pelo modificador `macrodetails/Age`, undo e redo no histórico original;
- mapas especulares e transparência separados, incluindo intensidade zero;
- foco, ângulo e atenuação das luzes com comparação de pixels e regressão dos widgets originais;
- salvamento e recarregamento `.mhm`, com comparação das coordenadas;
- exportação OBJ com vértices/faces, FBX binário com cabeçalho, Collada com geometria XML e STL binário com contagem/tamanho dos triângulos;
- carregamento dos plugins de modificadores, materiais, OBJ, FBX, Collada e STL;
- resposta do controle wireframe, com arestas pretas e imagem diferente da superfície sólida;
- processo ainda vivo e ausência de traceback ou erro de render no log;
- no Windows, igualdade exata de 23 capturas PNG entre fontes e executável. As
  capturas só são geradas após terminar a carga da iluminação, plugins e targets.

Isso **não** comprova equivalência visual dos shaders, todos os controles da
interface ou todos os formatos/opções de exportação. Os quatro formatos citados
são exportados com a malha original e olhos padrão; animações, roupas externas e
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

- [CI e pacotes da revisão funcional](https://github.com/SrTristeSad/brincadeira/actions/runs/42188995351)
- [CPU, Vulkan e GUI com/sem PyOpenGL](https://github.com/SrTristeSad/brincadeira/actions/runs/42188995342)
- [246 testes em Python 3.12 e 3.13](https://github.com/SrTristeSad/brincadeira/actions/runs/42188995343)

As builds acima correspondem ao código `1b93c3d6f683156062e4dfb94732c5678d6d9a34`.

Consultar a conclusão dos jobs antes de aprovar um ZIP. O teste pelos fontes
usa diretamente `codigo/makehuman/makehuman.py`, evitando deixar processos
filhos abertos ao encerrar o iniciador `executar.py` durante o smoke Windows.
