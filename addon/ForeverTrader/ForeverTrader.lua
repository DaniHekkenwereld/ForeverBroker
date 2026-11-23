-- ForeverTrader v4.0.0 - account-wide inventory with offline-server strategies.
local L=ForeverTraderLogic
local T=ForeverTraderTarget
local V4=ForeverTraderV4
local frame=CreateFrame('Frame')
local function say(s) print('|cffe4ba63ForeverTrader:|r '..s) end
local function now() return GetServerTime and GetServerTime() or time() end
local function db() if type(ForeverTraderDB)~='table' then ForeverTraderDB={} end; ForeverTraderDB.schema='FT1';return ForeverTraderDB end
local function market() return UnitFactionGroup('player') or 'Unknown',tostring(GetCurrentRegion and GetCurrentRegion() or 0) end
-- Forever's character identity is FIRST NAME + SURNAME, unique per
-- region. UnitName/UnitFullName return surname as their *second* value,
-- NOT a realm. GetUnitName("player") returns the joined full name.
-- The market ID is independent of character identity and is fixed for
-- this EU PvP Alliance addon.
local MARKET_ID='eu-2-110'
local function validIdentity(v)
    return type(v)=='string' and #v>0 and #v<=100 and not v:find('[|;#?"\\%c]')
end
local function characterName()
    -- Prefer the native full-name function. Never identify a Forever
    -- character only by its first name: first names are NOT unique.
    if GetUnitName then
        local full=GetUnitName('player',true)
        if validIdentity(full) and full:find('%S+%s+%S+') then return full end
    end
    local first,surname
    if UnitName then first,surname=UnitName('player') end
    if (not validIdentity(first) or not validIdentity(surname)) and UnitFullName then
        local a,b=UnitFullName('player')
        if not validIdentity(first) then first=a end
        if not validIdentity(surname) then surname=b end
    end
    if not validIdentity(first) or not validIdentity(surname) then return nil end
    local full=first..(CHARACTERNAME_SURNAME_SEPARATOR or ' ')..surname
    return validIdentity(full) and full or nil
end
local function identity()
    local character=characterName()
    if not character then return nil,nil end
    return MARKET_ID,character
end
local function realmOK()
    local faction,region=market()
    return faction=='Alliance' and region=='3'
