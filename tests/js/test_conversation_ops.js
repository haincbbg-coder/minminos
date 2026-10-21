/* Mẫu chỉ chèn nháp, không bao giờ gửi tin; mã sai giữ nguyên để người trực sửa. */
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');
const requests = [];
const context = {window:{},URLSearchParams,fetch:async (url,opts) => {
  requests.push({url,opts});
  return {ok:true,json:async()=>({ok:true,items:[{code:'chao',text:'Chào {tenKhach}, {tenKhach} cần gì ạ?'}]})};
}};
vm.runInNewContext(fs.readFileSync(path.resolve(__dirname,'../../dashboard/conversation-ops.js'),'utf8'),context);
(async()=>{
  const ops = context.window.JavisConversationOps;
  const field = {value:'/chao',focus(){this.focused=true;}};
  assert.strictEqual(await ops.slash(field,'Lan'),true);
  assert.strictEqual(field.value,'Chào Lan, Lan cần gì ạ?');
  assert.strictEqual(field.focused,true);
  assert.strictEqual(requests.length,1);
  assert.strictEqual(requests[0].url,'/conversation-ops/templates');
  assert.strictEqual(requests[0].opts.method,undefined);
  field.value='/khong_co';
  await assert.rejects(()=>ops.slash(field,'Lan'),/Chưa có mẫu/);
  assert.strictEqual(field.value,'/khong_co');
  field.value='Nội dung tự viết';
  assert.strictEqual(await ops.slash(field,'Lan'),false);
  assert.strictEqual(requests.length,2);
  assert.strictEqual(ops.expand('Chào {tenKhach}','<script>'), 'Chào <script>'); // đi vào .value, không HTML
  console.log('OK: chọn /lệnh chỉ tạo nháp, thay tên, không gọi API gửi, mã sai không gửi.');
})().catch(e=>{console.error(e);process.exitCode=1;});
