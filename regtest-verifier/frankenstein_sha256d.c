
#include <stdint.h>
#include <string.h>
#include <stddef.h>
static const uint32_t K[64]={0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u};
static const uint32_t IV[8]={0x6a09e667u,0xbb67ae85u,0x3c6ef372u,0xa54ff53au,0x510e527fu,0x9b05688cu,0x1f83d9abu,0x5be0cd19u};
static inline uint32_t rr(uint32_t x,int n){return (x>>n)|(x<<(32-n));}
static inline uint32_t be32(const uint8_t *p){return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];}
static inline void put32(uint8_t *p,uint32_t x){p[0]=x>>24;p[1]=x>>16;p[2]=x>>8;p[3]=x;}
static void sched(const uint8_t b[64],uint32_t w[64]){
 for(int i=0;i<16;i++)w[i]=be32(b+4*i);
 for(int i=16;i<64;i++){
 uint32_t x=w[i-15],y=w[i-2];
 w[i]=w[i-16]+(rr(x,7)^rr(x,18)^(x>>3))+w[i-7]+(rr(y,17)^rr(y,19)^(y>>10));
 }
}
static void core(uint32_t a[8],const uint32_t w[64],int begin,int end,int factored){
 uint32_t A=a[0],B=a[1],C=a[2],D=a[3],E=a[4],F=a[5],G=a[6],H=a[7];
 for(int i=begin;i<end;i++){
 uint32_t ch=factored?(G^(E&(F^G))):((E&F)^(~E&G));
 uint32_t maj=factored?((A&B)|((A|B)&C)):((A&B)^(A&C)^(B&C));
 uint32_t s1=rr(E,6)^rr(E,11)^rr(E,25);
 uint32_t s0=rr(A,2)^rr(A,13)^rr(A,22);
 uint32_t t1=H+s1+ch+K[i]+w[i], t2=s0+maj;
 H=G;G=F;F=E;E=D+t1;D=C;C=B;B=A;A=t1+t2;
 }
 a[0]=A;a[1]=B;a[2]=C;a[3]=D;a[4]=E;a[5]=F;a[6]=G;a[7]=H;
}
static void compression(const uint32_t in[8],const uint8_t block[64],uint32_t out[8],int factored){
 uint32_t w[64],reg[8];sched(block,w);memcpy(reg,in,32);core(reg,w,0,64,factored);
 for(int i=0;i<8;i++)out[i]=in[i]+reg[i];
}
static void tailblock(const uint8_t header[80],uint8_t tail[64]){
 memset(tail,0,64);memcpy(tail,header+64,16);tail[16]=0x80;tail[62]=2;tail[63]=0x80; // 640 bits
}
static void digestblock(const uint32_t mid[8],uint8_t b[64]){
 memset(b,0,64);for(int i=0;i<8;i++)put32(b+4*i,mid[i]);b[32]=0x80;b[62]=1; // 256 bits
}
// mode 0: no cached prefix; mode 1: prefix cache; mode 2: prefix+3 round checkpoint;
// mode 3: prefix+checkpoint+factored Ch/Maj; all modes compute exact SHA256d.
int franken_hash(const uint8_t header[80],const uint32_t *mid_cached,const uint32_t *checkpoint,int mode,uint8_t out[32]){
 if(mode<0||mode>3)return -1;
 int factored=(mode==3);
 uint32_t mid[8],first[8],final[8],w[64],state[8];uint8_t block[64];
 if(mode==0||!mid_cached)compression(IV,header,mid,factored);else memcpy(mid,mid_cached,32);
 tailblock(header,block);
 if(mode>=2 && checkpoint){
 sched(block,w);memcpy(state,checkpoint,32);core(state,w,3,64,factored);
 for(int i=0;i<8;i++)first[i]=mid[i]+state[i];
 }else compression(mid,block,first,factored);
 digestblock(first,block);compression(IV,block,final,factored);
 for(int i=0;i<8;i++)put32(out+4*i,final[i]);
 return 0;
}
void franken_prepare(const uint8_t header[80],uint32_t mid[8],uint32_t checkpoint[8],int factored){
 uint32_t w[64];uint8_t tail[64];compression(IV,header,mid,factored);
 tailblock(header,tail);sched(tail,w);memcpy(checkpoint,mid,32);core(checkpoint,w,0,3,factored);
}
// Native batch loop: hashes contiguous 80-byte headers; 8 family slots each
// with 8-word midstate and checkpoint stored contiguously. Benchmark only.
int franken_batch(const uint8_t *headers,const uint8_t *family_ids,size_t n,
                  const uint32_t *mids,const uint32_t *checkpoints,int mode,uint8_t *out){
 if(mode<0||mode>3)return -1;
 for(size_t i=0;i<n;i++){
  unsigned f=family_ids[i];if(f>=8)return -2;
  const uint32_t *m=mids+8*f,*c=checkpoints+8*f;
  int rc=franken_hash(headers+80*i,mode?m:0,mode>=2?c:0,mode,out+32*i);
  if(rc)return rc;
 }
 return 0;
}