end
local s={active=false,mailOpen=false,ahOpen=false,mailKnown=false,ready=0,pending=0,attachments=0,partial=false,cash=0,reserve=150000,threshold=20000,buyCount=0,sellCount=0,mailAlert=false,bought=false,live=false,liveSpent=0,walletKnown=false,autoSearch=false,autoSearchCount=0}
local plan,book,bags,buys,sells=nil,{},{},{},{}
local listed={}
local bankStock,bankBound,bagBound,equipped={},{},{},{}
local bankOpen=false
local targetBook,lastTry={},{}
local pending,lastQuery=nil,0
local browseFull=false
local targetMode=true
local update
local recordCharacter
local function owned()
    if not s.ahOpen or not C_AuctionHouse or not C_AuctionHouse.GetOwnedAuctions or not C_AuctionHouse.HasFullOwnedAuctionResults or not C_AuctionHouse.HasFullOwnedAuctionResults() then return end
    local rows={};listed={};for _,a in ipairs(C_AuctionHouse.GetOwnedAuctions() or {}) do
        local i=a.itemKey and a.itemKey.itemID;local q=a.quantity;local b=a.buyoutAmount
        if i and q and a.status==0 then listed[i]=(listed[i] or 0)+q;rows[#rows+1]=i..":"..q..":"..(b or 0) end
    end
    table.sort(rows);db().owned=now()..";"..table.concat(rows,";")
    s.ownedKnown=true
    if recordCharacter then recordCharacter('owned') end
end
local function gold(n) return string.format('%.2fg',(n or 0)/10000) end
local function goldExact(n)
    n=math.max(0,math.floor(n or 0))
    return math.floor(n/10000)..'g '..math.floor(n%10000/100)..'s '..(n%100)..'c'
end
local function wallet()
    local f,r=market();local money=GetMoney()
    if type(money)~='number' or money<0 then return end
    if s.live and s.walletKnown and money<s.cash then s.liveSpent=s.liveSpent+s.cash-money end
    s.cash=money;s.walletKnown=true
    db().wallet=string.format('%d|%d|%s|%s',now(),money,f,r)
    if recordCharacter then recordCharacter('wallet') end
end
-- Never discard a bound or locked item from a portfolio. Bound is tracked
-- separately so a bank full of BoP gear does not count as sellable stock.
local function containerStock(containerIds)
    if not C_Container or not C_Container.GetContainerItemInfo or
       not C_Container.GetContainerNumSlots then return nil,nil end
    local counts,bound={},{}
    for _,bag in ipairs(containerIds) do
        local ok,slots=pcall(C_Container.GetContainerNumSlots,bag)
        if ok and type(slots)=='number' and slots>=0 and slots<=200 then
            for slot=1,slots do
                local good,item=pcall(C_Container.GetContainerItemInfo,bag,slot)
                if good and type(item)=='table' and type(item.itemID)=='number' and
                   item.itemID>0 and item.itemID<=10000000 then
                    local qty=tonumber(item.stackCount) or 1
                    if qty>0 and qty<=10000000 then
                        counts[item.itemID]=(counts[item.itemID] or 0)+qty
                        if item.isBound then bound[item.itemID]=(bound[item.itemID] or 0)+qty end
                    end
                end
            end
        end
    end
    return counts,bound
end
local function getBags()
    local ids={};for i=0,(NUM_BAG_SLOTS or 4) do ids[#ids+1]=i end
    local counts,bound=containerStock(ids)
    if not counts then return end
    bags=counts;bagBound=bound
    local rows={};for id,q in pairs(bags) do rows[#rows+1]=id..':'..q end;table.sort(rows)
    db().bags=now()..';'..table.concat(rows,';')
    s.bagsKnown=true;s.bagBoundAt=now()
    if recordCharacter then recordCharacter('bags') end
end
local function getBank()
    if not bankOpen then return end
    if not C_Container or not C_Container.GetContainerNumSlots then return end
    local ok,slots=pcall(C_Container.GetContainerNumSlots,-1)
    -- The main bank must actually be accessible. Never replace the last
    -- known bank inventory with an empty cache after a missed bank event.
    if not ok or type(slots)~='number' or slots<=0 then return end
    local ids={-1}
    for i=(NUM_BAG_SLOTS or 4)+1,(NUM_BAG_SLOTS or 4)+(NUM_BANKBAGSLOTS or 7) do
        ids[#ids+1]=i
    end
    local counts,bound=containerStock(ids)
    if not counts then return end
    bankStock=counts;bankBound=bound;s.bankKnown=true;s.bankAt=now()
    if recordCharacter then recordCharacter('bank') end
end
local function getEquipment()
    if not GetInventoryItemID then return end
    local found={}
    for slot=1,19 do
        local ok,id=pcall(GetInventoryItemID,'player',slot)
        if ok and type(id)=='number' and id>0 then found[id]=(found[id] or 0)+1 end
    end
    equipped=found;s.equipmentKnown=true;s.equipmentAt=now()
    if recordCharacter then recordCharacter('equipment') end
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
    if recordCharacter then recordCharacter('mail') end
end
-- Store snapshots of ALL previously visited characters on the same account.
-- SavedVariables are written by WoW at logout/reload, not immediately on login.
-- charactersWire is a bounded line-oriented export that desktop Python can parse
-- safely without executing arbitrary SavedVariables Lua.
recordCharacter=function(reason)
    local realm,character=identity()
    if not realm or not character then return end
    local d=db()
    if type(d.characters)~='table' then d.characters={} end
    local key=realm..'#'..character
    local rec=d.characters[key]
    -- Migrate old snapshots only when an exact name OR player GUID matches.
    -- A first name on its own is ambiguous on Forever, so never merge two
    -- different characters merely because they share the first name.
    local guid=UnitGUID and UnitGUID('player') or nil
    for oldKey,old in pairs(d.characters) do
        if oldKey~=key and type(old)=='table' and old.faction=='Alliance' and
           (old.name==character or (guid and old.guid and old.guid==guid)) then
            if type(rec)~='table' or (old.lastSeen or 0)>(rec.lastSeen or 0) then rec=old end
            d.characters[oldKey]=nil
        end
    end
    if type(rec)~='table' then rec={name=character,realm=realm} end
    rec.name=character;rec.realm=realm;rec.faction=(UnitFactionGroup and UnitFactionGroup('player')) or 'Unknown'
    rec.lastSeen=now();rec.lastUpdate=reason
    if UnitGUID then rec.guid=UnitGUID('player') end
    if not s.loggingOut and s.walletKnown then rec.gold=s.cash;rec.walletAt=now() end
    if s.bagsKnown then
        rec.bagBound={}
        for id,q in pairs(bagBound) do
            if type(id)=='number' and type(q)=='number' and id>0 and q>0 then rec.bagBound[id]=q end
        end
        rec.bagBoundAt=s.bagBoundAt
        rec.bags={}
        for id,q in pairs(bags) do
            if type(id)=='number' and type(q)=='number' and id>0 and q>0 then rec.bags[id]=q end
        end
        rec.bagsAt=now()
    end
    if s.bankKnown then
        rec.bank={}
        rec.bankBound={}
        for id,q in pairs(bankStock) do if type(id)=='number' and q>0 then rec.bank[id]=q end end
        for id,q in pairs(bankBound) do if type(id)=='number' and q>0 then rec.bankBound[id]=q end end
        rec.bankAt=s.bankAt
    end
    if s.equipmentKnown then
        rec.equipment={}
        for id,q in pairs(equipped) do if type(id)=='number' and q>0 then rec.equipment[id]=q end end
        rec.equipmentAt=s.equipmentAt
    end
    if s.ownedKnown then
        rec.auctions={}
        for id,q in pairs(listed) do if type(id)=='number' and type(q)=='number' and id>0 and q>0 then rec.auctions[id]=q end end
        rec.auctionsAt=now()
    end
    if s.mailKnown then
        rec.mailAt=s.lastMail;rec.mailPending=s.pending or 0;rec.mailReady=s.ready or 0
        rec.mailAttachments=s.attachments or 0
    end
    d.characters[key]=rec
    -- gsub returns (string,count); the extra value used to add a 15th
    -- column to the export, which the Python importer (correctly) rejects.
    local function safe(v)
        local cleaned=tostring(v or ''):gsub('[|;]','_'):gsub('%c','_'):gsub(string.char(34),'_'):gsub(string.char(92),'_')
        return cleaned
    end
    local function sums(items)
        local rows={}
        if type(items)=='table' then
            for id,qty in pairs(items) do
                if type(id)=='number' and type(qty)=='number' and id>0 and qty>0 then rows[#rows+1]=string.format('%d:%d',id,qty) end
            end
        end
        table.sort(rows)
        return table.concat(rows,',')
    end
    local rows={}
    for _,c in pairs(d.characters) do
        if type(c)=='table' and type(c.name)=='string' and type(c.realm)=='string' and type(c.lastSeen)=='number' then
            rows[#rows+1]={at=c.lastSeen,line=table.concat({
                safe(c.lastSeen),safe(c.realm),safe(c.name),safe(c.faction),safe(c.gold),
                safe(c.walletAt),safe(c.bagsAt),sums(c.bags),
                safe(c.auctionsAt),sums(c.auctions),safe(c.mailAt),
                safe(c.mailPending),safe(c.mailReady),safe(c.mailAttachments)
            },'|')}
        end
    end
    table.sort(rows,function(a,b)return a.at>b.at end)
    local output={'FTCHAR1'}
    local size=7
    for _,r in ipairs(rows) do
        if #output>=40 or size+#r.line+1>60000 then break end
        output[#output+1]=r.line;size=size+#r.line+1
    end
    d.charactersWire=table.concat(output,';')
    -- Backwards compatible portfolio extension. The original FTCHAR1 wire
    -- stays unchanged for older clients and all prior character records.
    local stockRows={}
    for _,c in pairs(d.characters) do
        if type(c)=='table' and type(c.name)=='string' and type(c.realm)=='string'
            and type(c.lastSeen)=='number' then
            stockRows[#stockRows+1]={at=c.lastSeen,line=table.concat({
                safe(c.lastSeen),safe(c.realm),safe(c.name),
                safe(c.bankAt),sums(c.bank),sums(c.bankBound),
                safe(c.bagBoundAt),sums(c.bagBound),
                safe(c.equipmentAt),sums(c.equipment)
            },'|')}
        end
    end
    table.sort(stockRows,function(a,b)return a.at>b.at end)
    local extra={'FTSTOCK1'};local bytes=8
    for _,r in ipairs(stockRows) do
        if #extra>=40 or bytes+#r.line+1>60000 then break end
        extra[#extra+1]=r.line;bytes=bytes+#r.line+1
    end
    d.stockWire=table.concat(extra,';')
end

local function ensureV4Identity(reason)
    local realm,character=identity()
    if not realm or not character then return false end
    recordCharacter(reason or 'identity')
    if V4 and not db().v4ActiveSession then
        V4.login(db(),now(),realm,character,s.walletKnown and s.cash or nil,bags)
        plan,s.v4PlanLoaded=V4.plan(db(),now(),realm,character,L)
        if s.v4PlanLoaded and reason~='logout' then
            say('V4-serverstrategie voor '..character..' geladen.')
        end
    end
    return true
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
local title=ui:CreateFontString(nil,'OVERLAY','GameFontNormalLarge');title:SetPoint('TOPLEFT',14,-12);title:SetText('ForeverTrader 4.0.0')
local text=ui:CreateFontString(nil,'OVERLAY','GameFontHighlight');text:SetPoint('TOPLEFT',14,-39);text:SetWidth(402);text:SetJustifyH('LEFT');text:SetJustifyV('TOP')
local close=CreateFrame('Button',nil,ui,'UIPanelCloseButton');close:SetPoint('TOPRIGHT',0,0)
-- Compact high-contrast communication marker read by local AHK via PixelSearch.
local voiceMarker=ui:CreateTexture(nil,'OVERLAY')
voiceMarker:SetSize(18,18);voiceMarker:SetPoint('TOPRIGHT',-64,-10)
local voiceSignature=ui:CreateTexture(nil,'OVERLAY')
voiceSignature:SetSize(18,18);voiceSignature:SetPoint('LEFT',voiceMarker,'RIGHT',6,0)
local function bridgeStatus(code)
    local state=(code=='MAIL' or code=='MAIL_CHECK' or code=='COLLECT' or code=='MAIL_WAIT') and 'MAIL'
                or (code=='AH' or code=='RETURN') and 'AH' or 'IDLE'
    if state=='MAIL' then
        voiceMarker:SetColorTexture(1,.16,.33,1)
        voiceSignature:SetColorTexture(.4,0,.13,1)
    elseif state=='AH' then
        voiceMarker:SetColorTexture(.07,.85,.55,1)
        voiceSignature:SetColorTexture(.02,.25,.10,1)
    else
        voiceMarker:SetColorTexture(.10,.14,.19,1)
        voiceSignature:SetColorTexture(.10,.14,.19,1)
    end
    s.voiceState=state
end
local lastCode,lastNotify=nil,0
local function name(id) return (GetItemInfo and GetItemInfo(id)) or (C_Item and C_Item.GetItemNameByID and C_Item.GetItemNameByID(id)) or ('Item '..id) end
update=function()
    if not s.loggingOut then wallet() end;s.market=realmOK();s.reserve=math.max(150000,math.floor(s.cash*.20));s.planValid=plan and now()<plan.expires
    s.targetMode=targetMode
    if pending and now()-pending.at>=20 then pending=nil end
    s.searchPending=pending~=nil;s.searchCandidate=T.choose(plan,targetBook,bags,listed,now(),lastTry)
    local remaining=math.max(0,50000-(s.liveSpent or 0))
    buys,sells=L.matches(plan,targetBook,bags,s.cash,s.reserve,now(),s.scanAt,listed,true,s.live and math.min(10000,remaining) or nil)
    if s.buyBlocked or pending then buys={} end;if pending then sells={} end
    if s.live then
        local safe={}
        for _,r in ipairs(buys) do if L.liveAllowed(s,r,targetBook[r.id],now()) then safe[#safe+1]=r end end
        buys=safe
    end
    s.buyCount=#buys;s.sellCount=#sells
    local code,msg=L.next(s,now());bridgeStatus(code);local lines={msg,'Gold '..gold(s.cash)..' | Incoming (laatst gezien) '..gold(s.pending)..' | Klaar (laatst gezien) '..gold(s.ready)}
    if s.v4PlanLoaded then lines[#lines+1]='V4: serverstrategie geladen voor dit character (/ft v4)' end
    if s.autoSearch then lines[#lines+1]='AUTO ZOEKEN: '..(s.autoSearchCount or 0)..' gestuurd / '..(s.autoResultCount or 0)..' resultaten' end
    if s.live then
        lines[#lines+1]='LIVE TEST: alleen adviezen, transacties zelf klikken!'
        lines[#lines+1]='Budget gebruikt '..gold(s.liveSpent)..'/5.00g | max 1g per advies | reserve 15g'
    end
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
    if type(rawScan)~='table' or not realmOK() then return end
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
-- Persist a bounded audit trail; WoW writes it on logout or /reload.
local function logAuto(kind,id,price,rows)
    if type(id)~='number' or id<1 then return end
    local entry=now()..':'..kind..':'..id..':'..math.floor(price or 0)..':'..(rows or 0)
    local d=db();local log=d.v4SearchLog or ''
    log=(log=='' and entry or log..';'..entry)
    while #log>14000 do log=log:match('^[^;]+;(.*)$') or '' end
    d.v4SearchLog=log
end
local function targeted(e,key)
    if not s.ahOpen or not realmOK() or not C_AuctionHouse then return end
    local kind=e:find('COMMODITY',1,true) and 'commodity' or 'item'
    local id,b=T.read(C_AuctionHouse,kind,key,now());if not id then
        local maybe=kind=='item' and type(key)=='table' and key.itemID or kind=='commodity' and key
        if maybe then targetBook[maybe]=nil;if pending and pending.id==maybe then pending.kind=kind end end
        return
    end
    local tracked=pending and pending.id==id and s.autoSearch
    targetBook[id]=b
    if pending and pending.id==id then pending=nil end
    if tracked then
        local count=#(b.stacks or {})
        s.autoResultCount=(s.autoResultCount or 0)+1
        s.lastAutoResult={id=id,at=now(),price=b.floor or 0,rows=count}
        logAuto('R',id,b.floor or 0,count)
        say('AH resultaat: '..name(id)..' | laagste '..goldExact(b.floor or 0)..
            '/stuk | '..count..' prijsregels (geen bewezen verkoop).')
        if V4 then
            local realm,character=identity()
            if realm and character then
                V4.actions(db(),realm,character,function(action,item,qty,maxBuy,target)
                    if item==id and (action=='INVEST_SHORT' or action=='INVEST_LONG')
                       and type(maxBuy)=='number' then
                        local freshPlan=plan and plan.made and
                            now()>=plan.made and now()-plan.made<=5400
                        if not freshPlan then
                            say('INVESTERING '..name(id)..': advies ouder dan 90 minuten.'..
                                ' Alleen prijscontrole, niet op oud advies kopen.')
                        elseif not b.floor or b.floor<=0 then
                            say('INVESTERING '..name(id)..': geen verkoopbare AH-prijs gevonden.')
                        elseif b.floor<=maxBuy then
                            say('INSTAPPRIJS GEHAALD '..name(id)..': '..goldExact(b.floor)..
                                ' <= limiet '..goldExact(maxBuy)..
                                '. Alleen handmatig kopen na controle van variant, volume en risico.')
                        else
                            say('TE DUUR '..name(id)..': AH '..goldExact(b.floor)..
                                ' > maximale instap '..goldExact(maxBuy)..'. Niet blind kopen.')
                        end
                    end
                end)
            end
        end
    end
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
local function searchNext(id,quiet)
    if not s.ahOpen and AuctionHouseFrame and AuctionHouseFrame.IsShown and AuctionHouseFrame:IsShown() then s.ahOpen=true end
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
    if not r then if not quiet then say('Geen nieuw item te controleren.') end;return end
    local key=a.MakeItemKey(r.id);if not key then return end
    pending={id=r.id,at=now()};lastQuery=now();lastTry[r.id]=now();targetBook[r.id]=nil
    local ok,err=pcall(a.SendSearchQuery,key,{{sortOrder=0,reverseSort=false}},true)
    if not ok then pending=nil;say('Zoeken mislukt: '..tostring(err))
    else
        if quiet then
            s.autoSearchCount=(s.autoSearchCount or 0)+1
            db().lastAutoSearch=now()..'|'..r.id..'|'..s.autoSearchCount
            logAuto('Q',r.id,0,0)
            say('AH zoekt '..s.autoSearchCount..': '..name(r.id)..' (item '..r.id..').')
        else say('AH-zoekopdracht verstuurd: '..name(r.id)..'. Wacht op resultaat.') end
    end
    update()
end
-- Diagnose every silent auto-search gate. The search list is read-only.
local function autoBlockReason()
    if not s.autoSearch then return 'Automatisch zoeken staat uit.' end
    if not s.active then return 'Start eerst de coach met /ft start.' end
    -- If the client missed AUCTION_HOUSE_SHOW, recover from the visible AH.
    if not s.ahOpen and AuctionHouseFrame and AuctionHouseFrame.IsShown and AuctionHouseFrame:IsShown() then
        s.ahOpen=true
    end
    if not s.ahOpen then return 'Auction House niet herkend. Open het AH-venster en probeer /ft auto status.' end
    if not realmOK() then return 'Alleen EU Alliance wordt ondersteund.' end
    if not plan then return 'Geen geldige V4-zoeklijst geladen. /ft v4 kan wel tasadviezen tonen zonder zoeklijst.' end
    if now()>=plan.expires then return 'V4-zoeklijst verlopen; de Windows-bridge werkt deze bij voor de volgende WoW-start.' end
    if not plan.rows or #plan.rows==0 then return 'Server heeft 0 AH-items op de zoeklijst gezet.' end
    if pending then return 'Wachten op AH-resultaten voor item '..pending.id..'.' end
    -- Mail alerts, manual sales and buy-blocks must not stop read-only searches.
    if not s.searchCandidate then return 'Alle zoekitems zijn recent gecontroleerd of worden nog verwerkt.' end
    if now()-lastQuery<5 then return 'Wachten op AH-zoekcooldown (5 seconden).' end
    local a=C_AuctionHouse
    if not a or not a.SendSearchQuery or not a.MakeItemKey then
        return 'AH-zoekfuncties ontbreken in deze WoW-client.'
    end
    if not a.IsThrottledMessageSystemReady or not a.IsThrottledMessageSystemReady() then
        return 'AH-server laat momenteel geen nieuwe zoekopdracht toe (throttle).'
    end
    return nil
end

-- Read-only queries only. Pause on actionable results, throttle and mailbox hints.
local function maybeAutoSearch()
    if autoBlockReason() then return end
    searchNext(nil,true)
end
local function mailSignal() if HasNewMail then local has=HasNewMail() and true or false;if has and not s.lastMailSignal and not s.mailOpen then s.mailAlert=true end;s.lastMailSignal=has end end
for _,event in ipairs({'PLAYER_LOGIN','PLAYER_ENTERING_WORLD','PLAYER_LOGOUT','PLAYER_MONEY','MAIL_SHOW','MAIL_CLOSED','MAIL_INBOX_UPDATE','UPDATE_PENDING_MAIL','REPLICATE_ITEM_LIST_UPDATE','AUCTION_HOUSE_SHOW','AUCTION_HOUSE_CLOSED','PLAYER_INTERACTION_MANAGER_FRAME_SHOW','PLAYER_INTERACTION_MANAGER_FRAME_HIDE','BAG_UPDATE_DELAYED','BANKFRAME_OPENED','BANKFRAME_CLOSED','PLAYERBANKSLOTS_CHANGED','PLAYERBANKBAGSLOTS_CHANGED','PLAYER_EQUIPMENT_CHANGED','OWNED_AUCTIONS_UPDATED','ITEM_PURCHASED','COMMODITY_PURCHASE_SUCCEEDED','AUCTION_HOUSE_AUCTIONS_EXPIRED','AUCTION_HOUSE_AUCTION_CREATED','ITEM_SEARCH_RESULTS_UPDATED','ITEM_SEARCH_RESULTS_ADDED','COMMODITY_SEARCH_RESULTS_UPDATED','COMMODITY_SEARCH_RESULTS_ADDED','AUCTION_HOUSE_BROWSE_RESULTS_UPDATED','AUCTION_HOUSE_BROWSE_RESULTS_ADDED'}) do pcall(frame.RegisterEvent,frame,event) end
frame:SetScript('OnEvent',function(_,e,...)
    local key=...
    check(function()
        if e=='PLAYER_LOGIN' then
            ensureAuctionatorListener()
            s.loggingOut=false;s.autoSearch=false;s.autoSearchCount=0;s.autoResultCount=0;s.lastAutoResult=nil
            s.live=false;s.liveSpent=0;s.walletKnown=false;s.bagsKnown=false;s.ownedKnown=false
            s.mailKnown=false;s.active=false;s.cash=0;s.ahOpen=false;s.mailOpen=false
            s.bankKnown=false;s.bagBoundAt=nil;s.equipmentKnown=false
            bankOpen=false;bankStock={};bankBound={};bagBound={};equipped={}
            bags={};listed={};targetBook={}
            getBags();wallet();getEquipment()
            plan=nil
            if V4 then
                db().realmOverride=nil  -- Remove the obsolete manual realm override.
                db().v4ActiveSession=nil
                ensureV4Identity('login')
            else plan=L.plan(db().planText,now()) end
            mailSignal();ui:Hide()
        elseif e=='PLAYER_ENTERING_WORLD' then
            getBags();wallet();getEquipment()
            if V4 then ensureV4Identity('world') end
        elseif e=='PLAYER_LOGOUT' then
            if V4 then
                ensureV4Identity('logout')
                V4.logout(db(),now(),s.walletKnown and s.cash or nil,bags)
            end
            recordCharacter('logout');s.loggingOut=true
        elseif e=='BANKFRAME_OPENED' then
            bankOpen=true;getBank()
            if s.bankKnown then
                local types=0;for _ in pairs(bankStock) do types=types+1 end
                say('Portfolio: bank opgeslagen ('..types..
                    ' itemtypes). Deze wordt bij uitloggen naar de VPS gesynchroniseerd.')
            else
                say('Portfolio: bank nog niet uitleesbaar. Houd bank open en controleer /ft portfolio.')
            end
        elseif e=='BANKFRAME_CLOSED' then getBank();bankOpen=false
        elseif e=='PLAYERBANKSLOTS_CHANGED' or e=='PLAYERBANKBAGSLOTS_CHANGED' then
            if bankOpen then getBank() end
        elseif e=='PLAYER_EQUIPMENT_CHANGED' then getEquipment()
        elseif e=='MAIL_SHOW' then s.mailOpen=true;s.mailKnown=false;s.ahOpen=false;if C_Timer and C_Timer.After then C_Timer.After(1,function() if s.mailOpen then check(function() mailbox();update() end) end end) end
        elseif e=='MAIL_INBOX_UPDATE' then mailbox()
        elseif e=='MAIL_CLOSED' then s.mailOpen=false
        elseif e=='UPDATE_PENDING_MAIL' then mailSignal();if not s.mailOpen and HasNewMail and HasNewMail() and now()-(s.lastMail or 0)>60 then s.mailAlert=true end
        elseif e=='AUCTION_HOUSE_SHOW' then s.ahOpen=true;s.mailOpen=false;owned()
        elseif e=='PLAYER_INTERACTION_MANAGER_FRAME_SHOW' and Enum and Enum.PlayerInteractionType and key==Enum.PlayerInteractionType.Auctioneer then s.ahOpen=true;s.mailOpen=false;owned()
        elseif e=='PLAYER_INTERACTION_MANAGER_FRAME_HIDE' and Enum and Enum.PlayerInteractionType and key==Enum.PlayerInteractionType.Auctioneer then s.ahOpen=false;pending=nil;targetBook={};browseFull=false
        elseif e=='AUCTION_HOUSE_CLOSED' then s.ahOpen=false;pending=nil;targetBook={};browseFull=false
        elseif e=='REPLICATE_ITEM_LIST_UPDATE' then scan()
        elseif e=='AUCTION_HOUSE_BROWSE_RESULTS_UPDATED' or e=='AUCTION_HOUSE_BROWSE_RESULTS_ADDED' then browseSummary()
        elseif e=='ITEM_SEARCH_RESULTS_UPDATED' or e=='ITEM_SEARCH_RESULTS_ADDED' or e=='COMMODITY_SEARCH_RESULTS_UPDATED' or e=='COMMODITY_SEARCH_RESULTS_ADDED' then targeted(e,key)
        elseif e=='OWNED_AUCTIONS_UPDATED' or e=='AUCTION_HOUSE_AUCTION_CREATED' then owned()
        elseif e=='ITEM_PURCHASED' or e=='COMMODITY_PURCHASE_SUCCEEDED' then if s.active and s.ahOpen then s.bought=true;s.buyBlocked=true;targetBook={} end
        elseif e=='AUCTION_HOUSE_AUCTIONS_EXPIRED' then if s.active then s.mailAlert=true end
        elseif e=='BAG_UPDATE_DELAYED' then getBags();if bankOpen then getBank() end
        end;update()
    end)
end)
local elapsed=0; frame:SetScript('OnUpdate',function(_,dt)
    elapsed=elapsed+dt
    if elapsed>=5 then
        elapsed=0
        if V4 and not s.loggingOut and not db().v4ActiveSession then
            check(function() ensureV4Identity('retry') end)
        end
        if s.active then check(function() mailSignal();update();maybeAutoSearch() end) end
    end
end)
local function button(label,x,fn) local b=CreateFrame('Button',nil,ui,'UIPanelButtonTemplate');b:SetSize(124,22);b:SetPoint('BOTTOMLEFT',x,10);b:SetText(label);b:SetScript('OnClick',fn);return b end
button('Auto status',12,function() check(function()
    update()
    say('Zoeklijst: '..(plan and #plan.rows or 0)..' items. '..(autoBlockReason() or 'Klaar om te zoeken.'))
end) end)
button('Naar mailbox',150,function() s.bought=true;s.buyBlocked=true;lastCode=nil;check(update) end)
button('Zoek volgend',288,function() check(searchNext) end)
SLASH_FOREVERTRADER1='/ft';SlashCmdList.FOREVERTRADER=function(msg)
    local original=msg or ''
    msg=original:lower():match('^%s*(.-)%s*$');check(function()
        if msg=='start' then s.active=true;ui:Show();mailSignal();getBags();lastCode=nil
        elseif msg=='auto on' then
            s.autoSearch=true;s.active=true;s.autoSearchCount=0;s.autoResultCount=0;s.lastAutoResult=nil
            ui:Show();update()
            say('Automatisch AH-zoeken AAN; alleen zoekopdrachten, geen aankopen.')
            local reason=autoBlockReason()
            if reason then say('Auto status: '..reason) else maybeAutoSearch() end
        elseif msg=='auto off' then s.autoSearch=false;say('Automatisch AH-zoeken UIT.')
        elseif msg=='auto' or msg=='auto status' then
            update()
            say('Auto: '..(s.autoSearch and 'AAN' or 'UIT')..
                ' | zoeklijst: '..(plan and #plan.rows or 0)..
                ' | verzonden: '..(s.autoSearchCount or 0)..
                ' | resultaten: '..(s.autoResultCount or 0))
            if s.lastAutoResult then
                local r=s.lastAutoResult
                say('Laatste AH-resultaat: '..name(r.id)..' | '..gold(r.price)..'/stuk | '..r.rows..' prijsregels')
            end
            local reason=autoBlockReason()
            say('Auto status: '..(reason or 'Klaar om te zoeken.'))
        elseif msg=='live on' then
            if not s.ahOpen and AuctionHouseFrame and AuctionHouseFrame.IsShown and AuctionHouseFrame:IsShown() then s.ahOpen=true end
            if not realmOK() or not s.ahOpen or not s.walletKnown then say('Live test alleen met AH open, bevestigde EU Alliance en geladen wallet.');return end
            s.live=true;s.liveSpent=0;s.active=true;s.buyBlocked=false;ui:Show();lastCode=nil
            say('Live test AAN: adviezen met 5g sessiebudget en max 1g per item. Kopen/verkopen blijft handmatig.')
        elseif msg=='live off' then s.live=false;s.liveSpent=0;s.buyBlocked=true;say('Live test UIT. Geen aankopen zonder eigen bevestiging.')
        elseif msg=='live' then say('Live test '..(s.live and 'AAN' or 'UIT')..'. Gebruik /ft live on of /ft live off. Geen automatische orders.')
        elseif msg=='stop' then s.active=false;s.live=false;s.autoSearch=false;ui:Hide()
        elseif msg=='identity' or msg=='market' then
            local realm,character=identity()
            local faction,region=market()
            say('Character: '..tostring(character or '(niet beschikbaar)')..
                ' | Markt: Forever EU PvP Alliance ('..MARKET_ID..')'..
                ' | Faction: '..faction..' | Region: '..region..
                ' | Export: '..(db().charactersWire and #db().charactersWire>7 and 'aanwezig' or 'leeg'))
            if not realmOK() then say('Waarschuwing: deze client is geen EU Alliance. Geen live AH-adviezen.') end
        elseif msg=='plan' then say('V4 gebruikt automatisch de serverzoeklijst. Handmatig plakken is niet nodig.')
        elseif msg:match('^trade ') then
            local side,item,qty,amount=msg:match('^trade (%a+) (%d+) (%d+) ([%d%.]+g?)$')
            if not side or (side~='buy' and side~='sell') then
                say('Gebruik: /ft trade buy 12363 2 15.25g of /ft trade sell 12363 2 18g (SELL is NET ontvangen gold).')
                return
            end
            local goldAmount=amount:sub(-1)=='g'
            local n=tonumber(goldAmount and amount:sub(1,-2) or amount)
            local copper=n and (goldAmount and math.floor(n*10000+.5) or n) or nil
            local realm,character=identity()
            local id,err=V4 and V4.recordTrade(db(),now(),realm,character,
                side:upper(),tonumber(item),tonumber(qty),copper)
            if id then
                say('Handmatig '..(side=='buy' and 'INKOOP' or 'VERKOOP')..
                    ' geregistreerd: '..name(tonumber(item))..' x'..qty..
                    ' | totaal '..goldExact(copper)..
                    '. Alleen echte transacties invoeren; uitloggen voor VPS-sync.')
                wallet();recordCharacter('trade')
            else say('Transactie niet vastgelegd: '..tostring(err or 'V4 ontbreekt')) end
        elseif msg=='portfolio' or msg=='bank' then
            local realm,character=identity()
            local c=realm and character and db().characters and
                    db().characters[realm..'#'..character]
            if not c then say('Portfolio: character nog niet geregistreerd.');return end
            local function types(tab)
                local count,units=0,0
                for _,q in pairs(type(tab)=='table' and tab or {}) do
                    count=count+1;units=units+q
                end
                return count..' itemtypes / '..units..' stuks'
            end
            say('Portfolio '..character..': '..goldExact(c.gold or 0)..
                ' | tassen '..types(c.bags)..
                ' | gear '..types(c.equipment)..
                ' | bank '..(c.bankAt and types(c.bank) or 'nog niet gemeten'))
            if c.bankAt then
                say('Bank laatst gezien: '..(type(date)=='function' and
                    date('%d-%m %H:%M',c.bankAt) or tostring(c.bankAt))..
                    '. Oude bankgegevens blijven bewaard totdat je opnieuw scant.')
            else
                say('Open de bank op dit character minstens één keer en log daarna uit.')
            end
            say('Naar VPS: automatisch na /reload of uitloggen via de Windows-bridge.')
        elseif msg=='trades' then
            local d=db();say('Handmatige transacties in export: '..#(d.v4Trades or {})..
                '. /ft trade buy [itemID] [aantal] [totaal g] of sell (netto na AH-fees).')
        elseif msg=='bought' or msg=='mail' then s.bought=true;s.buyBlocked=true;targetBook={};lastCode=nil
        elseif msg=='search' then searchNext()
        elseif msg:match('^search %d+$') then searchNext(tonumber(msg:match('%d+')))
        elseif msg=='v4' then
            ui:Show()
            local realm,character=identity()
            local count=V4 and realm and character and V4.actions(db(),realm,character,function(action,id,qty,maxBuy,target)
                if action=='INVEST_SHORT' or action=='INVEST_LONG' then
                    local horizon=action=='INVEST_SHORT' and 'KORT (1-5 dagen)' or 'LANG (1-3 weken)'
                    say('INVESTEREN '..horizon..': '..name(id)..
                        ' | max instap '..(maxBuy and goldExact(maxBuy) or 'onbekend')..
                        ' | verkoopscenario '..(target and goldExact(target) or 'onbekend')..
                        ' | zelf AH en verkoopsnelheid controleren!')
                else
                    local verb=action=='REVIEW_SELL' and 'Verkoop controleren' or
                               action=='VERIFY_BUY' and 'Koopkans controleren' or
                               action=='CHECK_LISTING' and 'Veiling controleren' or 'Volgen'
                    say(verb..': '..name(id)..' x'..qty)
                end
            end) or 0
            if count==0 then say('Geen V4-adviezen beschikbaar voor dit character.') end
            lastCode=nil
        elseif msg=='status' or msg=='' then ui:Show();lastCode=nil
        else say('/ft start | stop | v4 | identity | market | auto on/off/status | live on/off | bought | mail | search [itemID] | status');return end
        update()
    end)
end
