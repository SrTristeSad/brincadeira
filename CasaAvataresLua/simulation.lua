local Agent = require('agent')
local Sim = {}
Sim.__index = Sim

local falas = {
  {'Oi! Como está seu dia?', 'Tudo bem! E o seu?'},
  {'Quer descansar um pouco?', 'Talvez depois. Obrigado!'},
  {'Vou explorar a casa.', 'Boa ideia!'},
  {'Você viu a cozinha?', 'Vi sim. Parece ótima.'},
  {'Que tal dançar?', 'Gostei da ideia!'},
  {'O que está fazendo?', 'Só curtindo a casa.'},
  {'Vamos conversar?', 'Claro, estou ouvindo.'},
  {'Está confortável aqui?', 'Muito confortável!'}
}

function Sim.new(settings)
  local self = setmetatable({}, Sim)
  self.agentes = {
    Agent.new(1,settings.avatares[1]),
    Agent.new(2,settings.avatares[2])
  }
  self.total = math.max(1,math.min(2,settings.totalAvatares))
  self.comunicacao = settings.comunicacao
  self.pausado = false
  self.tempo = 0
  self.proximoEncontro = 12
  self.encontro = nil
  self.respostas = {}
  self.historico = {}
  return self
end

function Sim:registrar(autor, fala)
  self.historico[#self.historico+1] = {autor=autor.nome, fala=fala, tempo=self.tempo}
  if #self.historico > 8 then table.remove(self.historico,1) end
  autor:dizer(fala)
  print(string.format('[%s] %s',autor.nome, fala))
end

function Sim:setTotal(n)
  self.total = math.max(1,math.min(2,n))
  if self.total == 1 then
    self.encontro, self.respostas = nil, {}
  end
end

function Sim:setComunicacao(ativar)
  self.comunicacao = not not ativar
  if not self.comunicacao then
    self.encontro, self.respostas = nil, {}
  else
    self.proximoEncontro = self.tempo + 4
  end
end

function Sim:ativarAnimacao(id, acao)
  if not self.agentes[id] or id > self.total then return end
  local a = self.agentes[id]
  -- Para pré-visualizar uma animação sem navegar pela casa.
  a:iniciar(acao,{x=a.x,z=a.z}, 7)
end

function Sim:prepararEncontro()
  local a,b = self.agentes[1],self.agentes[2]
  if a.energia < 30 or b.energia < 30 then return end
  a:iniciar('talk',{x=-.65,z=.9},10)
  b:iniciar('talk',{x=.65,z=.9},10)
  self.encontro = {t=0, iniciado=false}
end

function Sim:update(dt)
  if self.pausado then return end
  dt = math.min(.12, dt)
  self.tempo = self.tempo + dt
  for i=1,self.total do self.agentes[i]:update(dt) end
  if self.total ~= 2 or not self.comunicacao then return end

  for i=#self.respostas,1,-1 do
    local resposta = self.respostas[i]
    resposta.delay = resposta.delay - dt
    if resposta.delay <= 0 then
      self:registrar(self.agentes[resposta.para],resposta.texto)
      self.agentes[resposta.para].social = math.min(100,self.agentes[resposta.para].social + 9)
      table.remove(self.respostas,i)
    end
  end

  if not self.encontro and self.tempo >= self.proximoEncontro then
    self:prepararEncontro()
    self.proximoEncontro = self.tempo + 18
  end
  if self.encontro then
    self.encontro.t = self.encontro.t + dt
    local a,b = self.agentes[1],self.agentes[2]
    local dx,dz = a.x-b.x,a.z-b.z
    if not self.encontro.iniciado and
       a.estado == 'agir' and b.estado == 'agir' and
       math.sqrt(dx*dx+dz*dz) < 2.4 then
      local frase = falas[math.random(#falas)]
      local speaker = math.random(2)
      local other = speaker == 1 and 2 or 1
      self:registrar(self.agentes[speaker],frase[1])
      self.respostas[#self.respostas+1] = {para=other,texto=frase[2],delay=1.65}
      self.agentes[speaker].social = math.min(100,self.agentes[speaker].social+10)
      self.encontro.iniciado = true
    end
    if self.encontro.t > 14 or (self.encontro.iniciado and self.encontro.t > 9) then
      self.encontro = nil
    end
  end
end

return Sim