/* v0.3: bounded, non-overlapping nonce scan for an 80-byte header template.
 * Nonce is the final 4 bytes of the serialized header, little-endian.
 * target_le is the 256-bit Bitcoin target in little-endian byte order.
 * Hashes are compared after reversing digest display order: digest[0] is
 * most significant byte when interpreting SHA256d as a SHA256 digest.
 * This API is offline-only; never performs block submission.
 */
static inline int meets_target(const uint8_t digest[32], const uint8_t target_le[32]){
 for(int i=31;i>=0;--i){
  uint8_t v=digest[31-i];
  if(v<target_le[i])return 1;
  if(v>target_le[i])return 0;
 }
 return 1;
}
/* caller guarantees count <= 2^32-start_nonce; no implicit wraparound.
 * result_nonce and result_digest are filled only on success.
 * return 1: found, 0: not found, negative: invalid arguments.
 */
int franken_scan(const uint8_t template_header[80],uint32_t start_nonce,
 uint64_t count,const uint8_t target_le[32],int mode,
 uint32_t *result_nonce,uint8_t result_digest[32],uint64_t *processed){
 if(!template_header||!target_le||!processed||mode<0||mode>3||
    count>0x100000000ULL-(uint64_t)start_nonce)return -1;
 uint8_t header[80],out[32];uint32_t mid[8],cp[8];
 memcpy(header,template_header,80);
 franken_prepare(header,mid,cp,mode==3);
 *processed=0;
 for(uint64_t i=0;i<count;++i){
  uint32_t nonce=start_nonce+(uint32_t)i;
  header[76]=(uint8_t)nonce;header[77]=(uint8_t)(nonce>>8);
  header[78]=(uint8_t)(nonce>>16);header[79]=(uint8_t)(nonce>>24);
  if(franken_hash(header,mode?mid:NULL,mode>=2?cp:NULL,mode,out))return -2;
  ++*processed;
  if(meets_target(out,target_le)){
    if(result_nonce)*result_nonce=nonce;
    if(result_digest)memcpy(result_digest,out,32);
    return 1;
  }
 }
 return 0;
}

/* v0.4: schedule specialization with exact dependency tracking.
 * Each fixed schedule word is precomputed and variable ones reconstructed.
 * The input may change only at header bytes 76..79 (second block word 3).
 */
typedef struct {
  uint32_t mid[8], checkpoint[8], base[64];
  uint8_t variable[64];
  uint8_t tail[64];
} franken_job04;

