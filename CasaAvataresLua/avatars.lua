local Avatars = {}
local Catalog = require('animation_library')
Avatars.extraAliases = {}

-- Cada ação tem aliases para mapear clipes com nomes de Mixamo/GLB.
local aliases = {
  idle={'idle','breathing','stand'}, walk={'walk','walking'}, run={'run','jog'},
  sit={'sit','sitting'}, sleep={'sleep','lying','lay'},
  dance={'dance','dancing'}, wave={'wave','waving'},
  talk={'talk','talking','speaking'}, read={'read','reading'},
  cook={'cook','stir'}, eat={'eat','eating'}, work={'type','work','computer'},
  stretch={'stretch'}, exercise={'exercise','jump','workout'},
  think={'think','ponder'}, observe={'look','observe','inspect'},
  clean={'clean','sweep'}, laugh={'laugh'}, relax={'relax','rest'},
  greet={'greet','hello','wave'}, explore={'walk'}
}

local function setColor(p,c) p:setColor(c[1],c[2],c[3]) end
local function box(p,c,x,y,z,sx,sy,sz)
  setColor(p,c)
  p:box(x,y,z,sx,sy,sz)
end
local function sphere(p,c,x,y,z,r)
  setColor(p,c)
  p:sphere(x,y,z,r)
end

local function limb(p, color, x, y, z, upperAngle, elbowAngle, isArm)
  p:push()
  p:translate(x,y,z)
  p:rotate(upperAngle,1,0,0)
  box(p,color,0,-.22,0,isArm and .17 or .20,.44,isArm and .18 or .23)
  p:translate(0,-.43,0)
  p:rotate(elbowAngle,1,0,0)
  box(p,color,0,-.23,0,isArm and .15 or .18,.43,isArm and .17 or .21)
  if isArm then
    sphere(p,{.85,.66,.52},0,-.49,0,.11)
  else
    box(p,{.26,.23,.24},0,-.46,.08,.25,.15,.34)
  end
  p:pop()
end

local function visualPosition(agent, act)
  -- Quando a ação acontece sobre um móvel, aproximamos o boneco da superfície.
  -- É só uma correção visual: a navegação continua no ponto livre próximo ao móvel.
  if agent.estado == 'agir' then
    if act == 'sleep' then return 3.78, -3.25 end
    if act == 'sit' or act == 'relax' then return -3.35, 2.45 end
  end
  return agent.x, agent.z
end

local function procedural(p, agent, act)
  local t = agent.animTime
  local move = act == 'walk' or act == 'run' or act == 'explore'
  local speed = act == 'run' and 13 or 9
  local stride = move and math.sin(t*speed) * (act == 'run' and .75 or .48) or 0
  local bounce = .025*math.sin(t*2)
  local sit = act == 'sit' or act == 'relax' or act == 'read' or act == 'eat' or act == 'work'
  local sleep = act == 'sleep'
  local dance = act == 'dance'
  if move then bounce = .05*math.abs(math.sin(t*speed)) end
  if dance then bounce = .14*math.abs(math.sin(t*6)) end
  local torsoTwist = dance and .15*math.sin(t*5) or 0
  local armL, armR = -stride, stride
  local legL, legR = stride, -stride
  local kneeL, kneeR = 0, 0
  if sit then
    legL, legR = -1.28,-1.28
    kneeL, kneeR = 1.20,1.20
    armL, armR = -.35,-.35
  elseif sleep then
    armL, armR = -.24,.25
  elseif act == 'wave' or act == 'greet' then
    armR = -2.2 + .3*math.sin(t*7)
  elseif dance then
    armL,armR = -1.9+.4*math.sin(t*4),-1.8-.4*math.sin(t*4)
    legL,legR = .45*math.sin(t*5),-.45*math.sin(t*5)
  elseif act == 'stretch' then
    armL,armR = -2.9,-2.9
  elseif act == 'talk' then
    armL,armR = -.45 + .3*math.sin(t*4), -.65 - .35*math.sin(t*3)
  elseif act == 'eat' then
    armR = -1.8+.22*math.sin(t*4)
  elseif act == 'cook' or act == 'clean' then
    armL,armR = -1+.5*math.sin(t*4), -1-.6*math.sin(t*4)
  elseif act == 'work' then
    armL,armR = -1.15+.13*math.sin(t*13), -1.15-.13*math.sin(t*13)
  elseif act == 'read' then
    armL,armR = -1.1,-1.1
  elseif act == 'exercise' then
    armL,armR = -2+.9*math.sin(t*6),-2-.9*math.sin(t*6)
    legL,legR = .6*math.sin(t*6),-.6*math.sin(t*6)
  elseif act == 'think' then
    armR = -1.55
  elseif act == 'laugh' then
    armL,armR = -.6,-.6
    bounce = .07*math.abs(math.sin(t*11))
  elseif act == 'observe' then
    armR = -.3
  end
  p:push()
  local visualX, visualZ = visualPosition(agent, act)
  p:translate(visualX,0,visualZ)
  p:rotate(agent.angulo,0,1,0)
  if sleep then
    -- Demo: o corpo inteiro se deita horizontalmente; avatar real exige clipe próprio.
    p:translate(0,.79,-.58)
    p:rotate(math.pi/2,1,0,0)
  else
    p:translate(0,(sit and -.28 or 0)+bounce,0)
  end
  p:push()
  p:rotate(torsoTwist,0,1,0)
  box(p,agent.info.corRoupa,0,1.12,0,.54,.68,.30)
  box(p,agent.info.corPele,0,1.49,0,.18,.16,.18)
  -- Cabeça, cabelo e olhos (frente = +Z).
  sphere(p,agent.info.corPele,0,1.68,0,.24)
  box(p,{.22,.18,.16},0,1.88,-.04,.49,.13,.40)
  sphere(p,{.17,.16,.17},-.09,1.70,.22,.031)
  sphere(p,{.17,.16,.17}, .09,1.70,.22,.031)
  local shoulderR = act == 'wave' and -1.25 or 0
  -- Braços com dois segmentos.
  limb(p,agent.info.corRoupa,-.38,1.32,0,armL,0,true)
  p:push()
  p:translate(.38,1.32,0)
  p:rotate(shoulderR,0,0,1)
  p:translate(-.38,-1.32,0)
  limb(p,agent.info.corRoupa,.38,1.32,0,armR,0,true)
  p:pop()
  p:pop()
  box(p,{.25,.30,.40},0,.83,0,.53,.21,.33)
  limb(p,{.25,.30,.40},-.15,.79,0,legL,kneeL,false)
  limb(p,{.25,.30,.40}, .15,.79,0,legR,kneeR,false)
  p:pop()
