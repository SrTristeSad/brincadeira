package.path='./?.lua;'..package.path
local Nav=require('navigation')
local path=assert(Nav.findPath(-1,1,4.4,2.4))
assert(#path>0 and #path<180)
for _,p in ipairs(path) do assert(not Nav.isBlocked(p.x,p.z),'Caminho cruza móveis') end
local near=assert(Nav.findPath(0,0,0,0))
assert(#near==0)
assert(Nav.isBlocked(99,99))
print('OK: A* e colisão com móveis.')
