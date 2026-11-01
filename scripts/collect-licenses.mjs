// Preserve license/notice files from packages bundled into the web build.
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve(process.argv[2]);
const output=process.argv[3];
const blocks=['Third-party dependency notices (including build tools).\nEach package retains its original license.\n'];
function walk(dir){
 for(const entry of fs.readdirSync(dir,{withFileTypes:true})){
  if(!entry.isDirectory() || entry.name==='bin' || entry.name==='.bin')continue;
  const folder=path.join(dir,entry.name), manifest=path.join(folder,'package.json');
  if(fs.existsSync(manifest)){
   const pkg=JSON.parse(fs.readFileSync(manifest,'utf8'));
   const files=fs.readdirSync(folder).filter(f=>/^(licen[cs]e|copying|notice)(\.|$)/i.test(f)&&fs.statSync(path.join(folder,f)).isFile());
   blocks.push(`\n===== ${pkg.name}@${pkg.version} (${typeof pkg.license==='string'?pkg.license:'see package source'}) =====\n`);
   for(const f of files)blocks.push(fs.readFileSync(path.join(folder,f),'utf8'));
   if(fs.existsSync(path.join(folder,'node_modules')))walk(path.join(folder,'node_modules'));
  }else if(entry.name.startsWith('@'))walk(folder);
 }
}
walk(root);fs.writeFileSync(output,blocks.join('\n'));
