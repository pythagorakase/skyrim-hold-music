"""Independent binary ESP/VMAD/SEQ validation; no Mutagen dependency."""
import hashlib
import json
from pathlib import Path
import struct
import unittest
import zlib

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build'


def records(data):
    result=[]
    def walk(start,end):
        while start<end:
            tag,size=struct.unpack_from('<4sI',data,start)
            if tag==b'GRUP':
                assert size>=24 and start+size<=end
                walk(start+24,start+size); start+=size
                continue
            tag,size,flags,fid,revision,version,unknown=struct.unpack_from('<4sIIIIHH',data,start)
            payload=data[start+24:start+24+size]
            assert len(payload)==size
            if flags&0x40000:
                length=struct.unpack_from('<I',payload)[0]
                payload=zlib.decompress(payload[4:]); assert len(payload)==length
            pos=0; parts=[]; ext=None
            while pos<len(payload):
                sub,n=struct.unpack_from('<4sH',payload,pos);pos+=6
                if sub==b'XXXX':
                    assert n==4; ext=struct.unpack_from('<I',payload,pos)[0];pos+=4;continue
                if ext is not None: n=ext;ext=None
                value=payload[pos:pos+n];assert len(value)==n
                parts.append((sub,value));pos+=n
            assert pos==len(payload)
            result.append({'tag':tag,'flags':flags,'id':fid,'parts':parts,'values':dict(parts)})
            start+=size+24
        assert start==end
    walk(0,len(data));return result

class Reader:
    def __init__(self,data): self.data=data;self.pos=0
    def take(self,fmt):
        value=struct.unpack_from(fmt,self.data,self.pos);self.pos+=struct.calcsize(fmt)
        return value[0] if len(value)==1 else value
    def string(self):
        n=self.take('<H');value=self.data[self.pos:self.pos+n];self.pos+=n
        return value.decode()
    def object(self):
        unused,alias,form=self.take('<HhI');assert unused==0
        return {'form':form,'alias':alias}
    def value(self,typ):
        if typ==1: return self.object()
        if typ==2: return self.string()
        if typ in (3,4,5): return self.take({3:'<i',4:'<f',5:'<B'}[typ])
        if 11<=typ<=15: return [self.value(typ-10) for _ in range(self.take('<I'))]
        raise AssertionError(('VMAD type',typ))
    def script(self):
        name=self.string(); status=self.take('<B'); props={}
        for _ in range(self.take('<H')):
            key=self.string();typ,flags=self.take('<BB');props[key]=self.value(typ)
        return name,props

class PluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records=records((BUILD/'package/HoldMusic.esp').read_bytes())
        cls.header=cls.records[0]
        cls.by_edid={r['values'][b'EDID'].rstrip(b'\0').decode():r for r in cls.records[1:]}
        cls.master_count=len([x for x in cls.header['parts'] if x[0]==b'MAST'])
        cls.base=cls.master_count<<24

    def test_esl_masters_and_counts(self):
        from collections import Counter
        self.assertTrue(self.header['flags']&0x200)
        self.assertEqual([v for t,v in self.header['parts'] if t==b'MAST'],[b'Skyrim.esm\0'])
        self.assertEqual(Counter(r['tag'] for r in self.records),{b'TES4':1,b'QUST':1,b'GLOB':5,b'SNDR':24,b'SOUN':24})
        self.assertTrue(all(r['id']>>24==self.master_count and 0x800<=r['id']&0xffffff<=0xfff for r in self.records[1:]))

    def test_quest_alias_scripts_and_every_property(self):
        q=self.by_edid['HM_Quest']; d=q['values']
        self.assertEqual(struct.unpack_from('<H',d[b'DNAM'])[0]&0x101,0x101)
        self.assertEqual(struct.unpack('<I',d[b'ALFR'])[0],0x14)
        self.assertEqual(struct.unpack('<I',d[b'ALST'])[0],0)
        r=Reader(d[b'VMAD']);self.assertEqual(r.take('<HHH'),(5,2,2))
        scripts=dict(r.script() for _ in range(2))
        self.assertEqual(set(scripts),{'HM_Config','HM_Library'})
        self.assertEqual(scripts['HM_Config']['ModName'],'HoldMusic')
        # Version 2 quest fragment extension: no stage fragments, empty filename.
        self.assertEqual(r.take('<BH'),(2,0));self.assertEqual(r.string(),'')
        self.assertEqual(r.take('<H'),1)
        self.assertEqual(r.object(),{'form':q['id'],'alias':0})
        self.assertEqual(r.take('<HHH'),(5,2,2))
        alias_scripts=dict(r.script() for _ in range(2))
        self.assertEqual(set(alias_scripts),{'HM_Controller','SKI_PlayerLoadGameAlias'})
        self.assertEqual(r.pos,len(r.data))
        props=alias_scripts['HM_Controller']
        for key in ('Library','Config'):
            self.assertEqual(props[key],{'form':q['id'],'alias':-1})
        forms=json.loads((ROOT/'data/forms.json').read_text())['forms']
        for key in ('LocTypeInn','CurrentFollowerFaction','IdleLuteStart','IdleStop'):
            form=next(x for x in forms if x['edid']==key)
            self.assertEqual(props[key],{'form':int(form['id'],16),'alias':-1})
        for key in ('HM_Enabled','HM_InstrumentalPercent','HM_SessionCap','HM_MinDelaySeconds','HM_MaxDelaySeconds'):
            self.assertEqual(props[key]['form'],self.by_edid[key]['id'])
            if key in ('HM_Enabled','HM_InstrumentalPercent','HM_SessionCap'):
                self.assertEqual(scripts['HM_Config'][key],props[key])
        self.assertEqual(props['SlotSounds'],[{'form':self.by_edid[f'HM_Sound_{i:02}']['id'],'alias':-1} for i in range(1,25)])

    def test_sound_paths_markers_category_3d_and_no_loop(self):
        for slot in json.loads((ROOT/'data/slots.json').read_text()):
            with self.subTest(slot=slot['slot']):
                d=self.by_edid[slot['descriptor']]
                m=self.by_edid[slot['marker']]
                self.assertEqual(struct.unpack('<I',m['values'][b'SDSC'])[0],d['id'])
                paths=[v.rstrip(b'\0').decode() for t,v in d['parts'] if t==b'ANAM']
                self.assertEqual([p.lower() for p in paths],[slot['file'].lower()])
                self.assertEqual(struct.unpack('<I',d['values'][b'GNAM'])[0],0x9F254)
                self.assertEqual(struct.unpack('<I',d['values'][b'ONAM'])[0],0xE324B)
                self.assertEqual(d['values'][b'LNAM'][1],0)
                self.assertEqual(struct.unpack('<I',d['values'][b'CNAM'])[0],0x1EEF540A)

    def test_globals_and_seq(self):
        actual={name:struct.unpack('<f',r['values'][b'FLTV'])[0] for name,r in self.by_edid.items() if r['tag']==b'GLOB'}
        self.assertEqual(actual,{'HM_Enabled':1,'HM_InstrumentalPercent':50,'HM_SessionCap':3,'HM_MinDelaySeconds':15,'HM_MaxDelaySeconds':60})
        self.assertEqual((BUILD/'package/SEQ/HoldMusic.seq').read_bytes(),struct.pack('<I',self.by_edid['HM_Quest']['id']))

    def test_hashes_and_compiled_sources_match(self):
        hashes=json.loads((BUILD/'package-hashes.json').read_text())
        actual={p.relative_to(BUILD/'package').as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (BUILD/'package').rglob('*') if p.is_file()}
        self.assertEqual(actual,hashes)
        for p in (ROOT/'src').rglob('*'):
            if p.is_file(): self.assertEqual(p.read_bytes(),(BUILD/'package'/p.relative_to(ROOT/'src')).read_bytes(),str(p))

if __name__=='__main__': unittest.main()
