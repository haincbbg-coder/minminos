const assert=require('assert');
const {PDFDocument}=require('../../dashboard/vendor/pdf-lib-1.17.1.min.js');
const {appendPDF}=require('../../dashboard/file-shelf-core.js');
(async()=>{
  const a=await PDFDocument.create(), b=await PDFDocument.create(), out=await PDFDocument.create();
  a.addPage([300,400]); b.addPage([200,600]);
  const bytesA=await a.save(), bytesB=await b.save();
  assert.equal(await appendPDF(PDFDocument,out,bytesB,'B.pdf',200),1);
  assert.equal(await appendPDF(PDFDocument,out,bytesA,'A.pdf',199),1);
  const saved=await PDFDocument.load(await out.save());
  assert.deepEqual(saved.getPages().map(p=>[p.getWidth(),p.getHeight()]),[[200,600],[300,400]]);
  const broken=new TextEncoder().encode('%PDF-1.7 broken sample');
  await assert.rejects(appendPDF(PDFDocument,out,broken,'hong.pdf',198),/hong.pdf/);
  await assert.rejects(appendPDF(PDFDocument,out,bytesA,'A.pdf',0),/200 trang/);
  assert.equal(out.getPageCount(),2,'failure must not append a partial document');
  assert.equal((await PDFDocument.load(bytesA)).getPageCount(),1,'source stays unchanged');
  console.log('OK: real PDF order, dimensions, malformed input, page cap and original preservation');
})().catch(e=>{console.error(e);process.exitCode=1;});
