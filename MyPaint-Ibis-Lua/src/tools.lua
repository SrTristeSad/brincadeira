-- Recorte intencional: somente ferramentas efetivamente implementadas
-- e cujo conceito também existe no MyPaint.
local Tools = {}
local entries = {
    {id = "brush",  name = "Brush",  shortcut = "B"},
    {id = "eraser", name = "Eraser", shortcut = "E"},
    {id = "picker", name = "Picker", shortcut = "I"},
    {id = "hand",   name = "Hand",   shortcut = "H"},
}
local lookup = {}
for _, entry in ipairs(entries) do lookup[entry.id] = entry end
function Tools.all()
    local copy = {}
    for i, e in ipairs(entries) do
        copy[i] = {id = e.id, name = e.name, shortcut = e.shortcut}
    end
    return copy
end
function Tools.exists(id) return lookup[id] ~= nil end
function Tools.get(id)
    local e = lookup[id]
    if not e then return nil end
    return {id = e.id, name = e.name, shortcut = e.shortcut}
end
return Tools
