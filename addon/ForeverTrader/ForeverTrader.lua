-- ForeverTrader v3.1.2 - read-only companion. No protected actions or movement.
local L=ForeverTraderLogic
local T=ForeverTraderTarget
local frame=CreateFrame('Frame')
local function say(s) print('|cffe4ba63ForeverTrader:|r '..s) end
local function now() return GetServerTime and GetServerTime() or time() end
local function db() if type(ForeverTraderDB)~='table' then ForeverTraderDB={} end; ForeverTraderDB.schema='FT1';return ForeverTraderDB end
local function market() return UnitFactionGroup('player') or 'Unknown',tostring(GetCurrentRegion and GetCurrentRegion() or 0) end
local function realmOK() local a,b=market();return a=='Alliance' and b=='3' and db().pvpConfirmed==true and (not GetRealmName or db().confirmedRealm==GetRealmName()) end
local s={active=false,mailOpen=false,ahOpen=false,mailKnown=false,ready=0,pending=0,attachments=0,partial=false,cash=0,reserve=150000,threshold=20000,buyCount=0,sellCount=0,mailAlert=false,bought=false}
local plan,book,bags,buys,sells=nil,{},{},{},{}
local listed={}
local targetBook,lastTry={},{}
local pending,lastQuery=nil,0
local browseFull=false
local targetMode=true
local update
local function owned()
    if not s.ahOpen or not C_AuctionHouse or not C_AuctionHouse.GetOwnedAuctions or not C_AuctionHouse.HasFullOwnedAuctionResults or not C_AuctionHouse.HasFullOwnedAuctionResults() then return end
    local rows={};listed={};for _,a in ipairs(C_AuctionHouse.GetOwnedAuctions() or {}) do
        local i=a.itemKey and a.itemKey.itemID;local q=a.quantity;local b=a.buyoutAmount
        if i and q and a.status==0 then listed[i]=(listed[i] or 0)+q;rows[#rows+1]=i..":"..q..":"..(b or 0) end
    end
    table.sort(rows);db().owned=now()..";"..table.concat(rows,";")
end
local function gold(n) return string.format('%.2fg',(n or 0)/10000) end
local function wallet() local f,r=market();s.cash=GetMoney();db().wallet=string.format('%d|%d|%s|%s',now(),s.cash,f,r) end
local function getBags()
    bags={}; if not C_Container or not C_Container.GetContainerItemInfo then return end
    for bag=0,(NUM_BAG_SLOTS or 4) do for slot=1,C_Container.GetContainerNumSlots(bag) do
        local a=C_Container.GetContainerItemInfo(bag,slot)
        if a and a.itemID and not a.isLocked and not a.isBound then bags[a.itemID]=(bags[a.itemID] or 0)+(a.stackCount or 1) end
    end end
    local rows={};for id,q in pairs(bags) do rows[#rows+1]=id..':'..q end;table.sort(rows)
    db().bags=now()..';'..table.concat(rows,';')
end
local function mailbox()
    if not s.mailOpen or not GetInboxNumItems or not GetInboxInvoiceInfo or not GetInboxHeaderInfo then return end
    local n,total=GetInboxNumItems(); if type(n)~='number' then return end
    local pending,ready,attachments,unknown=0,0,0,0;local eta=nil;local gh,gm;if GetGameTime then gh,gm=GetGameTime() end
    for i=1,n do
        local ok,kind,_,_,bid,buyout,deposit,cut,delay,eh,em=pcall(GetInboxInvoiceInfo,i)
        local _,_,_,_,money,cod,_,hasItem=GetInboxHeaderInfo(i)
        if ok and kind=='seller_temp_invoice' then
            if type(bid)=='number' and bid>0 then pending=pending+math.max(0,bid+(tonumber(deposit) or 0)-(tonumber(cut) or 0))
            elseif type(delay)=='number' and delay>0 then pending=pending+delay
            else unknown=unknown+1 end
            if type(gh)=='number' and type(gm)=='number' and type(eh)=='number' and type(em)=='number' and eh>=0 and eh<24 and em>=0 and em<60 then
                local delta=(eh*60+em-gh*60-gm)%1440;if delta<=90 then local at=now()+delta*60;eta=math.min(eta or at,at) end
            end
        elseif ok and kind=='seller' and type(money)=='number' then ready=ready+math.max(0,money)
        elseif ok and kind=='buyer' and (tonumber(cod) or 0)==0 then attachments=attachments+(tonumber(hasItem) or 0)
        elseif (tonumber(hasItem) or 0)>0 and (tonumber(cod) or 0)==0 then unknown=unknown+1 end
    end
    s.pending=pending;s.eta=eta;s.ready=ready;s.attachments=attachments;s.partial=type(total)=='number' and total>n or false;s.unknown=unknown;s.mailKnown=true;s.lastMail=now();s.mailAlert=false;s.bought=false;s.buyBlocked=false
    db().mail=string.format('%d|%d|%d',s.lastMail,pending,ready)
    db().mail3=string.format('%d|%d|%d|%d|%d|%d',s.lastMail,pending,ready,attachments,s.partial and 1 or 0,unknown)
end
local function scan()
    if not C_AuctionHouse or not C_AuctionHouse.GetNumReplicateItems or not C_AuctionHouse.GetReplicateItemInfo then return end
    local n=C_AuctionHouse.GetNumReplicateItems(); if type(n)~='number' or n<=0 then return end
    local rows,nb={},{}
    -- Only raw scan; no game query. Treat buyout as stack total, verify in client before purchase.
    for i=0,n-1 do
        local ok,_,_,q,_,_,_,_,_,_,cost,_,_,_,owner,_,status,id=pcall(C_AuctionHouse.GetReplicateItemInfo,i)
        if ok and type(q)=='number' and type(cost)=='number' and type(id)=='number' and q>0 and cost>0 and id>0 and status==0 and not owner then
            rows[#rows+1]=string.format('%d:%d:%d',id,q,cost)
            local b=nb[id] or {stacks={}};nb[id]=b;local p=math.ceil(cost/q);b.floor=math.min(b.floor or p,p);b.stacks[#b.stacks+1]={qty=q,cost=cost}
        end
    end
    if #rows==0 then return end
    for _,b in pairs(nb) do table.sort(b.stacks,function(a,b) return a.cost/a.qty<b.cost/b.qty end) end
    book=nb;s.scanAt=now();local f,r=market();db().scan=string.format('%d|%s|%s|%d;',s.scanAt,f,r,#rows)..table.concat(rows,';'); say('Scan ontvangen: '..#rows..' regels.')
end
local ui=CreateFrame('Frame','ForeverTraderCoach',UIParent,'BackdropTemplate');ui:SetSize(430,302);ui:SetPoint('CENTER',UIParent,'CENTER',360,0);ui:SetMovable(true);ui:EnableMouse(true);ui:RegisterForDrag('LeftButton');ui:SetScript('OnDragStart',ui.StartMoving);ui:SetScript('OnDragStop',ui.StopMovingOrSizing)
ui:SetBackdrop({bgFile='Interface/Tooltips/UI-Tooltip-Background',edgeFile='Interface/Tooltips/UI-Tooltip-Border',edgeSize=14});ui:SetBackdropColor(.04,.06,.09,.96)
local title=ui:CreateFontString(nil,'OVERLAY','GameFontNormalLarge');title:SetPoint('TOPLEFT',14,-12);title:SetText('ForeverTrader 3.1.2')
local text=ui:CreateFontString(nil,'OVERLAY','GameFontHighlight');text:SetPoint('TOPLEFT',14,-39);text:SetWidth(402);text:SetJustifyH('LEFT');text:SetJustifyV('TOP')
local close=CreateFrame('Button',nil,ui,'UIPanelCloseButton');close:SetPoint('TOPRIGHT',0,0)
local lastCode,lastNotify=nil,0
local function name(id) return (GetItemInfo and GetItemInfo(id)) or (C_Item and C_Item.GetItemNameByID and C_Item.GetItemNameByID(id)) or ('Item '..id) end
update=function()
    wallet();s.market=realmOK();s.reserve=math.max(150000,math.floor(s.cash*.20));s.planValid=plan and now()<plan.expires
    s.targetMode=targetMode
    if pending and now()-pending.at>=20 then pending=nil end
    s.searchPending=pending~=nil;s.searchCandidate=not s.buyBlocked and T.choose(plan,targetBook,bags,listed,now(),lastTry) or nil
    buys,sells=L.matches(plan,targetBook,bags,s.cash,s.reserve,now(),s.scanAt,listed,true);if s.buyBlocked or pending then buys={} end;if pending then sells={} end;s.buyCount=#buys;s.sellCount=#sells
    local code,msg=L.next(s,now());local lines={msg,'Gold '..gold(s.cash)..' | Incoming (laatst gezien) '..gold(s.pending)..' | Klaar (laatst gezien) '..gold(s.ready)}
    if s.partial or (s.unknown or 0)>0 then lines[#lines+1]='Inbox: controleer ook onbekende / overige berichten.' end
    if s.searchCandidate then lines[#lines+1]='Volgende zoekopdracht: '..name(s.searchCandidate.id) end
    if code=='BUY' then for i=1,math.min(3,#buys) do local r=buys[i];lines[#lines+1]=name(r.id)..' x'..r.qty..' | max '..gold(r.max)..'/st | doel '..gold(r.target)..' | hold '..r.hold..'u | live '..gold(targetBook[r.id].floor) end end
    if code=='SELL' then for i=1,math.min(3,#sells) do local r=sells[i];lines[#lines+1]=name(r.id)..' x'..r.qty..' | doel '..gold(r.target)..'/st (check eigen kostprijs)' end end
    if s.eta then lines[#lines+1]='Eerstvolgende verwachte uitbetaling: '..math.max(0,math.ceil((s.eta-now())/60))..' min (controle nodig).' end
    if s.lastMail then lines[#lines+1]='Mail gecontroleerd: '..math.floor((now()-s.lastMail)/60)..' min geleden.' end
    if s.scanAt then lines[#lines+1]='Full scan: '..math.max(0,900-(now()-s.scanAt))..'s tot volgende lokale richttijd.' else lines[#lines+1]='Full scan: nog niet ontvangen.' end
    lines[#lines+1]='Controleer altijd de live prijs en je eigen voorraad.';text:SetText(table.concat(lines,'\n'))
    if code~=lastCode then
        db().coach=now()..'|'..code..'|'..s.cash..'|'..s.pending..'|'..s.ready..'|'..s.buyCount..'|'..s.sellCount
        local logs={};for row in (db().coachLog or ''):gmatch('[^;]+') do logs[#logs+1]=row end;logs[#logs+1]=db().coach;while #logs>200 do table.remove(logs,1) end;db().coachLog=table.concat(logs,';')
        if s.active and now()-lastNotify>=8 and code~='WAIT' and code~='OFF' then say(msg);if UIErrorsFrame and UIErrorsFrame.AddMessage then UIErrorsFrame:AddMessage(msg,1,.82,.25,1) end; if (code=='MAIL' or code=='COLLECT') and PlaySound and SOUNDKIT then pcall(PlaySound,SOUNDKIT.RAID_WARNING or 8959) end;lastNotify=now() end
        lastCode=code
    end
end
local function check(fn) local ok,err=pcall(fn);if not ok then say('Fout: '..tostring(err)) end end
-- Auctionator's default Full Scan is an IncrementalScan (browse summary), not
-- a Blizzard replicate scan. Read its completed result payload rather than guessing
-- whether an arbitrary BrowseQuery was truly a full-market scan.
local auctionatorListener
local function readAuctionatorSummary(rawScan)
    if type(rawScan)~='table' or not s.ahOpen or not realmOK() then return end
    local rows,count={},0
    -- This summary reports a minimum UNIT price and aggregate quantity; it is
    -- not a set of executable per-listing buyouts. Never feed it to L.matches.
    for _,r in ipairs(rawScan) do
        local k=type(r)=='table' and r.itemKey
        local id=k and k.itemID
        local price=r and r.minPrice
        local qty=r and r.totalQuantity
        if type(id)=='number' and id>0 and type(price)=='number' and price>0 and type(qty)=='number' and qty>0
           and (k.itemLevel or 0)==0 and (k.itemSuffix or 0)==0 and (k.battlePetSpeciesID or 0)==0 then
            rows[#rows+1]=string.format('%d:%d:%d',id,math.floor(price),math.floor(qty))
            count=count+1
        end
    end
    if count==0 then say('Auctionator-scan voltooid, maar geen bruikbare basisitemprijzen.');return end
    local t=now()
    db().browseSummary=t..';'..table.concat(rows,';')
    s.scanAt=t
    say('Auctionator summary-scan ontvangen: '..count..' items (alleen prijsreferenties).')
    update()
end
local function registerAuctionatorScan()
    local a=Auctionator
    local inc=a and a.IncrementalScan
    local bus=a and a.EventBus
    if not bus or not bus.Register or not inc or not inc.Events or not inc.Events.ScanComplete then
        return false
    end
    auctionatorListener={ReceiveEvent=function(_,event,rawScan)
        local ok,err=pcall(readAuctionatorSummary,rawScan)
        if not ok then say('Auctionator scanfout: '..tostring(err)) end
    end}
    bus:Register(auctionatorListener,{inc.Events.ScanComplete})
    return true
end
-- OptionalDeps ensures Auctionator loads before us. If it is loaded only after
-- our addon, try once more at PLAYER_LOGIN.
local registeredAuctionator=false
local function ensureAuctionatorListener()
    if not registeredAuctionator then
        local ok,res=pcall(registerAuctionatorScan)
        registeredAuctionator=(ok and res==true)
        if not ok then say('Auctionator-koppeling mislukt: '..tostring(res)) end
    end
end
ensureAuctionatorListener()

local function browseSummary()
    local a=C_AuctionHouse
    if not browseFull or not s.ahOpen or not realmOK() or not a or not a.HasFullBrowseResults or not a.GetBrowseResults or not a.HasFullBrowseResults() then return end
    browseFull=false;local rows={}
    for _,r in ipairs(a.GetBrowseResults() or {}) do
        local k=r.itemKey;local p,q=r.minPrice,r.totalQuantity
        if k and type(k.itemID)=='number' and (k.itemLevel or 0)==0 and (k.itemSuffix or 0)==0 and (k.battlePetSpeciesID or 0)==0 and type(p)=='number' and p>0 and type(q)=='number' and q>0 then rows[#rows+1]=k.itemID..':'..p..':'..q end
    end
    if #rows>0 then s.scanAt=now();db().browseSummary=s.scanAt..';'..table.concat(rows,';');say('Volledige browse-samenvatting ontvangen: '..#rows..' items.');end
end
local function targeted(e,key)
    if not s.ahOpen or not realmOK() or not C_AuctionHouse then return end
    local kind=e:find('COMMODITY',1,true) and 'commodity' or 'item'
    local id,b=T.read(C_AuctionHouse,kind,key,now());if not id then
        local maybe=kind=='item' and type(key)=='table' and key.itemID or kind=='commodity' and key
        if maybe then targetBook[maybe]=nil;if pending and pending.id==maybe then pending.kind=kind end end
        return
    end
    targetBook[id]=b
    if pending and pending.id==id then pending=nil end
    if not s.bought then s.buyBlocked=false end
    local row=T.record(id,b)
    if row then
        local d=db();local logs={};for v in (d.targetLog or ''):gmatch('[^;]+') do logs[#logs+1]=v end
        if logs[#logs]~=row then logs[#logs+1]=row end
        local size=0;for _,v in ipairs(logs) do size=size+#v+1 end
        while #logs>500 or size>3000000 do size=size-#logs[1]-1;table.remove(logs,1) end;d.targetLog=table.concat(logs,';')
    else say('Zoekresultaat te groot voor export; lokaal advies wel bijgewerkt.') end
end
-- Invalidate the cache as soon as another normal search starts, before any new results arrive.
if hooksecurefunc and C_AuctionHouse and C_AuctionHouse.SendSearchQuery then
    pcall(hooksecurefunc,C_AuctionHouse,'SendSearchQuery',function(key)
        if type(key)=='table' and key.itemID then targetBook[key.itemID]=nil end
    end)
end
if hooksecurefunc and C_AuctionHouse and C_AuctionHouse.SendBrowseQuery then
    pcall(hooksecurefunc,C_AuctionHouse,'SendBrowseQuery',function(q)
        browseFull=type(q)=='table' and q.searchString=='' and type(q.filters)=='table' and type(q.itemClassFilters)=='table' and not next(q.filters) and not next(q.itemClassFilters) and not q.minLevel and not q.maxLevel
    end)
    for _,fn in ipairs({'SearchForItemKeys','SearchForFavorites'}) do
        if C_AuctionHouse[fn] then pcall(hooksecurefunc,C_AuctionHouse,fn,function() browseFull=false end) end
    end
end
local function searchNext(id)
    if not s.active or not s.ahOpen or not realmOK() then say('Open het AH en start de coach.');return end
    if now()-lastQuery<5 then say('Wacht op AH-resultaten.');return end
    local a=C_AuctionHouse
    if not a or not a.SendSearchQuery or not a.MakeItemKey or not a.IsThrottledMessageSystemReady or not a.IsThrottledMessageSystemReady() then say('AH niet klaar; probeer later.');return end
    if pending then
        local key=a.MakeItemKey(pending.id)
        if pending.kind=='item' and a.RequestMoreItemSearchResults then a.RequestMoreItemSearchResults(key)
        elseif pending.kind=='commodity' and a.RequestMoreCommoditySearchResults then a.RequestMoreCommoditySearchResults(pending.id)
        else say('Wacht op AH-resultaten.');return end
        lastQuery=now();pending.at=now();return
    end
    -- Explicit /ft search <itemID> is a read-only diagnostic even without a
    -- current desktop plan. It never creates a buyable plan row.
    if id and (type(id)~='number' or id<1 or id>10000000 or id~=math.floor(id)) then say('Ongeldig itemID.');return end
    local r
    if id then
        r={id=id,monitor=true,qty=0,max=0,target=0,hold=0}
    else
        if not plan or now()>=plan.expires then say('Laad eerst een actuele planning of gebruik /ft search <itemID> voor een losse prijscontrole.');return end
        r=T.choose(plan,targetBook,bags,listed,now(),lastTry)
    end
    if not r then say('Geen nieuw item te controleren.');return end
    local key=a.MakeItemKey(r.id);if not key then return end
    pending={id=r.id,at=now()};lastQuery=now();lastTry[r.id]=now();targetBook[r.id]=nil
    local ok,err=pcall(a.SendSearchQuery,key,{{sortOrder=0,reverseSort=false}},true)
    if not ok then pending=nil;say('Zoeken mislukt: '..tostring(err))
    else say('AH-zoekopdracht verstuurd: '..name(r.id)..'. Wacht op resultaat.') end
    update()
end
local function mailSignal() if HasNewMail then local has=HasNewMail() and true or false;if has and not s.lastMailSignal and not s.mailOpen then s.mailAlert=true end;s.lastMailSignal=has end end
for _,event in ipairs({'PLAYER_LOGIN','PLAYER_LOGOUT','PLAYER_MONEY','MAIL_SHOW','MAIL_CLOSED','MAIL_INBOX_UPDATE','UPDATE_PENDING_MAIL','REPLICATE_ITEM_LIST_UPDATE','AUCTION_HOUSE_SHOW','AUCTION_HOUSE_CLOSED','BAG_UPDATE_DELAYED','OWNED_AUCTIONS_UPDATED','ITEM_PURCHASED','COMMODITY_PURCHASE_SUCCEEDED','AUCTION_HOUSE_AUCTIONS_EXPIRED','AUCTION_HOUSE_AUCTION_CREATED','ITEM_SEARCH_RESULTS_UPDATED','ITEM_SEARCH_RESULTS_ADDED','COMMODITY_SEARCH_RESULTS_UPDATED','COMMODITY_SEARCH_RESULTS_ADDED','AUCTION_HOUSE_BROWSE_RESULTS_UPDATED','AUCTION_HOUSE_BROWSE_RESULTS_ADDED'}) do pcall(frame.RegisterEvent,frame,event) end
frame:SetScript('OnEvent',function(_,e,...)
    local key=...
    check(function()
        if e=='PLAYER_LOGIN' then ensureAuctionatorListener();s.active=false;plan=L.plan(db().planText,now());getBags();mailSignal();ui:Hide()
        elseif e=='MAIL_SHOW' then s.mailOpen=true;s.mailKnown=false;s.ahOpen=false;if C_Timer and C_Timer.After then C_Timer.After(1,function() if s.mailOpen then check(function() mailbox();update() end) end end) end
        elseif e=='MAIL_INBOX_UPDATE' then mailbox()
        elseif e=='MAIL_CLOSED' then s.mailOpen=false
        elseif e=='UPDATE_PENDING_MAIL' then mailSignal();if not s.mailOpen and HasNewMail and HasNewMail() and now()-(s.lastMail or 0)>60 then s.mailAlert=true end
        elseif e=='AUCTION_HOUSE_SHOW' then s.ahOpen=true;s.mailOpen=false;owned()
        elseif e=='AUCTION_HOUSE_CLOSED' then s.ahOpen=false;pending=nil;targetBook={};browseFull=false
        elseif e=='REPLICATE_ITEM_LIST_UPDATE' then scan()
        elseif e=='AUCTION_HOUSE_BROWSE_RESULTS_UPDATED' or e=='AUCTION_HOUSE_BROWSE_RESULTS_ADDED' then browseSummary()
        elseif e=='ITEM_SEARCH_RESULTS_UPDATED' or e=='ITEM_SEARCH_RESULTS_ADDED' or e=='COMMODITY_SEARCH_RESULTS_UPDATED' or e=='COMMODITY_SEARCH_RESULTS_ADDED' then targeted(e,key)
        elseif e=='OWNED_AUCTIONS_UPDATED' or e=='AUCTION_HOUSE_AUCTION_CREATED' then owned()
        elseif e=='ITEM_PURCHASED' or e=='COMMODITY_PURCHASE_SUCCEEDED' then if s.active and s.ahOpen then s.bought=true;s.buyBlocked=true;targetBook={} end
        elseif e=='AUCTION_HOUSE_AUCTIONS_EXPIRED' then if s.active then s.mailAlert=true end
        elseif e=='BAG_UPDATE_DELAYED' then getBags()
        end;update()
    end)
end)
local elapsed=0; frame:SetScript('OnUpdate',function(_,dt) elapsed=elapsed+dt;if elapsed>=5 then elapsed=0;if s.active then check(function() mailSignal();update() end) end end end)
local input=CreateFrame('EditBox','ForeverTraderPlanInput',ui,'InputBoxTemplate');input:SetSize(390,22);input:SetPoint('BOTTOM',0,36);input:SetAutoFocus(false);input:SetMaxLetters(12000);input:Hide()
input:SetScript('OnEnterPressed',function(self) local p,err=L.plan(self:GetText(),now());if not p then say(err);return end;plan=p;db().planText=self:GetText();self:SetText('');self:ClearFocus();self:Hide();say('Planning geladen: '..#p.rows..' items (inclusief alleen-controleren).');update() end)
input:SetScript('OnEscapePressed',function(self) self:ClearFocus();self:Hide() end)
local function button(label,x,fn) local b=CreateFrame('Button',nil,ui,'UIPanelButtonTemplate');b:SetSize(124,22);b:SetPoint('BOTTOMLEFT',x,10);b:SetText(label);b:SetScript('OnClick',fn);return b end
button('Planning plakken',12,function() input:Show();input:SetFocus() end)
button('Naar mailbox',150,function() s.bought=true;s.buyBlocked=true;lastCode=nil;check(update) end)
button('Zoek volgend',288,function() check(searchNext) end)
SLASH_FOREVERTRADER1='/ft';SlashCmdList.FOREVERTRADER=function(msg)
    msg=msg:lower():match('^%s*(.-)%s*$');check(function()
        if msg=='start' then s.active=true;ui:Show();mailSignal();getBags();lastCode=nil
        elseif msg=='stop' then s.active=false;ui:Hide()
        elseif msg=='market' then local f,r=market();if f~='Alliance' or r~='3' then say('Geen EU Alliance.');return end;db().pvpConfirmed=true;db().confirmedRealm=GetRealmName and GetRealmName() or nil;s.market=true;say('PvP door jou bevestigd; controleer dat dit de juiste realm is.')
        elseif msg=='plan' then ui:Show();input:Show();input:SetFocus();say('Plak de FT3-planning uit het dashboard en druk Enter.')
        elseif msg=='bought' or msg=='mail' then s.bought=true;s.buyBlocked=true;targetBook={};lastCode=nil
        elseif msg=='search' then searchNext()
        elseif msg:match('^search %d+$') then searchNext(tonumber(msg:match('%d+')))
        elseif msg=='status' or msg=='' then ui:Show();lastCode=nil
        else say('/ft start | stop | market | plan | bought | mail | search [itemID] | status');return end
        update()
    end)
end
