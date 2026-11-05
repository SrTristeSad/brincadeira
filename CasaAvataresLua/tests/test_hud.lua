package.path='./?.lua;'..package.path
local H=require('hud')
assert(H.hit(35,91,1280,800)=='room1')
assert(H.hit(201,90,1280,800)=='room2')
assert(H.hit(320,91,1280,800)=='room3')
assert(H.hit(460,91,1280,800)=='room4')
assert(H.hit(1200,702,1280,800)=='play')
assert(H.hit(15,15,1280,800)==nil)
print('OK: botões da interface e regiões clicáveis.')
