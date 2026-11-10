#!/usr/bin/env python3
"""hardening.py — исполнитель tasks.json. Dry-run по умолчанию.
  probe                      проба токена (закон 11): GET /user -> 200 + срок
  plan [--wave W2]           что будет сделано (ничего не меняет)
  apply T-xxx [--yes]        выполнить одну задачу (без --yes печатает запрос)
  verify [--wave W1]         проверить задачи живым GET
Токен — только из env GH_TOKEN, нигде не печатается и не пишется на диск.
Правила: только репо rtynbirf; задачи owner_decision требуют --owner-ok; без force-push."""
import json,os,sys,base64,re,urllib.request,urllib.error
D=os.path.dirname(os.path.abspath(__file__))+'/..'
OWNER='rtynbirf'
def api(method,path,body=None):
    tok=os.environ.get('GH_TOKEN') or sys.exit('нет GH_TOKEN в env')
    d=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request('https://api.github.com'+path,method=method,data=d,headers={'Authorization':'Bearer '+tok,'Accept':'application/vnd.github+json','Content-Type':'application/json'})
    try:
        x=urllib.request.urlopen(r,timeout=30); b=x.read(); return x.status,(json.loads(b) if b else {}),x.headers
    except urllib.error.HTTPError as e:
        try: b=json.loads(e.read())
        except Exception: b={}
        return e.code,b,e.headers
def load(): return json.load(open(D+'/tasks.json'))['tasks']
def dig(o,k):
    for p in k.split('.'):
        o=o.get(p) if isinstance(o,dict) else None
    return o
def probe():
    s,u,h=api('GET','/user'); exp=h.get('github-authentication-token-expiration')
    print('GET /user ->',s,'login=',u.get('login'),'expires=',exp)
    if s!=200 or u.get('login')!=OWNER: sys.exit('проба провалена: честный ноль')
def guard_immutable(repo):
    s,fl,_=api('GET',f'/repos/{OWNER}/{repo}/contents/.github/workflows')
    bad=[]
    for f in (fl if isinstance(fl,list) else []):
        s2,c,_=api('GET',f['url'].replace('https://api.github.com',''))
        t=base64.b64decode(c.get('content','')).decode('utf8','ignore')
        if re.search(r'--clobber|release upload|release edit',t): bad.append(f['name'])
    return bad
def show(t): print(t['id'],t['wave'],t['repo'],'|',t['title'],'|',t['status'],'OWNER' if t.get('owner_decision') else '')
def apply(t,yes,owner_ok):
    if t['kind'] not in('api','put_file'): sys.exit('задача не машинная: '+t['kind'])
    if t.get('owner_decision') and not owner_ok: sys.exit('нужно решение хозяина: добавь --owner-ok')
    if t['kind']=='api' and not t['apply']['path'].startswith('/repos/'+OWNER+'/'): sys.exit('чужой путь')
    if t.get('guard')=='immutable_releases':
        bad=guard_immutable(t['repo'])
        if bad: sys.exit('GUARD: workflow правят релиз после публикации: '+', '.join(bad))
    a=t['apply']
    if t['kind']=='put_file':
        tp=open(D+'/'+a['template']).read()
        if '{{' in tp: sys.exit('шаблон не заполнен: подставь {{…}} (см. fill)')
        path=f"/repos/{OWNER}/{t['repo']}/contents/{a['path']}"
        s,ex,_=api('GET',path)
        if s==200: print('уже есть, пропуск'); return
        method,body='PUT',{'message':a['message'],'content':base64.b64encode(tp.encode()).decode()}
    else:
        method,path,body=a['method'],a['path'],a.get('body')
        if a.get('fill') and not (body and body.get('names')): sys.exit('сначала заполни: '+a['fill'])
    print(method,path,json.dumps(body,ensure_ascii=False)[:200] if body else '')
    if not yes: print('(dry-run; добавь --yes)'); return
    s,r,_=api(method,path,body); print('->',s,'' if s<300 else r.get('message'))
def verify(t):
    v=t.get('verify')
    if not v: return None
    s,r,_=api('GET',v['path'])
    if 'expect_status' in v: return s==v['expect_status']
    if 'expect_nonempty' in v: return bool(dig(r,v['key']))
    return dig(r,v['key'])==v['expect']
if __name__=='__main__':
    a=sys.argv[1:]; cmd=a[0] if a else 'plan'; wave=a[a.index('--wave')+1] if '--wave' in a else None
    ts=[t for t in load() if not wave or t['wave']==wave]
    if cmd=='probe': probe()
    elif cmd=='plan': [show(t) for t in ts if t['status']=='open']
    elif cmd=='apply':
        probe(); t=next(x for x in load() if x['id']==a[1]); apply(t,'--yes' in a,'--owner-ok' in a)
    elif cmd=='verify':
        probe()
        for t in ts:
            if t['kind'] in('api','put_file'): print(t['id'],t['repo'],t['title'][:50],'->','OK' if verify(t) else 'НЕТ')
