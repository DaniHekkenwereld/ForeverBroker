-- Minimal read-only WoW API mocks. This validates the addon event wiring, not the real client.
local clock=1800000000;local events={};local frames={};local prints={}
function GetServerTime() return clock end
function GetMoney() return 500000 end
function UnitFactionGroup() return 'Alliance' end
function GetCurrentRegion() return 3 end
function HasNewMail() return false end
function GetItemInfo(i) return 'Linen' end
UIParent={};SlashCmdList={};SOUNDKIT={RAID_WARNING=1};function PlaySound() end
local function noop() end
local function widget()
 local self={scripts={}}
 return setmetatable(self,{__index=function(t,k)
  if k=='SetScript' then return function(_,event,fn)t.scripts[event]=fn end end
  if k=='RegisterEvent' then return function(_,e)events[e]=t end end
  if k=='CreateFontString' then return function()return widget() end end
  if k=='SetText' then return function(_,v)t.value=v end end
  if k=='GetText' then return function()return t.value end end
  return noop
 end})
end
function CreateFrame(...) local a=widget();frames[#frames+1]=a;return a end
C_Container={GetContainerNumSlots=function()return 1 end,GetContainerItemInfo=function()return nil end}
C_AuctionHouse={GetNumReplicateItems=function()return 1 end,GetReplicateItemInfo=function()return 'Linen',1,5,1,true,1,'',0,0,500,0,nil,nil,nil,nil,0,2589,true end,HasFullOwnedAuctionResults=function()return true end,GetOwnedAuctions=function()return {} end}
local mail={{'seller_temp_invoice',0,100000,2000,5000,97000,0,0},{'seller',0,0,0,0,0,40000,0},{'buyer',0,0,0,0,0,0,1}}
function GetInboxNumItems()return #mail,#mail end
function GetInboxInvoiceInfo(i)local a=mail[i];return a[1],'Linen',nil,a[2],a[3],a[4],a[5],a[6] end
function GetInboxHeaderInfo(i)local a=mail[i];return nil,nil,nil,nil,a[7],0,30,a[8] end
local realprint=print;print=function(x) prints[#prints+1]=x end
local function fire(e) assert(events[e],e);events[e].scripts.OnEvent(events[e],e) end
dofile('addon/ForeverTrader/Logic.lua');dofile('addon/ForeverTrader/Target.lua');dofile('addon/ForeverTrader/ForeverTrader.lua');fire('PLAYER_LOGIN');SlashCmdList.FOREVERTRADER('market');SlashCmdList.FOREVERTRADER('start');fire('MAIL_SHOW');fire('MAIL_INBOX_UPDATE')
assert(ForeverTraderDB.mail3==clock..'|97000|40000|1|0|0',ForeverTraderDB.mail3)
assert(ForeverTraderDB.coach:match('|COLLECT|'));mail={};fire('MAIL_INBOX_UPDATE');assert(ForeverTraderDB.coach:match('|RETURN|'));fire('MAIL_CLOSED');fire('AUCTION_HOUSE_SHOW');assert(ForeverTraderDB.coach:match('|PLAN|'));fire('REPLICATE_ITEM_LIST_UPDATE');assert(ForeverTraderDB.scan:match('2589:5:500'));assert(ForeverTraderDB.coach:match('|PLAN|'));fire('ITEM_PURCHASED');assert(ForeverTraderDB.coach:match('|MAIL|'));for _,v in ipairs(prints)do assert(not v:match('Fout:'),v)end
realprint('Lua client mock: mailbox invoice, events, scan and purchase transition OK')
