const utf8 = new TextEncoder();
export function from64(value) {
  return Uint8Array.from(atob(value.replace(/-/g,"+").replace(/_/g,"/")), c => c.charCodeAt(0));
}
export function to64(data) {
  let chunks = [];
  for (let i=0; i<data.length; i+=24576) chunks.push(String.fromCharCode(...data.subarray(i,i+24576)));
  return btoa(chunks.join(""));
}
export const hex = data => Array.from(new Uint8Array(data), v=>v.toString(16).padStart(2,"0")).join("");
function storedZip(bytes) {
  const name = utf8.encode("toma.bin"), n=bytes.length;
  let crc=0xffffffff;
  for (const b of bytes) { crc ^= b; for(let i=0;i<8;i++) crc=(crc>>>1)^((crc&1)?0xedb88320:0); }
  crc=(crc^0xffffffff)>>>0;
  function header(length, fields) {
    const a=new Uint8Array(length), v=new DataView(a.buffer);
    for (const [offset,size,value] of fields) v[size===2?"setUint16":"setUint32"](offset,value,true);
    return a;
  }
  const loc=header(30,[[0,4,0x04034b50],[4,2,20],[14,4,crc],[18,4,n],[22,4,n],[26,2,name.length]]);
  const central=header(46,[[0,4,0x02014b50],[4,2,20],[6,2,20],[16,4,crc],[20,4,n],[24,4,n],[28,2,name.length]]);
  const end=header(22,[[0,4,0x06054b50],[8,2,1],[10,2,1],[12,4,46+name.length],[16,4,30+name.length+n]]);
  return new Blob([loc,name,bytes,central,name,end],{type:"application/zip"});
}
async function aes(key,use){return crypto.subtle.importKey("raw",from64(key),"AES-GCM",false,[use]);}
const params=(iv,id)=>({name:"AES-GCM",iv,additionalData:utf8.encode("studio-v1/"+id)});
export async function seal(blob,id,secret) {
  const iv=crypto.getRandomValues(new Uint8Array(12));
  const encrypted=await crypto.subtle.encrypt(params(iv,id),await aes(secret,"encrypt"),await blob.arrayBuffer());
  const packet=new Uint8Array(12+encrypted.byteLength);packet.set(iv);packet.set(new Uint8Array(encrypted),12);
  return storedZip(packet);
}
export async function openFinal(buffer,secret) {
  const bytes=new Uint8Array(buffer);
  const clear=await crypto.subtle.decrypt(params(bytes.subarray(0,12),"final"),await aes(secret,"decrypt"),bytes.subarray(12));
  return new Blob([clear],{type:"video/mp4"});
}
let dbPromise;
async function db(){
  if (!dbPromise) dbPromise=new Promise((resolve,reject)=>{const req=indexedDB.open("estudio-v1",1);
    req.onupgradeneeded=()=>req.result.createObjectStore("tomas");req.onerror=()=>reject(req.error);req.onsuccess=()=>resolve(req.result);});
  return dbPromise;
}
export async function draft(id,blob) {
  const database=await db();return new Promise((resolve,reject)=>{
    const tx=database.transaction("tomas",blob?"readwrite":"readonly");
    const req=blob?tx.objectStore("tomas").put(blob,id):tx.objectStore("tomas").get(id);
    tx.oncomplete=()=>resolve(req.result);tx.onabort=tx.onerror=()=>reject(tx.error);
  });
}
