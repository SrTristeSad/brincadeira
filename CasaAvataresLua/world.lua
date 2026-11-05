-- Casa 3D construída inteiramente com formas geométricas do LÖVR.
-- Não há necessidade de Blender ou de texturas externas para a casa funcionar.
local World = {}
local C = {
  wood = {.52,.35,.26}, woodLight={.71,.52,.35}, floor={.83,.73,.60},
  plaster={.94,.92,.86}, trim={.29,.38,.40}, brick={.65,.39,.33},
  rug={.49,.65,.69}, sofa={.33,.55,.64}, cushion={.86,.82,.73},
  counter={.89,.88,.84}, fridge={.83,.87,.89}, bed={.67,.73,.82},
  pillow={.95,.95,.94}, green={.24,.54,.34}, dark={.17,.23,.29},
  glass={.60,.80,.90}, warm={.98,.81,.52}, gold={.82,.65,.35},
  leaves2={.32,.63,.43}, gray={.48,.51,.55}
}
local function box(p,c,x,y,z,w,h,d,rot)
  p:setColor(c[1],c[2],c[3])
  p:box(x,y,z,w,h,d,rot or 0,0,1,0)
end
local function sphere(p,c,x,y,z,r)
  p:setColor(c[1],c[2],c[3])
  p:sphere(x,y,z,r)
end
local function post(p,x,z)
  box(p,C.wood,x,.4,z,.13,.80,.13)
end
local function plant(p,x,z)
  box(p,C.brick,x,.24,z,.42,.47,.40)
  box(p,C.wood,x,.65,z,.08,.54,.08)
  for i = 1, 5 do
    local a = i * math.pi * 2 / 5
    sphere(p,i % 2 == 0 and C.green or C.leaves2,
      x + math.cos(a) * .20, .96 + (i % 3) * .10,
      z + math.sin(a) * .20, .24)
  end
end
local function books(p,x,y,z)
  for i=1,7 do
    local c = i % 3 == 0 and C.gold or (i % 2 == 0 and C.rug or C.brick)
    box(p,c,x + (i-4)*.105,y,z,.075,.36+(i%3)*.08,.18)
  end
end
local function window(p,x,y,z,w)
  box(p,C.trim,x,y,z,w+.10,1.36,.13)
  box(p,C.glass,x,y,z+.08,w,1.24,.05)
  box(p,C.plaster,x,y,z+.13,.065,1.24,.05)
  box(p,C.plaster,x,y,z+.13,w,.065,.05)
end

local function sofa(p)
  box(p,C.rug,-3.40,.03,1.86,3.50,.05,2.42)
  box(p,C.sofa,-3.35,.34,2.45,2.70,.47,1.40)
  box(p,C.sofa,-3.35,.80,3.02,2.70,.65,.25)
  box(p,C.sofa,-4.72,.61,2.38,.22,.56,1.25)
  box(p,C.sofa,-1.98,.61,2.38,.22,.56,1.25)
  box(p,C.cushion,-4.03,.61,2.41,.65,.14,.58)
  box(p,C.cushion,-2.71,.61,2.41,.65,.14,.58)
  -- mesa de centro, colocada diante do sofá
  box(p,C.woodLight,-3.30,.43,.44,1.45,.13,.75)
  for _,x in ipairs({-3.91,-2.69}) do
    for _,z in ipairs({.17,.70}) do post(p,x,z) end
  end
  box(p,C.warm,-3.08,.54,.45,.23,.08,.25)
end

local function kitchen(p)
  box(p,C.woodLight,-4.03,.48,-3.67,3.02,.95,.79)
  box(p,C.counter,-4.03,.98,-3.67,3.10,.11,.86)
  for i=0,2 do
    box(p,C.wood,-4.95+i*.89,.47,-3.21,.76,.69,.04)
    sphere(p,C.gray,-4.95+i*.89,.47,-3.17,.035)
  end
  box(p,C.dark,-4.45,1.05,-3.64,.70,.035,.48)
  for _,x in ipairs({-4.65,-4.26}) do
    for _,z in ipairs({-3.82,-3.48}) do sphere(p,C.gray,x,1.09,z,.07) end
  end
  box(p,C.fridge,-2.07,.96,-3.88,.80,1.92,.85)
  box(p,C.dark,-2.07,1.00,-3.43,.035,.44,.035)
  box(p,C.wood,-4.20,1.85,-4.14,2.70,.36,.34)
  box(p,C.gold,-3.23,1.15,-3.52,.33,.13,.31)
end

