dofile('addon/ForeverTrader/Logic.lua')
local L=ForeverTraderLogic
local t=1800000000
local p=assert(L.plan('FT3|eu-2-110|'..t..'|'..(t+5400)..';2589:100:20:150:0;10620:100:20:200:6',t))
assert(#p.rows==2)
local monitor=assert(L.plan(' FT3||eu-2-110||'..t..'||'..(t+5400)..';2589:0:0:0:0\n',t))
assert(#monitor.rows==1 and monitor.rows[1].monitor)
local mb,ms=L.matches(monitor,{[2589]={floor=1,at=t,stacks={{qty=20,cost=20}}}},{[2589]=20},500000,150000,t,t,{},true)
assert(#mb==0 and #ms==0)
assert(not L.plan('FT3|eu-2-110|'..t..'|'..(t+1)..';2589:100:20:150:0',t+2))
assert(not L.plan('FT3|eu-2-110|'..t..'|'..(t+1)..';2589:100:20:150:0;2589:100:20:150:0',t))
assert(not L.plan('FT3|eu-2-111|'..t..'|'..(t+5400)..';2589:100:20:150:0',t))
local s={active=true,market=true,mailOpen=false,ahOpen=true,mailKnown=true,ready=0,attachments=0,threshold=20000,cash=500000,reserve=150000,lastMail=t,scanAt=t,buyCount=0,sellCount=0,planValid=true}
local function expect(code,at) assert(L.next(s,at or t)==code,L.next(s,at or t)) end
expect('WAIT');s.buyCount=1;expect('BUY');s.bought=true;expect('MAIL');s.mailOpen=true;s.mailKnown=false;expect('MAIL_WAIT');s.mailKnown=true;s.attachments=1;expect('COLLECT');s.attachments=0;s.bought=false;expect('RETURN');s.mailOpen=false;s.ahOpen=false;expect('AH');s.ahOpen=true;s.sellCount=1;expect('SELL');expect('SCAN',t+900);expect('MAIL_CHECK',t+1800);s.sellCount=0;s.buyCount=0;s.planValid=false;expect('PLAN');s.market=false;expect('MARKET');s.active=false;expect('OFF')
local b={ [2589]={floor=90,stacks={{qty=5,cost=450},{qty=5,cost=550}}},[10620]={floor=200,stacks={{qty=5,cost=1000}}}}
local buy,sell=L.matches(p,b,{},500000,150000,t,t,{});assert(#buy==1 and buy[1].qty==5 and buy[1].cost==450)
assert(#L.matches(p,b,{},150000,150000,t,t,{})==0)
assert(#L.matches(p,b,{},500000,150000,t+900,t,{})==0)
assert(#L.matches(p,b,{},500000,150000,t,t,{[2589]=5})==0)
b[2589].floor=160;buy,sell=L.matches(p,b,{[2589]=10,[10620]=20},500000,150000,t,t,{});assert(#buy==0 and #sell==1 and sell[1].id==2589)
local live={live=true,market=true,ahOpen=true,walletKnown=true,liveSpent=0,cash=400000}
assert(L.liveAllowed(live,{cost=10000},{at=t},t))
assert(not L.liveAllowed(live,{cost=10001},{at=t},t))
assert(not L.liveAllowed(live,{cost=10000},{at=t-60},t))
live.liveSpent=49001
assert(not L.liveAllowed(live,{cost=10000},{at=t},t))
live.liveSpent=0;live.cash=150001
assert(not L.liveAllowed(live,{cost=10000},{at=t},t))
print('Lua coach: live test budget/price checks OK')
