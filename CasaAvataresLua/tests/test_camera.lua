package.path='./?.lua;'..package.path
local Camera=require('camera')
local c=Camera.new()
assert(c:irPara(4) and c.vista==4)
local x,z=c.focusX,c.focusZ
c:orbitar(30,-20)
assert(c.pitch>.2 and c.pitch<1.4)
c:aproximar(100);assert(c.distance==4.5)
c:aproximar(-100);assert(c.distance==32)
c.follow=true
c:seguir({x=1,z=2},.25)
assert(math.abs(c.focusX-1)<.001 and math.abs(c.focusZ-2)<.001)
c:arrastar(10,10,2)
assert(c.follow==false)
assert(not c:irPara(7))
assert(c:irPara(1) and c.focusX==0)
print('OK: câmera, zoom, vistas e acompanhamento.')
