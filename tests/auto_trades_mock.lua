-- End-to-end automatic AH evidence tests. No trading commands.
local tick=1800000000
local money=200000
local d={}
local cache={['Arcane Crystal']=12363,['Elemental Fire']=7068}
function GetItemInfoInstant(name) return cache[name] end
dofile('addon/ForeverTrader/AutoTrades.lua')
local A=ForeverTraderAutoTrades
local function clock()return tick end
A.login(d,'eu-2-110','Mage Pump',clock,money)
-- A buy is recorded ONLY if purchase event, quantity and exact gold
-- expenditure all agree. Hook intent alone means no transaction.
A.intent(12363,2,77,'item')
tick=tick+1
A.onMoney(160000)
A.purchased(12363,nil,'item')
tick=tick+3
A.update()
assert(#d.autoTrades==1,'confirmed item purchase must be recorded without commands')
assert(d.autoTrades[1][5]=='BUY' and d.autoTrades[1][6]==12363 and
       d.autoTrades[1][7]==2 and d.autoTrades[1][8]==40000)
-- A commodity emits both success and purchased; never double-count.
A.intent(7068,5,nil,'commodity')
A.onMoney(135000)
A.purchased(nil,nil,'commodity')
A.purchased(7068,5,'commodity')
tick=tick+3;A.update()
assert(#d.autoTrades==2,'commodity success + purchased must count once')
assert(d.autoTrades[2][7]==5 and d.autoTrades[2][8]==25000)
-- A gold decrease by itself is NOT an AH buy.
A.onMoney(125000)
tick=tick+20;A.update()
assert(#d.autoTrades==2,'repairs/posting deposits are not buys')
-- A purchase without a measured cost cannot fabricate realized profit.
A.purchased(12363,nil,'item')
tick=tick+3;A.update()
local count,issues=A.count()
assert(count==2 and issues==1,'missing quantity and cost must remain unresolved')

-- Seller invoice pays actual money including the returned deposit. The
-- buyout/bid listing is not a confirmed sale. Only seller invoice counts.
local mailbox={{name='Arcane Crystal',kind='seller_temp_invoice',
  qty=2,received=0,deposit=500,expiry=tick+12*86400}}
local function getCount()return true,#mailbox end
local function invoice(i)
  local m=mailbox[i]
  return m.kind,m.name,nil,0,15000,m.deposit,1000,0,nil,nil,m.qty
end
local function header(i)
  local m=mailbox[i]
  return nil,nil,'Auction House','Auction successful',m.received,0,
         (m.expiry-tick)/86400
end
A.mailScan(header,invoice,getCount)
assert(#d.autoTrades==2,'pending sale invoices are not completed sales')
mailbox[1].kind='seller';mailbox[1].received=14500
A.mailScan(header,invoice,getCount)
assert(#d.autoTrades==3,'completed seller invoice must automatically record sale')
assert(d.autoTrades[3][5]=='SELL' and d.autoTrades[3][6]==12363 and
       d.autoTrades[3][7]==2 and d.autoTrades[3][8]==14000,
       'seller proceeds should exclude returned refundable deposit')
tick=tick+10
A.mailScan(header,invoice,getCount)
assert(#d.autoTrades==3,'reopening mail must not double count a sale')
-- Two distinct equally priced invoices must remain distinct when their
-- respective message expirations differ.
mailbox[#mailbox+1]={kind='seller',name='Arcane Crystal',qty=2,
                     received=14500,deposit=500,expiry=tick+12*86400+3600}
A.mailScan(header,invoice,getCount)
assert(#d.autoTrades==4,'two matching amounts at different mail dates count twice')
-- Unknown item cache: visible unresolved sale, then automatic repair.
mailbox[#mailbox+1]={kind='seller',name='Uncached Crystal',qty=1,
                     received=10000,deposit=0,expiry=tick+12*86400+7200}
A.mailScan(header,invoice,getCount)
local _,unresolved=A.count()
assert(unresolved>=2 and #d.autoTrades==4,'unknown item should be visibly unresolved')
cache['Uncached Crystal']=12363
A.mailScan(header,invoice,getCount)
assert(#d.autoTrades==5,'late item cache resolves sale automatically')
local _,after=A.count()
assert(after==unresolved-1,'previously unresolved invoice warning should clear')
assert(d.autoTradesWire:find('FTTRADE2;',1,true),'persist automatic ledger for bridge')
assert(d.autoTradeIssuesWire:find('FTISSUE2;',1,true),'persist unresolved observations')
local issueRow=d.autoTradeIssuesWire:match('^FTISSUE2;([^;]+)')
assert(issueRow and select(2,issueRow:gsub('|',''))==8,
       'automatic unresolved row must have EXACTLY 9 fields, no Lua gsub count')
print('Automatic AH trade tests PASS')
