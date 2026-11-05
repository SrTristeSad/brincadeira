local Nav = require('navigation')
local Agent = {}
Agent.__index = Agent

-- Animações / ações existentes no modo demonstrativo e palavras que serão
-- procuradas dentro das animações reais do arquivo GLB.
Agent.acoes = {
  'idle', 'walk', 'run', 'sit', 'sleep', 'dance', 'wave', 'talk',
  'read', 'cook', 'eat', 'work', 'stretch', 'exercise', 'think',
  'observe', 'clean', 'laugh', 'relax', 'greet', 'explore'
}

Agent.locais = {
  idle = { 0, .05 }, walk = { 0, .1 }, run = { .1, 2.1 },
  sit = {-3.35, 1.25}, sleep = { 1.85, -2.46 },
  dance = {-.2, 1.24}, wave = { 0, 2.25 }, talk = {0, .9},
  read = {-4.63, -.83}, cook = {-4.1, -2.63},
  eat = { 3.15, 2.55}, work = { .30, -2.35},
  stretch = {4.42, .10}, exercise = {.55, 2.72},
  think = {-1.38, -1.90}, observe = { 4.38, 2.40},
  clean = {-1.10, 1.65}, laugh = { .0, 1.5},
  relax = {-3.40, 1.27}, greet = {.2, 2.50},
  explore = { 0, .20 }
}

local function random(a, b) return a + (b - a) * math.random() end
local function clamp(v, a, b) return math.max(a, math.min(b, v)) end

function Agent.new(id, info)
  local self = setmetatable({}, Agent)
  self.id, self.nome = id, info.nome
  self.info = info
  self.x = id == 1 and -1.0 or 1.15
  self.z = id == 1 and 1.30 or 1.6
  self.angulo = id == 1 and .2 or -.2
  self.estado = 'agir'
  self.acao = 'idle'
  self.tempo = 2 + id
  self.animTime = 0
  self.energia = id == 1 and 78 or 66
  self.fome = id == 1 and 84 or 75
  self.social = id == 1 and 72 or 65
  self.diversao = 64
  self.path, self.pathStep = {}, 1
  self.balao, self.balaoTempo = '', 0
  self.ultimaAcao = 'idle'
  self.modelo = nil
  self.modeloErro = nil
  self.modeloEscala = 1
  self.modeloMinY = 0
  self.animacoes = {}
  return self
end

function Agent:dizer(texto)
  self.balao = texto
  self.balaoTempo = 4.5
end

function Agent:iniciar(nome, destino, duracao)
  local lugar = destino or Agent.locais[nome] or Agent.locais.idle
  if nome == 'explore' and not destino then
    local lugares = {{-1.3,1.9}, {1.3,-.9}, {4.4,2.4}, {-4.5,-1.65}, {.2, 2.7}}
    lugar = lugares[math.random(#lugares)]
  end
  local tx, tz = lugar.x or lugar[1], lugar.z or lugar[2]
  self.ultimaAcao = self.acao
  self.acao = nome
  self.tempo = duracao or random(4, 9)
  if nome == 'sleep' then self.tempo = duracao or random(10, 15) end
  self.animTime = 0
  self.path, self.pathStep = Nav.findPath(self.x, self.z, tx, tz), 1
  if #self.path == 0 then
    self.estado = 'agir'
  else
    self.estado = 'andar'
  end
end

function Agent:escolher()
  if self.energia < 28 then return 'sleep' end
  if self.fome < 32 then return 'eat' end
  local lista = {'idle', 'explore', 'read', 'cook', 'eat', 'work', 'stretch',
                 'exercise', 'think', 'observe', 'clean', 'dance', 'wave',
                 'sit', 'relax', 'laugh', 'run'}
  if self.info.personalidade == 'sociavel' then
    lista[#lista + 1] = 'dance'
    lista[#lista + 1] = 'wave'
    lista[#lista + 1] = 'laugh'
  else
    lista[#lista + 1] = 'read'
    lista[#lista + 1] = 'observe'
  end
  local nome = lista[math.random(#lista)]
  if nome == self.acao then nome = 'explore' end
  return nome
end

function Agent:irAte(dt)
  local p = self.path[self.pathStep]
  if not p then
    self.estado = 'agir'
    self.animTime = 0
    return
  end
  local dx, dz = p.x - self.x, p.z - self.z
  local dist = math.sqrt(dx * dx + dz * dz)
  local velocidade = self.acao == 'run' and 2.5 or 1.35
  if dist < velocidade * dt + .01 then
    self.x, self.z = p.x, p.z
    self.pathStep = self.pathStep + 1
  else
    self.x = self.x + dx / dist * velocidade * dt
    self.z = self.z + dz / dist * velocidade * dt
    self.angulo = math.atan(dx, dz)
  end
end

function Agent:update(dt)
  self.animTime = self.animTime + dt
  if self.balaoTempo > 0 then self.balaoTempo = math.max(0, self.balaoTempo - dt) end
  self.fome = clamp(self.fome - dt * .14, 0, 100)
  self.diversao = clamp(self.diversao - dt * .09, 0, 100)
  self.social = clamp(self.social - dt * .09, 0, 100)
  if self.acao ~= 'sleep' or self.estado == 'andar' then
    self.energia = clamp(self.energia - dt * .24, 0, 100)
  end
  if self.estado == 'andar' then
    self:irAte(dt)
    return
  end
  self.tempo = self.tempo - dt
  if self.acao == 'sleep' then self.energia = clamp(self.energia + dt * 5.8, 0, 100) end
  if self.acao == 'eat' or self.acao == 'cook' then self.fome = clamp(self.fome + dt * 3.1, 0, 100) end
  if self.acao == 'dance' or self.acao == 'laugh' then self.diversao = clamp(self.diversao + dt * 2.8, 0, 100) end
  if self.acao == 'talk' then self.social = clamp(self.social + dt * 1.8, 0, 100) end
  if self.tempo <= 0 then self:iniciar(self:escolher()) end
end

function Agent:animacaoAtual()
  if self.estado == 'andar' then return self.acao == 'run' and 'run' or 'walk' end
  return self.acao
end

return Agent
