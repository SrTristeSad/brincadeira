-- Interface 2D de tela. Não ocupa nem esconde os móveis da casa.
-- Botões clicáveis e atalhos de teclado, sem dependências externas.
local H={}
local navy,ink,muted,accent,gold,danger={.095,.16,.19},{.95,.96,.93},{.66,.77,.77},{.25,.65,.64},{.97,.71,.42},{.89,.45,.43}
local function bg(p,c,x,y,w,h,a)
 p:setColor(c[1],c[2],c[3],a or 1);p:box(x+w/2,y+h/2,0,w,h,.01)
end
local function text(p,s,x,y,size,color,align)
 color=color or ink
 p:setColor(color[1],color[2],color[3]);p:text(s,x,y,.08,size,0,0,1,0,0,align or 'left','middle')
end
local function button(p,x,y,w,h,label,active)
 bg(p,active and accent or {.19,.28,.31},x,y,w,h,active and 1 or .94)
 text(p,label,x+w/2,y+h/2,17,active and navy or ink,'center')
end
function H.getRegions(w,h)
 -- All rectangles are screen pixels, also used for hit-testing.
 return {
  {x=24,y=76,w=150,h=39,id='room1'},
  {x=180,y=76,w=114,h=39,id='room2'},
  {x=300,y=76,w=130,h=39,id='room3'},
  {x=436,y=76,w=124,h=39,id='room4'},
  {x=w-230,y=76,w=100,h=39,id='one'},
  {x=w-122,y=76,w=98,h=39,id='two'},
  {x=24,y=h-116,w=66,h=48,id='previous'},
  {x=96,y=h-116,w=66,h=48,id='next'},
  {x=w-224,y=h-116,w=200,h=48,id='play'},
  {x=w-224,y=h-63,w=200,h=36,id='chat'},
  {x=24,y=h-62,w=140,h=35,id='camera'},
  {x=173,y=h-62,w=140,h=35,id='follow'},
 }
end
function H.hit(x,y,w,h)
 for _,r in ipairs(H.getRegions(w,h)) do
  if x>=r.x and x<r.x+r.w and y>=r.y and y<r.y+r.h then return r.id end
 end
end
local function bar(p,x,y,w,label,val,c)
 text(p,label,x,y,14,muted)
 bg(p,{.17,.27,.29},x+65,y-6,w,12)
 bg(p,c,x+65,y-6,w*math.max(0,math.min(100,val))/100,12)
end
function H.draw(p,sim,catalog,idx,sel,camera,mensagem)
 local w,h=p:getDimensions()
 p:origin()
 p:setShader()
 p:setViewPose(1,mat4(),true)
 p:setProjection('orthographic')
 p:setDepthTest()
 -- top navigation
 bg(p,navy,12,12,w-24,116,.94)
 text(p,'CASA VIVA',26,39,32,ink)
 text(p,'2 avatares animados  •  26 movimentos reais  •  Lua',225,39,17,muted)
 local r=H.getRegions(w,h)
 local names={'CASA [F1]','SALA [F2]','COZINHA [F3]','QUARTO [F4]'}
 for i=1,4 do local b=r[i];button(p,b.x,b.y,b.w,b.h,names[i],camera.vista==i) end
 button(p,r[5].x,r[5].y,r[5].w,r[5].h,'1 AVATAR',sim.total==1)
 button(p,r[6].x,r[6].y,r[6].w,r[6].h,'2 AVATARES',sim.total==2)
 -- left status card
 bg(p,navy,12,141,299,192,.9)
 local a=sim.agentes[sel]
 local state=sim.pausado and 'PAUSADO' or 'AUTÔNOMO'
 text(p,a.nome..'  /  '..state,27,169,22,ink)
 text(p,'Ação: '..a:animacaoAtual(),27,203,16,muted)
 bar(p,27,237,176,'Energia',a.energia,accent)
 bar(p,27,267,176,'Fome',a.fome,gold)
 bar(p,27,297,176,'Diversão',a.diversao,{.77,.52,.72})
 -- animation control bar
 bg(p,navy,12,h-134,w-24,122,.94)
 text(p,'ANIMAÇÕES',25,h-153+36,15,muted)
 button(p,r[7].x,r[7].y,r[7].w,r[7].h,'<',false)
 button(p,r[8].x,r[8].y,r[8].w,r[8].h,'>',false)
 local item=catalog[idx]
 local name=item and item.rotulo or 'Nenhuma animação'
 local status=item and require('avatars').temAnimacao(a,item.id) or 'sem clipe'
 text(p,(idx or 0)..'/'..#catalog..'  '..name,180,h-94,20,ink)
 text(p,status..(item and item.dupla and '  •  dupla' or '')..(item and item.adulto and '  •  +18' or ''),180,h-64,15,item and item.adulto and gold or muted)
 button(p,r[9].x,r[9].y,r[9].w,r[9].h,'REPRODUZIR [ENTER]',true)
 button(p,r[10].x,r[10].y,r[10].w,r[10].h,sim.comunicacao and 'CONVERSA: LIGADA' or 'CONVERSA: DESLIGADA',false)
 button(p,r[11].x,r[11].y,r[11].w,r[11].h,'TROCAR [TAB]',false)
 button(p,r[12].x,r[12].y,r[12].w,r[12].h,'SEGUIR [F]',camera.follow)
 if mensagem and mensagem~='' then text(p,mensagem,math.min(w*.65,800),148,16,gold,'center') end
 text(p,'Mouse: arrastar gira • roda aproxima | Espaço pausa • L relê animações • H ajuda',w/2,h-12,14,muted,'center')
end
return H
