-- Camera orbital com atalhos de ambientes, zoom e acompanhamento.
local Camera = {}
Camera.__index = Camera
Camera.vistas = {
  {nome='Casa inteira', x=0, z=0, yaw=-.24, pitch=.64, distance=16.7},
  {nome='Sala', x=-3.2, z=1.45, yaw=-.18, pitch=.75, distance=8.4},
  {nome='Cozinha', x=-3.75, z=-2.65, yaw=-.23, pitch=.79, distance=8.0},
  {nome='Quarto', x=3.8, z=-2.35, yaw=.12, pitch=.79, distance=7.8}
}
local function clamp(x,a,b) return math.max(a,math.min(b,x)) end
function Camera.new()
  local self = setmetatable({focusX=0,focusZ=0,follow=false,drag=0},Camera)
  self:irPara(1)
  return self
end
function Camera:irPara(i)
  local v = Camera.vistas[i]
  if not v then return false end
  self.focusX,self.focusZ = v.x,v.z
  self.yaw,self.pitch,self.distance = v.yaw,v.pitch,v.distance
  self.follow = false
  self.vista = i
  return true
end
function Camera:orbitar(dx,dy)
  self.yaw = self.yaw + dx*.006
  self.pitch = clamp(self.pitch + dy*.006,.24,1.38)
end
function Camera:aproximar(delta)
  self.distance = clamp(self.distance - delta,4.5,32)
end
function Camera:arrastar(dx,dy,button)
  if button == 1 then self:orbitar(dx,dy)
  elseif button == 2 or button == 3 then
    local scale = self.distance*.003
    self.focusX = clamp(self.focusX - dx*math.cos(self.yaw)*scale,-7,7)
    self.focusZ = clamp(self.focusZ + dy*scale,-5,6)
    self.follow = false
  end
end
function Camera:seguir(a,dt)
  if not self.follow or not a then return end
  local amount = clamp(dt*4,0,1)
  self.focusX = self.focusX + (a.x-self.focusX)*amount
  self.focusZ = self.focusZ + (a.z-self.focusZ)*amount
end
function Camera:posicao()
  local horizontal = math.cos(self.pitch)*self.distance
  return self.focusX+math.sin(self.yaw)*horizontal,
    .7+math.sin(self.pitch)*self.distance,
    self.focusZ+math.cos(self.yaw)*horizontal
end
return Camera
