#!/usr/bin/env python3
"""Abyss Depths release combat bot.
Runs before every release: boots the game headless, plays every class through the outdoor zones
against real monster packs, checks the floor-boss intro and Azmot's phases, and fails the release
on any JS error, a hero death in an early zone, or a broken system.
usage: python3 tools/release_bot.py [--port 8765] [--quick]
"""
import sys,os,json,asyncio,subprocess,time,socket
from playwright.async_api import async_playwright
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT=int(sys.argv[sys.argv.index('--port')+1]) if '--port' in sys.argv else 8765
QUICK='--quick' in sys.argv
ZONES=[(0,4),(1,8),(2,12)] if QUICK else [(0,4),(1,8),(2,12),(3,16),(4,20)]
CLASSES=sys.argv[sys.argv.index('--cls')+1].split(',') if '--cls' in sys.argv else ['warrior','sorc','rogue','necro','paladin']
def up():
    try: socket.create_connection(('localhost',PORT),1).close(); return None
    except OSError: return subprocess.Popen([sys.executable,'-m','http.server',str(PORT)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
async def newgame(pg,cls):
    await pg.evaluate("(()=>{localStorage.clear();localStorage.setItem('abyss.intro','1')})()")
    await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_selector('#tnew',timeout=120000)
    await pg.evaluate("document.getElementById('tnew').click()"); await pg.wait_for_timeout(500)
    await pg.evaluate(f"document.querySelector('.cc[data-c={cls}]').click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("document.getElementById('tgo').click()"); await pg.wait_for_timeout(800)
    await pg.evaluate("(()=>{const b=document.querySelector('#dbt button');if(b&&document.getElementById('dlg').style.display==='flex')b.click();__dbg.P.tutDone=1;window.__notravel=1;})()")
async def main():
    srv=up(); errs=[]; res=[]; fails=[]; warns=[]; deaths={}
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--autoplay-policy=no-user-gesture-required'])
        pg=await (await b.new_context(viewport={'width':1280,'height':720})).new_page()
        pg.on('pageerror',lambda e:errs.append(str(e)))
        await pg.goto(f'http://localhost:{PORT}/index.html'); await pg.wait_for_selector('#tnew',timeout=120000)
        for cls in CLASSES:
            await newgame(pg,cls)
            for zi,lv in ZONES:
                await pg.evaluate(f"(()=>{{__dbg.P.level={lv};__dbg.enterZone({zi},'west');}})()"); await pg.wait_for_timeout(250)
                r=await pg.evaluate(f"""(()=>{{const D=__dbg,P=D.P,RT=D.RT,L=D.L,X=__x,C=D.P.cls;const lv={lv};
 // build a 'normal' hero for this level: stats into main attr + vit, magic gear, skill ranks
 P.level=lv;const c={{warrior:'str',sorc:'ene',rogue:'dex',necro:'ene',paladin:'str'}}[C];P[c]+= (lv-1)*3;P.vit+=(lv-1)*2;
 const sk=Object.keys(P.skills).length?null:null;const ids={{warrior:['bash','whirl','leap','cry'],sorc:['fireball','nova','chain','tele'],rogue:['multi','frost','rain','roll'],necro:['raise','bonespear','corpseboom','curse'],paladin:['zeal','hammer','aura','charge']}}[C];
 const req=[1,3,6,10];let pts=lv-1+1;P.skills={{}};ids.forEach((id,i)=>{{if(lv>=req[i])P.skills[id]=1;}});pts-=Object.keys(P.skills).length;
 while(pts>0){{for(const id of [ids[1],ids[0],ids[2]]){{if(pts>0&&P.skills[id]){{P.skills[id]++;pts--;}}}}}}
 for(const s of ['weapon','off','helm','armor','gloves','belt','boots','ring','amulet']){{let it=null;for(let g=0;g<40&&(!it||it.slot!==s);g++)it=D.genItem(lv,1,s,C);P.eq[s]=it;}}
 D.updateGear();D.recalc();P.hp=D.S.maxhp;P.mp=D.S.maxmp;P.hpPot=4;P.mpPot=3;
 X.ALLIES.slice().forEach(a=>{{a.hp=0;}});
 D.pause(false);L.mons.filter(m=>!m.d.prop).forEach(m=>L.group.remove(m.mesh));L.mons.length=0;L.spawns.forEach(s=>s.dead=true);
 const ros=L.roster;let n=0;for(let k=0;k<3;k++){{const an=k*2.1,x=RT.x+Math.sin(an)*10,z=RT.z+Math.cos(an)*10;const t=ros[k%ros.length];for(let j=0;j<4;j++){{const m=D.spawnMon(t,x+j*.7,z+(j%2),j===0&&k===1?1:0,{{awake:true}});n++;}}}}
 const mons=L.mons.filter(m=>!m.d.prop);const types=[...new Set(mons.map(m=>m.type))].join('/');
 let t=0,minHp=1,taken=0,pots=0,last=P.hp,dead=false,mlvl=L.mlvl,firstHit=null;
 for(;t<75;t+=.05){{const alive=L.mons.filter(m=>!m.d.prop&&m.hp>0);if(!alive.length)break;
   let best=null,bd=1e9;for(const m of alive){{const q=Math.hypot(m.x-RT.x,m.z-RT.z);if(q<bd){{bd=q;best=m;}}}}RT.target=best;
   // skills: cast whatever is off cooldown in priority, aimed at nearest
   if(Math.floor(t*20)%6===0){{RT.target=best;for(const i of [3,2,1,0]){{const id=ids[i];if(!P.skills[id]||(RT.cds[id]||0)>0)continue;if((id==='tele'||id==='roll'||id==='leap'||id==='charge')&&bd>4)continue;if((id==='cry'||id==='aura'||id==='curse')&&bd>6)continue;if(id==='raise'&&X.ALLIES.filter(a=>a.kind==='skel').length>=2+Math.floor(P.skills.raise/3))continue;X.castSkill(i);break;}}}}
   if(P.hp<D.S.maxhp*.35&&P.hpPot>0&&!(RT.hot>0)){{P.hpPot--;P.hp=Math.min(D.S.maxhp,P.hp+D.S.maxhp*.2);RT.hot=2.5;RT.hotV=D.S.maxhp*.35/2.5;pots++;}}
   if(P.mp<10&&P.mpPot>0){{P.mpPot--;P.mp=Math.min(D.S.maxmp,P.mp+D.S.maxmp*.5);}}
   const r=D.sim(.05);if(P.hp<last){{taken+=last-P.hp;if(firstHit==null)firstHit=t;}}last=P.hp;minHp=Math.min(minHp,P.hp/D.S.maxhp);if(r!=='alive'){{dead=true;break;}}}}
 const lm=L.mons.filter(m=>!m.d.prop&&m.hp>0);const left=lm.length;const why=lm.slice(0,3).map(m=>m.type+':d'+Math.round(Math.hypot(m.x-RT.x,m.z-RT.z))+(m.fleeT>0?':flee':'')+(m.escape?':esc':'')+(m.awake?'':':sleep')+(D.los?'':'')+':hp'+Math.round(m.hp/m.maxhp*100)).join(' ');
 return {{why,cls:C,zone:{zi},lv,mlvl,types,n,t:+t.toFixed(1),left,dead,minHp:+minHp.toFixed(2),taken:Math.round(taken),maxhp:Math.round(D.S.maxhp),pots,dps:Math.round((D.S.dmin+D.S.dmax)/2),armor:Math.round(D.S.armor)}};}})()""")
                if r['dead']:
                    await pg.evaluate("(()=>{const D=__dbg;D.P.hp=D.S.maxhp;document.getElementById('dead').style.display='none';})()")
                    deaths[cls]=deaths.get(cls,0)+1; warns.append(f"{cls} died in zone {zi} (lv {lv})")
                    if zi==0: fails.append(f"{cls} died in the first zone (lv {lv})")
                res.append(r); print(f"  {cls:8} zone {zi} lv{lv:<3} {'DEAD' if r['dead'] else 'ok  '} t={r['t']:>5}s left={r['left']} minHp={r['minHp']} pots={r['pots']}",flush=True)
        # systems: floor boss intro + Azmot phases
        await newgame(pg,'warrior')
        s=await pg.evaluate("""(()=>{const D=__dbg,M=__m,out={};D.P.level=10;D.enterDungeon(2);const b=D.L.mons.find(m=>m.d.fboss);out.fboss=!!b;
          if(b){D.RT.x=b.x+3;D.RT.z=b.z+3;D.hitMon(b,{d:1});out.intro=!!M.BI;}
          D.P.level=40;D.enterDungeon(9);const l=D.L.mons.find(m=>m.type==='lord');out.lord=!!l;if(l){D.RT.x=l.x+4;D.RT.z=l.z+4;l.awake=true;l.hp=l.maxhp*.45;D.sim(3,()=>{D.P.hp=1e6;});out.ph1=l.ph===1&&l.hoverT>0;l.hp=l.maxhp*.15;D.sim(3,()=>{D.P.hp=1e6;});out.ph2=l.ph===2;}
          const it=M.legItem(30,'warrior');out.legend=!!it.leg;return out;})()""")
        print('  systems',json.dumps(s))
        for k,v in s.items():
            if not v: fails.append('system check failed: '+k)
        await b.close()
    if srv: srv.terminate()
    for c,n in deaths.items():
        if n>=2: fails.append(f'{c} died in {n} zones — balance regression')
    for e in errs: fails.append('JS error: '+e[:200])
    if warns: print('warnings:\n - '+'\n - '.join(warns))
    json.dump({'results':res,'fails':fails,'warnings':warns},open(os.path.join(ROOT,'tools','last_bot.json'),'w'),ensure_ascii=False,indent=1)
    print('\nRESULT:',('FAIL\n - '+'\n - '.join(fails)) if fails else 'PASS')
    sys.exit(1 if fails else 0)
asyncio.run(main())
