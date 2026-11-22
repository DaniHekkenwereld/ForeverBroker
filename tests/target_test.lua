dofile('addon/ForeverTrader/Logic.lua');dofile('addon/ForeverTrader/Target.lua')
local T,L=ForeverTraderTarget,ForeverTraderLogic
local t=1800000000
local key={itemID=2589}
local a={HasFullItemSearchResults=function()return true end,GetNumItemSearchResults=function()return 3 end,GetItemSearchResultInfo=function(k,i)return ({
{quantity=5,buyoutAmount=501,containsOwnerItem=false,containsAccountItem=false,auctionID=1},
{quantity=2,buyoutAmount=180,containsOwnerItem=false,containsAccountItem=false,auctionID=2},
{quantity=10,buyoutAmount=10,containsOwnerItem=true,containsAccountItem=true,auctionID=3}})[i] end}
local id,b=T.read(a,'item',key,t);assert(id==2589 and b.floor==90 and #b.stacks==2)
assert(T.record(id,b):match('2:180:1'))
local p=assert(L.plan('FT3|eu-2-110|'..t..'|'..(t+5400)..';2589:100:20:150:0',t))
local buys=L.matches(p,{[id]=b},{},500000,150000,t,nil,{},true);assert(#buys==1 and buys[1].qty==2)
assert(#L.matches(p,{[id]=b},{},500000,150000,t+120,nil,{},true)==0)
a.HasFullItemSearchResults=function()return false end;assert(not T.read(a,'item',key,t))
a.HasFullItemSearchResults=function()return true end;a.GetNumItemSearchResults=function()return 0 end;id,b=T.read(a,'item',key,t);assert(id==2589 and not b.floor and #b.stacks==0)
assert(T.record(id,b):match('|0|$'))
a.HasFullCommoditySearchResults=function()return true end;a.GetNumCommoditySearchResults=function()return 1 end;a.GetCommoditySearchResultInfo=function()return {quantity=200,unitPrice=80,containsOwnerItem=false,containsAccountItem=false} end
id,b=T.read(a,'commodity',2589,t);buys=L.matches(p,{[id]=b},{},500000,150000,t,nil,{},true);assert(buys[1].qty==20 and buys[1].cost==1600)
assert(T.choose(p,{}, {},{},t,{}).id==2589);assert(not T.choose(p,{[2589]=b},{},{},t,{}));assert(T.choose(p,{[2589]=b},{},{},t+120,{}).id==2589)
print('Lua targeted: stack totals, unit prices, own auction exclusion, empty, partial, expiry, selection PASS')

local t=1800000000;local mp={expires=t+1000,rows={{id=2589,max=0,qty=0,target=0,hold=0,monitor=true}}};local r=ForeverTraderTarget.choose(mp,{}, {},{},t,{})
assert(r and r.id==2589)