static inline uint32_t sig0(uint32_t x){return rr(x,7)^rr(x,18)^(x>>3);}
static inline uint32_t sig1(uint32_t x){return rr(x,17)^rr(x,19)^(x>>10);}
static inline void csa3(uint32_t a,uint32_t b,uint32_t c,uint32_t *s,uint32_t *carry){
 *s=a^b^c;*carry=((a&b)|(a&c)|(b&c))<<1;
}
static void core04(uint32_t st[8],const uint32_t w[64],int begin,int csa){
 uint32_t A=st[0],B=st[1],C=st[2],D=st[3],E=st[4],F=st[5],G=st[6],H=st[7];
 for(int i=begin;i<64;i++){
  uint32_t ch=G^(E&(F^G));
  uint32_t maj=(A&B)|((A|B)&C);
  uint32_t s1=rr(E,6)^rr(E,11)^rr(E,25);
  uint32_t s0=rr(A,2)^rr(A,13)^rr(A,22);
  uint32_t t1;
  if(csa){
   uint32_t s,c,s2,c2,s3,c3;
   csa3(H,s1,ch,&s,&c);
   csa3(s,c,K[i],&s2,&c2);
   csa3(s2,c2,w[i],&s3,&c3);
   t1=s3+c3;
  } else t1=H+s1+ch+K[i]+w[i];
  uint32_t t2=s0+maj;
  H=G;G=F;F=E;E=D+t1;D=C;C=B;B=A;A=t1+t2;
 }
 st[0]=A;st[1]=B;st[2]=C;st[3]=D;st[4]=E;st[5]=F;st[6]=G;st[7]=H;
}
int franken_prepare04(const uint8_t header[80],franken_job04 *job){
 if(!header||!job)return -1;
 compression(IV,header,job->mid,0);
 tailblock(header,job->tail);
 for(int i=0;i<16;i++){job->base[i]=be32(job->tail+4*i);job->variable[i]=(i==3);}
 job->base[3]=0;
 for(int i=16;i<64;i++){
  job->variable[i]=job->variable[i-16]|job->variable[i-15]|job->variable[i-7]|job->variable[i-2];
  if(!job->variable[i])job->base[i]=job->base[i-16]+sig0(job->base[i-15])+job->base[i-7]+sig1(job->base[i-2]);
  else job->base[i]=0;
 }
 uint32_t w[64];memcpy(w,job->base,sizeof(w));
 memcpy(job->checkpoint,job->mid,32);
 core(job->checkpoint,w,0,3,0);
 return 0;
}
static void schedule04(const franken_job04 *job,uint32_t nonce,uint32_t w[64]){
 memcpy(w,job->base,sizeof(job->base));
 w[3]=((nonce&255)<<24)|((nonce&65280)<<8)|((nonce>>8)&65280)|(nonce>>24);
 for(int i=16;i<64;i++)if(job->variable[i])w[i]=w[i-16]+sig0(w[i-15])+w[i-7]+sig1(w[i-2]);
}
int franken_hash04(const franken_job04 *job,uint32_t nonce,int variant,uint8_t digest[32]){
 if(!job||!digest||variant<0||variant>3)return -1;
 uint32_t w[64],st[8],first[8],fin[8];uint8_t b[64];
 if(variant==0){
  memcpy(b,job->tail,64);
  b[12]=(uint8_t)nonce;b[13]=(uint8_t)(nonce>>8);b[14]=(uint8_t)(nonce>>16);b[15]=(uint8_t)(nonce>>24);
  compression(job->mid,b,first,0);
 }else{
  schedule04(job,nonce,w);
  if(variant>=2){memcpy(st,job->checkpoint,32);core04(st,w,3,variant==3);}
  else {memcpy(st,job->mid,32);core04(st,w,0,0);}
  for(int i=0;i<8;i++)first[i]=job->mid[i]+st[i];
 }
 digestblock(first,b);compression(IV,b,fin,0);
 for(int i=0;i<8;i++)put32(digest+4*i,fin[i]);
 return 0;
}
int franken_batch04(const franken_job04 *job,uint32_t start,uint32_t count,int variant,uint8_t *output){
 if(!job||!output||(uint64_t)start+count>0x100000000ULL)return -1;
 for(uint32_t i=0;i<count;i++)if(franken_hash04(job,start+i,variant,output+(size_t)i*32))return -2;
 return 0;
}
size_t franken_job04_size(void){return sizeof(franken_job04);}

