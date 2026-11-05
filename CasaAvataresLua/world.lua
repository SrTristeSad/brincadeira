-- Casa Viva | diorama 3D original, sem downloads de cenários e sem Blender.
-- Decorações são desenhadas com primitivas do LÖVR, todas editáveis aqui.
local W = {}
local C = {
  grass={.36,.58,.39}, grass2={.40,.62,.42}, land={.27,.43,.32},
  wall={.94,.91,.84}, wallEdge={.79,.75,.69}, frame={.23,.37,.41}, glass={.66,.84,.88},
  wood={.64,.42,.29}, wood2={.73,.51,.36}, wood3={.82,.62,.46}, darkwood={.35,.25,.25},
  floor={.87,.75,.61}, floor2={.91,.80,.66}, pale={.98,.95,.86},
  tile={.91,.91,.85}, tile2={.80,.86,.82},
  teal={.16,.47,.49}, teal2={.22,.60,.59}, sofa={.27,.60,.64},
  mustard={.93,.61,.33}, terracotta={.70,.35,.27}, gold={.87,.66,.32},
  shade={.19,.25,.29}, metal={.52,.58,.58}, monitor={.17,.22,.24},
  white={.98,.98,.96}, linen={.88,.84,.72}, rug={.92,.67,.50},
  leaf={.24,.50,.34}, leaf2={.39,.63,.38}, leaf3={.52,.71,.41},
  pot={.75,.43,.34}, pink={.84,.48,.51}, blue={.50,.64,.73},
  water={.37,.68,.77}, sun={1.0,.84,.59}, shadow={.31,.35,.29},
}
local function box(p,c,x,y,z,w,h,d,rot)
 p:setColor(c[1],c[2],c[3])
 p:box(x,y,z,w,h,d,rot or 0,0,1,0)
end
local function sphere(p,c,x,y,z,r)
 p:setColor(c[1],c[2],c[3]);p:sphere(x,y,z,r)
end
local function ellipsoid(p,c,x,y,z,rx,ry,rz)
 p:setColor(c[1],c[2],c[3]);p:push();p:translate(x,y,z);p:scale(rx,ry,rz);p:sphere(0,0,0,1);p:pop()
end
local function cylinder(p,c,x,y,z,r,length)
 p:setColor(c[1],c[2],c[3]);p:cylinder(x,y,z,r,length)
end
local function plankFloor(p)
 box(p,C.darkwood,0,-.22,0,12.5,.35,9.5)
 box(p,C.pale,0,-.027,0,12.2,.035,9.1)
 for z=-4.2,4.3,.45 do
  box(p,(math.floor((z+5)*4)%3==0) and C.floor or C.floor2,-.35,-.008,z,11.30,.024,.42)
  -- seams at alternating points to make the wooden floor legible
  for x=-5.35,4.95,2.25 do
   local shift = math.floor(z*9)%2==0 and 0 or .45
   box(p,C.wood3,x+shift,.006,z,.022,.01,.39)
  end
 end
 -- tile floor in the kitchen (back left)
 box(p,C.tile,-3.84,.01,-2.75,4.12,.065,3.52)
 for i=0,8 do for j=0,7 do
  if (i+j)%2==0 then box(p,C.tile2,-5.75+i*.47,.048,-4.25+j*.44,.464,.010,.436) end
 end end
end
local function greenery(p,x,z,size)
 local s=size or 1
 ellipsoid(p,C.shadow,x,.04,z,.42*s,.025,.37*s)
 cylinder(p,C.pot,x,.23*s,z,.20*s,.44*s)
 cylinder(p,C.wood,x,.60*s,z,.057*s,.40*s)
 for i=1,6 do
  local a=i*math.pi/3
  ellipsoid(p,i%3==0 and C.leaf3 or (i%2==0 and C.leaf or C.leaf2),
   x+math.cos(a)*.18*s,.88*s+math.sin(a*2)*.09*s,z+math.sin(a)*.17*s,
   .23*s,.27*s,.23*s)
 end
end
local function window(p,x,z,width)
 box(p,C.frame,x,1.79,z,width+.17,1.36,.14)
 box(p,C.glass,x,1.79,z+.083,width,1.21,.055)
 box(p,C.pale,x,1.79,z+.12,.055,1.31,.06)
 box(p,C.pale,x,1.79,z+.12,width,.055,.06)
 box(p,C.wood3,x,1.11,z+.15,width+.27,.11,.33)
 box(p,C.pale,x,2.49,z,width+.26,.14,.27)
