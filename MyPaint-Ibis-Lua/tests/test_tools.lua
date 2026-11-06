package.path = "./?.lua;./?/init.lua;" .. package.path
local tools = require("src.tools")
local list = tools.all()
assert(#list == 4, "Devem existir apenas quatro ferramentas")
for _, tool in ipairs(list) do assert(tools.exists(tool.id)) end
for _, id in ipairs({"text", "vector", "filter", "magic_wand", "animation", "lasso"}) do
    assert(not tools.exists(id), "Ferramenta indevida: " .. id)
end
list[1].name = "Modificado"
assert(tools.get("brush").name == "Brush", "Catálogo não deve expor estado mutável")
print("test_tools: ok")