/* v0.5: avoid serializing first digest and decoding it again for the second SHA256.
 * This is an exact output-preserving circuit/dataflow optimization. */
static void second_digest_words(const uint32_t first[8],uint32_t result[8]){
 uint32_t w[64],reg[8];
 for(int i=0;i<8;i++)w[i]=first[i];
 w[8]=0x80000000u;
 for(int i=9;i<15;i++)w[i]=0;
 w[15]=256;
 for(int i=16;i<64;i++)w[i]=w[i-16]+sig0(w[i-15])+w[i-7]+sig1(w[i-2]);
 memcpy(reg,IV,32);core(reg,w,0,64,0);
 for(int i=0;i<8;i++)result[i]=IV[i]+reg[i];
}
int franken_hash05(const franken_job04 *job,uint32_t nonce,int variant,uint8_t digest[32]){
 if(!job||!digest||variant<0||variant>3)return -1;
 uint32_t w[64],st[8],first[8],fin[8];uint8_t b[64];
 if(variant==0){
  memcpy(b,job->tail,64);
  b[12]=(uint8_t)nonce;b[13]=(uint8_t)(nonce>>8);b[14]=(uint8_t)(nonce>>16);b[15]=(uint8_t)(nonce>>24);
  compression(job->mid,b,first,0);
 }else{
  schedule04(job,nonce,w);
  if(variant>=2){memcpy(st,job->checkpoint,32);core04(st,w,3,variant==3);}
  else {memcpy(st,job->mid,32);core04(st,w,0,0);}
  for(int i=0;i<8;i++)first[i]=job->mid[i]+st[i];
 }
 second_digest_words(first,fin);
 for(int i=0;i<8;i++)put32(digest+4*i,fin[i]);
 return 0;
}
int franken_batch05(const franken_job04 *job,uint32_t start,uint32_t count,int variant,uint8_t *output){
 if(!job||!output||(uint64_t)start+count>0x100000000ULL)return -1;
 for(uint32_t i=0;i<count;i++)if(franken_hash05(job,start+i,variant,output+(size_t)i*32))return -2;
 return 0;
}

/* v0.6: fused nonce scanner. The SHA-256d digest remains in words until
 * a qualifying nonce is found; no 32-byte output is emitted per miss.
 * target_le stores the Bitcoin 256-bit target in little-endian byte order.
 * variant 0: ordinary midstate, variant 1: nonce-specialized schedule.
 */
static inline int target_words06(const uint32_t digest[8],const uint8_t target_le[32]){
    /* Bitcoin displays block hashes in reverse digest byte order. Compare the
       256-bit integer interpreting SHA256d digest bytes as LITTLE endian. */
    for(int i=7;i>=0;i--){
        uint32_t d=digest[i];
        uint32_t little=((d&0xffu)<<24)|((d&0xff00u)<<8)|((d>>8)&0xff00u)|(d>>24);
        uint32_t t=(uint32_t)target_le[4*i] | ((uint32_t)target_le[4*i+1]<<8) |
                   ((uint32_t)target_le[4*i+2]<<16) | ((uint32_t)target_le[4*i+3]<<24);
        if(little<t)return 1;
        if(little>t)return 0;
    }
    return 1;
}
int franken_scan06(const uint8_t header[80], uint32_t start, uint64_t count,
    const uint8_t target_le[32], int variant, uint32_t *found,
    uint8_t out[32],uint64_t *processed){
    if(!header||!target_le||!processed||variant<0||variant>1||
       count>0x100000000ULL-(uint64_t)start)return -1;
    franken_job04 job;
    if(franken_prepare04(header,&job))return -2;
    uint32_t w[64],state[8],first[8],final[8];
    uint8_t block[64];
    memcpy(block,job.tail,64);
    *processed=0;
    for(uint64_t i=0;i<count;i++){
        uint32_t nonce=(uint32_t)(start+i);
        if(!variant){
            block[12]=(uint8_t)nonce;block[13]=(uint8_t)(nonce>>8);
            block[14]=(uint8_t)(nonce>>16);block[15]=(uint8_t)(nonce>>24);
            sched(block,w);
        }else schedule04(&job,nonce,w);
        memcpy(state,job.mid,32);core(state,w,0,64,0);
        for(int j=0;j<8;j++)first[j]=job.mid[j]+state[j];
        second_digest_words(first,final);
        *processed=i+1;
        if(target_words06(final,target_le)){
            if(found)*found=nonce;
            if(out)for(int j=0;j<8;j++)put32(out+j*4,final[j]);
            return 1;
        }
    }
    return 0;
}

