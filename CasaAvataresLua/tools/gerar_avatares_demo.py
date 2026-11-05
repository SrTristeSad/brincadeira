"""Build original animated stylized characters as self-contained glTF 2.0 binaries.
No Blender or copyrighted external assets required. Uses standard icosphere mesh.
"""
import json, struct, math, os, numpy as np
from pathlib import Path
from trimesh.creation import icosphere

TARGET=Path(__file__).resolve().parents[1] / 'assets'
TARGET.mkdir(parents=True,exist_ok=True)

ACTIONS=['idle','walk','run','sit','sleep','dance','wave','talk','read','cook','eat','work','stretch','exercise','think','observe','clean','laugh','relax','greet','explore','jump','clap','nod','celebrate','point']

class GLB:
 def __init__(self):
  self.b=bytearray();self.g={'asset':{'version':'2.0','generator':'Casa Viva | personagenzinho original, procedural'},'scene':0,'scenes':[{'nodes':[]}], 'nodes':[], 'meshes':[],'materials':[],'accessors':[],'bufferViews':[],'buffers':[{'byteLength':0}],'animations':[]}
 def addbuf(self,data,target=None):
  while len(self.b)%4:self.b.append(0)
  offset=len(self.b);self.b+=data
  i=len(self.g['bufferViews']);v={'buffer':0,'byteOffset':offset,'byteLength':len(data)}
  if target:v['target']=target
  self.g['bufferViews'].append(v)
  return i
 def accessor(self,arr,component=5126,atype='VEC3',target=None):
  a=np.asarray(arr,dtype={5126:np.float32,5123:np.uint16,5125:np.uint32}[component]);
  if a.ndim==1:a=a.reshape(-1,1)
  view=self.addbuf(a.tobytes(order='C'),target)
  acc={'bufferView':view,'componentType':component,'count':len(a),'type':atype}
  if component==5126:acc.update(min=a.min(axis=0).tolist(),max=a.max(axis=0).tolist())
  elif atype=='SCALAR':acc.update(min=[int(a.min())],max=[int(a.max())])
  idx=len(self.g['accessors']);self.g['accessors'].append(acc);return idx
 def material(self,name,rgba):
  idx=len(self.g['materials']);self.g['materials'].append({'name':name,'pbrMetallicRoughness':{'baseColorFactor':rgba,'metallicFactor':0,'roughnessFactor':.84},'doubleSided':True});return idx
 def mesh(self,geom,mat):
  idx=len(self.g['meshes']);self.g['meshes'].append({'primitives':[{'attributes':{'POSITION':geom[0],'NORMAL':geom[1]},'indices':geom[2],'material':mat}]});return idx
 def node(self,name,parent=None,mesh=None,pos=(0,0,0),scale=(1,1,1)):
  n={'name':name,'translation':list(map(float,pos)),'scale':list(map(float,scale))}
  if mesh is not None:n['mesh']=mesh
  idx=len(self.g['nodes']);self.g['nodes'].append(n)
  if parent is None:self.g['scenes'][0]['nodes'].append(idx)
  else:self.g['nodes'][parent].setdefault('children',[]).append(idx)
  return idx
 def animation(self,name,channels,duration=2):
  a={'name':name,'samplers':[],'channels':[]}
  for target,path,keyframes in channels:
   if not keyframes:continue
   times=[p[0] for p in keyframes];data=[p[1] for p in keyframes]
   ti=self.accessor([[x] for x in times],atype='SCALAR');v=self.accessor(data,atype='VEC4' if path=='rotation' else 'VEC3')
   sampler=len(a['samplers']);a['samplers'].append({'input':ti,'output':v,'interpolation':'LINEAR'})
   a['channels'].append({'sampler':sampler,'target':{'node':target,'path':path}})
  self.g['animations'].append(a)
 def save(self,path):
  while len(self.b)%4:self.b.append(0)
  self.g['buffers'][0]['byteLength']=len(self.b)
  js=json.dumps(self.g,separators=(',',':'),ensure_ascii=False).encode()
  while len(js)%4:js+=b' '
  total=12+8+len(js)+8+len(self.b)
  with open(path,'wb') as f:
   f.write(struct.pack('<4sII',b'glTF',2,total));f.write(struct.pack('<I4s',len(js),b'JSON'));f.write(js);f.write(struct.pack('<I4s',len(self.b),b'BIN\0'));f.write(self.b)

