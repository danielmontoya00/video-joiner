const fs=require('node:fs'),http=require('node:http'),path=require('node:path');
const root=path.resolve(__dirname,'../site');
const types={'.html':'text/html','.js':'text/javascript','.json':'application/json','.css':'text/css','.mp4':'video/mp4','.webm':'video/webm','.png':'image/png'};
http.createServer((req,res)=>{
  const name=new URL(req.url,'http://127.0.0.1').pathname;
  const file=path.resolve(root,'.'+(name==='/'?'/index.html':name));
  if(!file.startsWith(root+path.sep)||!fs.existsSync(file))return res.writeHead(404).end();
  const size=fs.statSync(file).size, range=/^bytes=(\d+)-(\d*)$/.exec(req.headers.range||'');
  const start=range?Number(range[1]):0,end=range&&range[2]?Math.min(size-1,Number(range[2])):size-1;
  if(start>end||start>=size)return res.writeHead(416).end();
  res.writeHead(range?206:200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Accept-Ranges':'bytes','Content-Length':end-start+1,...(range?{'Content-Range':'bytes '+start+'-'+end+'/'+size}:{})});
  if(req.method==='HEAD')res.end();else fs.createReadStream(file,{start,end}).pipe(res);
}).listen(8100,'127.0.0.1');
