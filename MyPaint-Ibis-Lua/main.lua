-- Interface inspirada no Ibis-Lua, recortada às ferramentas básicas do MyPaint.
-- Protótipo autônomo em LÖVE; NÃO modifica nem incorpora o programa MyPaint.
local Theme = require("src.ui_theme")
local Tools = require("src.tools")
local Document = require("src.document")
local lg = love.graphics
local C = Theme.colors
local app = {}
local hits = {}
local PANEL_WIDTH = 296

local function clamp(v, lo, hi)
    return math.max(lo, math.min(hi, v))
end

local function color(c, a)
    lg.setColor(c[1], c[2], c[3], a or 1)
end

local function contains(px, py, x, y, w, h)
    return px >= x and py >= y and px <= x + w and py <= y + h
end

local function addHit(x, y, w, h, action, modal)
    hits[#hits + 1] = {x = x, y = y, w = w, h = h, action = action, modal = modal == true}
end

local function text(str, x, y, w, align, font, tint)
    lg.setFont(font or app.font)
    color(tint or C.white)
    lg.printf(tostring(str), x, y, w, align or "left")
end

local function panelWidth()
    return app.panel and PANEL_WIDTH or 0
end

local function viewport()
    local w, h = lg.getDimensions()
    return {x = 60, y = 62, w = w - 60 - panelWidth(), h = h - 118}
end

local function canvasOrigin()
    local view = viewport()
    return view.x + (view.w - app.doc.width * app.zoom) / 2 + app.panX,
           view.y + (view.h - app.doc.height * app.zoom) / 2 + app.panY
end

local function documentPoint(sx, sy, requireInside)
    local ox, oy = canvasOrigin()
    local x, y = (sx - ox) / app.zoom, (sy - oy) / app.zoom
    if requireInside and (x < 0 or y < 0 or x >= app.doc.width or y >= app.doc.height) then
        return nil, nil
    end
    return x, y
end

local function isInViewport(x, y)
    local v = viewport()
    return contains(x, y, v.x, v.y, v.w, v.h)
end

local function btn(x, y, w, h, label, selected, callback, modal)
    local mx, my = love.mouse.getPosition()
    local bg = selected and C.accent or
        (contains(mx, my, x, y, w, h) and C.hover or C.top_button)
    color(bg)
    lg.rectangle("fill", x, y, w, h, 8, 8)
    color(selected and C.deep or C.soft)
    lg.setLineWidth(1)
    lg.rectangle("line", x + .5, y + .5, w - 1, h - 1, 8, 8)
    text(label, x + 3, y + (h - 19) / 2, w - 6, "center", app.font,
         selected and C.deep or C.white)
    addHit(x, y, w, h, callback, modal)
end

local function slider(x, y, w, label, value, minv, maxv, callback)
    text(label, x, y, w, "left", app.small, C.soft)
    text(tostring(math.floor(value + .5)), x, y, w, "right", app.small, C.white)
    local trackY = y + 23
    color(C.top_button)
    lg.rectangle("fill", x, trackY, w, 7, 4, 4)
    local ratio = clamp((value - minv) / (maxv - minv), 0, 1)
    color(C.accent)
    lg.rectangle("fill", x, trackY, w * ratio, 7, 4, 4)
    lg.circle("fill", x + w * ratio, trackY + 3.5, 8)
    addHit(x - 8, trackY - 9, w + 16, 27, function(mx)
        local function update(px)
            local t = clamp((px - x) / w, 0, 1)
            callback(minv + t * (maxv - minv))
        end
        update(mx)
        app.drag = {kind = "slider", update = update}
    end, false)
end

local function showPanel(panel)
    app.panel = (app.panel == panel) and nil or panel
end

local function resetView()
    app.zoom = math.min(0.72, (viewport().w - 100) / app.doc.width,
        (viewport().h - 80) / app.doc.height)
    app.zoom = math.max(.10, app.zoom)
    app.panX, app.panY = 0, 0
end

local function requestNew()
    app.modal = "new"
    app.newW, app.newH = tostring(app.doc.width), tostring(app.doc.height)
    app.focus = "width"
end

local function confirmNew()
    local w, h = tonumber(app.newW), tonumber(app.newH)
    if not w or not h or w ~= math.floor(w) or h ~= math.floor(h) or
        w < 1 or h < 1 or w > Document.MAX_SIZE or h > Document.MAX_SIZE then
        app.status = "Tamanho invalido: use 1 a 4096 pixels."
        return
    end
    local ok, doc = pcall(Document.new, w, h)
    if not ok then
        app.status = "Falha ao criar canvas: " .. tostring(doc)
        return
    end
    app.doc = doc
    app.layerScroll = 0
    app.modal = nil
    resetView()
    app.status = "Nova tela criada. Exporte seu trabalho para salvar."
end

local function exportImage()
    local ok, path = pcall(function() return app.doc:exportPNG() end)
    app.status = ok and ("PNG exportado: " .. path) or ("Falha ao exportar: " .. tostring(path))
end

local function drawWorkspace()
    local v = viewport()
    color(C.background)
    lg.rectangle("fill", v.x, v.y, v.w, v.h)
    lg.setScissor(v.x, v.y, v.w, v.h)
    local ox, oy = canvasOrigin()
    local cw, ch = app.doc.width * app.zoom, app.doc.height * app.zoom
    color(C.card_border)
    lg.rectangle("fill", ox - 7, oy - 7, cw + 14, ch + 14, 2, 2)
    color(C.paper)
    lg.rectangle("fill", ox, oy, cw, ch)
    lg.push()
    lg.translate(ox, oy)
    lg.scale(app.zoom)
    app.doc:drawLayers()
    lg.pop()
    color(C.ink)
    lg.rectangle("line", ox, oy, cw, ch)
    lg.setScissor()

    local mx, my = love.mouse.getPosition()
    if isInViewport(mx, my) and (app.tool == "brush" or app.tool == "eraser") and not app.modal then
        color(app.tool == "eraser" and C.muted or C.accent, .8)
        lg.setLineWidth(1.5)
        lg.circle("line", mx, my, math.max(3, app.size * app.zoom / 2))
    end
end

local function drawTop()
    local w = lg.getWidth()
    color(C.topbar)
    lg.rectangle("fill", 0, 0, w, 62)
    color(C.accent)
    lg.rectangle("fill", 0, 0, 6, 62)
    text("Paint Lua", 17, 12, 143, "left", app.large, C.white)
    text("MyPaint tools", 17, 37, 150, "left", app.small, C.soft)
    btn(172, 12, 78, 38, "New", false, requestNew)
    btn(260, 12, 113, 38, "Export PNG", false, exportImage)
    btn(386, 12, 45, 38, "Undo", false, function()
        app.status = app.doc:undo() and "Pincelada desfeita." or "Nada para desfazer."
    end)
    btn(440, 12, 45, 38, "Redo", false, function()
        app.status = app.doc:redo() and "Pincelada refeita." or "Nada para refazer."
    end)
    local tabX = w - 300
    btn(tabX, 12, 89, 38, "Brush", app.panel == "brush", function() showPanel("brush") end)
    btn(tabX + 98, 12, 89, 38, "Color", app.panel == "color", function() showPanel("color") end)
    btn(tabX + 196, 12, 89, 38, "Layers", app.panel == "layers", function() showPanel("layers") end)
end

local function drawRail()
    local h = lg.getHeight()
    color(C.rail)
    lg.rectangle("fill", 0, 62, 60, h - 62)
    local tools = Tools.all()
    for i, tool in ipairs(tools) do
        local y = 90 + (i - 1) * 67
        local selected = app.tool == tool.id
        btn(7, y, 46, 43, tool.shortcut, selected, function()
            app.tool = tool.id
        end)
        text(tool.name, 0, y + 46, 60, "center", app.tiny, C.soft)
    end
end

local function drawFooter()
    local w, h = lg.getDimensions()
    color(C.deep)
    lg.rectangle("fill", 60, h - 56, w - 60, 56)
    text("Size", 81, h - 42, 50, "left", app.small, C.soft)
    slider(129, h - 45, 153, "", app.size, 1, 120, function(v)
        app.size = math.floor(v + .5)
    end)
    text("Opacity", 316, h - 42, 65, "left", app.small, C.soft)
    slider(385, h - 45, 145, "", app.opacity * 100, 1, 100, function(v)
        app.opacity = math.floor(v + .5) / 100
    end)
    local footerRight = w - 26
    text(string.format("%d x %d   |   %d%%", app.doc.width, app.doc.height,
        math.floor(app.zoom * 100 + .5)), footerRight - 245, h - 39,
        245, "right", app.small, C.white)
    text(app.status or "", 70, h - 16, w - 100, "left", app.tiny, C.soft)
end

local function drawBrushPanel(px, py, pw)
    text("Brush properties", px + 18, py + 15, pw - 36, "left", app.large)
    slider(px + 22, py + 70, pw - 44, "Brush size (px)", app.size, 1, 120,
        function(v) app.size = math.floor(v + .5) end)
    slider(px + 22, py + 135, pw - 44, "Brush opacity", app.opacity * 100, 1, 100,
        function(v) app.opacity = math.floor(v + .5) / 100 end)
    color(C.paper)
    lg.rectangle("fill", px + 22, py + 210, pw - 44, 110, 9, 9)
    color(app.color)
    lg.circle("fill", px + pw / 2, py + 264, math.min(app.size / 2, 47))
    text("Circular brush preview", px + 18, py + 333, pw - 36, "center", app.small, C.soft)
    text("B: Brush   E: Eraser", px + 18, py + 377, pw - 36, "left", app.small, C.soft)
    text("I: Picker   H: Hand", px + 18, py + 404, pw - 36, "left", app.small, C.soft)
end

local palette = {
    {0.09,0.10,0.15}, {1,1,1}, {.89,.23,.27}, {1,.51,.27}, {1,.83,.25},
    {.30,.67,.37}, {.19,.69,.77}, {.29,.49,.88}, {.54,.35,.78}, {.92,.45,.63},
    {.44,.29,.20}, {.67,.52,.36}, {.42,.48,.56}, {.18,.38,.32}, {.84,.80,.70}
}

local function drawColorPanel(px, py, pw)
    text("Color", px + 18, py + 15, pw - 36, "left", app.large)
    color(app.color)
    lg.rectangle("fill", px + 20, py + 59, pw - 40, 68, 10, 10)
    local channels = {"Red", "Green", "Blue"}
    for i = 1, 3 do
        slider(px + 22, py + 147 + (i - 1) * 58, pw - 44, channels[i],
            math.floor(app.color[i] * 255 + .5), 0, 255, function(v)
                app.color[i] = math.floor(v + .5) / 255
            end)
    end
    text("Palette", px + 22, py + 340, pw - 44, "left", app.small, C.soft)
    for i, rgb in ipairs(palette) do
        local col = (i - 1) % 5
        local row = math.floor((i - 1) / 5)
        local x, y = px + 22 + col * 49, py + 369 + row * 46
        color(rgb)
        lg.rectangle("fill", x, y, 38, 36, 6, 6)
        color(C.card_border)
        lg.rectangle("line", x, y, 38, 36, 6, 6)
        addHit(x, y, 38, 36, function()
            app.color = {rgb[1], rgb[2], rgb[3]}
        end)
    end
end

local function drawLayersPanel(px, py, pw)
    text("Layers", px + 18, py + 15, pw - 36, "left", app.large)
    btn(px + 18, py + 55, 121, 36, "+ Add layer", false, function()
        app.doc:addLayer()
    end)
    btn(px + 150, py + 55, 127, 36, "Remove", false, function()
        if not app.doc:removeActiveLayer() then
            app.status = "A ultima camada nao pode ser removida."
        end
    end)
    local active = app.doc:activeLayer()
    slider(px + 22, py + 112, pw - 44, "Layer opacity", active.opacity * 100, 0, 100,
        function(v) active.opacity = math.floor(v + .5) / 100 end)
    local availableRows = math.floor((lg.getHeight() - 56 - (py + 187)) / 73)
    local count = math.min(#app.doc.layers, math.max(1, availableRows))
    local offset = clamp(app.layerScroll or 0, 0, math.max(0, #app.doc.layers - count))
    for row = 1, count do
        local i = #app.doc.layers - offset - row + 1
        local layer = app.doc.layers[i]
        local y = py + 177 + (row - 1) * 73
        color(i == app.doc.active and C.hover or C.top_button)
        lg.rectangle("fill", px + 12, y, pw - 24, 66, 7, 7)
        addHit(px + 12, y, pw - 24, 66, function() app.doc:setActive(i) end)
        color(C.paper)
        lg.rectangle("fill", px + 19, y + 7, 56, 51, 3, 3)
        local scale = math.min(52 / app.doc.width, 47 / app.doc.height)
        color(C.white)
        lg.draw(layer.canvas, px + 21, y + 9, 0, scale, scale)
        text(layer.name, px + 83, y + 11, 127, "left", app.small, C.white)
        text(tostring(math.floor(layer.opacity * 100 + .5)) .. "%",
            px + 83, y + 37, 110, "left", app.tiny, C.soft)
        btn(px + pw - 63, y + 14, 42, 37, layer.visible and "Eye" or "Off", layer.visible,
            function() layer.visible = not layer.visible end)
    end
    if #app.doc.layers > count then
        text("Roda do mouse aqui para ver outras camadas", px + 18,
            lg.getHeight() - 96, pw - 36, "center", app.tiny, C.soft)
    end
end

local function drawPanel()
    if not app.panel then return end
    local w, h = lg.getDimensions()
    local px, py, pw = w - PANEL_WIDTH, 62, PANEL_WIDTH
    color(C.panel_body)
    lg.rectangle("fill", px, py, pw, h - py - 56)
    color(C.panel_head)
    lg.rectangle("fill", px, py, pw, 48)
    if app.panel == "brush" then drawBrushPanel(px, py, pw) end
    if app.panel == "color" then drawColorPanel(px, py, pw) end
    if app.panel == "layers" then drawLayersPanel(px, py, pw) end
end

local function newField(x, y, label, value, name)
    local focused = app.focus == name
    color(focused and C.accent_tint or C.top_button)
    lg.rectangle("fill", x, y, 179, 54, 8, 8)
    text(label, x + 11, y + 5, 160, "left", app.tiny, focused and C.ink or C.soft)
    text(value, x + 11, y + 23, 157, "left", app.font, focused and C.ink or C.white)
    addHit(x, y, 179, 54, function() app.focus = name end, true)
end

local function drawModal()
    local w, h = lg.getDimensions()
    lg.setColor(0, 0, 0, .66)
    lg.rectangle("fill", 0, 0, w, h)
    local x, y = (w - 447) / 2, (h - 253) / 2
    color(C.panel_body)
    lg.rectangle("fill", x, y, 447, 253, 16, 16)
    text("New canvas", x + 22, y + 18, 380, "left", app.large)
    text("Uma nova tela substitui a atual (exporte antes).",
        x + 22, y + 49, 395, "left", app.small, C.soft)
    newField(x + 26, y + 90, "Width (px)", app.newW, "width")
    newField(x + 238, y + 90, "Height (px)", app.newH, "height")
    btn(x + 170, y + 181, 112, 43, "Cancel", false, function()
        app.modal = nil
    end, true)
    btn(x + 295, y + 181, 124, 43, "Create", true, confirmNew, true)
end

function love.load()
    lg.setDefaultFilter("linear", "linear")
    app.font = lg.newFont(14)
    app.small = lg.newFont(12)
    app.tiny = lg.newFont(10)
    app.large = lg.newFont(20)
    app.doc = Document.new(1200, 800)
    app.tool, app.panel = "brush", "brush"
    app.layerScroll = 0
    app.color = {.12, .16, .22}
    app.size, app.opacity = 16, 1
    app.status = "Protótipo raster. Arraste PNG/JPEG para abrir; Ctrl+S exporta PNG."
    resetView()
    love.keyboard.setKeyRepeat(true)
end

function love.draw()
    hits = {}
    drawWorkspace()
    drawTop()
    drawRail()
    drawFooter()
    drawPanel()
    if app.modal then drawModal() end
end

function love.mousepressed(x, y, button)
    if button ~= 1 and button ~= 2 then return end
    if button == 1 then
        for i = #hits, 1, -1 do
            local r = hits[i]
            if (not app.modal or r.modal) and contains(x, y, r.x, r.y, r.w, r.h) then
                r.action(x, y)
                return
            end
        end
    end
    if app.modal or not isInViewport(x, y) then return end
    if button == 2 or app.tool == "hand" or love.keyboard.isDown("space") then
        app.drag = {kind = "pan"}
        return
    end
    local px, py = documentPoint(x, y, true)
    if not px then return end
    if app.tool == "picker" then
        local picked = app.doc:sampleColor(px, py)
        if picked then app.color = picked; app.tool = "brush" end
    elseif app.tool == "brush" or app.tool == "eraser" then
        if app.doc:beginStroke() then
            app.doc:paintPoint(px, py, app.tool, app.color, app.size, app.opacity)
            app.drag = {kind = "paint", x = px, y = py, tool = app.tool}
        else
            app.status = "Ative a visibilidade da camada para pintar."
        end
    end
end

function love.mousemoved(x, y, dx, dy)
    local drag = app.drag
    if not drag then return end
    if drag.kind == "slider" then
        drag.update(x)
    elseif drag.kind == "pan" then
        app.panX, app.panY = app.panX + dx, app.panY + dy
    elseif drag.kind == "paint" then
        local px, py = documentPoint(x, y, false)
        app.doc:paintSegment(drag.x, drag.y, px, py, drag.tool,
            app.color, app.size, app.opacity)
        drag.x, drag.y = px, py
    end
end

function love.mousereleased(x, y, button)
    if button == 1 or button == 2 then app.drag = nil end
end

function love.wheelmoved(dx, dy)
    if app.modal or dy == 0 then return end
    local mx, my = love.mouse.getPosition()
    if app.panel == "layers" and mx >= lg.getWidth() - PANEL_WIDTH and my > 205 then
        local availableRows = math.floor((lg.getHeight() - 56 - (62 + 187)) / 73)
        local count = math.min(#app.doc.layers, math.max(1, availableRows))
        app.layerScroll = clamp((app.layerScroll or 0) - (dy > 0 and 1 or -1),
            0, math.max(0, #app.doc.layers - count))
        return
    end
    if not isInViewport(mx, my) then return end
    local px, py = documentPoint(mx, my, false)
    local nextZoom = clamp(app.zoom * (dy > 0 and 1.12 or 1 / 1.12), .10, 5)
    app.zoom = nextZoom
    local ox, oy = canvasOrigin()
    app.panX = app.panX + (mx - (ox + px * nextZoom))
    app.panY = app.panY + (my - (oy + py * nextZoom))
end

function love.textinput(t)
    if app.modal ~= "new" or not t:match("^%d+$") then return end
    local key = app.focus == "height" and "newH" or "newW"
    if #app[key] + #t <= 4 then app[key] = app[key] .. t end
end

function love.keypressed(key)
    if app.modal == "new" then
        local field = app.focus == "height" and "newH" or "newW"
        if key == "backspace" then
            app[field] = app[field]:sub(1, -2)
        elseif key == "tab" then
            app.focus = app.focus == "width" and "height" or "width"
        elseif key == "return" or key == "kpenter" then
            confirmNew()
        elseif key == "escape" then
            app.modal = nil
        end
        return
    end
    local ctrl = love.keyboard.isDown("lctrl") or love.keyboard.isDown("rctrl")
    if ctrl then
        if key == "z" then app.doc:undo()
        elseif key == "y" then app.doc:redo()
        elseif key == "n" then requestNew()
        elseif key == "s" then exportImage()
        end
        return
    end
    if key == "b" then app.tool = "brush"
    elseif key == "e" then app.tool = "eraser"
    elseif key == "i" then app.tool = "picker"
    elseif key == "h" then app.tool = "hand"
    elseif key == "c" then showPanel("color")
    elseif key == "l" then showPanel("layers")
    elseif key == "[" then app.size = math.max(1, app.size - 2)
    elseif key == "]" then app.size = math.min(120, app.size + 2)
    end
end

function love.filedropped(file)
    local ok, image = pcall(function()
        assert(file:open("r"), "Nao foi possivel abrir arquivo")
        local data = file:read("data")
        file:close()
        return lg.newImage(data)
    end)
    if not ok then
        app.status = "Importacao falhou (use PNG/JPEG): " .. tostring(image)
        return
    end
    local doc, err = Document.fromImage(image)
    if not doc then
        app.status = err
        return
    end
    app.doc, app.modal = doc, nil
    app.layerScroll = 0
    app.panel = "layers"
    resetView()
    app.status = "Imagem importada. A tela anterior foi substituida."
end
