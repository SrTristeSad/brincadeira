package.path='./?.lua;'..package.path
local Avatar=require('avatars')
local Agent=require('agent')
local Settings=require('settings')
local Library=require('animation_library')
local animHits={}
local function model(n,animations)
  local m={name=n}
  function m:getBoundingBox() return -.2,.2,0,1.7,-.2,.2 end
  function m:getAnimationCount() return #animations end
  function m:getAnimationName(i) return animations[i] end
  function m:getAnimationDuration(i) return 1.4 end
  function m:resetNodeTransforms() end
  function m:animate(i,t) animHits[#animHits+1]={name=n,index=i,time=t} end
  return m
end
local base=model('base',{'Idle','Walk'})
local pack=model('pack',{'SomeAction','adult_cena_02'})
lovr={
  filesystem={
    isFile=function(path) return path=='assets/avatar1.glb' or path=='assets/animations/avatar1/adult_cena_02.glb' end,
    getDirectoryItems=function(path)
      if path=='assets/animations/avatar1' then return {'adult_cena_02.glb'} end
      return {}
    end
  },
  graphics={newModel=function(path)
    if path:match('adult_cena_02') then return pack end
    return base
  end}
}
local p={}
for _,method in ipairs({'push','pop','translate','rotate','scale','setColor','draw'}) do p[method]=function() end end
local actions=Library.construir(Settings,lovr.filesystem)
local a=Agent.new(1,Settings.avatares[1])
Avatar.carregar(a,actions)
assert(a.pacotes.adult_cena_02 and a.pacotes.adult_cena_02.clip==2)
a.estado='agir';a.acao='adult_cena_02';a.animTime=10.2
Avatar.draw(p,a)
assert(animHits[#animHits].name=='pack' and animHits[#animHits].index==2,
  'Deveria tocar clipe do arquivo GLB avulso, não do modelo base')
assert(animHits[#animHits].time<1.4, 'Clip deve repetir no final')
print('OK: carregamento independente e reprodução de GLB customizado.')