end
local function walls(p)
 -- Dollhouse: back and side walls, front edge deliberately low so the rooms remain visible.
 box(p,C.wall,0,1.38,-4.61,12.3,2.74,.23)
 box(p,C.wall,-6.13,1.37,0,.23,2.75,9.43)
 box(p,C.wall,6.13,1.37,0,.23,2.75,9.43)
 box(p,C.wallEdge,0,2.75,-4.58,12.35,.18,.38)
 box(p,C.wallEdge,-6.1,2.75,0,.32,.18,9.45)
 box(p,C.wallEdge,6.1,2.75,0,.32,.18,9.45)
 box(p,C.wallEdge,0,.16,4.63,12.3,.30,.19)
 -- partial room divider: separates the bedroom without obscuring its furniture
 box(p,C.wall,1.83,1.02,-3.63,.16,2.05,1.75)
 box(p,C.wallEdge,1.83,2.09,-3.63,.21,.09,1.83)
 box(p,C.wall,5.40,.88,-1.19,1.40,1.75,.13)
 box(p,C.wallEdge,5.40,1.78,-1.19,1.44,.10,.18)
 window(p,-3.70,-4.43,1.70)
 window(p, 4.17,-4.43,1.50)
 -- area frame and wall artwork
 box(p,C.wood3,.15,1.67,-4.41,1.12,.87,.08)
 box(p,C.pale,.15,1.67,-4.347,.97,.72,.055)
 ellipsoid(p,C.sun,.22,1.75,-4.30,.22,.22,.02)
 box(p,C.leaf3,.05,1.42,-4.294,.58,.16,.022)
 box(p,C.frame,-5.97,1.54,-.30,.06,.9,1.28)
 box(p,C.pink,-5.93,1.53,-.30,.07,.69,1.06)
 -- front porch / stairs
 box(p,C.pale,.1,-.21,4.85,2.88,.23,.55)
 box(p,C.wood3,.1,-.35,5.35,2.40,.17,.44)
end
local function outside(p)
 box(p,C.grass,0,-.46,.4,17.8,.12,14.0)
 box(p,C.grass2,0,-.39,5.85,17.8,.02,2.8)
 -- small garden beds and stone footpath
 for i=1,10 do
  local x=(i%2==0 and -.48 or .45)+.18*math.sin(i)
  box(p,C.pale,x,-.37,6.20+i*.45,.87,.06,.36)
 end
 for _,x in ipairs({-7.15,7.15}) do
  cylinder(p,C.darkwood,x,.21,3.3,.17,1.55)
  for i=1,5 do
   local a=i*math.pi*2/5
   ellipsoid(p,i%2==0 and C.leaf2 or C.leaf3,x+math.cos(a)*.45,1.23+math.sin(i)*.15,3.3+math.sin(a)*.37,.59,.60,.53)
  end
 end
 for i=1,16 do
  local x=-7.45+i*.82
  ellipsoid(p,i%2==0 and C.leaf3 or C.leaf2,x,-.24,5.39,.19,.18,.20)
 end
end
local function softSofa(p)
 -- rug with trim, L-shaped sofa and soft cushions
 box(p,C.rug,-3.52,.045,1.63,3.70,.038,2.72)
 box(p,C.pale,-3.52,.069,1.63,3.44,.019,2.46)
 box(p,C.rug,-3.52,.080,1.63,3.25,.01,2.24)
 for i=0,5 do box(p,C.pale,-5.02+i*.55,.084,1.64,.035,.011,2.06) end
 box(p,C.wood,-3.63,.29,2.83,3.18,.52,.42)
 box(p,C.teal,-3.55,.35,2.37,2.95,.59,1.30)
 box(p,C.sofa,-3.56,.83,2.98,2.99,.91,.30)
 box(p,C.teal,-5.04,.64,2.36,.32,.74,1.43)
 box(p,C.teal,-2.04,.64,2.36,.32,.74,1.43)
 for i=0,2 do
  ellipsoid(p,C.teal2,-4.46+i*.92,.72,2.33,.41,.24,.55)
  ellipsoid(p,i==1 and C.mustard or C.linen,-4.42+i*.92,.91,2.83,.32,.30,.16)
 end
 -- coffee table with a tray and decorative cups
 box(p,C.darkwood,-3.49,.39,.54,1.70,.12,.83)
 for _,x in ipairs({-4.17,-2.81}) do
  for _,z in ipairs({.27,.79}) do cylinder(p,C.darkwood,x,.18,z,.055,.32) end
 end
 cylinder(p,C.pale,-3.55,.48,.55,.18,.045)
 cylinder(p,C.gold,-3.52,.57,.55,.065,.15)
 -- entertainment cabinet and TV, screen faces +Z
 box(p,C.darkwood,-1.03,.32,2.18,.43,.62,2.07)
 box(p,C.monitor,-1.05,1.24,2.18,.17,1.32,1.72)
 box(p,C.blue,-.95,1.25,2.18,.045,1.08,1.52)
