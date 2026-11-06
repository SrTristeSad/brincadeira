-- Motor raster simples do protótipo (NÃO é libmypaint).
-- Todas as dimensões são pixels de documento, sem DPI da interface.
local lg = love.graphics
local Document = {}
Document.__index = Document
Document.MAX_SIZE = 4096
local HISTORY_LIMIT = 12

local function clamp(v, minv, maxv)
    return math.max(minv, math.min(maxv, v))
end

local function create_layer_canvas(w, h)
    local canvas = lg.newCanvas(w, h, {dpiscale = 1})
    lg.push("all")
    lg.setCanvas(canvas)
    lg.clear(0, 0, 0, 0)
    lg.pop()
    return canvas
end

function Document.new(width, height)
    width, height = math.floor(tonumber(width) or 0), math.floor(tonumber(height) or 0)
    assert(width >= 1 and width <= Document.MAX_SIZE, "Largura fora do limite")
    assert(height >= 1 and height <= Document.MAX_SIZE, "Altura fora do limite")
    local self = setmetatable({
        width = width, height = height, layers = {}, active = 0,
        nextId = 1, undoStack = {}, redoStack = {}
    }, Document)
    self:addLayer()
    return self
end

function Document:activeLayer()
    return self.layers[self.active]
end

function Document:layerById(id)
    for _, layer in ipairs(self.layers) do
        if layer.id == id then return layer end
    end
    return nil
end

function Document:addLayer()
    local id = self.nextId
    self.nextId = id + 1
    self.layers[#self.layers + 1] = {
        id = id, name = "Layer " .. id, canvas = create_layer_canvas(self.width, self.height),
        visible = true, opacity = 1
    }
    self.active = #self.layers
    return self.active
end

function Document:removeActiveLayer()
    if #self.layers == 1 then return false end
    table.remove(self.layers, self.active)
    self.active = clamp(self.active, 1, #self.layers)
    -- As capturas de pincelada fazem referência a IDs de camada.
    -- A exclusão invalida o histórico em vez de tentar restaurar uma camada removida.
    self.undoStack, self.redoStack = {}, {}
    return true
end

function Document:setActive(index)
    if index < 1 or index > #self.layers then return false end
    self.active = index
    return true
end

function Document:beginStroke()
    local layer = self:activeLayer()
    if not layer or not layer.visible then return false end
    self.undoStack[#self.undoStack + 1] = {
        id = layer.id, pixels = layer.canvas:newImageData()
    }
    if #self.undoStack > HISTORY_LIMIT then table.remove(self.undoStack, 1) end
    self.redoStack = {}
    return true
end

function Document:paintPoint(x, y, tool, rgb, size, opacity)
    local layer = self:activeLayer()
    if not layer or not layer.visible then return end
    local radius = math.max(0.5, size / 2)
    lg.push("all")
    lg.setCanvas(layer.canvas)
    lg.setScissor()
    if tool == "eraser" then
        lg.setBlendMode("replace", "premultiplied")
        lg.setColor(0, 0, 0, 0)
    else
        lg.setBlendMode("alpha", "alphamultiply")
        lg.setColor(rgb[1], rgb[2], rgb[3], clamp(opacity, 0.01, 1))
    end
    lg.circle("fill", x, y, radius)
    lg.pop()
end

function Document:paintSegment(x1, y1, x2, y2, tool, rgb, size, opacity)
    local dx, dy = x2 - x1, y2 - y1
    local distance = math.sqrt(dx * dx + dy * dy)
    local steps = math.max(1, math.ceil(distance / math.max(1, size * 0.28)))
    for i = 1, steps do
        local t = i / steps
        self:paintPoint(x1 + dx * t, y1 + dy * t, tool, rgb, size, opacity)
    end
end

local function restore_pixels(layer, pixels)
    lg.push("all")
    lg.setCanvas(layer.canvas)
    lg.setScissor()
    lg.clear(0, 0, 0, 0)
    lg.setBlendMode("replace", "premultiplied")
    lg.setColor(1, 1, 1, 1)
    lg.draw(lg.newImage(pixels), 0, 0)
    lg.pop()
end

function Document:undo()
    local before = table.remove(self.undoStack)
    if not before then return false end
    local layer = self:layerById(before.id)
    if not layer then return false end
    self.redoStack[#self.redoStack + 1] = {id = layer.id, pixels = layer.canvas:newImageData()}
    restore_pixels(layer, before.pixels)
    return true
end

function Document:redo()
    local after = table.remove(self.redoStack)
    if not after then return false end
    local layer = self:layerById(after.id)
    if not layer then return false end
    self.undoStack[#self.undoStack + 1] = {id = layer.id, pixels = layer.canvas:newImageData()}
    restore_pixels(layer, after.pixels)
    return true
end

function Document:drawLayers()
    for _, layer in ipairs(self.layers) do
        if layer.visible and layer.opacity > 0 then
            lg.setColor(1, 1, 1, layer.opacity)
            lg.draw(layer.canvas)
        end
    end
end

function Document:composite()
    local canvas = create_layer_canvas(self.width, self.height)
    lg.push("all")
    lg.setCanvas(canvas)
    lg.setScissor()
    self:drawLayers()
    lg.pop()
    return canvas
end

function Document:sampleColor(x, y)
    x, y = math.floor(x), math.floor(y)
    if x < 0 or y < 0 or x >= self.width or y >= self.height then return nil end
    local data = self:composite():newImageData()
    local r, g, b, a = data:getPixel(x, y)
    if a < 0.01 then return nil end
    return {r, g, b}
end

function Document:exportPNG()
    local filename = os.date("pintura-%Y%m%d-%H%M%S.png")
    local image = self:composite():newImageData()
    image:encode("png", filename)
    return love.filesystem.getSaveDirectory() .. "/" .. filename
end

function Document.fromImage(image)
    local w, h = image:getDimensions()
    if w < 1 or h < 1 or w > Document.MAX_SIZE or h > Document.MAX_SIZE then
        return nil, "A imagem excede 4096 x 4096"
    end
    local doc = Document.new(w, h)
    lg.push("all")
    lg.setCanvas(doc.layers[1].canvas)
    lg.setScissor()
    lg.setColor(1, 1, 1, 1)
    lg.draw(image, 0, 0)
    lg.pop()
    return doc
end

return Document
