-- Teste simples sem gráficos: pode ser rodado por um interpretador Lua 5.4.
package.path = './?.lua;' .. package.path
local Settings = require('settings')
local Nav = require('navigation')
local Simulation = require('simulation')
local Agent = require('agent')
math.randomseed(1740)
local path = Nav.findPath(-1,1,4.4,2.4)
assert(#path > 0 and #path < 200, 'Navegação: caminho não encontrado')
local sim = Simulation.new(Settings)
for i=1,5000 do sim:update(.04) end
assert(sim.tempo > 150, 'Tempo simulado deveria avançar')
for i=1,2 do
  local a = sim.agentes[i]
  assert(a.x > -5.5 and a.x < 5.5, 'Avatar fora do cenário no eixo x')
  assert(a.z > -4 and a.z < 4, 'Avatar fora do cenário no eixo z')
  assert(a.energia >=0 and a.energia <= 100, 'Energia fora de faixa')
end
sim:setTotal(1)
sim:setComunicacao(true)
local oldHistory = #sim.historico
local lastSpeech = #sim.historico > 0 and sim.historico[#sim.historico].tempo or 0
for i=1,2000 do sim:update(.04) end
assert(#sim.historico == oldHistory, 'Houve diálogo com um avatar apenas')
assert((#sim.historico > 0 and sim.historico[#sim.historico].tempo or 0) == lastSpeech, 'Fala inesperada ao ficar sozinho')
sim:setTotal(2)
sim:setComunicacao(true)
sim:ativarAnimacao(1,'dance')
assert(sim.agentes[1].acao == 'dance')
for i=1,2000 do sim:update(.04) end
assert(#sim.historico > 0 and sim.historico[#sim.historico].tempo > lastSpeech, 'Esperava diálogo com dois agentes')
print('OK: navegação, comportamento, 1 e 2 agentes, diálogo e ações.')
