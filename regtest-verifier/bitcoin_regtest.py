"""Regtest-first Bitcoin block assembly and native Frankenstein nonce scanner.

Explicitly NOT mainnet-ready: empty blocks only, OP_TRUE payout only for regtest,
no job refresh or network reconnection, no persistent work ledger.
"""
from __future__ import annotations
import argparse, ctypes as C, hashlib, json, os, struct, subprocess, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from base64 import b64encode

ROOT=Path(__file__).resolve().parent

def sha256d(b): return hashlib.sha256(hashlib.sha256(b).digest()).digest()
def compact_size(n):
    if n<253:return bytes([n])
    if n<=0xffff:return b'\xfd'+struct.pack('<H',n)
    if n<=0xffffffff:return b'\xfe'+struct.pack('<I',n)
    return b'\xff'+struct.pack('<Q',n)

def script_num(n):
    if n<0:raise ValueError('negative height')
    if n==0:return b''
    out=bytearray()
    while n:out.append(n&255);n>>=8
    if out[-1]&0x80:out.append(0)
    return bytes(out)

def push(b):
    if len(b)>75:raise ValueError('data push exceeds simple format')
    return bytes([len(b)])+b

def bip34_height(n):
    if n<0:raise ValueError('negative height')
    if n==0:return b'\x00'
    if 1<=n<=16:return bytes([0x50+n])
    return push(script_num(n))

def coinbase(height,value,payout_script=b'\x51',tag=b'/FrankensteinRegtest/'):
    if not (0<=value<=0xffffffffffffffff):raise ValueError('invalid subsidy')
    script=bip34_height(height)+push(tag)
    if not 2<=len(script)<=100:raise ValueError('coinbase scriptSig length')
    tx=(struct.pack('<I',2)+b'\x01'+bytes(32)+struct.pack('<I',0xffffffff)+
        compact_size(len(script))+script+struct.pack('<I',0xffffffff)+
        b'\x01'+struct.pack('<Q',value)+compact_size(len(payout_script))+payout_script+
        struct.pack('<I',0))
    return tx

def decode_compact(bits):
    """Bitcoin SetCompact-style unsigned positive target, rejects negative/overflow/zero."""
    if isinstance(bits,str):bits=int(bits,16)
    size=bits>>24; mant=bits&0x007fffff
    if bits&0x00800000 or mant==0 or (size>34) or (mant>0xff and size>33) or (mant>0xffff and size>32):
        raise ValueError('invalid compact target')
    target=(mant>>(8*(3-size))) if size<=3 else (mant<<(8*(size-3)))
    if not (0<target<1<<256):raise ValueError('invalid target')
    return target

def make_block(template, payout_script=b'\x51'):
    """Assemble an empty regtest block from Bitcoin Core getblocktemplate."""
    height=int(template['height']);cb=coinbase(height,int(template['coinbasevalue']),payout_script)
    merkle=sha256d(cb) # digest bytes are internal wire order
    version=int(template['version']); previous=bytes.fromhex(template['previousblockhash'])[::-1]
    bits=int(template['bits'],16); timestamp=int(template['curtime'])
    header=(struct.pack('<I',version)+previous+merkle+struct.pack('<III',timestamp,bits,0))
    assert len(header)==80
    return header,cb,decode_compact(bits)

def block_bytes(header,cb):return header+b'\x01'+cb