end
local function kitchen(p)
 -- Cabinets, counter, appliances, handles, sink, backsplash
 box(p,C.wood2,-4.00,.48,-3.57,3.26,.96,.94)
 box(p,C.pale,-4.00,.98,-3.57,3.43,.12,1.03)
 for i=0,3 do
  box(p,i%2==0 and C.floor or C.wood3,-5.12+i*.75,.49,-3.01,.68,.70,.07)
  sphere(p,C.gold,-5.08+i*.75,.52,-2.967,.032)
 end
 box(p,C.tile2,-4.00,1.55,-4.42,3.47,.73,.04)
 for i=0,6 do box(p,C.pale,-5.60+i*.49,1.52,-4.37,.023,.68,.05) end
 box(p,C.monitor,-4.58,1.06,-3.55,.89,.04,.58)
 for _,x in ipairs({-4.80,-4.39}) do for _,z in ipairs({-3.77,-3.40}) do
  cylinder(p,C.metal,x,1.10,z,.072,.022)
 end end
 -- oven
 box(p,C.monitor,-3.30,.50,-2.967,.62,.50,.06)
 box(p,C.metal,-3.30,.80,-2.958,.50,.055,.05)
 -- sink
 box(p,C.metal,-5.10,1.042,-3.57,.77,.023,.58)
 box(p,C.glass,-5.10,1.052,-3.57,.61,.015,.45)
 cylinder(p,C.metal,-5.10,1.24,-3.80,.042,.34)
 -- fridge + handle
 box(p,C.white,-2.13,.94,-3.92,.86,1.85,.87)
 box(p,C.metal,-2.13,.92,-3.43,.037,.57,.055)
 box(p,C.metal,-2.13,1.57,-3.43,.037,.40,.055)
 box(p,C.wood,-4.24,1.90,-4.15,2.25,.43,.38)
 for i=0,2 do box(p,C.wood3,-5.0+i*.76,1.90,-3.91,.65,.35,.045) end
 -- countertop accessories
 cylinder(p,C.terracotta,-3.66,1.14,-3.50,.13,.19)
 ellipsoid(p,C.leaf3,-3.66,1.31,-3.50,.15,.18,.11)
end
local function dining(p)
 -- round dining table + chairs and plates
 cylinder(p,C.darkwood,3.17,.41,1.35,.14,.76)
 cylinder(p,C.wood3,3.17,.81,1.35,1.04,.13)
 cylinder(p,C.pale,3.17,.89,1.35,.76,.03)
 for i=1,4 do
  local a=(i-1)*math.pi/2
  local x,z=3.17+math.cos(a)*1.41,1.35+math.sin(a)*1.34
  cylinder(p,C.wood,x,.45,z,.35,.18)
  cylinder(p,C.darkwood,x,.23,z,.075,.42)
  box(p,C.wood2,x,.93,z+math.sin(a)*.26,.68,.80,.13,a+math.pi/2)
  cylinder(p,C.pale,3.17+math.cos(a)*.65,.91,1.35+math.sin(a)*.65,.14,.025)
 end
 cylinder(p,C.pot,3.17,1.08,1.35,.11,.27)
 for i=0,3 do
  ellipsoid(p,i%2==0 and C.pink or C.mustard,3.17+math.cos(i*1.6)*.1,1.30,1.35+math.sin(i*1.6)*.10,.10,.14,.10)
 end
