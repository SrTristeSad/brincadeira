-- Verifica o fluxo de carregamento e reprodução de clipes GLB, sem importar GLB real.
package.path = './?.lua;' .. package.path
local Avatar = require('avatars')
local Agent = require('agent')
local Settings = require('settings')
local animations = {'Idle_01','Walking_01','Dancing_01'}
local hits = {}
local model = {}
function model:getBoundingBox() return -.3,.3,0,1.75,-.25,.25 end
function model:getAnimationCount() return #animations end
function model:getAnimationName(i) return animations[i] end
function model:resetNodeTransforms() hits.reset = (hits.reset or 0)+1 end
function model:animate(i,t) hits.last = i end
lovr = {
  filesystem = {isFile = function(path) return path == 'assets/avatar1.glb' end},
  graphics = {newModel = function(file) return model end}
}
local p = {}
for _, method in ipairs({'push','pop','translate','rotate','scale','setColor','draw'}) do
  p[method] = function() end
end
local a = Agent.new(1,Settings.avatares[1])
Avatar.carregar(a)
assert(a.modelo == model)
a.estado = 'agir'; a.acao = 'dance'; a.animTime = 1.2
Avatar.draw(p,a)
assert(hits.last == 3, 'Dança deveria usar o terceiro clipe')
a.estado = 'andar'; a.acao = 'read'; a.animTime = .4
Avatar.draw(p,a)
assert(hits.last == 2, 'Andar deveria usar o segundo clipe')
a.estado = 'agir'; a.acao = 'cook'
Avatar.draw(p,a)
assert(hits.last == 1, 'Sem clipe de cozinha, usar o idle')
print('OK: mock de GLB, aliases de animação e fallback idle.')
