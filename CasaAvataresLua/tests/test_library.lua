package.path='./?.lua;'..package.path
local Library=require('animation_library')
local Settings=require('settings')
local fs={getDirectoryItems=function(path)
  if path:find('avatar1') then return {'adult_cena_02.glb','dupla_adult_02.glb','extra_dance.glb','not.txt'} end
  return {'extra_dance.glb','dupla_adult_02.glb'}
end}
local actions=Library.construir(Settings,fs)
assert(#actions >= 26,'Catálogo deveria reconhecer ações internas e GLBs avulsos')
assert(Library.encontrar(actions,'adult_cena_02').adulto)
assert(Library.encontrar(actions,'dupla_adult_02').dupla)
assert(Library.encontrar(actions,'extra_dance'))
assert(Library.caminho(2,'extra_dance')=='assets/animations/avatar2/extra_dance.glb')
assert(Library.caminho(1,'../invasor')==nil,'Arquivos não devem escapar da pasta')
local old=Settings.animacoesAdultas
Settings.animacoesAdultas=false
local filtered=Library.construir(Settings,fs)
assert(not Library.encontrar(filtered,'adult_cena_02'))
assert(not Library.encontrar(filtered,'dupla_adult_01'))
Settings.animacoesAdultas=old
print('OK: catálogo, varredura de GLB, filtro +18 e nomes seguros.')
