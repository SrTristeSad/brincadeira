-- Catálogo de ações embutidas e de arquivos GLB independentes.
-- Para cada ação personalizada: assets/animations/avatar1/<id>.glb
-- Opcionalmente:             assets/animations/avatar2/<id>.glb
local Agent = require('agent')
local Catalog = {}
local function nomeLimpo(name)
  return type(name)=='string' and name:match('^[%w_%-]+$') ~= nil and not name:find('%.%.',1,true)
end
local function criar(id,descricao)
  local adult = id:match('^adult_') ~= nil or id:match('^dupla_adult_') ~= nil
  local pair = id:match('^dupla_') ~= nil or id:match('^adult_dupla_') ~= nil
  local d = descricao or {}
  return {id=id, rotulo=d.rotulo or id:gsub('_',' '), adulto=d.adulto == true or adult,
    dupla=d.dupla == true or pair, duracao=d.duracao or 9, aliases=d.aliases}
end
function Catalog.construir(config,filesystem)
  local out,seen = {},{}
  local function add(id,data)
    if not nomeLimpo(id) or seen[id] then return end
    local item = criar(id,data)
    if item.adulto and not config.animacoesAdultas then return end
    seen[id]=true; out[#out+1]=item
  end
  for _,id in ipairs(Agent.acoes) do add(id) end
  for _,entry in ipairs(config.animacoesExtra or {}) do
    if type(entry)=='string' then add(entry)
    elseif type(entry)=='table' then add(entry.id,entry) end
  end
  if filesystem and type(filesystem.getDirectoryItems)=='function' then
    for id=1,2 do
      local path='assets/animations/avatar'..id
      local ok,items=pcall(filesystem.getDirectoryItems,path)
      if ok and type(items)=='table' then
        for _,file in ipairs(items) do
          local name=file:match('^([%w_%-]+)%.glb$')
          if name then add(name) end
        end
      end
    end
  end
  return out
end
function Catalog.encontrar(catalog,id)
  for i,entry in ipairs(catalog) do if entry.id==id then return entry,i end end
end
function Catalog.caminho(avatar,id)
  if not nomeLimpo(id) then return nil end
  return 'assets/animations/avatar'..avatar..'/'..id..'.glb'
end
return Catalog
