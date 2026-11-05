-- Casa Viva: casa 3D, agentes e catálogo de animações controlados por Lua.
local Settings=require('settings')
local World=require('world')
local Simulation=require('simulation')
local Avatars=require('avatars')
local Camera=require('camera')
local Library=require('animation_library')

local sim, catalog, camera
local selecionado,indice=1,1
local painel=true
local function clamp(v,a,b) return math.max(a,math.min(b,v)) end

local function importar()
  catalog=Library.construir(Settings,lovr.filesystem)
  for _,agent in ipairs(sim.agentes) do Avatars.carregar(agent,catalog) end
  indice=clamp(indice,1,math.max(1,#catalog))
  print('CASA VIVA: '..#catalog..' ações no catálogo. H = ajuda.')
end

local function nomeDaAcao()
  return catalog[indice] and catalog[indice].id or 'idle'
end
local function proximaAcao(sinal)
  if #catalog==0 then return end
  indice=(indice-1+sinal)%#catalog+1
  local item=catalog[indice]
  print(string.format('[ANIMAÇÕES] %d/%d %s%s%s',indice,#catalog,item.rotulo,
    item.adulto and ' [+18]' or '',item.dupla and ' [dupla]' or ''))
end
local function executar()
  local item=catalog[indice]
  if not item then return end
  if item.dupla then
    local ok,erro=sim:ativarDupla(item)
    if not ok then print('[ANIMAÇÕES] '..erro) end
  else
    sim:ativarAnimacao(selecionado,item.id,item.duracao)
  end
  local agente=sim.agentes[selecionado]
  print('[ANIMAÇÕES] '..item.id..' -> '..Avatars.temAnimacao(agente,item.id))
end

local function rotulo(p,agente)
  local y=agente:animacaoAtual()=='sleep' and 1.15 or 2.15
  p:setColor(.15,.20,.24)
  p:box(agente.x,y+.27,agente.z,1.10,.25,.035)
  local cor=agente.id==selecionado and {.99,.82,.43} or {.95,.95,.97}
  p:setColor(cor[1],cor[2],cor[3])
  p:text(agente.nome,agente.x,y+.27,agente.z+.038,.17)
  if agente.balaoTempo>0 then
    p:setColor(.96,.97,.92)
    p:box(agente.x,y+.65,agente.z,2.58,.40,.04)
    p:setColor(.1,.2,.22)
    p:text(agente.balao,agente.x,y+.65,agente.z+.05,.15,0,0,1,0,2.30)
  end
end

local function interface(p)
  if not painel then return end
  local item=catalog[indice]
  local a=sim.agentes[selecionado]
  local state=sim.pausado and 'PAUSADO' or 'AUTÔNOMO'
  local status=sim.total==1 and 'sozinho' or (sim.comunicacao and 'conversa ligada' or 'conversa desligada')
  p:setColor(.11,.19,.23)
  p:box(0,3.40,4.34,10.3,1.32,.10)
  p:setColor(.97,.97,.91)
  p:text('CASA VIVA  |  F1 casa  F2 sala  F3 cozinha  F4 quarto  |  M: ocultar painel',
    0,3.83,4.43,.18,0,0,1,0,10.0)
  p:setColor(.89,.88,.72)
  p:text('Mouse arrastar: girar   Roda: zoom   TAB: avatar   Z/X: navegar animações   ENTER: executar',
    0,3.54,4.43,.17,0,0,1,0,10.0)
  p:setColor(.99,.89,.63)
  local line=string.format('%s  |  %s  |  %s  |  Energia %d  Fome %d',
    a.nome,state,status,math.floor(a.energia),math.floor(a.fome))
  p:text(line,0,3.24,4.43,.16,0,0,1,0,10.0)
  if item then
    local nome=string.format('%d/%d %s%s%s (%s)',indice,#catalog,item.rotulo,
      item.adulto and ' +18' or '', item.dupla and ' [2 avatares]' or '',
      Avatars.temAnimacao(a,item.id))
    p:setColor(.89,.97,.99)
    p:text(nome,0,2.97,4.43,.165,0,0,1,0,9.80)
  end
end

function lovr.load()
  math.randomseed(os.time())
  lovr.graphics.setBackgroundColor(.69,.83,.91)
  camera=Camera.new()
  sim=Simulation.new(Settings)
  importar()
  sim.agentes[1]:iniciar('explore')
  sim.agentes[2]:iniciar('observe')
end

function lovr.update(dt)
  local speed=dt*1.1
  if lovr.system.isKeyDown('left','a') then camera:orbitar(-speed/.006,0) end
  if lovr.system.isKeyDown('right','d') then camera:orbitar(speed/.006,0) end
  if lovr.system.isKeyDown('up','w') then camera:orbitar(0,-speed*.65/.006) end
  if lovr.system.isKeyDown('down','s') then camera:orbitar(0,speed*.65/.006) end
  if lovr.system.isKeyDown('q') then camera:aproximar(-dt*7) end
  if lovr.system.isKeyDown('e') then camera:aproximar(dt*7) end
  sim:update(dt*(Settings.velocidadeTempo or 1))
  camera:seguir(sim.agentes[selecionado],dt)
end

function lovr.draw(pass)
  local x,y,z=camera:posicao()
  pass:setViewPose(1,mat4():lookAt(vector(x,y,z),vector(camera.focusX,.73,camera.focusZ)),true)
  World.draw(pass,sim)
  for i=1,sim.total do
    local a=sim.agentes[i]
    Avatars.draw(pass,a)
    rotulo(pass,a)
  end
  interface(pass)
end

function lovr.keypressed(key,_,repeated)
  if repeated then return end
  if key=='1' or key=='2' then
    sim:setTotal(tonumber(key))
    selecionado=math.min(selecionado,sim.total)
  elseif key=='c' then sim:setComunicacao(not sim.comunicacao)
  elseif key=='space' then sim.pausado=not sim.pausado
  elseif key=='tab' then selecionado=selecionado%sim.total+1
  elseif key=='z' then proximaAcao(-1)
  elseif key=='x' then proximaAcao(1)
  elseif key=='return' or key=='kpenter' then executar()
  elseif key=='t' then executar();proximaAcao(1) -- compatível com versão inicial
  elseif key=='f1' then camera:irPara(1)
  elseif key=='f2' then camera:irPara(2)
  elseif key=='f3' then camera:irPara(3)
  elseif key=='f4' then camera:irPara(4)
  elseif key=='f' then camera.follow=not camera.follow
  elseif key=='m' then painel=not painel
  elseif key=='l' then importar() -- relê GLBs após atualizar arquivos
  elseif key=='r' then
    sim=Simulation.new(Settings); importar()
  elseif key=='h' then
    print('== CONTROLES CASA VIVA ==')
    print('F1 casa | F2 sala | F3 cozinha | F4 quarto | F seguir avatar')
    print('Mouse esquerdo arrastar: girar | direito: deslocar | roda ou Q/E: zoom')
    print('W/A/S/D ou setas: girar | TAB: trocar avatar | 1/2: total de avatares')
    print('Z/X: trocar animação | ENTER: executar | L: reler pacotes GLB')
    print('C: comunicação | Espaço: pausar | M: painel | T: prévia próxima | R: reiniciar')
    for i,item in ipairs(catalog) do print(i..' - '..item.id) end
  elseif key=='escape' then lovr.event.quit() end
end
function lovr.mousepressed(x,y,button) camera.drag=button end
function lovr.mousereleased(x,y,button) if camera.drag==button then camera.drag=0 end end
function lovr.mousemoved(x,y,dx,dy)
  if camera.drag~=0 then camera:arrastar(dx,dy,camera.drag) end
end
function lovr.wheelmoved(dx,dy) camera:aproximar(dy*1.2) end
