-- Targeted searches, never purchases. Integer copper, stack totals vs divisible commodities.
ForeverTraderTarget={}
local T=ForeverTraderTarget
local function pos(n) return type(n)=='number' and n>0 and n==math.floor(n) and n<=9007199254740991 end
function T.read(api,kind,key,at)
    local id=kind=='item' and type(key)=='table' and key.itemID or kind=='commodity' and key
    if not pos(id) then return end
    if kind=='item' and ((key.itemLevel or 0)~=0 or (key.itemSuffix or 0)~=0 or (key.battlePetSpeciesID or 0)~=0) then return end
    local count,read,full
    if kind=='item' then count=api.GetNumItemSearchResults;read=api.GetItemSearchResultInfo;full=api.HasFullItemSearchResults
    else count=api.GetNumCommoditySearchResults;read=api.GetCommoditySearchResultInfo;full=api.HasFullCommoditySearchResults end
    if not count or not read or not full or not full(key) then return end
    local n=count(key);if type(n)~='number' or n<0 or n>10000 then return end
    local b={at=at,kind=kind,stacks={},complete=true}; local seen={}
    for i=1,n do
        local r=read(key,i);if not r or not pos(r.quantity) then return end
        if r.containsOwnerItem==nil or r.containsAccountItem==nil then return end -- unknown ownership: do not guess
        if not r.containsOwnerItem and not r.containsAccountItem then
            local cost=kind=='item' and r.buyoutAmount or (pos(r.unitPrice) and r.unitPrice*r.quantity or nil)
            if pos(cost) then
                if kind=='item' and r.auctionID then if seen[r.auctionID] then return end;seen[r.auctionID]=true end
                b.stacks[#b.stacks+1]={qty=r.quantity,cost=cost,divisible=kind=='commodity'}
            end
        end
    end
    table.sort(b.stacks,function(a,b) return a.cost/a.qty<b.cost/b.qty end)
    if #b.stacks>0 then b.floor=math.ceil(b.stacks[1].cost/b.stacks[1].qty) end
    return id,b
end
function T.record(id,b)
    -- bounded log: export only complete observations; aggregate equal stack types losslessly within limit.
    local rows,groups={},{};for _,r in ipairs(b.stacks) do
        local key=r.qty..':'..string.format('%.0f',r.cost);groups[key]=(groups[key] or 0)+1
    end
    for k,n in pairs(groups) do rows[#rows+1]=k..':'..n end;table.sort(rows)
    if #rows>2000 then return end -- live coach still uses full book; export not silently truncated
    return b.at..'|Alliance|3|1|'..id..'|'..b.kind..'|'..#rows..'|'..table.concat(rows,',')
end
function T.choose(plan,book,bags,listed,at,lastTry)
    if not plan or plan.expires<=at then return end
    local best,score
    for _,r in ipairs(plan.rows) do
        local b=book[r.id];local tried=lastTry[r.id] or 0
        if at-tried>=30 and (not b or not b.at or at-b.at>=120) then
            local rank=r.monitor and (-100 - (tried>0 and 1000 or 0) + math.min((at-tried)/3600,24)) or (((bags[r.id] or 0)>0 and 2000 or 0) + (r.target/r.max-1)*100/(1+r.hold/12))
            if ((bags[r.id] or 0)>0 or ((listed or {})[r.id] or 0)==0) and (not best or rank>score) then best,score=r,rank end
        end
    end
    return best
end
