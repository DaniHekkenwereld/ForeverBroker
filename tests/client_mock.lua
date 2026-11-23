-- Minimal Lua integration mock for addon states and read-only AH auto searching.
local clock=1800000000
local events,frames,prints,textures={},{},{},{}
function GetServerTime() return clock end
local currentMoney=500000
function GetMoney() return currentMoney end
function UnitFactionGroup() return 'Alliance' end
function GetCurrentRegion() return 3 end
function GetRealmName() return 'Forever' end
function UnitName() return 'Mage','Pump' end
function GetUnitName() return 'Mage Pump' end
function UnitFullName() return 'Mage','Pump' end
function UnitGUID() return 'Player-1-MagePump' end
function HasNewMail() return false end
function GetItemInfo(i) return 'Item '..tostring(i) end
UIParent={}; SlashCmdList={}
SOUNDKIT={RAID_WARNING=1};function PlaySound() end
local function noop() end
local function widget()
    local self={scripts={}}
    return setmetatable(self,{__index=function(t,k)
        if k=='SetScript' then return function(_,event,fn)t.scripts[event]=fn end end
        if k=='RegisterEvent' then return function(_,event)events[event]=t end end
        if k=='CreateFontString' then return function()return widget() end end
        if k=='CreateTexture' then return function()local a=widget();textures[#textures+1]=a;return a end end
        if k=='SetColorTexture' then return function(_,r,g,b,a)t.color={r,g,b,a} end end
        if k=='SetText' then return function(_,v)t.value=v end end
        if k=='GetText' then return function()return t.value end end
        return noop
    end})
end
function CreateFrame(...) local frame=widget();frames[#frames+1]=frame;return frame end
Auctionator={
    EventBus={Register=function(self,listener,registered)self.listener=listener;self.event=registered[1] end},
    IncrementalScan={Events={ScanComplete='incremental_scan_complete'}}
}
C_Container={GetContainerNumSlots=function()return 1 end,
             GetContainerItemInfo=function()return nil end}
C_AuctionHouse={
    MakeItemKey=function(id)return {itemID=id} end,
    IsThrottledMessageSystemReady=function()return true end,
    SendSearchQuery=function(key) C_AuctionHouse.lastSearched=key.itemID;C_AuctionHouse.searchCount=(C_AuctionHouse.searchCount or 0)+1 end,
    GetNumReplicateItems=function()return 1 end,
    GetReplicateItemInfo=function()return 'Linen',1,5,1,true,1,'',0,0,500,0,nil,nil,nil,nil,0,2589,true end,
    HasFullOwnedAuctionResults=function()return true end,
    GetOwnedAuctions=function()return {} end,
    HasFullItemSearchResults=function()return true end,
    GetNumItemSearchResults=function()return 1 end,
    GetItemSearchResultInfo=function(key,i)return {quantity=5,containsOwnerItem=false,containsAccountItem=false,buyoutAmount=500,auctionID=77} end,
}
local mail={{'seller_temp_invoice',0,100000,2000,5000,97000,0,0},
            {'seller',0,0,0,0,0,40000,0},
            {'buyer',0,0,0,0,0,0,1}}
function GetInboxNumItems()return #mail,#mail end
function GetInboxInvoiceInfo(i)local a=mail[i];return a[1],'Linen',nil,a[2],a[3],a[4],a[5],a[6] end
function GetInboxHeaderInfo(i)local a=mail[i];return nil,nil,nil,nil,a[7],0,30,a[8] end
local realprint=print
print=function(x)prints[#prints+1]=x end
local function fire(event,...)
    assert(events[event],event)
    events[event].scripts.OnEvent(events[event],event,...)
end

dofile('addon/ForeverTrader/Logic.lua')
dofile('addon/ForeverTrader/Target.lua')
dofile('addon/ForeverTrader/V4.lua')
dofile('addon/ForeverTrader/ForeverTrader.lua')
fire('PLAYER_LOGIN')
assert(type(ForeverTraderDB.characters)=='table','account-wide snapshot must exist')
assert(ForeverTraderDB.characters['eu-2-110#Mage Pump'].gold==500000,'gold captured on login')
assert(ForeverTraderDB.charactersWire:find('eu-2-110|Mage Pump|Alliance|500000',1,true),'bounded export should include mage')
local firstRow=ForeverTraderDB.charactersWire:match('^FTCHAR1;([^;]+)')
assert(firstRow and select(2,firstRow:gsub('|',''))==13,'character export must have exactly 14 columns')
SlashCmdList.FOREVERTRADER('market')
SlashCmdList.FOREVERTRADER('start')
fire('MAIL_SHOW');fire('MAIL_INBOX_UPDATE')
assert(ForeverTraderDB.mail3==clock..'|97000|40000|1|0|0',ForeverTraderDB.mail3)
assert(ForeverTraderDB.coach:match('|COLLECT|'))
assert(textures[1] and textures[1].color[1]==1,'MAIL voice marker should turn pink')
mail={};fire('MAIL_INBOX_UPDATE')
assert(ForeverTraderDB.coach:match('|RETURN|'))
assert(math.abs(textures[1].color[2]-.85)<.01,'AH voice marker should turn green')
fire('MAIL_CLOSED')
fire('AUCTION_HOUSE_SHOW')
assert(ForeverTraderDB.coach:match('|PLAN|'))
fire('REPLICATE_ITEM_LIST_UPDATE')
assert(ForeverTraderDB.scan:match('2589:5:500'))
assert(Auctionator.EventBus.event=='incremental_scan_complete')
Auctionator.EventBus.listener.ReceiveEvent(nil,'incremental_scan_complete',{
 {itemKey={itemID=2589,itemLevel=0,itemSuffix=0},minPrice=125,totalQuantity=90},
 {itemKey={itemID=2572,itemSuffix=2},minPrice=50,totalQuantity=10},
 {itemKey={itemID=2592},minPrice=200,totalQuantity=50},
})
assert(ForeverTraderDB.browseSummary==clock..';2589:125:90;2592:200:50',ForeverTraderDB.browseSummary)

-- Explicit search is always read-only, even without an imported plan.
SlashCmdList.FOREVERTRADER('search 2589')
assert(C_AuctionHouse.lastSearched==2589)
-- Missing server plan must explain why auto remains idle; no false success.
SlashCmdList.FOREVERTRADER('auto on')
assert(prints[#prints]:find('Geen geldige V4%-zoeklijst geladen'), 'auto must explain missing plan')
SlashCmdList.FOREVERTRADER('auto off')
-- Reconnect after the old search timeout with a valid desktop trading plan.
clock=clock+40
ForeverTraderDB.planText='FT3|eu-2-110|'..clock..'|'..(clock+900)..';2589:140:10:200:0'
fire('PLAYER_LOGIN')
SlashCmdList.FOREVERTRADER('start')
fire('AUCTION_HOUSE_SHOW')
local before=C_AuctionHouse.searchCount or 0
SlashCmdList.FOREVERTRADER('auto on')
assert(C_AuctionHouse.searchCount==before+1,'auto on should immediately start a search at open AH')
SlashCmdList.FOREVERTRADER('auto status')
assert(prints[#prints]:find('Wachten op AH-resultaten',1,true),'auto status must report pending results')
clock=clock+6
frames[1].scripts.OnUpdate(frames[1],5)
assert(C_AuctionHouse.searchCount==before+1,'pending search must not start a duplicate')
fire('ITEM_SEARCH_RESULTS_UPDATED',{itemID=2589})
local after=C_AuctionHouse.searchCount
clock=clock+6
frames[1].scripts.OnUpdate(frames[1],5)
assert(C_AuctionHouse.searchCount==after,'auto queue must pause when a buy signal is actionable')
SlashCmdList.FOREVERTRADER('auto off')
assert(not (C_AuctionHouse.searchCount>after),'auto off no more searches')
SlashCmdList.FOREVERTRADER('live on')
assert(ForeverTraderDB.wallet:match('|Alliance|3$'))
fire('ITEM_PURCHASED');assert(ForeverTraderDB.coach:match('|MAIL|'))
local beforeLogoutWallet=ForeverTraderDB.wallet
currentMoney=0
fire('PLAYER_LOGOUT')
assert(ForeverTraderDB.wallet==beforeLogoutWallet,'logout must not overwrite wallet with 0g')
assert(ForeverTraderDB.sessionsWire:match('^FTSESSION1;'),'logout should persist V4 session')
-- Forever realm APIs are deliberately blanked; unrelated functions may
-- return arbitrary values. No in-game configuration should be required.
clock=clock+30
GetRealmName=function() return '' end
GetNormalizedRealmName=function() return '' end
GetCVar=function() return 'Pump' end
UnitName=function() return 'Rogue','Pump' end
GetUnitName=function() return 'Rogue Pump' end
UnitFullName=function() return 'Rogue','Pump' end
UnitGUID=function() return 'Player-2-RoguePump' end
fire('PLAYER_LOGIN')
assert(ForeverTraderDB.characters['eu-2-110#Rogue Pump'],'full-name character should load without realm APIs')
assert(ForeverTraderDB.v4ActiveSession,'automatic session should start without realm APIs')
SlashCmdList.FOREVERTRADER('identity')
assert(ForeverTraderDB.charactersWire:find('eu-2-110|Rogue Pump|Alliance',1,true),'correct full name must be exported')
fire('PLAYER_LOGOUT')

-- If UnitName arrives late, PLAYER_ENTERING_WORLD recovers automatically.
UnitName=function() return '','' end
GetUnitName=function() return '' end
UnitFullName=function() return '','' end
clock=clock+30
fire('PLAYER_LOGIN')
assert(ForeverTraderDB.v4ActiveSession==nil,'no anonymous session should be opened')
UnitName=function() return 'Priest','Falcon' end
UnitFullName=function() return 'Priest','Falcon' end
fire('PLAYER_ENTERING_WORLD')
assert(ForeverTraderDB.characters['eu-2-110#Priest Falcon'],'world entry should recover full name')
assert(ForeverTraderDB.v4ActiveSession,'world entry should start the delayed session')
fire('PLAYER_LOGOUT')
assert(ForeverTraderDB.sessionsWire:find('|eu-2-110|Priest Falcon|',1,true),'sessions must use full name')
for _,v in ipairs(prints)do assert(not v:match('Fout:'),v)end
realprint('Lua client mock: auto AH search, wallet/mail and full first+surname identity OK')
