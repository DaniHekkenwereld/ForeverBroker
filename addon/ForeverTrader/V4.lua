-- ForeverTrader V4: safe per-character server plans and bounded session summaries.
-- This file uses only WoW addon APIs. No network, no execution of downloaded code.
ForeverTraderV4={}
local V=ForeverTraderV4

local function items(tab)
    local out={}
    if type(tab)=='table' then
        for i,q in pairs(tab) do
            if type(i)=='number' and type(q)=='number' and i>0 and q>0 then
                out[#out+1]=string.format('%d:%d',i,q)
            end
        end
    end
    table.sort(out)
    return table.concat(out,',')
end

local function clean(s)
    return tostring(s or ''):gsub('[|;]','_'):gsub('%c','_')
end

function V.entry(blob,key)
    if type(blob)~='string' or #blob>60000 or blob:sub(1,4)~='FT4!' then return nil end
    for row in blob:sub(5):gmatch('[^!]+') do
        local id,value=row:match('^(.-)%?(.*)$')
        if id==key then return value end
    end
    return nil
end

function V.plan(d,clock,realm,character,logic)
    if type(d)~='table' or not realm or not character then return nil,false end
    local code=V.entry(d.v4PlanBlob,realm..'#'..character)
    if code then
        local p=logic.plan(code,clock)
        if p then return p,true end
    end
    -- V4 must never silently fall back to a manually pasted/legacy plan.
    return nil,false
end

function V.actions(d,realm,character,display)
    local wire=V.entry(d and d.v4ActionsBlob,realm..'#'..character)
    if not wire then return 0 end
    local count=0
    for part in wire:gmatch('[^,]+') do
        local action,item,qty,maxBuy,target=part:match('^(%u[%u_]*):(%d+):(%d+):(%d+):(%d+)$')
        if not action then action,item,qty=part:match('^(%u[%u_]*):(%d+):(%d+)$') end
        if action and item and qty and count<8 then
            display(action,tonumber(item),tonumber(qty),tonumber(maxBuy),tonumber(target))
            count=count+1
        end
    end
    return count
end

local function wireSessions(d)
    local list={}
    for _,row in pairs(d.v4Sessions or {}) do
        if type(row)=='table' and type(row.ended)=='number' and type(row.started)=='number'
                and row.ended>=row.started and
                type(row.character)=='string' and #row.character>0 and
                not row.character:find('[|;]') then
            -- Ignore historical nameless sessions from older addon builds.
            list[#list+1]=row
        end
    end
    table.sort(list,function(a,b)return a.ended>b.ended end)
    local wire={'FTSESSION1'}
    local bytes=10
    for _,row in ipairs(list) do
        -- Normalize old realm labels to the configured EU PvP Alliance market
        -- so old observed sessions belong to the same scoped character.
        local fields={row.id,'eu-2-110',row.character,row.started,row.ended,
                      row.goldStart or '',row.goldEnd or '',
                      row.bagsStart or '',row.bagsEnd or ''}
        for j=1,#fields do fields[j]=clean(fields[j]) end
        local line=table.concat(fields,'|')
        if #wire>=41 or bytes+#line+1>48000 then break end
        wire[#wire+1]=line
        bytes=bytes+#line+1
    end
    d.sessionsWire=table.concat(wire,';')
end

function V.login(d,clock,realm,character,gold,bags)
    if not (type(d)=='table' and type(clock)=='number' and
            type(realm)=='string' and #realm>0 and
            type(character)=='string' and #character>0) then return end
    d.v4Sessions=type(d.v4Sessions)=='table' and d.v4Sessions or {}
    d.v4SessionCounter=(tonumber(d.v4SessionCounter) or 0)+1
    local id=(realm..':'..character..':'..clock..':'..d.v4SessionCounter):gsub('[^%w_.:-]','_')
    local row={id=id,realm=realm,character=character,started=clock,
               goldStart=type(gold)=='number' and gold or nil,
               bagsStart=type(bags)=='table' and items(bags) or nil}
    d.v4Sessions[id]=row
    d.v4ActiveSession=id
    wireSessions(d)
end

function V.logout(d,clock,gold,bags)
    if type(d)~='table' or type(d.v4Sessions)~='table' then return end
    local row=d.v4Sessions[d.v4ActiveSession]
    if row and not row.ended and type(clock)=='number' then
        row.ended=math.max(clock,row.started)
        row.goldEnd=type(gold)=='number' and gold or nil
        row.bagsEnd=type(bags)=='table' and items(bags) or nil
    end
    d.v4ActiveSession=nil
    -- Keep 70 latest completed sessions, and at most one incomplete session.
    local old={}
    for id,r in pairs(d.v4Sessions) do
        if type(r)=='table' and type(r.ended)=='number' then
            old[#old+1]={id=id,at=r.ended}
        end
    end
    table.sort(old,function(a,b)return a.at>b.at end)
    for i=71,#old do d.v4Sessions[old[i].id]=nil end
    wireSessions(d)
end
