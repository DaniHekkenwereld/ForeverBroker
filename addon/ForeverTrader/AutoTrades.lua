-- ForeverTrader 1.0 Beta: automatic AH transaction evidence.
-- No manual commands, no HTTP, no protected purchase/post actions.
-- A confirmed BUY requires a game purchase event, item quantity and the
-- matching actual copper decrease. A confirmed SELL requires a seller invoice.
-- Everything ambiguous is an observation, NEVER manufactured realized profit.
ForeverTraderAutoTrades={}
local A=ForeverTraderAutoTrades
local state=nil
local function pos(n) return type(n)=='number' and n==math.floor(n) and n>0 and n<=9007199254740991 end
local function safe(x) return tostring(x or ''):gsub('[|;]','_'):gsub('[%c\\"]','_') end
local function recordError(kind,item,qty,amount,reason,at,itemName)
    if not state then return end
    local d=state.d
    d.autoTradeIssues=type(d.autoTradeIssues)=='table' and d.autoTradeIssues or {}
    local issue={
        at=at or state.clock(),realm=state.realm,character=state.character,
        kind=kind,item=item or 0,qty=qty or 0,amount=amount or 0,
        reason=reason or 'UNKNOWN',name=itemName or ''}
    d.autoTradeIssues[#d.autoTradeIssues+1]=issue
    while #d.autoTradeIssues>100 do table.remove(d.autoTradeIssues,1) end
    A.export()
    return issue
end
function A.export()
    if not state then return end
    local d=state.d
    local lines={'FTTRADE2'}
    local bytes=8
    for _,r in ipairs(d.autoTrades or {}) do
        if type(r)=='table' and #r==9 then
            local fields={}
            for j=1,9 do fields[j]=safe(r[j]) end
            local line=table.concat(fields,'|')
            if bytes+#line+1<=59000 then
                lines[#lines+1]=line;bytes=bytes+#line+1
            end
        end
    end
    d.autoTradesWire=table.concat(lines,';')
    local issues={'FTISSUE2'}
    bytes=8
    for _,r in ipairs(d.autoTradeIssues or {}) do
        if type(r)=='table' and not r.resolved then
            local line=table.concat({
                safe(r.at),safe(r.realm),safe(r.character),safe(r.kind),
                safe(r.item),safe(r.qty),safe(r.amount),safe(r.reason),
                safe(r.name)},'|')
            if bytes+#line+1<=19000 then
                issues[#issues+1]=line;bytes=bytes+#line+1
            end
        end
    end
    d.autoTradeIssuesWire=table.concat(issues,';')
end
local function commit(side,item,qty,total,source,at)
    if not state then return end
    if not pos(item) or item>10000000 or not pos(qty) or qty>100000 or
       not pos(total) then
        recordError(side,item,qty,total,'INCOMPLETE_EXECUTION',at)
        return
    end
    local d=state.d
    d.autoTrades=type(d.autoTrades)=='table' and d.autoTrades or {}
    d.autoTradeSeq=(tonumber(d.autoTradeSeq) or 0)+1
    local id=('AH_'..(state.realm..'_'..state.character):gsub('[^%w_.-]','_')..
             '_'..math.floor(at)..'_'..math.floor(d.autoTradeSeq))
    d.autoTrades[#d.autoTrades+1]={
        id,state.realm,state.character,math.floor(at),
        side,math.floor(item),math.floor(qty),math.floor(total),source}
    -- Keep the most recent observations; server stores older ones permanently.
    while #d.autoTrades>240 do table.remove(d.autoTrades,1) end
    A.export()
end
function A.login(d,realm,character,clock,money)
    if type(d)~='table' or type(realm)~='string' or type(character)~='string'
       or type(clock)~='function' then return end
    state={d=d,realm=realm,character=character,clock=clock,
           money=type(money)=='number' and money or nil,
           intents={},lastSpend=nil,seenPurchase={}}
    A.export()
end
function A.intent(item,qty,auctionID,kind)
    if not state or (item~=nil and not pos(item)) then return end
    local at=state.clock()
    -- A new purchase intent never authorizes a ledger record by itself.
    local entry={at=at,item=item,qty=pos(qty) and qty or nil,
                 auctionID=auctionID,kind=kind,confirmed=false,spent=nil}
    state.intents[#state.intents+1]=entry
    while #state.intents>15 do table.remove(state.intents,1) end
end
function A.onMoney(value)
    if not state or type(value)~='number' or value<0 then return end
    local previous=state.money
    state.money=value
    if not previous or previous<=value then return end
    local difference=previous-value
    local clock=state.clock()
    local matches={}
    for _,r in ipairs(state.intents) do
        if not r.spent and clock-r.at>=0 and clock-r.at<=12 then
            matches[#matches+1]=r
        end
    end
    if #matches==1 then
        matches[1].spent=difference
    else
        -- A gold change from a vendor, repair, posting deposit or another
        -- unrelated action must NEVER be labelled an AH purchase.
        state.lastSpend={at=clock,amount=difference}
    end
end
function A.purchased(item,qty,kind)
    if not state then return end
    local at=state.clock()
    local found=nil
    for i=#state.intents,1,-1 do
        local entry=state.intents[i]
        if at-entry.at>=0 and at-entry.at<=15
            and (not kind or not entry.kind or kind==entry.kind)
            and (not entry.confirmed or (entry.confirmedAt and
                at-entry.confirmedAt<=2))
            and (not pos(item) or not pos(entry.item) or entry.item==item) then
            found=entry;break
        end
    end
    if not found then
        if not pos(item) then
            recordError('BUY',0,qty,0,'PURCHASE_WITHOUT_ITEM_ID',at)
            return
        end
        found={item=item,qty=qty,at=at,kind=kind,confirmed=false}
        state.intents[#state.intents+1]=found
    end
    found.confirmed=true
    found.confirmedAt=at
    if pos(item) then found.item=item end
    if pos(qty) then found.qty=qty end
    -- Never use an arbitrary unrelated wallet delta to invent a cost.
end
function A.failed()
    if not state then return end
    for i=#state.intents,1,-1 do
        local r=state.intents[i]
        if not r.confirmed and state.clock()-r.at<=15 then
            table.remove(state.intents,i)
            return
        end
    end
end
function A.update(force)
    if not state then return end
    local at=state.clock()
    for i=#state.intents,1,-1 do
        local r=state.intents[i]
        if (r.confirmed and (force or at-r.confirmedAt>=2)) or at-r.at>=18 then
            if r.confirmed and pos(r.item) and pos(r.qty) and pos(r.spent) then
                commit('BUY',r.item,r.qty,r.spent,'AH_BUY',r.confirmedAt)
            elseif r.confirmed then
                recordError('BUY',r.item,r.qty,r.spent,
                            not pos(r.qty) and 'QUANTITY_UNKNOWN' or
                            'COST_UNCONFIRMED',r.confirmedAt)
            end
            table.remove(state.intents,i)
        end
    end
end
local function resolve(name)
    if not name or name=='' then return nil end
    -- Prefer an itemID from the client's own item cache, NEVER a guessed ID.
    if GetItemInfoInstant then
        local ok,id=pcall(GetItemInfoInstant,name)
        if ok and pos(id) then return id end
    end
    if C_Item and C_Item.GetItemInfoInstant then
        local ok,id=pcall(C_Item.GetItemInfoInstant,name)
        if ok and pos(id) then return id end
    end
    if GetItemInfo then
        local ok,_,link=pcall(GetItemInfo,name)
        local id=ok and type(link)=='string' and tonumber(link:match('item:(%d+)'))
        if pos(id) then return id end
    end
    return nil
end
function A.mailScan(getHeader,getInvoice,getCount)
    if not state or type(getHeader)~='function' or
       type(getInvoice)~='function' or type(getCount)~='function' then return end
    local ok,number=getCount()
    if not ok or type(number)~='number' or number<0 or number>300 then return end
    local d=state.d
    d.autoMailSeen=type(d.autoMailSeen)=='table' and d.autoMailSeen or {}
    local visited={}
    local now=state.clock()
    for i=1,number do
        local good,kind,name,_,bid,buyout,deposit,cut,_,_,_,qty=
            pcall(getInvoice,i)
        if good and kind=='seller' and type(name)=='string' then
            local valid,_,_,sender,subject,money,_,daysLeft=pcall(getHeader,i)
            if valid then
                local received=type(money)=='number' and money or 0
                local dep=type(deposit)=='number' and deposit or 0
                local net=received-dep
                -- Dedup with the actual expiry implied by daysLeft rather
                -- than an inbox index (which changes after collecting mail).
                -- Missing precise expiry: group equal invoices conservatively;
                -- they remain unresolved rather than double booked.
                local expiry=type(daysLeft)=='number' and daysLeft>=0 and
                    (now+daysLeft*86400) or nil
                local signature=safe(name)..':'..safe(qty)..':'..safe(net)..':'..
                    safe(sender)..':'..safe(subject)
                local matches=d.autoMailSeen[signature]
                if type(matches)~='table' then matches={};d.autoMailSeen[signature]=matches end
                local matched=false
                local existing=nil
                for _,prev in ipairs(matches) do
                    if not visited[prev] and
                      ((not expiry and not prev.expiry) or
                        (expiry and prev.expiry and math.abs(expiry-prev.expiry)<=5)) then
                        visited[prev]=true;matched=true;existing=prev;break
                    end
                end
                if not matched then
                    existing={expiry=expiry,at=now,status='new'}
                    matches[#matches+1]=existing
                    visited[existing]=true
                end
                if existing and existing.status~='resolved' then
                    local item=resolve(name)
                    if pos(item) and pos(qty) and pos(net) then
                        commit('SELL',item,qty,net,'AH_MAIL',now)
                        existing.status='resolved'
                        if existing.issue then existing.issue.resolved=true;A.export() end
                    elseif existing.status=='new' then
                        existing.issue=recordError('SELL',item,qty,net,
                            not pos(item) and 'MAIL_ITEM_UNRESOLVED' or
                            not pos(qty) and 'MAIL_QUANTITY_UNRESOLVED' or
                            'MAIL_NET_UNCONFIRMED',now,name)
                        existing.status='unresolved'
                    end
                end
            end
        end
    end
    -- Retain mail evidence for 50 days; do not delete valid recent invoices.
    for signature,rows in pairs(d.autoMailSeen) do
        for i=#rows,1,-1 do
            if type(rows[i].at)=='number' and now-rows[i].at>50*86400 then
                table.remove(rows,i)
            end
        end
        if #rows==0 then d.autoMailSeen[signature]=nil end
    end
end
function A.count()
    if not state then return 0,0 end
    local unresolved=0
    for _,issue in ipairs(state.d.autoTradeIssues or {}) do
        if not issue.resolved then unresolved=unresolved+1 end
    end
    return #(state.d.autoTrades or {}),unresolved
end