/* v0.7: CPU batch scanner. Modes: 0 reference fused path;
 * 1 four-candidate software-unrolled batch; 2 four interleaved independent
 * SHA-256 compression lanes, with sequential target reporting. */
static void four_lanes07(const uint32_t mid[8], uint32_t w[4][64],uint32_t first[4][8]){
 uint32_t s[4][8];
 for(int lane=0;lane<4;lane++)memcpy(s[lane],mid,32);
 for(int r=0;r<64;r++){
  for(int lane=0;lane<4;lane++){
   uint32_t *v=s[lane];
   uint32_t A=v[0],B=v[1],C=v[2],D=v[3],E=v[4],F=v[5],G=v[6],H=v[7];
   uint32_t t1=H+(rr(E,6)^rr(E,11)^rr(E,25))+(G^(E&(F^G)))+K[r]+w[lane][r];
   uint32_t t2=(rr(A,2)^rr(A,13)^rr(A,22))+((A&B)|((A|B)&C));
   v[0]=t1+t2;v[1]=A;v[2]=B;v[3]=C;
   v[4]=D+t1;v[5]=E;v[6]=F;v[7]=G;
  }
 }
 for(int lane=0;lane<4;lane++)for(int j=0;j<8;j++)first[lane][j]=s[lane][j]+mid[j];
}
int franken_scan07(const uint8_t header[80],uint32_t start,uint64_t count,
  const uint8_t target_le[32],int variant,uint32_t *found,
  uint8_t out[32],uint64_t *processed){
 if(!header||!target_le||!processed||variant<0||variant>2||
    count>0x100000000ULL-(uint64_t)start)return -1;
 if(variant==0)return franken_scan06(header,start,count,target_le,0,found,out,processed);
 franken_job04 job;
 if(franken_prepare04(header,&job))return -2;
 uint32_t w[4][64],first[4][8],last[8],state[8];
 uint8_t block[64];memcpy(block,job.tail,64);
 *processed=0;
 for(uint64_t i=0;i<count;){
  int n=(int)((count-i)>=4?4:(count-i));
  for(int k=0;k<n;k++){
   uint32_t nonce=(uint32_t)((uint64_t)start+i+(uint64_t)k);
   block[12]=(uint8_t)nonce;block[13]=(uint8_t)(nonce>>8);
   block[14]=(uint8_t)(nonce>>16);block[15]=(uint8_t)(nonce>>24);
   sched(block,w[k]);
  }
  if(variant==2&&n==4)four_lanes07(job.mid,w,first);
  else for(int k=0;k<n;k++){
   memcpy(state,job.mid,32);core(state,w[k],0,64,0);
   for(int j=0;j<8;j++)first[k][j]=state[j]+job.mid[j];
  }
  for(int k=0;k<n;k++){
   second_digest_words(first[k],last);
   ++*processed;
   if(target_words06(last,target_le)){
    if(found)*found=(uint32_t)((uint64_t)start+i+(uint64_t)k);
    if(out)for(int j=0;j<8;j++)put32(out+j*4,last[j]);
    return 1;
   }
  }
  i+=(uint64_t)n;
 }
 return 0;
}
