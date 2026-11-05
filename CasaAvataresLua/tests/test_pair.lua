package.path='./?.lua;'..package.path
local Simulation=require('simulation')
local Settings=require('settings')
local sim=Simulation.new(Settings)
local pair={id='dupla_adult_01',dupla=true,duracao=15}
assert(sim:ativarDupla(pair))
for i=1,1500 do sim:update(.03);if sim.dupla and not sim.dupla.pendente then break end end
assert(sim.dupla and not sim.dupla.pendente,'Deveria iniciar sincronizada após chegada')
assert(sim.agentes[1].animTime==sim.agentes[2].animTime,'Clipes precisam iniciar juntos')
local count=#sim.historico
for i=1,200 do sim:update(.03) end
assert(#sim.historico==count,'Sem diálogo espontâneo durante a cena')
sim:setTotal(1)
assert(sim.dupla==nil)
assert(not sim:ativarDupla(pair),'Não pode executar cena com 1 agente')
print('OK: cenas em dupla e sincronização.')
