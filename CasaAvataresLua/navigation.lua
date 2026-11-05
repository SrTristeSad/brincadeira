-- Busca de caminhos numa grade 2D para os personagens não atravessarem os móveis.
local Nav = {}
local CELL = .35
local MINX, MAXX, MINZ, MAXZ = -5.45, 5.45, -3.85, 3.85
local NX = math.floor((MAXX - MINX) / CELL) + 1
local NZ = math.floor((MAXZ - MINZ) / CELL) + 1
local obstacles = {
  -- sofá, mesa de centro, balcão, estante, mesa de jantar, cama, escritório
  {-4.95, -1.80, 1.62, 3.17},
  {-4.15, -2.38, -.03, 1.06},
  {-5.40, -2.60, -4.12, -3.19},
  {-5.65, -5.03, -1.60, -.03},
  { 1.95,  3.67,  .52, 1.98},
  { 2.56,  5.08, -4.00,-1.00},
  {-.85, .96, -4.00,-3.17},
  { 4.68, 5.40, 2.15, 3.22}
}

local function blocked(x, z)
  for _, r in ipairs(obstacles) do
    if x > r[1] and x < r[2] and z > r[3] and z < r[4] then
      return true
    end
  end
  return false
end

local function unpackCell(ix, iz)
  return MINX + (ix - 1) * CELL, MINZ + (iz - 1) * CELL
end
local function idx(ix, iz)
  return (iz - 1) * NX + ix
end
local function toCell(x, z)
  local ix = math.max(1, math.min(NX, math.floor((x - MINX) / CELL + .5) + 1))
  local iz = math.max(1, math.min(NZ, math.floor((z - MINZ) / CELL + .5) + 1))
  return ix, iz
end
local function snapToOpen(ix, iz)
  local bestX, bestZ, bestD
  for radius = 0, 6 do
    for dx = -radius, radius do
      for dz = -radius, radius do
        local x, z = ix + dx, iz + dz
        if x >= 1 and x <= NX and z >= 1 and z <= NZ then
          local px, pz = unpackCell(x, z)
          if not blocked(px, pz) then
            local d = dx * dx + dz * dz
            if not bestD or d < bestD then bestX, bestZ, bestD = x, z, d end
          end
        end
      end
    end
    if bestX then return bestX, bestZ end
  end
  return ix, iz
end

function Nav.findPath(x1, z1, x2, z2)
  local sx, sz = toCell(x1, z1)
  local tx, tz = toCell(x2, z2)
  sx, sz = snapToOpen(sx, sz)
  tx, tz = snapToOpen(tx, tz)
  local start, finish = idx(sx, sz), idx(tx, tz)
  local queue, head = { start }, 1
  local previous = {[start] = 0}
  local directions = {{1,0}, {-1,0}, {0,1}, {0,-1}}
  while head <= #queue and not previous[finish] do
    local current = queue[head]; head = head + 1
    local iz = math.floor((current - 1) / NX) + 1
    local ix = current - (iz - 1) * NX
    for _, step in ipairs(directions) do
      local nx, nz = ix + step[1], iz + step[2]
      if nx >= 1 and nx <= NX and nz >= 1 and nz <= NZ then
        local key = idx(nx, nz)
        if not previous[key] then
          local px, pz = unpackCell(nx, nz)
          if not blocked(px, pz) then
            previous[key] = current
            queue[#queue + 1] = key
          end
        end
      end
    end
  end
  if not previous[finish] then return {{x = x2, z = z2}} end
  local reversed, current = {}, finish
  while current ~= start do
    local iz = math.floor((current - 1) / NX) + 1
    local ix = current - (iz - 1) * NX
    local x, z = unpackCell(ix, iz)
    reversed[#reversed + 1] = { x = x, z = z }
    current = previous[current]
  end
  local path = {}
  for i = #reversed, 1, -1 do
    path[#path + 1] = reversed[i]
  end
  return path
end

return Nav