class Native:
    def __init__(self):
        import platform
        if os.name=='nt': lib=ROOT/'frankenstein.dll'
        else: lib=ROOT/'libfrankenstein.so'
        if not lib.exists():
            if os.name=='nt':raise RuntimeError('Build frankenstein.dll with your Windows C compiler first')
            subprocess.run(['gcc','-O3','-std=c11','-fPIC','-shared',str(ROOT/'frankenstein_sha256d.c'),'-o',str(lib)],check=True)
        self.dll=C.CDLL(str(lib))
        self.fn=self.dll.franken_scan07
        self.fn.argtypes=[C.POINTER(C.c_ubyte),C.c_uint32,C.c_uint64,C.POINTER(C.c_ubyte),C.c_int,C.POINTER(C.c_uint32),C.POINTER(C.c_ubyte),C.POINTER(C.c_uint64)]
        self.fn.restype=C.c_int
    def scan(self,header,target,start,count):
        if len(header)!=80 or not (0<=target<1<<256):raise ValueError('invalid input')
        found=C.c_uint32();hashout=(C.c_ubyte*32)();processed=C.c_uint64()
        rc=self.fn((C.c_ubyte*80).from_buffer_copy(header),start,count,
            (C.c_ubyte*32).from_buffer_copy(target.to_bytes(32,'little')),0,
            C.byref(found),hashout,C.byref(processed))
        if rc<0:raise ValueError('invalid scan range')
        digest=bytes(hashout) if rc else None
        if rc:
            h=header[:76]+struct.pack('<I',found.value)
            if sha256d(h)!=digest or int.from_bytes(digest,'little')>target:
                raise AssertionError('native result verification failed')
        return (found.value if rc else None),processed.value

def rpc(method,params,host,username,password):
    payload=json.dumps({'jsonrpc':'1.0','id':'frankenstein','method':method,'params':params}).encode()
    auth=b64encode(f'{username}:{password}'.encode()).decode()
    req=Request(host,data=payload,headers={'Content-Type':'application/json','Authorization':'Basic '+auth})
    with urlopen(req,timeout=20) as res:data=json.load(res)
    if data.get('error'):raise RuntimeError(f'RPC {method}: {data["error"]}')
    return data['result']

def main():
    p=argparse.ArgumentParser(description='Offline or Bitcoin Core regtest-only Frankenminer v0.8')
    p.add_argument('--template',help='getblocktemplate JSON file (offline; no submit)')
    p.add_argument('--regtest-rpc',help='Regtest-only JSON-RPC endpoint, e.g. http://127.0.0.1:18443/')
    p.add_argument('--start',type=int,default=0);p.add_argument('--count',type=int,default=100000)
    p.add_argument('--submit',action='store_true',help='Submit found block to a regtest node only')
    p.add_argument('--cookie-file',help='Path to Bitcoin Core .cookie file for authentication')
    args=p.parse_args()
    if bool(args.template)==bool(args.regtest_rpc):p.error('provide exactly one of --template or --regtest-rpc')
    if args.submit and not args.regtest_rpc:p.error('--submit requires --regtest-rpc')
    if args.regtest_rpc:
        if not (args.regtest_rpc.startswith('http://127.0.0.1:') or args.regtest_rpc.startswith('http://localhost:')):
            p.error('RPC restricted to loopback for this prototype')
        user=os.environ.get('BTC_RPC_USER');password=os.environ.get('BTC_RPC_PASSWORD')
        cookie_path = Path(args.cookie_file) if args.cookie_file else (ROOT.parent / 'regtest_data' / 'regtest' / '.cookie')
        if (not user or not password) and cookie_path.exists():
            cookie_content = cookie_path.read_text().strip()
            if ':' in cookie_content:
                user, password = cookie_content.split(':', 1)
        if not user or not password:
            p.error('Missing credentials: set BTC_RPC_USER / BTC_RPC_PASSWORD or provide .cookie file')
        def call(method,params=[]):return rpc(method,params,args.regtest_rpc,user,password)
        chain=call('getblockchaininfo')['chain']
        if chain!='regtest':p.error('Refusing to connect to any chain other than regtest')
        template=call('getblocktemplate',[{'rules':['segwit']}])
    else:template=json.loads(Path(args.template).read_text())
    header,cb,target=make_block(template)
    start_time=time.perf_counter()
    nonce,processed=Native().scan(header,target,args.start,args.count)
    print(json.dumps({'height':template['height'],'difficulty_bits':template['bits'],'checked':processed,
        'nonce':nonce,'elapsed_seconds':round(time.perf_counter()-start_time,4)},indent=2))
    if nonce is not None:
        solved_header=header[:76]+struct.pack('<I',nonce)
        candidate=block_bytes(solved_header,cb)
        print('block_hash:',sha256d(solved_header)[::-1].hex())
        print('block_bytes:',len(candidate))
        if args.submit:print('submitblock result:',call('submitblock',[candidate.hex()]))
    elif args.submit:print('No qualifying header found; nothing submitted')

if __name__=='__main__':main()