def qaxis(ax,ay,az,angle):
 s=math.sin(angle/2);return [ax*s,ay*s,az*s,math.cos(angle/2)]
def qxyz(x=0,y=0,z=0):
 a=np.array(qaxis(1,0,0,x));b=np.array(qaxis(0,1,0,y));c=np.array(qaxis(0,0,1,z))
 def mul(p,r):
  x,y,z,w=p;u,v,t,s=r
  return np.array([w*u+x*s+y*t-z*v,w*v-x*t+y*s+z*u,w*t+x*v-y*u+z*s,w*s-x*u-y*v-z*t])
 return mul(mul(a,b),c).tolist()

def make(which):
 g=GLB()
 # An original low-poly sphere, shared by geometric pieces. Normals triangulated for smooth skin.
 sph=icosphere(subdivisions=2,radius=1)
 gv=g.accessor(np.asarray(sph.vertices,dtype=np.float32),atype='VEC3',target=34962)
 gn=g.accessor(np.asarray(sph.vertex_normals,dtype=np.float32),atype='VEC3',target=34962)
 gi=g.accessor(np.asarray(sph.faces.flatten(),dtype=np.uint16),component=5123,atype='SCALAR',target=34963)
 geom=(gv,gn,gi)
 palettes=[
  {'skin':[.84,.56,.38,1],'hair':[.13,.105,.10,1],'shirt':[.18,.43,.61,1],'trim':[.11,.27,.38,1], 'trousers':[.18,.22,.32,1],'shoes':[.13,.14,.17,1], 'eyes':[.12,.15,.17,1], 'lips':[.56,.29,.29,1], 'bright':[.97,.91,.78,1]},
  {'skin':[.97,.74,.56,1],'hair':[.40,.20,.13,1],'shirt':[.93,.60,.29,1],'trim':[.70,.34,.24,1], 'trousers':[.34,.38,.49,1],'shoes':[.68,.28,.32,1], 'eyes':[.16,.21,.23,1], 'lips':[.62,.30,.37,1], 'bright':[.97,.93,.83,1]}
 ]
 colors=palettes[which]
 mat={k:g.material(k,v) for k,v in colors.items()}
 # warm cheek tint and room shadow color
 mat['blush']=g.material('blush',[.91,.52,.46,1]);mat['white']=g.material('white',[1,1,1,1]);mat['gloss']=g.material('gloss',[.15,.20,.24,1]);mat['zip']=g.material('zip',[.93,.81,.48,1]);
 cache={k:g.mesh(geom,v) for k,v in mat.items()}
 root=g.node('body_root')
 def piece(name,material,xyz,scale,parent=root):return g.node(name,parent,cache[material],xyz,scale)
 # rounded stylized full-body proportions (about 1.83 m tall)
 hips=piece('hips','trousers',(0,.88,0),(.27,.17,.17))
 torso=piece('sweater','shirt',(0,1.22,0),(.36,.43,.25))
 piece('shirt_band','trim',(0,.96,.01),(.30,.055,.21))
 piece('collar','trim',(0,1.53,.035),(.20,.09,.19))
 piece('button1','zip',(0,1.34,.245),(.024,.028,.016))
 piece('button2','zip',(0,1.23,.262),(.024,.028,.016))
 neck=piece('neck','skin',(0,1.58,0),(.13,.15,.11))
 head=g.node('head_joint',root,pos=(0,1.71,0))
 piece('head','skin',(0,.04,0),(.245,.29,.22),head)
 for x in [-1,1]:
  piece('ear'+str(x),'skin',(x*.239,.045,-.01),(.051,.090,.051),head)
  piece('eye_white'+str(x),'white',(x*.094,.083,.192),(.049,.056,.022),head)
  piece('eye_pupil'+str(x),'eyes',(x*.093,.082,.215),(.029,.039,.019),head)
  piece('eyebrow'+str(x),'hair',(x*.095,.164,.203),(.076,.023,.022),head)
  piece('cheek'+str(x),'blush',(x*.152,-.002,.162),(.055,.031,.011),head)
 piece('nose','skin',(0,.023,.23),(.055,.078,.064),head)
 piece('mouth','lips',(0,-.105,.207),(.078,.016,.016),head)
 piece('hair_cap','hair',(0,.258,-.031),(.251,.112,.214),head)
 piece('hair_fringe','hair',(-.090,.222,.157),(.158,.059,.076),head)
 if which==1:
  piece('ponytail','hair',(0,.14,-.25),(.13,.30,.10),head)
  piece('hair_side_a','hair',(-.218,.078,-.026),(.068,.20,.15),head)
  piece('hair_side_b','hair',(.218,.078,-.026),(.068,.20,.15),head)
 else:
  piece('hair_tuft','hair',(.15,.29,.03),(.11,.095,.15),head)
  piece('hair_tuft_2','hair',(-.17,.29,.02),(.10,.090,.13),head)
 # arms: shoulder rotating upper segment + elbow rotating lower, visible cloth cuffs, hands
 arms={}
 for side in [-1,1]:
  name='left' if side<0 else 'right'
  s=g.node(name+'_shoulder',root,pos=(side*.385,1.43,0))
  piece(name+'_sleeve','shirt',(side*.02,-.165,0),(.145,.232,.143),s)
  piece(name+'_cuff','trim',(side*.02,-.33,0),(.126,.05,.128),s)
  e=g.node(name+'_elbow',s,pos=(0,-.35,0))
  piece(name+'_forearm','skin',(0,-.15,0),(.103,.185,.103),e)
  piece(name+'_hand','skin',(0,-.34,0),(.11,.105,.12),e)
  arms[name]=(s,e)
 legs={}
 for side in [-1,1]:
  name='left' if side<0 else 'right'
  hip=g.node(name+'_hip',root,pos=(side*.16,.83,0))
  piece(name+'_thigh','trousers',(0,-.19,0),(.17,.27,.18),hip)
  knee=g.node(name+'_knee',hip,pos=(0,-.41,0))
  piece(name+'_shin','trousers',(0,-.17,0),(.148,.26,.14),knee)
  piece(name+'_shoe','shoes',(0,-.385,.105),(.17,.115,.285),knee)
  legs[name]=(hip,knee)
 # animations for all 21 built in + 5 extra; 5 key poses/clip
 nodes={'left_arm':arms['left'][0],'right_arm':arms['right'][0], 'left_elbow':arms['left'][1],'right_elbow':arms['right'][1], 'left_leg':legs['left'][0], 'right_leg':legs['right'][0], 'left_knee':legs['left'][1],'right_knee':legs['right'][1], 'head':head, 'root':root}
 times=[0,.25,.5,.75,1.0]
 for name in ACTIONS:
  duration=1 if name in ['walk','run','exercise','jump','clap','dance'] else 2.4
  if name=='sleep':duration=3.2
  tracks={k:[] for k in nodes}
  positions=[]
  for u in times:
   t=u*math.tau;sin=math.sin(t);cos=math.cos(t)
   value={'left_arm':(0,0,0), 'right_arm':(0,0,0), 'left_elbow':(0,0,0), 'right_elbow':(0,0,0), 'left_leg':(0,0,0), 'right_leg':(0,0,0), 'left_knee':(0,0,0), 'right_knee':(0,0,0), 'head':(0,0,0), 'root':(0,0,0)}
   yoffset=.015*math.sin(t);xoffset=0;zoffset=0
   if name in ['walk','run','explore']:
    amp=.52 if name!='run' else .86
    value.update(left_leg=(amp*sin,0,0),right_leg=(-amp*sin,0,0),left_arm=(-amp*sin*.72,0,.10),right_arm=(amp*sin*.72,0,-.10),left_knee=(-.14*max(0,sin),0,0),right_knee=(-.14*max(0,-sin),0,0))
    yoffset=.045*abs(sin) if name!='run' else .090*abs(sin)
   elif name in ['sit','read','work','eat','relax']:
    value.update(left_leg=(-1.25,0,0),right_leg=(-1.25,0,0),left_knee=(1.24,0,0),right_knee=(1.24,0,0))
    value['left_arm']=(-1.00,0,-.05);value['right_arm']=(-1.08,0,.05)
    if name=='eat':value['right_arm']=(-1.65+.18*sin,0,0)
    if name=='read':value['head']=(.19,0,0)
    if name=='relax':value['head']=(-.16,0,0)
    yoffset=-.26
   elif name=='sleep':
    value.update(left_arm=(-.15,0,-.4),right_arm=(-.15,0,.4),root=(math.pi/2,0,0));yoffset=-.0
   elif name in ['wave','greet']:
    value['right_arm']=(-2.33,0,-.38+.30*sin);value['right_elbow']=(-.28+.18*sin,0,0)
   elif name=='talk':
    value['left_arm']=(-.46+.22*sin,0,-.16);value['right_arm']=(-.5-.19*sin,0,.16);value['head']=(.035*sin,.12*sin,0)
   elif name=='dance':
    value.update(left_arm=(-1.9+.34*sin,0,-.4),right_arm=(-1.9-.34*sin,0,.4),left_leg=(.32*sin,0,.16*cos),right_leg=(-.32*sin,0,-.16*cos),root=(0,.18*sin,.08*cos)); yoffset=.13*abs(sin)
   elif name=='stretch':value.update(left_arm=(-2.75,0,-.18),right_arm=(-2.75,0,.18),head=(-.11,0,0))
   elif name=='exercise':value.update(left_arm=(-2+1.1*sin,0,-.12),right_arm=(-2-1.1*sin,0,.12),left_leg=(.52*sin,0,0),right_leg=(-.52*sin,0,0));yoffset=.13*abs(sin)
   elif name in ['cook','clean']:
    value.update(left_arm=(-.8+.36*sin,0,0),right_arm=(-1.2-.25*sin,0,0))
   elif name=='think':value.update(right_arm=(-1.8,0,0),right_elbow=(-.85,0,0),head=(.12,0,0))
   elif name=='observe':value['head']=(0,.38*sin,0)
   elif name=='laugh':value.update(left_arm=(-.75,0,-.3),right_arm=(-.75,0,.3),head=(-.16*sin,0,0));yoffset=.05*abs(sin)
   elif name=='jump':value.update(left_leg=(-.27*sin,0,0),right_leg=(-.27*sin,0,0),left_arm=(-1.6,0,-.4),right_arm=(-1.6,0,.4));yoffset=.25*max(0,math.sin(t))
   elif name=='clap':value.update(left_arm=(-1.25,0,-.85+.22*sin),right_arm=(-1.25,0,.85-.22*sin))
   elif name=='nod':value['head']=(.24*sin,0,0)
   elif name=='celebrate':value.update(left_arm=(-2.45+.13*sin,0,-.3),right_arm=(-2.45+.13*sin,0,.3));yoffset=.08*abs(sin)
   elif name=='point':value.update(right_arm=(-1.3,0,-.38),right_elbow=(-.25,0,0),head=(0,-.24,0))
   for k,vec in value.items():tracks[k].append((duration*u,qxyz(*vec)))
   positions.append((duration*u,[xoffset,float(yoffset),zoffset]))
  channels=[(nodes[k],'rotation',v) for k,v in tracks.items()]
  channels.append((root,'translation',positions))
  g.animation(name,channels,duration)
 path=TARGET/f'avatar{which+1}.glb'
 g.save(path)
 print('Created',path,round(path.stat().st_size/1024,1),'KiB',len(g.g['nodes']),'nodes',len(g.g['animations']),'clips')
 # validate GLB content / nodes
 data=path.read_bytes();assert data[:4]==b'glTF'
 assert struct.unpack_from('<I',data,8)[0]==len(data)
 length=struct.unpack_from('<I',data,12)[0];j=json.loads(data[20:20+length])
 assert len(j['animations'])==len(ACTIONS)
 assert j['buffers'][0]['byteLength'] <= len(data)
 assert all(x['channels'] for x in j['animations'])
 return path
if __name__=='__main__':
 make(0); make(1)
