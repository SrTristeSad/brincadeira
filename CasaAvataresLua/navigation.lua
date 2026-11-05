-- A* em grade para circular entre os móveis sem atravessá-los.
-- Implementação independente para a planta da Casa Viva.
local Nav = {}
local CELL = .35
local MINX, MAXX, MINZ, MAXZ = -5.45, 5.45, -3.85, 3.85
local NX = math.floor((MAXX-MINX)/CELL)+1
local NZ = math.floor((MAXZ-MINZ)/CELL)+1
local obstacles = {
  {-4.95,-1.80, 1.62,3.17}, {-4.15,-2.38,-.03,1.06},
  {-5.40,-2.60,-4.12,-3.19}, {-5.65,-5.03,-1.60,-.03},
  {1.95,3.67,.52,1.98}, {2.56,5.08,-4.00,-1.00},
  {-.85,.96,-4.00,-3.17}, {4.68,5.40,2.15,3.22}
}
function Nav.isBlocked(x,z)
  if x<MINX or x>MAXX or z<MINZ or z>MAXZ then return true end
  for _,r in ipairs(obstacles) do
    if x>r[1] and x<r[2] and z>r[3] and z<r[4] then return true end
  end
  return false
end
local function key(i,j) return (j-1)*NX+i end
local function point(i,j) return MINX+(i-1)*CELL,MINZ+(j-1)*CELL end
local function cell(x,z)
  return math.max(1,math.min(NX,math.floor((x-MINX)/CELL+.5)+1)),
    math.max(1,math.min(NZ,math.floor((z-MINZ)/CELL+.5)+1))
end
local function snap(i,j)
  for radius=0,9 do
    local bx,bz,dist
    for dx=-radius,radius do for dz=-radius,radius do
      local x,z=i+dx,j+dz
      if x>=1 and x<=NX and z>=1 and z<=NZ then
        local px,pz=point(x,z)
        if not Nav.isBlocked(px,pz) then
          local d=dx*dx+dz*dz
          if not dist or d<dist then bx,bz,dist=x,z,d end
        end
      end
    end end
    if bx then return bx,bz end
  end
end
local function heuristic(i,j,ti,tj) return math.abs(i-ti)+math.abs(j-tj) end
function Nav.findPath(x1,z1,x2,z2)
  local si,sj=cell(x1,z1); local ti,tj=cell(x2,z2)
  si,sj=snap(si,sj); ti,tj=snap(ti,tj)
  if not si or not ti then return nil end
  local start,finish=key(si,sj),key(ti,tj)
  if start==finish then return {} end
  local open,inside,closed,previous,gscore={}, {}, {}, {}, {[start]=0}
  local function queue(k,i,j,score)
    open[#open+1]={k=k,i=i,j=j,f=score}; inside[k]=true
  end
  queue(start,si,sj,heuristic(si,sj,ti,tj))
  local steps={{1,0},{-1,0},{0,1},{0,-1}}
  while #open>0 do
    local best=1
    for n=2,#open do if open[n].f<open[best].f then best=n end end
    local node=table.remove(open,best)
    inside[node.k]=nil
    if not closed[node.k] then
      if node.k==finish then
        local reversed,k={},finish
        while k~=start do
          local j=math.floor((k-1)/NX)+1
          local i=k-(j-1)*NX
          local x,z=point(i,j)
          reversed[#reversed+1]={x=x,z=z}
          k=previous[k]
          if not k then return nil end
        end
        local path={}
        for n=#reversed,1,-1 do path[#path+1]=reversed[n] end
        return path
      end
      closed[node.k]=true
      for _,step in ipairs(steps) do
        local i,j=node.i+step[1],node.j+step[2]
        if i>=1 and i<=NX and j>=1 and j<=NZ then
          local x,z=point(i,j);local k=key(i,j)
          if not closed[k] and not Nav.isBlocked(x,z) then
            local score=gscore[node.k]+1
            if not gscore[k] or score<gscore[k] then
              previous[k]=node.k; gscore[k]=score
              local f=score+heuristic(i,j,ti,tj)
              if inside[k] then
                for _,item in ipairs(open) do if item.k==k then item.f=f end end
              else queue(k,i,j,f) end
            end
          end
        end
      end
    end
  end
  return nil
end
return Nav
