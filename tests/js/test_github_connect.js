// GitHub UI helpers and MinMin integration contract.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root=path.resolve(__dirname,'../..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const gh=require(path.join(root,'dashboard/github-connect.js'));
assert.equal(gh.chipText(['acme/app','acme/lib'],20),'app +1');
assert.equal(gh.chipText([],20),'');
assert.deepEqual(gh.toggle(['a/b'],'a/b'),[]);
assert.deepEqual(gh.toggle(['a/b'],'c/d'),['a/b','c/d']);
assert.ok(gh.sameSet(['a','b'],['b','a']));
assert.equal(gh.iconSpec({}),null);
assert.equal(gh.iconSpec({state:'working',running:3}).count,3);
assert.ok(gh.iconSpec({state:'merged',merged_warning:true}).cls.includes('gh-warn'));
for(const lang of ['vi','en']){
  const d=JSON.parse(read('dashboard/i18n/'+lang+'.json'));
  for(const state of ['working','ready','merged','broken'])assert.ok(d[gh.iconSpec({state}).key]);
}
const html=read('dashboard/index.html'), app=read('dashboard/app.js'), conn=read('dashboard/console.js'), sess=read('dashboard/sessions-ui.js');
assert.ok(html.indexOf('/static/github-minmin.js')<html.indexOf('/static/github-connect.js'));
assert.ok(conn.includes('JavisGithubRepos.mount(document.getElementById("mcpGithub"))'));
assert.ok(app.includes('await window.JavisGithubRepos.claimPending(sid)'));
assert.ok(sess.includes('item.setAttribute("data-sid", s.id)'));
assert.ok(sess.includes('JavisGithubRepos.decorate(listEl)'));
const js=read('dashboard/github-connect.js');
assert.ok(js.includes('held = list; heldBrain = chatBrain(); heldBase = bases;'));
assert.ok(js.includes('throw new Error((d && d.error)'));
assert.ok(!/token\s*:\s*st\./.test(js));
console.log('PASS: repo chip, selection, CI indicators, translated labels, native mounts and failed-attachment guard');
