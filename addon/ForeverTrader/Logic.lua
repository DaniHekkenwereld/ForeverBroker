-- Pure read-only coach rules, isolated for tests. All amounts are copper.
ForeverTraderLogic = {}
local L=ForeverTraderLogic
function L.plan(text,now)
    if type(text)~='string' or #text>12000 then return nil,'Ongeldige planning' end
    -- The WoW editbox may double | on paste; ignore copy/paste whitespace and BOM.
    text=text:gsub('^\239\187\191',''):gsub('||','|'):gsub('%s+','')
    local h,body=text:match('^(FT3|eu%-2%-110|%d+|%d+);(.*)$')
    if not h then return nil,'Verkeerde markt of formaat. Kopieer alleen de volledige FT3-regel.' end
    local made,expires=h:match('(%d+)|(%d+)$'); made,expires=tonumber(made),tonumber(expires)
    if made>now+60 or expires<=now or expires<=made or expires-made>7200 then return nil,'Planning verlopen of ongeldige tijd' end
    local list,seen={},{}
    for row in body:gmatch('[^;]+') do
        local i,p,q,s,hold=row:match('^(%d+):(%d+):(%d+):(%d+):(%d+)$')
        i,p,q,s,hold=tonumber(i),tonumber(p),tonumber(q),tonumber(s),tonumber(hold)
        local monitor=i and i>0 and p==0 and q==0 and s==0 and hold==0
        local validBuy=i and i>0 and p and p>0 and q and q>0 and q<=10000 and s and s>p and hold and hold<=168 and p<=100000000 and s<=100000000
        if (not monitor and not validBuy) or seen[i] or #list>=30 then return nil,'Ongeldige planregel' end
        seen[i]=true; list[#list+1]={id=i,max=p,qty=q,target=s,hold=hold,monitor=monitor}
    end
    return {made=made,expires=expires,rows=list}
end
function L.next(s,now)
    if not s.active then return 'OFF','Handelsmodus uit. /ft start' end
    if not s.market then return 'MARKET','Controleer EU PvP Alliance; /ft market bevestigt PvP.' end
    if s.mailOpen then
        if not s.mailKnown then return 'MAIL_WAIT','Inbox laden; even wachten.' end
        if s.ready>0 or s.attachments>0 then return 'COLLECT','Haal AH-gold en items op via de mailbox. Controleer zelf de berichten.' end
        if s.partial then return 'MAIL_WAIT','Inbox niet volledig geladen; controleer overige berichten.' end
        return 'RETURN','Mailbox klaar. Terug naar het Auction House.'
    end
    if s.bought or s.mailAlert then return 'MAIL','Ga naar de mailbox: aankoop of nieuw mail-signaal; inhoud nog niet bevestigd.' end
    if s.mailKnown and (s.attachments>0 or s.ready>=s.threshold or (s.ready>0 and s.cash<s.reserve)) then return 'MAIL','Ga naar de mailbox om items of beschikbaar gold op te halen.' end
    if s.eta and now>=s.eta+300 and s.pending>=s.threshold and (not s.lastMail or now-s.lastMail>=600) then return 'MAIL_CHECK','Verwachte betalingstijd verstreken; controleer de mailbox.' end
    if not s.lastMail or now-s.lastMail>=1800 then return 'MAIL_CHECK','Controleer de mailbox (laatste controle onbekend of ouder dan 30 min).'
    end
    if not s.ahOpen then return 'AH','Ga naar het Auction House.' end
    if s.searchPending then return 'SEARCH_WAIT','Gerichte resultaten worden geladen.' end
    if not s.targetMode and (not s.scanAt or now-s.scanAt>=900) then return 'SCAN','Doe een Full Scan met Auctionator als de server dit toestaat.' end
    if s.sellCount>0 then return 'SELL','Controleer verkoopadvies en plaats de geselecteerde items zelf.' end
    if s.buyCount>0 then return 'BUY','Controleer actuele stackprijs en koop zelf de geselecteerde items.' end
    if not s.planValid then return 'PLAN','Plak een actuele planning uit het desktopdashboard via /ft plan.' end
    if s.searchCandidate then return 'SEARCH','Klik Zoek volgend om de actuele orderboekprijs te controleren.' end
    if s.targetMode and (not s.scanAt or now-s.scanAt>=900) then return 'SCAN','Doe een Full Scan met Auctionator als de server dit toestaat.' end
    return 'WAIT','Geen passende actie. Wacht op nieuw mail-signaal of volgende scan.'
end
function L.matches(plan,book,bags,cash,reserve,now,scanAt,listed,targetMode)
    local buys,sells={},{}
    if not plan or now>=plan.expires or (not targetMode and (not scanAt or now-scanAt>=900)) then return buys,sells end
    local spend=math.max(0,cash-reserve)
    for _,r in ipairs(plan.rows) do
        local b=book[r.id]; if targetMode and (not b or not b.at or now<b.at or now-b.at>=120) then b=nil end; local owned=bags[r.id] or 0
        if not r.monitor and b and b.floor and owned>0 and r.hold==0 and b.floor>=r.target then sells[#sells+1]={id=r.id,qty=owned,target=r.target} end
        if not r.monitor and b and b.floor and b.floor<=r.max and owned==0 and ((listed or {})[r.id] or 0)==0 and spend>0 then
            local qty,cost=0,0; local cap=math.min(spend,math.floor(cash*.10))
            for _,v in ipairs(b.stacks) do
                if v.cost<=r.max*v.qty then
                    if v.divisible then
                        local unit=v.cost/v.qty;local take=math.min(v.qty,r.qty-qty,math.floor((cap-cost)/unit));if take>0 then qty=qty+take;cost=cost+take*unit end
                    elseif qty+v.qty<=r.qty and cost+v.cost<=cap then qty=qty+v.qty;cost=cost+v.cost end
                end
            end
            if qty>0 then buys[#buys+1]={id=r.id,qty=qty,max=r.max,target=r.target,cost=cost,hold=r.hold};spend=spend-cost end
        end
    end
    return buys,sells
end