local function dining(p)
  box(p,C.woodLight,2.75,.74,1.24,1.73,.13,1.39)
  for _,x in ipairs({2.11,3.39}) do
    for _,z in ipairs({.72,1.76}) do
      box(p,C.wood,x,.36,z,.13,.72,.13)
    end
  end
  for _,z in ipairs({.21,2.27}) do
    box(p,C.woodLight,2.75,.46,z,.70,.14,.60)
    box(p,C.wood,2.75,.85,z + (z < 1 and -.22 or .22),.70,.8,.13)
    for _,x in ipairs({2.49,3.02}) do
      box(p,C.wood,x,.22,z,.10,.45,.10)
    end
  end
  box(p,C.green,2.75,.84,1.24,.24,.11,.24)
end

local function bedroom(p)
  box(p,C.wood,3.78,.38,-2.55,2.40,.73,2.87)
  box(p,C.bed,3.78,.79,-2.55,2.28,.22,2.75)
  box(p,C.pillow,3.30,.94,-3.56,.75,.19,.47)
  box(p,C.pillow,4.24,.94,-3.56,.75,.19,.47)
  box(p,C.wood,3.78,1.08,-4.08,2.48,.74,.18)
  box(p,C.woodLight,5.30,.49,-2.35,.40,.85,.64)
  box(p,C.warm,5.29,1.02,-2.35,.27,.29,.27)
end

local function office(p)
  box(p,C.woodLight,.16,.78,-3.70,1.74,.14,.64)
  box(p,C.wood,-.56,.39,-3.70,.11,.79,.53)
  box(p,C.wood,.88,.39,-3.70,.11,.79,.53)
  box(p,C.dark,.10,1.20,-3.92,.65,.65,.09)
  box(p,C.gray,.10,.88,-3.61,.71,.05,.23)
  box(p,C.wood,.15,.41,-2.77,.64,.12,.58)
  box(p,C.wood,.15,.78,-2.48,.64,.67,.13)
end

local function decorations(p)
  -- estante, quadro, janelas, vasos e luminária
  box(p,C.woodLight,-5.36,1.22,-.86,.30,2.12,1.35)
  for _,y in ipairs({.46,1.09,1.73}) do
    box(p,C.wood,-5.05,y,-.85,.45,.08,1.40)
  end
  books(p,-4.95,1.35,-.84)
  plant(p,5.07,2.83)
  box(p,C.trim,-.05,1.62,-4.37,1.33,1.05,.08)
  box(p,C.rug,-.05,1.62,-4.31,1.16,.89,.055)
  box(p,C.gold,-.05,1.62,-4.25,.52,.50,.05)
  window(p,-3.60,1.88,-4.42,1.40)
  window(p,3.55,1.88,-4.42,1.36)
  box(p,C.woodLight,1.10,2.55,2.68,.18,.42,.18)
  sphere(p,C.warm,1.10,2.29,2.68,.25)
  box(p,C.rug,-.1,.015,1.17,1.95,.03,1.35)
  box(p,C.wood,0,.15,3.75,1.65,.19,.55) -- soleira
end

function World.draw(p,sim)
  -- Piso, paredes cortadas para mostrar o interior, rodapés, coluna.
  box(p,C.floor,0,-.14,0,12.2,.28,9.25)
  box(p,C.plaster,0,1.37,-4.57,12.2,2.75,.22)
  box(p,C.plaster,-6.03,1.37,0,.22,2.75,9.25)
  box(p,C.plaster,6.03,1.37,0,.22,2.75,9.25)
  box(p,C.plaster,-5.10,.60,4.55,1.85,1.25,.22)
  box(p,C.plaster,5.10,.60,4.55,1.85,1.25,.22)
  box(p,C.trim,0,2.74,-4.58,12.4,.14,.30)
  box(p,C.trim,-6.02,2.74,0,.28,.14,9.4)
  box(p,C.trim,6.02,2.74,0,.28,.14,9.4)
  box(p,C.woodLight,0,-.22,4.55,12.4,.18,.18)
  for i=-5,5 do
    box(p,C.woodLight,i,0,0,.022,.008,9.02)
  end
  sofa(p)
  kitchen(p)
  dining(p)
  bedroom(p)
  office(p)
  decorations(p)
  -- Painel de estado colocado sobre a parede do fundo.
  box(p,C.dark,0,2.23,-4.40,2.30,.68,.12)
  p:setColor(.93,.95,.95)
  local status = 'CASA VIVA | LUA\n' .. (sim.total == 2 and '2 AVATARES' or '1 AVATAR')
  p:text(status,0,2.23,-4.325,.21)
end

return World
