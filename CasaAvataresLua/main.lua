-- Casa Viva: ambiente 3D / dois avatares / agentes autônomos em Lua.
local Settings = require('settings')
local World = require('world')
local Simulation = require('simulation')
local Avatars = require('avatars')
local Agent = require('agent')

local sim
local camera = {yaw=-.24, pitch=.64, distance=16.7, focusX=0, focusZ=0}
local selecionado, teste = 1, 1
local hint = '1/2: avatares | C: conversar | TAB: selecionar | T: testar animação'

local function clamp(x,a,b) return math.max(a,math.min(b,x)) end

local function drawLabel(p,agent)
  local y = agent:animacaoAtual() == 'sleep' and 1.15 or 2.15
  local cor = agent.id==selecionado and {.99,.84,.41} or {.90,.94,.97}
  p:setColor(.12,.17,.20)
  p:box(agent.x,y+.27,agent.z,.98,.25,.035)
  p:setColor(cor[1],cor[2],cor[3])
  p:text(agent.nome,agent.x,y+.27,agent.z+.038,.18)
  if agent.balaoTempo > 0 then
    p:setColor(.95,.96,.93)
    p:box(agent.x,y+.64,agent.z,2.55,.39,.03)
    p:setColor(.12,.18,.21)
    p:text(agent.balao,agent.x,y+.64,agent.z+.04,.16,0,0,1,0,2.35)
  end
end

local function drawStatus(p)
  -- HUD 3D encostado na frente da casa, legível a partir da câmera inicial.
  p:setColor(.17,.23,.28)
  p:box(0,3.42,4.26,8.20,.63,.07)
  p:setColor(.96,.98,.98)
  p:text('CASA VIVA  |  1/2 personagens  |  C comunicação  |  TAB escolher  |  T animação  |  ESPAÇO pausar',
    0,3.53,4.31,.18,0,0,1,0,8.0)
  local comm = sim.total == 1 and 'desativada (só 1 avatar)' or
    (sim.comunicacao and 'ativada' or 'desativada')
  p:setColor(.89,.85,.65)
  local selecionadoInfo = sim.agentes[selecionado]
  local state = selecionadoInfo.estado == 'andar' and 'andando' or selecionadoInfo.acao
  local line = string.format('Comunicação: %s  |  Selecionado: %s (%s)  |  %s',
    comm,selecionadoInfo.nome,state,sim.pausado and 'PAUSADO' or 'AUTÔNOMO')
  p:text(line,0,3.25,4.31,.16,0,0,1,0,7.9)
end

function lovr.load()
  math.randomseed(os.time())
  lovr.graphics.setBackgroundColor(.69,.83,.91)
  sim = Simulation.new(Settings)
  for _,a in ipairs(sim.agentes) do Avatars.carregar(a) end
  sim.agentes[1]:iniciar('explore')
  sim.agentes[2]:iniciar('observe')
  print('CASA VIVA: pressione H para mostrar controles no terminal.')
end

function lovr.update(dt)
  local speed = 1.12 * dt
  if lovr.system.isKeyDown('left','a') then camera.yaw = camera.yaw-speed end
  if lovr.system.isKeyDown('right','d') then camera.yaw = camera.yaw+speed end
  if lovr.system.isKeyDown('up','w') then camera.pitch = clamp(camera.pitch+speed*.7,.25,1.29) end
  if lovr.system.isKeyDown('down','s') then camera.pitch = clamp(camera.pitch-speed*.7,.25,1.29) end
  if lovr.system.isKeyDown('q') then camera.distance = clamp(camera.distance+dt*7,7,30) end
  if lovr.system.isKeyDown('e') then camera.distance = clamp(camera.distance-dt*7,7,30) end
  sim:update(dt * (Settings.velocidadeTempo or 1))
end

function lovr.draw(pass)
  local cam = camera
  local hd = math.cos(cam.pitch) * cam.distance
  local px = cam.focusX + math.sin(cam.yaw) * hd
  local py = .7 + math.sin(cam.pitch) * cam.distance
  local pz = cam.focusZ + math.cos(cam.yaw) * hd
  pass:setViewPose(1, mat4():lookAt(vector(px,py,pz),vector(cam.focusX,.73,cam.focusZ)),true)
  World.draw(pass,sim)
  for i=1,sim.total do
    local a = sim.agentes[i]
    Avatars.draw(pass,a)
    drawLabel(pass,a)
  end
  drawStatus(pass)
end

function lovr.keypressed(key, _, repeatKey)
  if repeatKey then return end
  if key=='1' or key=='2' then
    sim:setTotal(tonumber(key))
    selecionado = math.min(selecionado,sim.total)
  elseif key=='c' then
    sim:setComunicacao(not sim.comunicacao)
  elseif key=='space' then
    sim.pausado = not sim.pausado
  elseif key=='tab' then
    selecionado = selecionado % sim.total + 1
  elseif key=='t' then
    sim:ativarAnimacao(selecionado,Agent.acoes[teste])
    print('Pré-visualização: '..Agent.acoes[teste])
    teste = teste % #Agent.acoes + 1
  elseif key=='r' then
    sim = Simulation.new(Settings)
    for _,a in ipairs(sim.agentes) do Avatars.carregar(a) end
  elseif key=='h' then
    print('CONTROLES: 1/2 quantidade | C comunicação | TAB personagem | T próxima animação')
    print('ESPAÇO pausar | A/D ou setas laterais girar | W/S ou setas verticais inclinar')
    print('Q/E zoom | R reiniciar | ESC sair')
    print('AÇÕES: '..table.concat(Agent.acoes,', '))
  elseif key=='escape' then
    lovr.event.quit()
  end
end

function lovr.wheelmoved(dx,dy)
  camera.distance = clamp(camera.distance - dy*1.2,7,30)
end
