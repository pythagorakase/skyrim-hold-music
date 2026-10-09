"""Adapted from halcyon ModernMarriage/tests/pex_vm.py.
Executes Champollion disassembly of built PEX, never source-level pseudocode.
Unknown instructions/calls fail. Native APIs are mocks, not engine validation.
"""
import json
import re
from pathlib import Path
BUILD = Path(__file__).resolve().parents[1] / 'build'

def functions(text):
    return {m.group(1).lower():m.group() for m in re.finditer(r"\.function (\w+)\b.*?\.endFunction",text,re.S)}

class VM:
    def __init__(self):
        self.scripts = {}
        self.state = {}
        for p in (BUILD/'disassembly').glob('*.pas'):
            text=p.read_text()
            owner=p.stem.lower()
            self.scripts[owner]=functions(text)
            self.state[owner]={}
            for name,typ,value in re.findall(r'\.variable (\S+) (\S+).*?\.initialValue ([^\r\n]+)',text,re.S):
                value=value.strip()
                if value.lower() in ('none','true','false'):
                    default={'none':None,'true':True,'false':False}[value.lower()]
                elif value.startswith('"'):
                    default=json.loads(value)
                else:
                    default=float(value) if '.' in value else int(value)
                self.state[owner][name.lower()]=default
        assert set(self.scripts)=={'hm_controller','hm_library','hm_config'}, 'Build three PEX files and disassemble first'
        self.now=100.0
        self.effects=[]
        self.scheduled=None
        self.settings={'HM_Enabled':1.,'HM_InstrumentalPercent':50.,'HM_SessionCap':3.,'HM_MinDelaySeconds':15.,'HM_MaxDelaySeconds':60.}
        for owner in ('hm_controller','hm_config'):
            for key in self.settings:
                self.prop(owner,key,('global',key))
        for key in ('Library','Config'):
            self.prop('hm_controller',key,('self','hm_'+key.lower()))
        for key in ('LocTypeInn','CurrentFollowerFaction','IdleLuteStart','IdleStop'):
            self.prop('hm_controller',key,key)
        self.prop('hm_controller','SlotSounds',[('sound',i) for i in range(1,25)])
        self.actors={x:dict(loaded=True,dead=False,combat=False,dialogue=False,follower=False,sit=0,sleep=0,cell='inn-cell',location='inn',base=f) for x,f in [('P',7),('Mikael',0x1A670),('Sven',0x1347F),('Other',999)]}
        self.candidates=['Mikael']
        root=Path(__file__).resolve().parents[1]
        self.files={'../HoldMusic/registry.json':json.loads((root/'src/SKSE/Plugins/HoldMusic/registry.json').read_text()),'HoldMusic/library.json':{'recordings':[{'slot':1,'performer_id':'mikael','region':'whiterun','mode':'instrumental','duration_seconds':6.0,'composition_id':'c1'},{'slot':2,'performer_id':'sven','region':'whiterun','mode':'vocal','duration_seconds':6.0,'composition_id':'c2'}]},'HoldMusic/receipts.json':{'receipts':[]}}
        self.modsettings={'bEnabled:General':True,'iInstrumentalPercent:General':50,'iSessionCap:General':3,'sWorldId:General':''}
        self.run('hm_controller','OnInit')

    def prop(self,owner,name,value):
        self.state[owner]['::'+name.lower()+'_var']=value

    def advance(self,seconds):
        self.now+=seconds
        self.run('hm_controller','OnUpdate')

    def enter(self,location='inn'):
        self.actors['P']['location']=location
        self.run('hm_controller','OnLocationChange',None,location)

    @property
    def receipts(self):
        return self.files['HoldMusic/receipts.json']['receipts']

    @staticmethod
    def default(typ):
        return {"int": 0, "float": 0.0, "bool": False, "string": ""}.get(typ.lower())

    def run(self, owner, method, *params):
        owner, method = owner.lower(), method.lower()
        block = self.scripts[owner][method]
        types = {n.lower(): t.lower() for n,t in re.findall(r"\.(?:param|local) (\S+) (\S+)", block)}
        env = {n:self.default(t) for n,t in types.items()}
        names = re.findall(r"\.param (\S+) \S+", block)
        assert len(names) == len(params), (owner, method, names, params)
        env.update({n.lower():p for n,p in zip(names,params)})
        env['self'] = ('self',owner)
        code = block.split('.code',1)[1].split('.endCode',1)[0]
        ins, labels = [], {}
        for line in code.splitlines():
            line = line.strip()
            if not line or line.startswith(';'): continue
            if line.startswith('_label'):
                labels[line.rstrip(':')] = len(ins)
            else:
                ins.append(re.findall(r'"(?:\\.|[^"\\])*"|[^\s;]+',line.split(' ;',1)[0]))
        def val(s):
            if s.startswith('"'): return json.loads(s)
            if s.lower() in ('none','true','false'): return {'none':None,'true':True,'false':False}[s.lower()]
            try: return float(s) if '.' in s else int(s)
            except ValueError: pass
            if s.lower() in env: return env[s.lower()]
            if s.lower() in self.state[owner]: return self.state[owner][s.lower()]
            raise AssertionError(('undefined variable',owner,method,s))
        def put(n,v):
            if n.lower() in env: env[n.lower()] = v
            else: self.state[owner][n.lower()] = v
        pc=0
        for _ in range(12000):
            if pc >= len(ins): return None
            op,*a=ins[pc]; pc+=1
            if op=='return': return val(a[0]) if a else None
            if op=='jmp': pc=labels[a[0]]
            elif op in ('jmpf','jmpt'):
                if bool(val(a[0])) == (op=='jmpt'): pc=labels[a[1]]
            elif op in ('assign','cast'):
                v=val(a[1]); typ=types.get(a[0].lower(),'')
                if op=='cast':
                    if typ=='bool': v=bool(v)
                    elif typ=='int': v=int(v or 0)
                    elif typ=='float': v=float(v or 0)
                    elif typ=='string': v=str(v)
                put(a[0],v)
            elif op=='not': put(a[0],not val(a[1]))
            elif op.startswith('cmp_') or op=='comp_gte':
                x,y=val(a[1]),val(a[2])
                funcs={'cmp_eq':lambda:x==y,'cmp_lt':lambda:x<y,'cmp_lte':lambda:x<=y,'cmp_gt':lambda:x>y,'comp_gte':lambda:x>=y,'cmp_gte':lambda:x>=y}
                put(a[0],funcs[op]())
            elif op in ('iadd','fadd'): put(a[0],val(a[1])+val(a[2]))
            elif op in ('isub','fsub'): put(a[0],val(a[1])-val(a[2]))
            elif op=='strcat': put(a[0],str(val(a[1]))+str(val(a[2])))
            elif op=='array_length': put(a[0],len(val(a[1]) or []))
            elif op=='array_create': put(a[0],[None]*val(a[1]))
            elif op=='array_getlement': put(a[0],val(a[1])[val(a[2])])
            elif op=='array_setelement': val(a[0])[val(a[1])]=val(a[2])
            elif op=='array_findelement':
                try: found=(val(a[0]) or []).index(val(a[2]),val(a[3]))
                except ValueError: found=-1
                put(a[1],found)
            elif op=='propget': put(a[2],self.state[val(a[1])[1]]['::'+a[0].lower()+'_var'])
            elif op=='propset': self.state[val(a[1])[1]]['::'+a[0].lower()+'_var']=val(a[2])
            elif op=='callparent': self.effects.append(('parent',a[0])); put(a[1],None)
            elif op=='callstatic': put(a[2],self.static(a[0].lower(),a[1].lower(),[val(x) for x in a[3:]]))
            elif op=='callmethod': put(a[2],self.method(val(a[1]),a[0].lower(),[val(x) for x in a[3:]]))
            else: raise AssertionError(('unsupported opcode',op,a))
        raise AssertionError('Loop limit')

    def method(self,obj,name,a):
        if isinstance(obj,tuple):
            kind,key=obj
            if kind=='global':
                if name=='getvalue': return self.settings[key]
                if name=='setvalue': self.settings[key]=a[0]; return None
            if kind=='sound' and name=='play':
                self.effects.append(('play',key,a[0])); return key+1000
            if kind=='base':
                if name=='getformid': return self.actors[key]['base']
                if name=='getname': return key
            if kind=='form' and name=='getformid': return key
            if kind=='self':
                if name in self.scripts[key]: return self.run(key,name,*a)
                if name=='registerforsingleupdate': self.scheduled=a[0]; self.effects.append(('schedule',a[0])); return None
                if name=='unregisterforupdate': self.scheduled=None; return None
                if name.startswith('getmodsetting'): return self.modsettings[a[0]]
        if obj in ('inn','outside') and name=='haskeyword':
            assert a==['LocTypeInn']; return obj=='inn'
        if isinstance(obj,str) and obj in self.actors:
            actor=self.actors[obj]
            attrs={'is3dloaded':'loaded','isdead':'dead','isincombat':'combat','isindialoguewithplayer':'dialogue','getsitstate':'sit','getsleepstate':'sleep','getparentcell':'cell','getcurrentlocation':'location'}
            if name in attrs: return actor[attrs[name]]
            if name=='isinfaction': assert a==['CurrentFollowerFaction']; return actor['follower']
            if name=='getactorbase': return ('base',obj)
            if name=='getformid': assert obj=='P'; return 0x14
            if name=='playidle': self.effects.append(('idle',obj,a[0])); return True
        raise AssertionError(('unmocked method',obj,name,a))

    @staticmethod
    def parts(path):
        return [int(b) if b else a for a,b in re.findall(r'\.([^\.\[\]]+)|\[(\d+)\]',path)]

    def json_get(self,file,path,default=None):
        value=self.files.get(file,{})
        try:
            for key in self.parts(path): value=value[key]
        except (IndexError,KeyError,TypeError): return default
        return value

    def json_set(self,file,path,value):
        keys=self.parts(path)
        obj=self.files.setdefault(file,{})
        for i,key in enumerate(keys):
            if isinstance(obj,list):
                while len(obj)<=key: obj.append(None)
            if i==len(keys)-1:
                obj[key]=value; break
            child=[] if isinstance(keys[i+1],int) else {}
            if isinstance(obj,list):
                if obj[key] is None: obj[key]=child
            else:
                obj.setdefault(key,child)
            obj=obj[key]

    def static(self,owner,name,a):
        if owner=='game':
            if name=='getplayer': return 'P'
            if name=='getformfromfile':
                return ('form',a[0]) if a[1]=='Skyrim.esm' else None
        if owner=='utility':
            if name=='getcurrentrealtime': return self.now
            if name=='getcurrentgametime': return 42.0
            if name=='randomfloat': return a[0]
            if name=='randomint': return 1
        if owner=='miscutil' and name=='scancellnpcs':
            assert a==['P',2000.0,None,True]; return self.candidates[:]
        if owner=='sound' and name=='stopinstance': self.effects.append(('stop',a[0])); return None
        if owner=='debug' and name=='trace': self.effects.append(('trace',*a)); return None
        if owner=='jsonutil':
            if name in ('load','isgood'): return a[0] in self.files
            if name=='save': self.effects.append(('save',a[0])); return True
            if name=='pathcount': return len(self.json_get(*a,default=[]) or [])
            if name=='pathmembers': return list(self.json_get(*a,default={}))
            if name.startswith('setpath'):
                self.json_set(*a); return None
            if name.startswith('getpath'): return self.json_get(*a)
            if name=='canresolvepath':
                missing=object(); return self.json_get(*a,default=missing) is not missing
            if name.startswith('ispath'):
                value=self.json_get(*a)
                typ={'ispathobject':dict,'ispatharray':list,'ispathstring':str,'ispathnumber':(int,float),'ispathbool':bool}[name]
                return isinstance(value,typ)
        raise AssertionError(('unmocked static',owner,name,a))
