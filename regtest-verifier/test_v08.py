import hashlib, json, struct, random, unittest
from pathlib import Path
from bitcoin_regtest import Native,sha256d,coinbase,make_block,decode_compact,block_bytes,script_num

class Tests(unittest.TestCase):
 def test_compact(self):
  self.assertEqual(decode_compact('207fffff'),0x7fffff << (8*(32-3)))
  self.assertEqual(decode_compact('1d00ffff'),0xffff << (8*(29-3)))
  for bad in ('00000000','1d80ffff','23000001'):
   with self.assertRaises(ValueError):decode_compact(bad)
 def test_genesis_hash(self):
  genesis=bytes.fromhex('01000000')+bytes(32)+bytes.fromhex('3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a')+bytes.fromhex('29ab5f49ffff001d1dac2b7c')
  self.assertEqual(len(genesis),80)
  self.assertEqual(sha256d(genesis)[::-1].hex(),'000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f')
 def test_block_and_native(self):
  t={'height':1,'version':0x20000000,'previousblockhash':'00'*32,'bits':'207fffff','curtime':1700000000,'coinbasevalue':5000000000}
  header,cb,target=make_block(t)
  self.assertEqual(len(header),80)
  self.assertEqual(header[36:68],sha256d(cb))
  self.assertTrue(block_bytes(header,cb).endswith(cb))
  n,done=Native().scan(header,target,0,100)
  self.assertIsNotNone(n)
  self.assertEqual(done,n+1)
  h=header[:76]+struct.pack('<I',n)
  self.assertLessEqual(int.from_bytes(sha256d(h),'little'),target)
 def test_low_target(self):
  t={'height':5,'version':0x20000000,'previousblockhash':'11'*32,'bits':'207fffff','curtime':1700000000,'coinbasevalue':5000000000}
  h,cb,target=make_block(t)
  n,done=Native().scan(h,0,20,200)
  self.assertIsNone(n);self.assertEqual(done,200)
  with self.assertRaises(ValueError):Native().scan(h,target,0xffffffff,2)
 def test_coinbase_height(self):
  for height in (1, 16, 17, 127, 128, 255, 256, 65536, 500000):
   tx = coinbase(height, 50)
   script_start = 4 + 1 + 32 + 4 + 1
   if 1 <= height <= 16:
    self.assertEqual(tx[script_start], 0x50 + height)
   else:
    sn = script_num(height)
    self.assertEqual(tx[script_start], len(sn))
    self.assertEqual(tx[script_start + 1:script_start + 1 + len(sn)], sn)

 def test_randomized_bitcoin_target_endianness(self):
  rng=random.Random(4082026); miner=Native()
  # Crucial: Bitcoin interprets raw SHA256d bytes as a little-endian 256-bit integer.
  for j in range(96):
   header=bytes(rng.getrandbits(8) for _ in range(80))
   start=rng.randrange(0,20000); count=rng.randrange(1,75)
   threshold=rng.choice([0, (1<<248)-1, (1<<252)-1, (1<<255)-1, (1<<256)-1])
   expected=None
   for nonce in range(start,start+count):
    digest=sha256d(header[:76]+struct.pack('<I',nonce))
    if int.from_bytes(digest,'little')<=threshold:
     expected=nonce;break
   actual,processed=miner.scan(header,threshold,start,count)
   self.assertEqual(actual,expected,(j,threshold))
   self.assertEqual(processed,(expected-start+1) if expected is not None else count)

if __name__=='__main__':unittest.main(verbosity=2)
