-- Paint Lua: independent studio-style design tokens.
-- These colors are not claimed to be ibisPaint Windows 14.1.4 assets.
local Theme={}
Theme.colors={
    background={0.919,0.929,0.943},bar={0.126,0.153,0.208},
    deep={0.061,0.079,0.118},dark={0.094,0.118,0.170},
    light={0.966,0.969,0.977},paper={0.970,0.970,0.964},
    blue={1.000,0.488,0.387},title={0.125,0.204,0.330},
    ranking={0.059,0.085,0.143},ink={0.125,0.160,0.216},
    white={0.993,0.993,0.998},soft={0.772,0.799,0.845},
    topbar={0.092,0.114,0.167},accent={1.000,0.488,0.387},
    accent_light={1.000,0.765,0.714},accent_tint={1.000,0.910,0.885},
    rail={0.120,0.149,0.207},tile={0.999,0.996,0.988},
    panel_head={0.176,0.207,0.284},panel_body={0.121,0.154,0.214},
    top_button={0.180,0.220,0.301},card_border={0.833,0.857,0.889},
    muted={0.385,0.437,0.505},hover={0.239,0.290,0.385},
    workspace_grid={0.150,0.208,0.295},success={0.423,0.829,0.681},
}
Theme.spacing={xs=4,sm=8,md=12,lg=18,xl=24,xxl=32}
Theme.radius={small=6,button=9,card=14,panel=12}
local function linear(channel)
    if channel<=0.04045 then return channel/12.92 end
    return ((channel+0.055)/1.055)^2.4
end
function Theme.luminance(rgb)
    assert(type(rgb)=="table" and #rgb>=3,"RGB inválido")
    return linear(rgb[1])*0.2126+linear(rgb[2])*0.7152+
        linear(rgb[3])*0.0722
end
function Theme.contrast(a,b)
    local l1,l2=Theme.luminance(a),Theme.luminance(b)
    if l2>l1 then l1,l2=l2,l1 end
    return (l1+0.05)/(l2+0.05)
end
function Theme.mix(a,b,t)
    assert(type(t)=="number" and t>=0 and t<=1,"Mistura inválida")
    return {a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t,
        a[3]+(b[3]-a[3])*t}
end
return Theme
