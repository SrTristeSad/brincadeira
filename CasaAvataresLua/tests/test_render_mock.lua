-- Smoke-test da camada gráfica sem GPU: simula chamadas de interface do LÖVR.
package.path = './?.lua;' .. package.path
local draws = 0
lovr = {
  graphics = {setBackgroundColor = function(...) end},
  filesystem = {isFile = function(_) return false end},
  system = {isKeyDown = function(...) return false end},
  event = {quit = function() end}
}
local mock = {}
for _,method in ipairs({'box','sphere','setColor','text','push','pop',
                         'translate','rotate','scale','draw','setViewPose'}) do
  mock[method] = function(self,...)
    draws = draws + 1
  end
end
function mat4() return {lookAt=function(self,...) return self end} end
function vector(...) return {...} end
require('main')
lovr.load()
for i=1,35 do
  lovr.update(.05)
  lovr.draw(mock)
end
lovr.keypressed('1', 0, false)
lovr.draw(mock)
lovr.keypressed('c', 0, false)
lovr.keypressed('2', 0, false)
lovr.keypressed('tab', 0, false)
for i=1,21 do
  lovr.keypressed('t', 0, false)
  lovr.update(.05)
  lovr.draw(mock)
end
lovr.keypressed('space', 0, false)
lovr.update(.05)
lovr.draw(mock)
lovr.keypressed('space', 0, false)
lovr.keypressed('r', 0, false)
lovr.draw(mock)
assert(draws > 1200, 'Esperava chamadas de desenho da casa')
print('OK: renderização mockada e controles. Desenhos:',draws)
