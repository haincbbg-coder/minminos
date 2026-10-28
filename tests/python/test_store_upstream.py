"""Only valid owner/repo names may become source links in the Store."""
from _paths import ROOT, SERVER
import packs_store as store

good=store._lam_sach({'id':'demo','upstream':{'repo':'remotion-dev/skills','ref':'main','commit':'a'*40,'synced':'2026-10-28'}})
assert good['upstream']['repo']=='remotion-dev/skills'
for bad in ['https://evil.test/repo','a/../../b','javascript:alert(1)','a/b?token=secret','<script>/x']:
    assert store._lam_sach({'upstream':{'repo':bad}})['upstream']=={}
safe=store._upstream({'repo':'a/b','commit':'not-a-sha','synced':'bad','ref':'<script>'})
assert safe['commit']=='' and safe['synced']=='' and safe['ref']==''
assert store._lam_sach({'name':'Legacy pack'})['upstream']=={}
print('PASS: validated source links, invalid metadata omitted, legacy pack compatible')