end
local function bedroom(p)
 -- large bed; two pillows, blanket with folded corner, bedside lights
 box(p,C.darkwood,4.18,.37,-2.83,2.72,.73,2.86)
 box(p,C.pale,4.18,.77,-2.85,2.60,.24,2.68)
 box(p,C.blue,4.18,.90,-2.12,2.56,.15,1.26)
 box(p,C.linen,4.18,.88,-3.45,2.58,.14,1.14)
 box(p,C.darkwood,4.18,1.16,-4.24,2.82,.92,.20)
 for _,x in ipairs({3.51,4.84}) do
  ellipsoid(p,C.white,x,.98,-3.75,.55,.14,.34)
 end
 box(p,C.rug,4.08,.04,-1.06,3.75,.035,1.01)
 box(p,C.pale,4.08,.07,-1.06,3.45,.014,.81)
 for _,x in ipairs({2.64,5.70}) do
  box(p,C.wood2,x,.41,-2.89,.58,.82,.59)
  cylinder(p,C.gold,x,.89,-2.88,.09,.16)
  ellipsoid(p,C.sun,x,1.04,-2.88,.23,.19,.23)
 end
end
local function office(p)
 box(p,C.wood3,.10,.79,-3.61,1.72,.12,.67)
 for _,x in ipairs({-.59,.80}) do box(p,C.darkwood,x,.39,-3.61,.10,.75,.60) end
 box(p,C.darkwood,.12,1.18,-3.91,.73,.68,.08)
 box(p,C.blue,.12,1.19,-3.864,.63,.56,.023)
 box(p,C.metal,.12,.86,-3.64,.74,.045,.25)
 -- simple swivel chair, big enough to see from above
 cylinder(p,C.darkwood,.08,.43,-2.58,.29,.08)
 box(p,C.teal,.08,.50,-2.58,.67,.16,.63)
 box(p,C.teal,.08,.88,-2.34,.70,.78,.16)
 cylinder(p,C.darkwood,.08,.24,-2.58,.075,.39)
 box(p,C.darkwood,.08,.05,-2.58,.70,.06,.14)
end
local function decor(p,sim)
 -- bookshelf with readable books
 box(p,C.darkwood,-5.55,1.19,-.42,.38,2.11,1.49)
 for _,y in ipairs({.43,1.04,1.64,2.11}) do box(p,C.wood3,-5.26,y,-.42,.45,.075,1.56) end
 for i=1,16 do
  local col=({C.terracotta,C.mustard,C.teal,C.pale,C.blue})[(i%5)+1]
  box(p,col,-5.15,1.39,-1.09+i*.09,.22,.37+(i%3)*.06,.066)
 end
 -- hanging lamps
 for _,pos in ipairs({{-3.40,1.25},{3.14,1.29},{3.97,-2.63}}) do
  local x,z=pos[1],pos[2]
  cylinder(p,C.darkwood,x,2.43,z,.035,.55)
  ellipsoid(p,C.sun,x,2.15,z,.25,.17,.25)
 end
 greenery(p,5.55,3.28,1.08)
 greenery(p,-1.06,-1.43,.83)
 -- colorful runner at entrance
 box(p,C.teal,0,.04,3.80,2.3,.04,.75)
 for i=0,5 do box(p,C.mustard,-.88+i*.34,.07,3.80,.07,.012,.52) end
 -- framed painting
 box(p,C.wood3,.72,1.66,-4.39,1.11,.93,.10)
 box(p,C.pale,.72,1.66,-4.325,.94,.78,.04)
 ellipsoid(p,C.sun,.88,1.78,-4.298,.20,.20,.02)
 ellipsoid(p,C.leaf2,.61,1.42,-4.291,.34,.11,.025)
 -- activity markers under agent feet, animated when available
 if sim then for i=1,sim.total do
  local a=sim.agentes[i];local color=i==1 and C.blue or C.mustard
  ellipsoid(p,color,a.x,.035,a.z,.24,.017,.24)
 end end
end
function W.draw(p,sim)
 outside(p)
 plankFloor(p)
 walls(p)
 softSofa(p)
 kitchen(p)
 dining(p)
 bedroom(p)
 office(p)
 decor(p,sim)
end
return W