end

local function lerModelo(path,altura)
  if not lovr.filesystem.isFile(path) then return nil,'arquivo não encontrado' end
  local ok,model=pcall(lovr.graphics.newModel,path)
  if not ok then return nil,tostring(model) end
  local _,_,miny,maxy=model:getBoundingBox()
  miny,maxy=miny or 0,maxy or 1.72
  local h=maxy-miny
  return {modelo=model,escala=h>.01 and altura/h or 1,minY=miny}
end

function Avatars.carregar(agent,catalog)
  agent.modelo,agent.modeloErro=nil,nil
  agent.animacoes,agent.pacotes={},{}
  local base,err=lerModelo(agent.info.arquivo,agent.info.altura)
  if base then
    agent.modelo,agent.modeloEscala,agent.modeloMinY=base.modelo,base.escala,base.minY
    for i=1,agent.modelo:getAnimationCount() do
      local name=agent.modelo:getAnimationName(i)
      if name then agent.animacoes[i]=name:lower() end
    end
    print(agent.nome..': modelo principal carregado, clipes: '..agent.modelo:getAnimationCount())
  else
    agent.modeloErro=err
    print(agent.nome..': usando avatar de demonstração ('..err..')')
  end
  for _,item in ipairs(catalog or {}) do
    if item.aliases then Avatars.extraAliases[item.id]=item.aliases end
    local path=Catalog.caminho(agent.id,item.id)
    if path and lovr.filesystem.isFile(path) then
      local pack,erro=lerModelo(path,agent.info.altura)
      if pack and pack.modelo:getAnimationCount()>0 then
        pack.clip=1
        for i=1,pack.modelo:getAnimationCount() do
          local name=(pack.modelo:getAnimationName(i) or ''):lower()
          if name==item.id:lower() then pack.clip=i;break end
        end
        agent.pacotes[item.id]=pack
        print(agent.nome..': animação importada '..item.id..' ('..path..')')
      else
        print('AVISO: '..path..' precisa conter avatar completo e clipe animado: '..tostring(erro))
      end
    end
  end
end

function Avatars.encontrar(agent, acao)
  local names = Avatars.extraAliases[acao] or aliases[acao] or {acao}
  for _, alias in ipairs(names) do
    for i, name in pairs(agent.animacoes) do
      if name:find(alias,1,true) then return i end
    end
  end
  if acao ~= 'idle' then
    for _, alias in ipairs(aliases.idle) do
      for i, name in pairs(agent.animacoes) do
        if name:find(alias,1,true) then return i end
      end
    end
  end
end

function Avatars.temAnimacao(agent,acao)
  if agent.pacotes and agent.pacotes[acao] then return 'GLB avulso' end
  if agent.modelo and Avatars.encontrar(agent,acao) then return 'clipe no avatar' end
  if agent.modelo then return 'sem clipe' end
  for _,id in ipairs(require('agent').acoes) do if id==acao then return 'boneco provisório' end end
  return 'GLB ausente'
end

function Avatars.draw(p,agent)
  local act=agent:animacaoAtual()
  local pack=agent.pacotes and agent.pacotes[act]
  local model=pack and pack.modelo or agent.modelo
  if not model then
    procedural(p,agent,act)
    return
  end
  local clip=pack and pack.clip or Avatars.encontrar(agent,act)
  if clip then
    model:resetNodeTransforms()
    local duration=model.getAnimationDuration and model:getAnimationDuration(clip) or nil
    local t=duration and duration>.001 and agent.animTime%duration or agent.animTime
    model:animate(clip,t)
  end
  p:push()
  local visualX,visualZ=visualPosition(agent,act)
  p:translate(visualX,0,visualZ)
  p:rotate(agent.angulo+agent.info.rotacao,0,1,0)
  if act=='sleep' then
    p:translate(0,.77,-.6)
    if not clip then p:rotate(math.pi/2,1,0,0) end
  elseif act=='sit' or act=='relax' then
    if not clip then p:translate(0,-.31,0) end
  end
  p:scale(pack and pack.escala or agent.modeloEscala)
  p:translate(0,-(pack and pack.minY or agent.modeloMinY),0)
  p:setColor(1,1,1)
  p:draw(model,0,0,0)
  p:pop()
end

return Avatars
