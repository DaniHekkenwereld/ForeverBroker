-- V4 plan is selected per character; all sessions are read-only observations.
dofile('addon/ForeverTrader/V4.lua')
local v=ForeverTraderV4
local now=1800000000
-- V4 read-only market queue stays valid for a full gameplay session.
dofile('addon/ForeverTrader/Logic.lua')
local logic=ForeverTraderLogic
local longMonitor='FT3|eu-2-110|'..now..'|'..(now+86400)..';1111:0:0:0:0'
local monitorPlan=logic.plan(longMonitor,now+21600)
assert(monitorPlan and monitorPlan.rows[1].monitor,'24-hour read-only queue must survive 6 hours in WoW')
local unsafePlan='FT3|eu-2-110|'..now..'|'..(now+86400)..';1111:100:1:200:0'
assert(not logic.plan(unsafePlan,now),'24-hour actionable buy plan must be rejected')
local oldMonitor='FT3|eu-2-110|'..now..'|'..(now+1800)..';1111:0:0:0:0'
local oldPlan=logic.plan(oldMonitor,now+21600)
assert(oldPlan and oldPlan.expires==now+86400,'legacy 30-min monitor queue should be searchable after 6 hours')
local expiredBuy='FT3|eu-2-110|'..now..'|'..(now+1800)..';1111:100:1:200:0'
assert(not logic.plan(expiredBuy,now+21600),'expired actionable buy plan must remain invalid')
assert(not logic.plan(oldMonitor,now+86400),'queue must eventually expire after 24 hours')

local p1='FT3|eu-2-110|1800000000|1800003600;1111:0:0:0:0'
local p2='FT3|eu-2-110|1800000000|1800003600;2222:0:0:0:0'
local db={v4PlanBlob='FT4!Forever#Mage?'..p1..'!Forever#Warrior?'..p2,
          v4ActionsBlob='FT4!Forever#Mage?VERIFY_BUY:1111:1!Forever#Warrior?REVIEW_SELL:2222:2'}
local logic={plan=function(raw,at)
    if type(raw)~='string' or not raw:match('^FT3') then return nil end
    return {raw=raw}
end}
local mage,ok=v.plan(db,now,'Forever','Mage',logic)
assert(ok and mage.raw==p1,'mage must get mage-only plan')
local warrior,ok2=v.plan(db,now,'Forever','Warrior',logic)
assert(ok2 and warrior.raw==p2,'warrior must get warrior-only plan')
local seen={}
assert(v.actions(db,'Forever','Mage',function(kind,id,qty)seen[#seen+1]={kind,id,qty} end)==1)
assert(seen[1][1]=='VERIFY_BUY' and seen[1][2]==1111)
assert(v.actions(db,'Forever','Warrior',function(kind,id)seen[#seen+1]={kind,id} end)==1)
v.login(db,now,'Forever','Mage',100000,{[2589]=20})
assert(db.v4ActiveSession)
v.logout(db,now+3600,130000,{[2589]=10,[1111]=1})
assert(db.sessionsWire:find('FTSESSION1;',1,true),'must export session on logout')
assert(db.sessionsWire:find('|eu-2-110|Mage|',1,true),'sessions use canonical market, never raw realm')
assert(db.sessionsWire:find('100000|130000|2589:20|1111:1,2589:10',1,true),
       'session must capture observed wallet and bag differences')
db.v4Sessions.orphan={id='orphan',realm='',character='',started=now,ended=now+1}
local previous=db.sessionsWire
v.logout(db,now+3601,120000,{})
assert(db.sessionsWire==previous,'second logout must not double-create session')
assert(not db.sessionsWire:find('orphan',1,true),'orphaned legacy session must be excluded')
print('V4 addon unit tests PASS')
