# 紙上交易回放 2026-01-01 → 2026-08-13（非真實券商；訊號 t 收盤、t+1 開盤成交）

## 2026-01-02
開始: cash=1000000 持倉=0 pending=0 equity=1000000
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 5，新排隊 0
排名:
(no signals)
收盤: cash=1000000 MV=0 equity=1000000 持倉=(空手) pending=(無)

## 2026-01-05
開始: cash=1000000 持倉=0 pending=0 equity=1000000
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 5，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    2330.TW      台積電         0.5226   0.0765    1660.14
*    6197.TW      佳必琪         0.4082   0.0613     155.35
QUEUE BUY 2330.TW 台積電 snr=0.5226 rs=0.0765 close=1660.14 → 下一根開盤成交
QUEUE BUY 6197.TW 佳必琪 snr=0.4082 rs=0.0613 close=155.35 → 下一根開盤成交
收盤: cash=1000000 MV=0 equity=1000000 持倉=(空手) pending=buy:2330.TW/breakout, buy:6197.TW/breakout

## 2026-01-06
開始: cash=1000000 持倉=0 pending=2 equity=1000000
PENDING_BUY 買不起1張，現金留存: 2330.TW alloc=500000 open=1635.29
BUY 6197.TW 佳必琪 3000股 @ 154.37 snr=0.4082 cash=536240
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 4 檔，空槽 4，新排隊 4
排名:
pick ticker       name           snr    rs_20      close
*    2330.TW      台積電         0.5434   0.0789    1694.93
*    2404.TW      漢唐          0.4495   0.1935     988.25
*    3711.TW      日月光投控       0.4525   0.0826     269.04
*    2345.TW      智邦          0.4579   0.1598    1230.26
QUEUE BUY 2330.TW 台積電 snr=0.5434 rs=0.0789 close=1694.93 → 下一根開盤成交
QUEUE BUY 2345.TW 智邦 snr=0.4579 rs=0.1598 close=1230.26 → 下一根開盤成交
QUEUE BUY 3711.TW 日月光投控 snr=0.4525 rs=0.0826 close=269.04 → 下一根開盤成交
QUEUE BUY 2404.TW 漢唐 snr=0.4495 rs=0.1935 close=988.25 → 下一根開盤成交
收盤: cash=536240 MV=441048 equity=977288 持倉=6197.TW 3000@154.4 pending=buy:2330.TW/breakout, buy:2345.TW/breakout, buy:3711.TW/breakout, buy:2404.TW/breakout

## 2026-01-07
開始: cash=536240 持倉=1 pending=4 equity=977288
PENDING_BUY 買不起1張，現金留存: 2330.TW alloc=134060 open=1655.17
PENDING_BUY 買不起1張，現金留存: 2345.TW alloc=134060 open=1255.07
PENDING_BUY 買不起1張，現金留存: 3711.TW alloc=134060 open=274.99
PENDING_BUY 買不起1張，現金留存: 2404.TW alloc=134060 open=988.25
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 4，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    3711.TW      日月光投控       0.4335   0.0826     272.51
QUEUE BUY 3711.TW 日月光投控 snr=0.4335 rs=0.0826 close=272.51 → 下一根開盤成交
收盤: cash=536240 MV=441048 equity=977288 持倉=6197.TW 3000@154.4 pending=buy:3711.TW/breakout

## 2026-01-08
開始: cash=536240 持倉=1 pending=1 equity=977288
BUY 3711.TW 日月光投控 1000股 @ 273.00 snr=0.4335 cash=262847
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 3，新排隊 0
排名:
(no signals)
收盤: cash=262847 MV=706190 equity=969036 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0 pending=(無)

## 2026-01-09
開始: cash=262847 持倉=2 pending=0 equity=969036
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 3，新排隊 0
排名:
(no signals)
收盤: cash=262847 MV=706173 equity=969020 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0 pending=(無)

## 2026-01-12
開始: cash=262847 持倉=2 pending=0 equity=969020
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 3，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    2360.TW      致茂電子        0.4365   0.1078     946.00
     3711.TW      日月光投控       0.4118   0.0667     280.44
QUEUE BUY 2360.TW 致茂電子 snr=0.4365 rs=0.1078 close=946.00 → 下一根開盤成交
收盤: cash=262847 MV=718544 equity=981390 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0 pending=buy:2360.TW/breakout

## 2026-01-13
開始: cash=262847 持倉=2 pending=1 equity=981390
PENDING_BUY 買不起1張，現金留存: 2360.TW alloc=262847 open=981.70
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 3 檔，空槽 3，新排隊 3
排名:
pick ticker       name           snr    rs_20      close
*    2330.TW      台積電         0.5476   0.0664    1699.90
*    2360.TW      致茂電子        0.4674   0.1334     975.75
*    2882.TW      國泰金         0.4591   0.0152      74.73
QUEUE BUY 2330.TW 台積電 snr=0.5476 rs=0.0664 close=1699.90 → 下一根開盤成交
QUEUE BUY 2360.TW 致茂電子 snr=0.4674 rs=0.1334 close=975.75 → 下一根開盤成交
QUEUE BUY 2882.TW 國泰金 snr=0.4591 rs=0.0152 close=74.73 → 下一根開盤成交
收盤: cash=262847 MV=717634 equity=980481 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0 pending=buy:2330.TW/breakout, buy:2360.TW/breakout, buy:2882.TW/breakout

## 2026-01-14
開始: cash=262847 持倉=2 pending=3 equity=980481
PENDING_BUY 買不起1張，現金留存: 2330.TW alloc=87616 open=1694.93
PENDING_BUY 買不起1張，現金留存: 2360.TW alloc=87616 open=981.70
BUY 2882.TW 國泰金 1000股 @ 74.83 snr=0.4591 cash=187912
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    2404.TW      漢唐          0.4039   0.1329    1114.20
QUEUE BUY 2404.TW 漢唐 snr=0.4039 rs=0.1329 close=1114.20 → 下一根開盤成交
收盤: cash=187912 MV=802064 equity=989976 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=buy:2404.TW/breakout

## 2026-01-15
開始: cash=187912 持倉=3 pending=1 equity=989976
PENDING_BUY 買不起1張，現金留存: 2404.TW alloc=187912 open=1114.20
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     3711.TW      日月光投控       0.7433   0.1846     295.80
收盤: cash=187912 MV=803570 equity=991482 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=(無)

## 2026-01-16
開始: cash=187912 持倉=3 pending=0 equity=991482
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 5 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    2330.TW      台積電         0.7045   0.0757    1729.73
*    3037.TW      欣興電子        0.5741   0.1514     273.44
     2308.TW      台達電         0.5635   0.1230    1119.15
     2303.TW      聯電          0.4286   0.0196      57.52
     3711.TW      日月光投控       0.7653   0.1871     300.75
QUEUE BUY 2330.TW 台積電 snr=0.7045 rs=0.0757 close=1729.73 → 下一根開盤成交
QUEUE BUY 3037.TW 欣興電子 snr=0.5741 rs=0.1514 close=273.44 → 下一根開盤成交
收盤: cash=187912 MV=809490 equity=997403 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=buy:2330.TW/breakout, buy:3037.TW/breakout

## 2026-01-19
開始: cash=187912 持倉=3 pending=2 equity=997403
PENDING_BUY 買不起1張，現金留存: 2330.TW alloc=93956 open=1714.82
PENDING_BUY 買不起1張，現金留存: 3037.TW alloc=93956 open=277.43
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 3 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    2330.TW      台積電         0.7174   0.0789    1749.61
*    3037.TW      欣興電子        0.7231   0.3023     300.38
     2303.TW      聯電          0.5351   0.0907      61.45
QUEUE BUY 3037.TW 欣興電子 snr=0.7231 rs=0.3023 close=300.38 → 下一根開盤成交
QUEUE BUY 2330.TW 台積電 snr=0.7174 rs=0.0789 close=1749.61 → 下一根開盤成交
收盤: cash=187912 MV=803249 equity=991162 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=buy:3037.TW/breakout, buy:2330.TW/breakout

## 2026-01-20
開始: cash=187912 持倉=3 pending=2 equity=991162
PENDING_BUY 買不起1張，現金留存: 3037.TW alloc=93956 open=296.39
PENDING_BUY 買不起1張，現金留存: 2330.TW alloc=93956 open=1729.73
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 4 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
     6217.TWO     中探針         0.4118   0.1166      63.80
*    2360.TW      致茂電子        0.6242   0.2433    1021.36
*    3037.TW      欣興電子        0.7209   0.2858     307.37
     2303.TW      聯電          0.6173   0.1906      66.66
QUEUE BUY 3037.TW 欣興電子 snr=0.7209 rs=0.2858 close=307.37 → 下一根開盤成交
QUEUE BUY 2360.TW 致茂電子 snr=0.6242 rs=0.2433 close=1021.36 → 下一根開盤成交
收盤: cash=187912 MV=802444 equity=990357 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=buy:3037.TW/breakout, buy:2360.TW/breakout

## 2026-01-21
開始: cash=187912 持倉=3 pending=2 equity=990357
PENDING_BUY 買不起1張，現金留存: 3037.TW alloc=93956 open=311.86
PENDING_BUY 買不起1張，現金留存: 2360.TW alloc=93956 open=989.63
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    3037.TW      欣興電子        0.7363   0.3458     320.34
QUEUE BUY 3037.TW 欣興電子 snr=0.7363 rs=0.3458 close=320.34 → 下一根開盤成交
收盤: cash=187912 MV=787800 equity=975712 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=buy:3037.TW/breakout

## 2026-01-22
開始: cash=187912 持倉=3 pending=1 equity=975712
PENDING_BUY 買不起1張，現金留存: 3037.TW alloc=187912 open=334.81
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    2308.TW      台達電         0.6371   0.1989    1238.52
QUEUE BUY 2308.TW 台達電 snr=0.6371 rs=0.1989 close=1238.52 → 下一根開盤成交
收盤: cash=187912 MV=803461 equity=991373 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=buy:2308.TW/breakout

## 2026-01-23
開始: cash=187912 持倉=3 pending=1 equity=991373
PENDING_BUY 買不起1張，現金留存: 2308.TW alloc=187912 open=1273.34
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 4 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    2449.TW      京元電子        0.6000   0.1817     271.82
     3044.TW      健鼎科技        0.4162  -0.0070     350.80
     2454.TW      聯發科         0.5132   0.0775    1620.32
*    2308.TW      台達電         0.6394   0.1929    1253.45
QUEUE BUY 2308.TW 台達電 snr=0.6394 rs=0.1929 close=1253.45 → 下一根開盤成交
QUEUE BUY 2449.TW 京元電子 snr=0.6000 rs=0.1817 close=271.82 → 下一根開盤成交
收盤: cash=187912 MV=812370 equity=1000282 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=buy:2308.TW/breakout, buy:2449.TW/breakout

## 2026-01-26
開始: cash=187912 持倉=3 pending=2 equity=1000282
PENDING_BUY 買不起1張，現金留存: 2308.TW alloc=93956 open=1213.65
PENDING_BUY 買不起1張，現金留存: 2449.TW alloc=93956 open=271.34
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 3 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    2449.TW      京元電子        0.6234   0.2112     282.26
     3044.TW      健鼎科技        0.4627   0.0211     359.56
*    2454.TW      聯發科         0.6109   0.1799    1759.49
QUEUE BUY 2449.TW 京元電子 snr=0.6234 rs=0.2112 close=282.26 → 下一根開盤成交
QUEUE BUY 2454.TW 聯發科 snr=0.6109 rs=0.1799 close=1759.49 → 下一根開盤成交
收盤: cash=187912 MV=817312 equity=1005224 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=buy:2449.TW/breakout, buy:2454.TW/breakout

## 2026-01-27
開始: cash=187912 持倉=3 pending=2 equity=1005224
PENDING_BUY 買不起1張，現金留存: 2449.TW alloc=93956 open=282.73
PENDING_BUY 買不起1張，現金留存: 2454.TW alloc=93956 open=1744.58
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 3 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    3037.TW      欣興電子        0.7784   0.4837     353.28
     3044.TW      健鼎科技        0.5644   0.0764     373.67
*    2303.TW      聯電          0.6436   0.4130      74.92
QUEUE BUY 3037.TW 欣興電子 snr=0.7784 rs=0.4837 close=353.28 → 下一根開盤成交
QUEUE BUY 2303.TW 聯電 snr=0.6436 rs=0.4130 close=74.92 → 下一根開盤成交
收盤: cash=187912 MV=803353 equity=991265 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=buy:3037.TW/breakout, buy:2303.TW/breakout

## 2026-01-28
開始: cash=187912 持倉=3 pending=2 equity=991265
PENDING_BUY 買不起1張，現金留存: 3037.TW alloc=93956 open=355.77
BUY 2303.TW 聯電 1000股 @ 78.26 snr=0.6436 cash=109540
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 3 檔，空槽 1，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
     2330.TW      台積電         0.5882   0.0547    1809.25
*    3037.TW      欣興電子        0.8043   0.5316     366.75
     3044.TW      健鼎科技        0.5984   0.0851     382.91
QUEUE BUY 3037.TW 欣興電子 snr=0.8043 rs=0.5316 close=366.75 → 下一根開盤成交
收盤: cash=109540 MV=883841 equity=993381 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8, 2303.TW 1000@78.3 pending=buy:3037.TW/breakout

## 2026-01-29
開始: cash=109540 持倉=4 pending=1 equity=993381
PENDING_BUY 買不起1張，現金留存: 3037.TW alloc=109540 open=364.25
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=109540 MV=874553 equity=984093 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8, 2303.TW 1000@78.3 pending=(無)

## 2026-01-30
開始: cash=109540 持倉=4 pending=0 equity=984093
QUEUE SELL 2303.TW sl (entry=78.26 H=64.30 L=60.56) → 下一根開盤成交
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 1，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    3037.TW      欣興電子        0.6660   0.6358     377.73
QUEUE BUY 3037.TW 欣興電子 snr=0.6660 rs=0.6358 close=377.73 → 下一根開盤成交
收盤: cash=109540 MV=844515 equity=954055 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8, 2303.TW 1000@78.3 pending=sell:2303.TW/sl, buy:3037.TW/breakout

## 2026-02-02
開始: cash=109540 持倉=4 pending=2 equity=954055
SELL 2303.TW 聯電 1000股 @ 61.25 reason=sl cash=170521
PENDING_BUY 買不起1張，現金留存: 3037.TW alloc=170521 open=374.23
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=170521 MV=788909 equity=959430 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=(無)

## 2026-02-03
開始: cash=170521 持倉=3 pending=0 equity=959430
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    3037.TW      欣興電子        0.5908   0.6173     384.21
*    3044.TW      健鼎科技        0.5597   0.2269     396.05
QUEUE BUY 3037.TW 欣興電子 snr=0.5908 rs=0.6173 close=384.21 → 下一根開盤成交
QUEUE BUY 3044.TW 健鼎科技 snr=0.5597 rs=0.2269 close=396.05 → 下一根開盤成交
收盤: cash=170521 MV=808026 equity=978547 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=buy:3037.TW/breakout, buy:3044.TW/breakout

## 2026-02-04
開始: cash=170521 持倉=3 pending=2 equity=978547
PENDING_BUY 買不起1張，現金留存: 3037.TW alloc=85260 open=370.24
PENDING_BUY 買不起1張，現金留存: 3044.TW alloc=85260 open=393.13
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=170521 MV=808499 equity=979020 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=(無)

## 2026-02-05
開始: cash=170521 持倉=3 pending=0 equity=979020
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=170521 MV=801735 equity=972256 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=(無)

## 2026-02-06
開始: cash=170521 持倉=3 pending=0 equity=972256
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=170521 MV=811469 equity=981990 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=(無)

## 2026-02-09
開始: cash=170521 持倉=3 pending=0 equity=981990
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    2454.TW      聯發科         0.4724   0.2063    1819.13
QUEUE BUY 2454.TW 聯發科 snr=0.4724 rs=0.2063 close=1819.13 → 下一根開盤成交
收盤: cash=170521 MV=826392 equity=996913 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=buy:2454.TW/breakout

## 2026-02-10
開始: cash=170521 持倉=3 pending=1 equity=996913
PENDING_BUY 買不起1張，現金留存: 2454.TW alloc=170521 open=1848.95
QUEUE SELL 3711.TW tp (entry=273.00 H=355.75 L=338.41) → 下一根開盤成交
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=170521 MV=843914 equity=1014435 持倉=6197.TW 3000@154.4, 3711.TW 1000@273.0, 2882.TW 1000@74.8 pending=sell:3711.TW/tp

## 2026-02-11
開始: cash=170521 持倉=3 pending=1 equity=1014435
SELL 3711.TW 日月光投控 1000股 @ 346.83 reason=tp cash=515816
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 3，新排隊 0
排名:
(no signals)
收盤: cash=515816 MV=498018 equity=1013834 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8 pending=(無)

## 2026-02-23
開始: cash=515816 持倉=2 pending=0 equity=1013834
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 3，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    3037.TW      欣興電子        0.4561   0.5291     404.67
*    2891.TW      中信金         0.4023  -0.0267      51.97
QUEUE BUY 3037.TW 欣興電子 snr=0.4561 rs=0.5291 close=404.67 → 下一根開盤成交
QUEUE BUY 2891.TW 中信金 snr=0.4023 rs=-0.0267 close=51.97 → 下一根開盤成交
收盤: cash=515816 MV=504671 equity=1020487 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8 pending=buy:3037.TW/breakout, buy:2891.TW/breakout

## 2026-02-24
開始: cash=515816 持倉=2 pending=2 equity=1020487
PENDING_BUY 買不起1張，現金留存: 3037.TW alloc=257908 open=409.66
BUY 2891.TW 中信金 4000股 @ 52.16 snr=0.4023 cash=306859
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    2330.TW      台積電         0.4206   0.0245    1953.40
*    3037.TW      欣興電子        0.4804   0.5229     445.09
QUEUE BUY 3037.TW 欣興電子 snr=0.4804 rs=0.5229 close=445.09 → 下一根開盤成交
QUEUE BUY 2330.TW 台積電 snr=0.4206 rs=0.0245 close=1953.40 → 下一根開盤成交
收盤: cash=306859 MV=718173 equity=1025032 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2 pending=buy:3037.TW/breakout, buy:2330.TW/breakout

## 2026-02-25
開始: cash=306859 持倉=3 pending=2 equity=1025032
PENDING_BUY 買不起1張，現金留存: 3037.TW alloc=153430 open=453.57
PENDING_BUY 買不起1張，現金留存: 2330.TW alloc=153430 open=1983.22
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 6 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    2330.TW      台積電         0.4513   0.0256    2003.10
     6217.TWO     中探針         0.4024   0.3497      85.20
*    3037.TW      欣興電子        0.4585   0.4040     457.56
     2308.TW      台達電         0.4406   0.1620    1427.54
     3711.TW      日月光投控       0.4306   0.1817     385.48
     2395.TW      研華          0.4381   0.0410     325.99
QUEUE BUY 3037.TW 欣興電子 snr=0.4585 rs=0.4040 close=457.56 → 下一根開盤成交
QUEUE BUY 2330.TW 台積電 snr=0.4513 rs=0.0256 close=2003.10 → 下一根開盤成交
收盤: cash=306859 MV=723111 equity=1029970 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2 pending=buy:3037.TW/breakout, buy:2330.TW/breakout

## 2026-02-26
開始: cash=306859 持倉=3 pending=2 equity=1029970
PENDING_BUY 買不起1張，現金留存: 3037.TW alloc=153430 open=457.06
PENDING_BUY 買不起1張，現金留存: 2330.TW alloc=153430 open=1988.19
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 6 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
     6217.TWO     中探針         0.4253   0.3536      93.70
*    2360.TW      致茂電子        0.4902   0.2247    1368.43
     3037.TW      欣興電子        0.4826   0.4482     480.52
     2454.TW      聯發科         0.4842   0.1947    1933.45
     2891.TW      中信金         0.4667  -0.0190      53.90
*    2395.TW      研華          0.5567   0.0867     329.42
QUEUE BUY 2395.TW 研華 snr=0.5567 rs=0.0867 close=329.42 → 下一根開盤成交
QUEUE BUY 2360.TW 致茂電子 snr=0.4902 rs=0.2247 close=1368.43 → 下一根開盤成交
收盤: cash=306859 MV=746833 equity=1053692 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2 pending=buy:2395.TW/breakout, buy:2360.TW/breakout

## 2026-03-02
開始: cash=306859 持倉=3 pending=2 equity=1053692
PENDING_BUY 買不起1張，現金留存: 2395.TW alloc=153430 open=332.84
PENDING_BUY 買不起1張，現金留存: 2360.TW alloc=153430 open=1408.09
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    6217.TWO     中探針         0.5469   0.5654     103.00
*    2360.TW      致茂電子        0.6388   0.3994    1502.29
QUEUE BUY 2360.TW 致茂電子 snr=0.6388 rs=0.3994 close=1502.29 → 下一根開盤成交
QUEUE BUY 6217.TWO 中探針 snr=0.5469 rs=0.5654 close=103.00 → 下一根開盤成交
收盤: cash=306859 MV=736995 equity=1043854 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2 pending=buy:2360.TW/breakout, buy:6217.TWO/breakout

## 2026-03-03
開始: cash=306859 持倉=3 pending=2 equity=1043854
PENDING_BUY 買不起1張，現金留存: 2360.TW alloc=153430 open=1546.92
BUY 6217.TWO 中探針 1000股 @ 100.50 snr=0.5469 cash=206216
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=206216 MV=821317 equity=1027533 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 1000@100.5 pending=(無)

## 2026-03-04
開始: cash=206216 持倉=4 pending=0 equity=1027533
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=206216 MV=776446 equity=982661 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 1000@100.5 pending=(無)

## 2026-03-05
開始: cash=206216 持倉=4 pending=0 equity=982661
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=206216 MV=816152 equity=1022367 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 1000@100.5 pending=(無)

## 2026-03-06
開始: cash=206216 持倉=4 pending=0 equity=1022367
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 1，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
     6217.TWO     中探針         0.4734   0.6733     111.00
*    2395.TW      研華          0.4985   0.2512     367.10
QUEUE BUY 2395.TW 研華 snr=0.4985 rs=0.2512 close=367.10 → 下一根開盤成交
收盤: cash=206216 MV=816366 equity=1022582 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 1000@100.5 pending=buy:2395.TW/breakout

## 2026-03-09
開始: cash=206216 持倉=4 pending=1 equity=1022582
PENDING_BUY 買不起1張，現金留存: 2395.TW alloc=206216 open=338.72
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=206216 MV=792005 equity=998221 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 1000@100.5 pending=(無)

## 2026-03-10
開始: cash=206216 持倉=4 pending=0 equity=998221
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=206216 MV=830753 equity=1036968 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 1000@100.5 pending=(無)

## 2026-03-11
開始: cash=206216 持倉=4 pending=0 equity=1036968
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 1，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
     6217.TWO     中探針         0.4648   0.8352     113.00
*    2357.TW      華碩          0.4074   0.1135     548.96
QUEUE BUY 2357.TW 華碩 snr=0.4074 rs=0.1135 close=548.96 → 下一根開盤成交
收盤: cash=206216 MV=863481 equity=1069697 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 1000@100.5 pending=buy:2357.TW/breakout

## 2026-03-12
開始: cash=206216 持倉=4 pending=1 equity=1069697
PENDING_BUY 買不起1張，現金留存: 2357.TW alloc=206216 open=555.54
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 1，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     6217.TWO     中探針         0.5187   1.0434     124.00
收盤: cash=206216 MV=894654 equity=1100870 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 1000@100.5 pending=(無)

## 2026-03-13
開始: cash=206216 持倉=4 pending=0 equity=1100870
QUEUE SELL 6217.TWO tp (entry=100.50 H=136.00 L=129.00) → 下一根開盤成交
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 1，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     6217.TWO     中探針         0.5414   1.0646     136.00
收盤: cash=206216 MV=919113 equity=1125329 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 1000@100.5 pending=sell:6217.TWO/tp

## 2026-03-16
開始: cash=206216 持倉=4 pending=1 equity=1125329
SELL 6217.TWO 中探針 1000股 @ 145.50 reason=tp cash=351072
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    6217.TWO     中探針         0.5890   1.2231     138.50
QUEUE BUY 6217.TWO 中探針 snr=0.5890 rs=1.2231 close=138.50 → 下一根開盤成交
收盤: cash=351072 MV=786103 equity=1137175 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2 pending=buy:6217.TWO/breakout

## 2026-03-17
開始: cash=351072 持倉=3 pending=1 equity=1137175
BUY 6217.TWO 中探針 2000股 @ 140.00 snr=0.589 cash=70673
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 1，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     6197.TW      佳必琪         0.4270   0.1959     187.69
     6217.TWO     中探針         0.6503   1.4949     152.00
收盤: cash=70673 MV=1141778 equity=1212451 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 2000@140.0 pending=(無)

## 2026-03-18
開始: cash=70673 持倉=4 pending=0 equity=1212451
QUEUE SELL 6197.TW tp (entry=154.37 H=193.08 L=182.79) → 下一根開盤成交
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 1，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     6197.TW      佳必琪         0.5027   0.2324     191.12
     6217.TWO     中探針         0.7141   1.8698     167.00
收盤: cash=70673 MV=1183805 equity=1254478 持倉=6197.TW 3000@154.4, 2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 2000@140.0 pending=sell:6197.TW/tp

## 2026-03-19
開始: cash=70673 持倉=4 pending=1 equity=1254478
SELL 6197.TW 佳必琪 3000股 @ 188.18 reason=tp cash=632716
QUEUE SELL 6217.TWO tp (entry=140.00 H=183.50 L=176.00) → 下一根開盤成交
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     6217.TWO     中探針         0.7329   1.9105     183.50
收盤: cash=632716 MV=635148 equity=1267864 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 2000@140.0 pending=sell:6217.TWO/tp

## 2026-03-20
開始: cash=632716 持倉=3 pending=1 equity=1267864
SELL 6217.TWO 中探針 2000股 @ 185.00 reason=tp cash=1001078
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 3，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    6217.TWO     中探針         0.7403   1.9545     190.00
QUEUE BUY 6217.TWO 中探針 snr=0.7403 rs=1.9545 close=190.00 → 下一根開盤成交
收盤: cash=1001078 MV=270463 equity=1271541 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2 pending=buy:6217.TWO/breakout

## 2026-03-23
開始: cash=1001078 持倉=2 pending=1 equity=1271541
BUY 6217.TWO 中探針 5000股 @ 171.00 snr=0.7403 cash=144860
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=144860 MV=1122859 equity=1267719 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 5000@171.0 pending=(無)

## 2026-03-24
開始: cash=144860 持倉=3 pending=0 equity=1267719
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=144860 MV=1038919 equity=1183779 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 5000@171.0 pending=(無)

## 2026-03-25
開始: cash=144860 持倉=3 pending=0 equity=1183779
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=144860 MV=1117584 equity=1262444 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 5000@171.0 pending=(無)

## 2026-03-26
開始: cash=144860 持倉=3 pending=0 equity=1262444
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=144860 MV=1147776 equity=1292636 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 5000@171.0 pending=(無)

## 2026-03-27
開始: cash=144860 持倉=3 pending=0 equity=1292636
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=144860 MV=1192583 equity=1337443 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 5000@171.0 pending=(無)

## 2026-03-30
開始: cash=144860 持倉=3 pending=0 equity=1337443
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=144860 MV=1175647 equity=1320507 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 5000@171.0 pending=(無)

## 2026-03-31
開始: cash=144860 持倉=3 pending=0 equity=1320507
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=144860 MV=1083236 equity=1228096 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 5000@171.0 pending=(無)

## 2026-04-01
開始: cash=144860 持倉=3 pending=0 equity=1228096
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=144860 MV=1174038 equity=1318898 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 5000@171.0 pending=(無)

## 2026-04-02
開始: cash=144860 持倉=3 pending=0 equity=1318898
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=144860 MV=1242027 equity=1386887 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 5000@171.0 pending=(無)

## 2026-04-07
開始: cash=144860 持倉=3 pending=0 equity=1386887
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=144860 MV=1284637 equity=1429497 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 5000@171.0 pending=(無)

## 2026-04-08
開始: cash=144860 持倉=3 pending=0 equity=1429497
QUEUE SELL 6217.TWO tp (entry=171.00 H=217.50 L=195.00) → 下一根開盤成交
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     2891.TW      中信金         0.4074   0.0253      54.48
收盤: cash=144860 MV=1266671 equity=1411531 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 6217.TWO 5000@171.0 pending=sell:6217.TWO/tp

## 2026-04-09
開始: cash=144860 持倉=3 pending=1 equity=1411531
SELL 6217.TWO 中探針 5000股 @ 191.00 reason=tp cash=1095634
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 3，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    2379.TW      瑞昱          0.4194   0.0493     512.00
QUEUE BUY 2379.TW 瑞昱 snr=0.4194 rs=0.0493 close=512.00 → 下一根開盤成交
收盤: cash=1095634 MV=282422 equity=1378056 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2 pending=buy:2379.TW/breakout

## 2026-04-10
開始: cash=1095634 持倉=2 pending=1 equity=1378056
BUY 2379.TW 瑞昱 2000股 @ 510.00 snr=0.4194 cash=74181
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    6217.TWO     中探針         0.5031   1.0547     236.50
QUEUE BUY 6217.TWO 中探針 snr=0.5031 rs=1.0547 close=236.50 → 下一根開盤成交
收盤: cash=74181 MV=1294660 equity=1368841 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:6217.TWO/breakout

## 2026-04-13
開始: cash=74181 持倉=3 pending=1 equity=1368841
PENDING_BUY 買不起1張，現金留存: 6217.TWO alloc=74181 open=237.00
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    6217.TWO     中探針         0.4874   0.8796     240.00
     2379.TW      瑞昱          0.4000   0.0541     525.00
QUEUE BUY 6217.TWO 中探針 snr=0.4874 rs=0.8796 close=240.00 → 下一根開盤成交
收盤: cash=74181 MV=1325091 equity=1399272 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:6217.TWO/breakout

## 2026-04-14
開始: cash=74181 持倉=3 pending=1 equity=1399272
PENDING_BUY 買不起1張，現金留存: 6217.TWO alloc=74181 open=237.00
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=74181 MV=1322996 equity=1397176 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=(無)

## 2026-04-15
開始: cash=74181 持倉=3 pending=0 equity=1397176
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 3 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    3711.TW      日月光投控       0.4467   0.2216     442.46
*    3008.TW      大立光         0.4586   0.1487    2794.48
     2345.TW      智邦          0.4427   0.3159    1954.53
QUEUE BUY 3008.TW 大立光 snr=0.4586 rs=0.1487 close=2794.48 → 下一根開盤成交
QUEUE BUY 3711.TW 日月光投控 snr=0.4467 rs=0.2216 close=442.46 → 下一根開盤成交
收盤: cash=74181 MV=1324032 equity=1398213 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:3008.TW/breakout, buy:3711.TW/breakout

## 2026-04-16
開始: cash=74181 持倉=3 pending=2 equity=1398213
PENDING_BUY 買不起1張，現金留存: 3008.TW alloc=37090 open=2809.34
PENDING_BUY 買不起1張，現金留存: 3711.TW alloc=37090 open=445.92
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     2379.TW      瑞昱          0.4478   0.0276     540.00
收盤: cash=74181 MV=1357601 equity=1431782 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=(無)

## 2026-04-17
開始: cash=74181 持倉=3 pending=0 equity=1431782
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    2360.TW      致茂電子        0.4233   0.3694    2236.09
QUEUE BUY 2360.TW 致茂電子 snr=0.4233 rs=0.3694 close=2236.09 → 下一根開盤成交
收盤: cash=74181 MV=1339216 equity=1413397 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2360.TW/breakout

## 2026-04-20
開始: cash=74181 持倉=3 pending=1 equity=1413397
PENDING_BUY 買不起1張，現金留存: 2360.TW alloc=74181 open=2047.68
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    2308.TW      台達電         0.4218   0.2088    1890.12
*    2303.TW      聯電          0.4483   0.2130      75.61
QUEUE BUY 2303.TW 聯電 snr=0.4483 rs=0.2130 close=75.61 → 下一根開盤成交
QUEUE BUY 2308.TW 台達電 snr=0.4218 rs=0.2088 close=1890.12 → 下一根開盤成交
收盤: cash=74181 MV=1352830 equity=1427011 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2303.TW/breakout, buy:2308.TW/breakout

## 2026-04-21
開始: cash=74181 持倉=3 pending=2 equity=1427011
PENDING_BUY 買不起1張，現金留存: 2303.TW alloc=37090 open=76.69
PENDING_BUY 買不起1張，現金留存: 2308.TW alloc=37090 open=1939.86
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 6 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
     3044.TW      健鼎科技        0.4175   0.1021     432.05
     2454.TW      聯發科         0.4239   0.1083    2077.59
*    2308.TW      台達電         0.4696   0.2450    2004.52
*    2382.TW      廣達          0.4330   0.0782     326.08
     2345.TW      智邦          0.4085   0.2392    2172.80
     2379.TW      瑞昱          0.4689   0.0280     551.00
QUEUE BUY 2308.TW 台達電 snr=0.4696 rs=0.2450 close=2004.52 → 下一根開盤成交
QUEUE BUY 2382.TW 廣達 snr=0.4330 rs=0.0782 close=326.08 → 下一根開盤成交
收盤: cash=74181 MV=1379314 equity=1453494 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2308.TW/breakout, buy:2382.TW/breakout

## 2026-04-22
開始: cash=74181 持倉=3 pending=2 equity=1453494
PENDING_BUY 買不起1張，現金留存: 2308.TW alloc=37090 open=2029.39
PENDING_BUY 買不起1張，現金留存: 2382.TW alloc=37090 open=328.00
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 6 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
     6217.TWO     中探針         0.4951   0.5764     296.50
     3037.TW      欣興電子        0.4255   0.2773     714.54
*    3044.TW      健鼎科技        0.5186   0.1368     447.14
*    2454.TW      聯發科         0.6381   0.2547    2281.37
     2379.TW      瑞昱          0.6151   0.0501     567.00
     3034.TW      聯詠          0.4532   0.0051     414.15
QUEUE BUY 2454.TW 聯發科 snr=0.6381 rs=0.2547 close=2281.37 → 下一根開盤成交
QUEUE BUY 3044.TW 健鼎科技 snr=0.5186 rs=0.1368 close=447.14 → 下一根開盤成交
收盤: cash=74181 MV=1413628 equity=1487809 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2454.TW/breakout, buy:3044.TW/breakout

## 2026-04-23
開始: cash=74181 持倉=3 pending=2 equity=1487809
PENDING_BUY 買不起1張，現金留存: 2454.TW alloc=37090 open=2311.19
PENDING_BUY 買不起1張，現金留存: 3044.TW alloc=37090 open=472.44
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    2317.TW      鴻海          0.4110  -0.0026     218.49
QUEUE BUY 2317.TW 鴻海 snr=0.4110 rs=-0.0026 close=218.49 → 下一根開盤成交
收盤: cash=74181 MV=1359481 equity=1433661 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2317.TW/breakout

## 2026-04-24
開始: cash=74181 持倉=3 pending=1 equity=1433661
PENDING_BUY 買不起1張，現金留存: 2317.TW alloc=74181 open=220.44
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 4 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
     2330.TW      台積電         0.4595   0.0200    2179.19
*    3037.TW      欣興電子        0.5691   0.3970     788.39
*    2454.TW      聯發科         0.6059   0.3388    2420.54
     6669.TW      緯穎          0.4060   0.0684    4504.54
QUEUE BUY 2454.TW 聯發科 snr=0.6059 rs=0.3388 close=2420.54 → 下一根開盤成交
QUEUE BUY 3037.TW 欣興電子 snr=0.5691 rs=0.3970 close=788.39 → 下一根開盤成交
收盤: cash=74181 MV=1354349 equity=1428529 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2454.TW/breakout, buy:3037.TW/breakout

## 2026-04-27
開始: cash=74181 持倉=3 pending=2 equity=1428529
PENDING_BUY 買不起1張，現金留存: 2454.TW alloc=37090 open=2455.33
PENDING_BUY 買不起1張，現金留存: 3037.TW alloc=37090 open=833.29
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 3 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
     2330.TW      台積電         0.5215   0.0426    2258.97
*    3037.TW      欣興電子        0.6195   0.4830     837.29
*    6669.TW      緯穎          0.6738   0.2229    4752.36
QUEUE BUY 6669.TW 緯穎 snr=0.6738 rs=0.2229 close=4752.36 → 下一根開盤成交
QUEUE BUY 3037.TW 欣興電子 snr=0.6195 rs=0.4830 close=837.29 → 下一根開盤成交
收盤: cash=74181 MV=1385191 equity=1459372 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:6669.TW/breakout, buy:3037.TW/breakout

## 2026-04-28
開始: cash=74181 持倉=3 pending=2 equity=1459372
PENDING_BUY 買不起1張，現金留存: 6669.TW alloc=37090 open=4786.38
PENDING_BUY 買不起1張，現金留存: 3037.TW alloc=37090 open=862.23
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 3 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    2454.TW      聯發科         0.6913   0.4563    2599.47
*    2308.TW      台達電         0.5146   0.2137    2113.95
     2345.TW      智邦          0.4238   0.1932    2276.98
QUEUE BUY 2454.TW 聯發科 snr=0.6913 rs=0.4563 close=2599.47 → 下一根開盤成交
QUEUE BUY 2308.TW 台達電 snr=0.5146 rs=0.2137 close=2113.95 → 下一根開盤成交
收盤: cash=74181 MV=1399698 equity=1473879 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2454.TW/breakout, buy:2308.TW/breakout

## 2026-04-29
開始: cash=74181 持倉=3 pending=2 equity=1473879
PENDING_BUY 買不起1張，現金留存: 2454.TW alloc=37090 open=2534.85
PENDING_BUY 買不起1張，現金留存: 2308.TW alloc=37090 open=2029.39
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 3 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    6197.TW      佳必琪         0.4356   0.0621     202.39
*    2308.TW      台達電         0.5620   0.2492    2153.74
     2882.TW      國泰金         0.5125  -0.0922      75.89
QUEUE BUY 2308.TW 台達電 snr=0.5620 rs=0.2492 close=2153.74 → 下一根開盤成交
QUEUE BUY 6197.TW 佳必琪 snr=0.4356 rs=0.0621 close=202.39 → 下一根開盤成交
收盤: cash=74181 MV=1382692 equity=1456873 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2308.TW/breakout, buy:6197.TW/breakout

## 2026-04-30
開始: cash=74181 持倉=3 pending=2 equity=1456873
PENDING_BUY 買不起1張，現金留存: 2308.TW alloc=37090 open=2208.45
PENDING_BUY 買不起1張，現金留存: 6197.TW alloc=37090 open=203.37
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    6197.TW      佳必琪         0.5025   0.0852     203.86
QUEUE BUY 6197.TW 佳必琪 snr=0.5025 rs=0.0852 close=203.86 → 下一根開盤成交
收盤: cash=74181 MV=1350255 equity=1424436 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:6197.TW/breakout

## 2026-05-04
開始: cash=74181 持倉=3 pending=1 equity=1424436
PENDING_BUY 買不起1張，現金留存: 6197.TW alloc=74181 open=215.62
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 8 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
     6197.TW      佳必琪         0.5721   0.1749     223.95
     2360.TW      致茂電子        0.4023   0.2078    2290.63
*    3037.TW      欣興電子        0.7278   0.6379     909.14
*    2454.TW      聯發科         0.8240   0.7321    2852.95
     2303.TW      聯電          0.4508   0.1876      79.83
     3711.TW      日月光投控       0.6560   0.2273     520.24
     2395.TW      研華          0.4776  -0.0336     386.68
     2345.TW      智邦          0.5298   0.2820    2485.33
QUEUE BUY 2454.TW 聯發科 snr=0.8240 rs=0.7321 close=2852.95 → 下一根開盤成交
QUEUE BUY 3037.TW 欣興電子 snr=0.7278 rs=0.6379 close=909.14 → 下一根開盤成交
收盤: cash=74181 MV=1333604 equity=1407784 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2454.TW/breakout, buy:3037.TW/breakout

## 2026-05-05
開始: cash=74181 持倉=3 pending=2 equity=1407784
PENDING_BUY 買不起1張，現金留存: 2454.TW alloc=37090 open=3136.26
PENDING_BUY 買不起1張，現金留存: 3037.TW alloc=37090 open=897.16
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 6 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    6197.TW      佳必琪         0.6935   0.2944     238.66
     2449.TW      京元電子        0.5000   0.1151     335.86
     2317.TW      鴻海          0.5849  -0.0107     232.57
*    2454.TW      聯發科         0.8492   0.9019    3136.26
     2303.TW      聯電          0.5796   0.2987      81.70
     2395.TW      研華          0.5703  -0.0260     388.15
QUEUE BUY 2454.TW 聯發科 snr=0.8492 rs=0.9019 close=3136.26 → 下一根開盤成交
QUEUE BUY 6197.TW 佳必琪 snr=0.6935 rs=0.2944 close=238.66 → 下一根開盤成交
收盤: cash=74181 MV=1346883 equity=1421064 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2454.TW/breakout, buy:6197.TW/breakout

## 2026-05-06
開始: cash=74181 持倉=3 pending=2 equity=1421064
PENDING_BUY 買不起1張，現金留存: 2454.TW alloc=37090 open=3449.39
PENDING_BUY 買不起1張，現金留存: 6197.TW alloc=37090 open=253.36
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 9 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
     2360.TW      致茂電子        0.4270   0.2556    2325.33
*    2317.TW      鴻海          0.6593   0.0745     244.71
*    2454.TW      聯發科         0.8673   1.0953    3409.63
     2303.TW      聯電          0.6073   0.3297      89.86
     2395.TW      研華          0.6214   0.0318     400.88
     2357.TW      華碩          0.5097  -0.0944     591.26
     3231.TW      緯創          0.4423  -0.0518     141.32
     3034.TW      聯詠          0.4071  -0.0898     422.76
     2301.TW      光寶科         0.4315   0.0602     185.00
QUEUE BUY 2454.TW 聯發科 snr=0.8673 rs=1.0953 close=3409.63 → 下一根開盤成交
QUEUE BUY 2317.TW 鴻海 snr=0.6593 rs=0.0745 close=244.71 → 下一根開盤成交
收盤: cash=74181 MV=1374960 equity=1449141 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2454.TW/breakout, buy:2317.TW/breakout

## 2026-05-07
開始: cash=74181 持倉=3 pending=2 equity=1449141
PENDING_BUY 買不起1張，現金留存: 2454.TW alloc=37090 open=3409.63
PENDING_BUY 買不起1張，現金留存: 2317.TW alloc=37090 open=247.63
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 7 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
     2317.TW      鴻海          0.6265   0.0517     246.17
*    2308.TW      台達電         0.6440   0.1630    2268.14
     2303.TW      聯電          0.6285   0.3940      94.88
*    2395.TW      研華          0.6431   0.0677     434.65
     2357.TW      華碩          0.5033  -0.0693     600.66
     3034.TW      聯詠          0.4256  -0.0492     433.78
     2301.TW      光寶科         0.4563   0.0940     203.50
QUEUE BUY 2308.TW 台達電 snr=0.6440 rs=0.1630 close=2268.14 → 下一根開盤成交
QUEUE BUY 2395.TW 研華 snr=0.6431 rs=0.0677 close=434.65 → 下一根開盤成交
收盤: cash=74181 MV=1371035 equity=1445216 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2308.TW/breakout, buy:2395.TW/breakout

## 2026-05-08
開始: cash=74181 持倉=3 pending=2 equity=1445216
PENDING_BUY 買不起1張，現金留存: 2308.TW alloc=37090 open=2218.40
PENDING_BUY 買不起1張，現金留存: 2395.TW alloc=37090 open=440.53
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 6 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    2454.TW      聯發科         0.8689   1.1113    3608.44
     2881.TW      富邦金         0.4767  -0.1008      93.53
*    2395.TW      研華          0.7119   0.1758     466.47
     6669.TW      緯穎          0.5704   0.2591    5053.64
     3034.TW      聯詠          0.5427   0.0531     476.87
     2301.TW      光寶科         0.4804   0.1227     204.00
QUEUE BUY 2454.TW 聯發科 snr=0.8689 rs=1.1113 close=3608.44 → 下一根開盤成交
QUEUE BUY 2395.TW 研華 snr=0.7119 rs=0.1758 close=466.47 → 下一根開盤成交
收盤: cash=74181 MV=1478772 equity=1552953 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2454.TW/breakout, buy:2395.TW/breakout

## 2026-05-11
開始: cash=74181 持倉=3 pending=2 equity=1552953
PENDING_BUY 買不起1張，現金留存: 2454.TW alloc=37090 open=3553.77
PENDING_BUY 買不起1張，現金留存: 2395.TW alloc=37090 open=472.83
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 4 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    2454.TW      聯發科         0.8815   1.2836    3856.96
*    2357.TW      華碩          0.5870   0.0069     644.84
     6669.TW      緯穎          0.5836   0.2912    5189.70
     2301.TW      光寶科         0.5411   0.2071     224.00
QUEUE BUY 2454.TW 聯發科 snr=0.8815 rs=1.2836 close=3856.96 → 下一根開盤成交
QUEUE BUY 2357.TW 華碩 snr=0.5870 rs=0.0069 close=644.84 → 下一根開盤成交
收盤: cash=74181 MV=1456984 equity=1531165 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2454.TW/breakout, buy:2357.TW/breakout

## 2026-05-12
開始: cash=74181 持倉=3 pending=2 equity=1531165
PENDING_BUY 買不起1張，現金留存: 2454.TW alloc=37090 open=3812.22
PENDING_BUY 買不起1張，現金留存: 2357.TW alloc=37090 open=644.84
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 5 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
     3035.TW      致新          0.4457   0.2177     206.64
     2303.TW      聯電          0.6184   0.5571     102.74
*    2395.TW      研華          0.7876   0.2621     484.09
     6669.TW      緯穎          0.6374   0.4068    5627.03
*    2301.TW      光寶科         0.6864   0.3460     234.50
QUEUE BUY 2395.TW 研華 snr=0.7876 rs=0.2621 close=484.09 → 下一根開盤成交
QUEUE BUY 2301.TW 光寶科 snr=0.6864 rs=0.3460 close=234.50 → 下一根開盤成交
收盤: cash=74181 MV=1390111 equity=1464292 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2395.TW/breakout, buy:2301.TW/breakout

## 2026-05-13
開始: cash=74181 持倉=3 pending=2 equity=1464292
PENDING_BUY 買不起1張，現金留存: 2395.TW alloc=37090 open=467.45
PENDING_BUY 買不起1張，現金留存: 2301.TW alloc=37090 open=222.00
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    6217.TWO     中探針         0.4473   0.4243     341.00
*    3044.TW      健鼎科技        0.5315   0.2467     514.77
QUEUE BUY 3044.TW 健鼎科技 snr=0.5315 rs=0.2467 close=514.77 → 下一根開盤成交
QUEUE BUY 6217.TWO 中探針 snr=0.4473 rs=0.4243 close=341.00 → 下一根開盤成交
收盤: cash=74181 MV=1390380 equity=1464560 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:3044.TW/breakout, buy:6217.TWO/breakout

## 2026-05-14
開始: cash=74181 持倉=3 pending=2 equity=1464560
PENDING_BUY 買不起1張，現金留存: 3044.TW alloc=37090 open=519.63
PENDING_BUY 買不起1張，現金留存: 6217.TWO alloc=37090 open=365.50
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    2303.TW      聯電          0.5419   0.6022     106.18
QUEUE BUY 2303.TW 聯電 snr=0.5419 rs=0.6022 close=106.18 → 下一根開盤成交
收盤: cash=74181 MV=1433415 equity=1507595 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2303.TW/breakout

## 2026-05-15
開始: cash=74181 持倉=3 pending=1 equity=1507595
PENDING_BUY 買不起1張，現金留存: 2303.TW alloc=74181 open=110.12
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    2303.TW      聯電          0.5180   0.5017     108.15
QUEUE BUY 2303.TW 聯電 snr=0.5180 rs=0.5017 close=108.15 → 下一根開盤成交
收盤: cash=74181 MV=1358573 equity=1432754 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2303.TW/breakout

## 2026-05-18
開始: cash=74181 持倉=3 pending=1 equity=1432754
PENDING_BUY 買不起1張，現金留存: 2303.TW alloc=74181 open=106.67
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=74181 MV=1405511 equity=1479692 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=(無)

## 2026-05-19
開始: cash=74181 持倉=3 pending=0 equity=1479692
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=74181 MV=1398791 equity=1472972 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=(無)

## 2026-05-20
開始: cash=74181 持倉=3 pending=0 equity=1472972
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=74181 MV=1432144 equity=1506325 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=(無)

## 2026-05-21
開始: cash=74181 持倉=3 pending=0 equity=1506325
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=74181 MV=1447759 equity=1521940 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=(無)

## 2026-05-22
開始: cash=74181 持倉=3 pending=0 equity=1521940
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    2404.TW      漢唐          0.4147   0.0639    1119.05
QUEUE BUY 2404.TW 漢唐 snr=0.4147 rs=0.0639 close=1119.05 → 下一根開盤成交
收盤: cash=74181 MV=1455111 equity=1529291 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2404.TW/breakout

## 2026-05-25
開始: cash=74181 持倉=3 pending=1 equity=1529291
PENDING_BUY 買不起1張，現金留存: 2404.TW alloc=74181 open=1148.11
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 7 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
     6197.TW      佳必琪         0.5364   0.4492     268.55
     2404.TW      漢唐          0.5020   0.1378    1206.25
     2317.TW      鴻海          0.4051   0.0573     253.45
     2454.TW      聯發科         0.4973   0.6223    4219.79
*    2303.TW      聯電          0.5495   0.5568     122.90
*    3008.TW      大立光         0.5603   0.4048    3810.20
     2357.TW      華碩          0.4460   0.0909     666.46
QUEUE BUY 3008.TW 大立光 snr=0.5603 rs=0.4048 close=3810.20 → 下一根開盤成交
QUEUE BUY 2303.TW 聯電 snr=0.5495 rs=0.5568 close=122.90 → 下一根開盤成交
收盤: cash=74181 MV=1465691 equity=1539872 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:3008.TW/breakout, buy:2303.TW/breakout

## 2026-05-26
開始: cash=74181 持倉=3 pending=2 equity=1539872
PENDING_BUY 買不起1張，現金留存: 3008.TW alloc=37090 open=3839.93
PENDING_BUY 買不起1張，現金留存: 2303.TW alloc=37090 open=126.83
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 4 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    6197.TW      佳必琪         0.5413   0.4716     273.94
     2454.TW      聯發科         0.5000   0.6529    4239.67
*    2303.TW      聯電          0.6046   0.6964     128.30
     2881.TW      富邦金         0.5032   0.0788     100.10
QUEUE BUY 2303.TW 聯電 snr=0.6046 rs=0.6964 close=128.30 → 下一根開盤成交
QUEUE BUY 6197.TW 佳必琪 snr=0.5413 rs=0.4716 close=273.94 → 下一根開盤成交
收盤: cash=74181 MV=1482393 equity=1556574 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2303.TW/breakout, buy:6197.TW/breakout

## 2026-05-27
開始: cash=74181 持倉=3 pending=2 equity=1556574
PENDING_BUY 買不起1張，現金留存: 2303.TW alloc=37090 open=137.15
PENDING_BUY 買不起1張，現金留存: 6197.TW alloc=37090 open=273.94
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 5 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
     2317.TW      鴻海          0.4031   0.0509     256.37
     2454.TW      聯發科         0.5253   0.6546    4612.44
*    2303.TW      聯電          0.6441   0.7910     141.09
*    2881.TW      富邦金         0.5815   0.1217     106.39
     2882.TW      國泰金         0.4100   0.0234      82.46
QUEUE BUY 2303.TW 聯電 snr=0.6441 rs=0.7910 close=141.09 → 下一根開盤成交
QUEUE BUY 2881.TW 富邦金 snr=0.5815 rs=0.1217 close=106.39 → 下一根開盤成交
收盤: cash=74181 MV=1520785 equity=1594966 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2303.TW/breakout, buy:2881.TW/breakout

## 2026-05-28
開始: cash=74181 持倉=3 pending=2 equity=1594966
PENDING_BUY 買不起1張，現金留存: 2303.TW alloc=37090 open=142.56
PENDING_BUY 買不起1張，現金留存: 2881.TW alloc=37090 open=106.39
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=74181 MV=1498591 equity=1572772 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=(無)

## 2026-05-29
開始: cash=74181 持倉=3 pending=0 equity=1572772
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 3 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    6197.TW      佳必琪         0.5086   0.2787     291.09
*    2317.TW      鴻海          0.5966   0.1675     280.64
     2357.TW      華碩          0.5028   0.1607     715.34
QUEUE BUY 2317.TW 鴻海 snr=0.5966 rs=0.1675 close=280.64 → 下一根開盤成交
QUEUE BUY 6197.TW 佳必琪 snr=0.5086 rs=0.2787 close=291.09 → 下一根開盤成交
收盤: cash=74181 MV=1476089 equity=1550269 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2317.TW/breakout, buy:6197.TW/breakout

## 2026-06-01
開始: cash=74181 持倉=3 pending=2 equity=1550269
PENDING_BUY 買不起1張，現金留存: 2317.TW alloc=37090 open=293.27
PENDING_BUY 買不起1張，現金留存: 6197.TW alloc=37090 open=294.52
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 6 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
     6197.TW      佳必琪         0.4835   0.2385     302.85
*    2317.TW      鴻海          0.5841   0.1763     285.01
     2882.TW      國泰金         0.5042   0.0437      85.16
     2891.TW      中信金         0.5610   0.0601      59.88
*    2357.TW      華碩          0.5802   0.3024     786.78
     3231.TW      緯創          0.4379   0.1246     167.84
QUEUE BUY 2317.TW 鴻海 snr=0.5841 rs=0.1763 close=285.01 → 下一根開盤成交
QUEUE BUY 2357.TW 華碩 snr=0.5802 rs=0.3024 close=786.78 → 下一根開盤成交
收盤: cash=74181 MV=1542674 equity=1616854 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=buy:2317.TW/breakout, buy:2357.TW/breakout

## 2026-06-02
開始: cash=74181 持倉=3 pending=2 equity=1616854
PENDING_BUY 買不起1張，現金留存: 2317.TW alloc=37090 open=288.90
PENDING_BUY 買不起1張，現金留存: 2357.TW alloc=37090 open=859.16
QUEUE SELL 2379.TW tp (entry=510.00 H=653.00 L=602.00) → 下一根開盤成交
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 5 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    2881.TW      富邦金         0.6246   0.1136     109.78
     2891.TW      中信金         0.5955   0.0807      61.81
*    2357.TW      華碩          0.6522   0.4419     864.80
     3231.TW      緯創          0.5326   0.2276     184.24
     3034.TW      聯詠          0.4123   0.0897     485.49
QUEUE BUY 2357.TW 華碩 snr=0.6522 rs=0.4419 close=864.80 → 下一根開盤成交
QUEUE BUY 2881.TW 富邦金 snr=0.6246 rs=0.1136 close=109.78 → 下一根開盤成交
收盤: cash=74181 MV=1639353 equity=1713534 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2379.TW 2000@510.0 pending=sell:2379.TW/tp, buy:2357.TW/breakout, buy:2881.TW/breakout

## 2026-06-03
開始: cash=74181 持倉=3 pending=3 equity=1713534
SELL 2379.TW 瑞昱 2000股 @ 685.00 reason=tp cash=1438118
PENDING_BUY 買不起1張，現金留存: 2357.TW alloc=719059 open=896.76
BUY 2881.TW 富邦金 6000股 @ 111.71 snr=0.6246 cash=766907
QUEUE SELL 2891.TW tp (entry=52.16 H=67.98 L=62.00) → 下一根開盤成交
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 7 檔，空槽 2，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
*    6197.TW      佳必琪         0.5815   0.2737     322.45
     2317.TW      鴻海          0.5481   0.0969     300.06
     2882.TW      國泰金         0.5261   0.0371      88.63
     2891.TW      中信金         0.6870   0.1595      67.98
     3008.TW      大立光         0.4875   0.4520    3948.93
*    2357.TW      華碩          0.6318   0.3508     875.14
     3231.TW      緯創          0.5249   0.1949     187.14
QUEUE BUY 2357.TW 華碩 snr=0.6318 rs=0.3508 close=875.14 → 下一根開盤成交
QUEUE BUY 6197.TW 佳必琪 snr=0.5815 rs=0.2737 close=322.45 → 下一根開盤成交
收盤: cash=766907 MV=1016297 equity=1783203 持倉=2882.TW 1000@74.8, 2891.TW 4000@52.2, 2881.TW 6000@111.7 pending=sell:2891.TW/tp, buy:2357.TW/breakout, buy:6197.TW/breakout

## 2026-06-04
開始: cash=766907 持倉=3 pending=3 equity=1783203
SELL 2891.TW 中信金 4000股 @ 65.57 reason=tp cash=1028017
PENDING_BUY 買不起1張，現金留存: 2357.TW alloc=514008 open=861.04
BUY 6197.TW 佳必琪 1000股 @ 311.67 snr=0.5815 cash=715899
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     2882.TW      國泰金         0.5662   0.1057      91.14
收盤: cash=715899 MV=1062900 equity=1778800 持倉=2882.TW 1000@74.8, 2881.TW 6000@111.7, 6197.TW 1000@311.7 pending=(無)

## 2026-06-05
開始: cash=715899 持倉=3 pending=0 equity=1778800
QUEUE SELL 2882.TW tp (entry=74.83 H=96.55 L=90.47) → 下一根開盤成交
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 2，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     2881.TW      富邦金         0.6068   0.1369     114.13
     2882.TW      國泰金         0.6289   0.1667      96.55
收盤: cash=715899 MV=1099850 equity=1815750 持倉=2882.TW 1000@74.8, 2881.TW 6000@111.7, 6197.TW 1000@311.7 pending=sell:2882.TW/tp

## 2026-06-08
開始: cash=715899 持倉=3 pending=1 equity=1815750
SELL 2882.TW 國泰金 1000股 @ 94.43 reason=tp cash=809909
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 3，新排隊 0
排名:
(no signals)
收盤: cash=809909 MV=993653 equity=1803562 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7 pending=(無)

## 2026-06-09
開始: cash=809909 持倉=2 pending=0 equity=1803562
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 4 檔，空槽 3，新排隊 2
排名:
pick ticker       name           snr    rs_20      close
     6197.TW      佳必琪         0.6412   0.3988     336.18
     2881.TW      富邦金         0.7262   0.2671     120.90
*    2882.TW      國泰金         0.6540   0.2943     100.41
*    2886.TW      兆豐金         0.4703   0.0440      41.99
QUEUE BUY 2882.TW 國泰金 snr=0.6540 rs=0.2943 close=100.41 → 下一根開盤成交
QUEUE BUY 2886.TW 兆豐金 snr=0.4703 rs=0.0440 close=41.99 → 下一根開盤成交
收盤: cash=809909 MV=1061562 equity=1871471 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7 pending=buy:2882.TW/breakout, buy:2886.TW/breakout

## 2026-06-10
開始: cash=809909 持倉=2 pending=2 equity=1871471
BUY 2882.TW 國泰金 4000股 @ 98.48 snr=0.654 cash=415417
BUY 2886.TW 兆豐金 9000股 @ 41.89 snr=0.4703 cash=37881
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=37881 MV=1792287 equity=1830169 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-06-11
開始: cash=37881 持倉=4 pending=0 equity=1830169
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=37881 MV=1804173 equity=1842055 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-06-12
開始: cash=37881 持倉=4 pending=0 equity=1842055
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=37881 MV=1793663 equity=1831545 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-06-15
開始: cash=37881 持倉=4 pending=0 equity=1831545
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 1，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     2886.TW      兆豐金         0.4863   0.0023      42.42
收盤: cash=37881 MV=1848224 equity=1886105 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-06-16
開始: cash=37881 持倉=4 pending=0 equity=1886105
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 1，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     2881.TW      富邦金         0.6148   0.2178     127.67
     2882.TW      國泰金         0.6204   0.2672     105.72
收盤: cash=37881 MV=1889136 equity=1927018 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-06-17
開始: cash=37881 持倉=4 pending=0 equity=1927018
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 4 檔，空槽 1，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
     2881.TW      富邦金         0.6763   0.2681     131.05
     2882.TW      國泰金         0.6473   0.3107     109.59
     2886.TW      兆豐金         0.5455  -0.0272      43.48
*    3008.TW      大立光         0.4893   0.4615    5098.43
QUEUE BUY 3008.TW 大立光 snr=0.4893 rs=0.4615 close=5098.43 → 下一根開盤成交
收盤: cash=37881 MV=1942353 equity=1980234 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=buy:3008.TW/breakout

## 2026-06-18
開始: cash=37881 持倉=4 pending=1 equity=1980234
PENDING_BUY 買不起1張，現金留存: 3008.TW alloc=37881 open=5068.70
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 1，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
     2886.TW      兆豐金         0.5824   0.0086      43.86
*    2379.TW      瑞昱          0.4586   0.3011     819.00
QUEUE BUY 2379.TW 瑞昱 snr=0.4586 rs=0.3011 close=819.00 → 下一根開盤成交
收盤: cash=37881 MV=1982267 equity=2020148 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=buy:2379.TW/breakout

## 2026-06-22
開始: cash=37881 持倉=4 pending=1 equity=2020148
PENDING_BUY 買不起1張，現金留存: 2379.TW alloc=37881 open=840.00
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 1，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    2379.TW      瑞昱          0.5279   0.4276     900.00
     3034.TW      聯詠          0.4324   0.0384     542.94
QUEUE BUY 2379.TW 瑞昱 snr=0.5279 rs=0.4276 close=900.00 → 下一根開盤成交
收盤: cash=37881 MV=1974396 equity=2012278 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=buy:2379.TW/breakout

## 2026-06-23
開始: cash=37881 持倉=4 pending=1 equity=2012278
PENDING_BUY 買不起1張，現金留存: 2379.TW alloc=37881 open=948.00
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=37881 MV=1971488 equity=2009370 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-06-24
開始: cash=37881 持倉=4 pending=0 equity=2009370
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 1，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     6197.TW      佳必琪         0.4348   0.2284     352.35
收盤: cash=37881 MV=1944233 equity=1982115 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-06-25
開始: cash=37881 持倉=4 pending=0 equity=1982115
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 2 檔，空槽 1，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     6197.TW      佳必琪         0.4694   0.2817     366.07
     2886.TW      兆豐金         0.5902   0.1374      44.97
收盤: cash=37881 MV=1990673 equity=2028555 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-06-26
開始: cash=37881 持倉=4 pending=0 equity=2028555
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=37881 MV=1944176 equity=1982058 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-06-29
開始: cash=37881 持倉=4 pending=0 equity=1982058
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=37881 MV=1876202 equity=1914083 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-06-30
開始: cash=37881 持倉=4 pending=0 equity=1914083
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=37881 MV=1887728 equity=1925609 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-01
開始: cash=37881 持倉=4 pending=0 equity=1925609
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=37881 MV=1856501 equity=1894383 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-02
開始: cash=37881 持倉=4 pending=0 equity=1894383
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=37881 MV=1853623 equity=1891505 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-03
開始: cash=37881 持倉=4 pending=0 equity=1891505
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=37881 MV=1867685 equity=1905566 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-06
開始: cash=37881 持倉=4 pending=0 equity=1905566
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=37881 MV=1876826 equity=1914708 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-07
開始: cash=37881 持倉=4 pending=0 equity=1914708
QUEUE SELL 6197.TW tp (entry=311.67 H=405.00 L=355.50) → 下一根開盤成交
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 1，新排隊 0
排名:
(no signals)
收盤: cash=37881 MV=1892064 equity=1929946 持倉=2881.TW 6000@111.7, 6197.TW 1000@311.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=sell:6197.TW/tp

## 2026-07-08
開始: cash=37881 持倉=4 pending=1 equity=1929946
SELL 6197.TW 佳必琪 1000股 @ 368.00 reason=tp cash=404253
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1554064 equity=1958318 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-09
開始: cash=404253 持倉=3 pending=0 equity=1958318
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1537397 equity=1941650 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-13
開始: cash=404253 持倉=3 pending=0 equity=1941650
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1556600 equity=1960853 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-14
開始: cash=404253 持倉=3 pending=0 equity=1960853
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1542200 equity=1946453 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-15
開始: cash=404253 持倉=3 pending=0 equity=1946453
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1556523 equity=1960776 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-16
開始: cash=404253 持倉=3 pending=0 equity=1960776
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1543529 equity=1947782 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-17
開始: cash=404253 持倉=3 pending=0 equity=1947782
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1537206 equity=1941459 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-20
開始: cash=404253 持倉=3 pending=0 equity=1941459
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1535212 equity=1939465 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-23
開始: cash=404253 持倉=3 pending=0 equity=1939465
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1577978 equity=1982231 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-24
開始: cash=404253 持倉=3 pending=0 equity=1982231
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    6669.TW      緯穎          0.4407   0.3594    5730.00
QUEUE BUY 6669.TW 緯穎 snr=0.4407 rs=0.3594 close=5730.00 → 下一根開盤成交
收盤: cash=404253 MV=1573381 equity=1977634 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=buy:6669.TW/breakout

## 2026-07-27
開始: cash=404253 持倉=3 pending=1 equity=1977634
PENDING_BUY 買不起1張，現金留存: 6669.TW alloc=404253 open=5700.00
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     2886.TW      兆豐金         0.4103   0.0996      47.62
收盤: cash=404253 MV=1602624 equity=2006877 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-28
開始: cash=404253 持倉=3 pending=0 equity=2006877
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1563657 equity=1967910 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-29
開始: cash=404253 持倉=3 pending=0 equity=1967910
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1547362 equity=1951615 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-07-30
開始: cash=404253 持倉=3 pending=0 equity=1951615
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 0
排名:
pick ticker       name           snr    rs_20      close
     2886.TW      兆豐金         0.5729   0.2653      49.65
收盤: cash=404253 MV=1571644 equity=1975897 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-08-03
開始: cash=404253 持倉=3 pending=0 equity=1975897
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1626712 equity=2030965 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-08-04
開始: cash=404253 持倉=3 pending=0 equity=2030965
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1607703 equity=2011956 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-08-05
開始: cash=404253 持倉=3 pending=0 equity=2011956
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 1 檔，空槽 2，新排隊 1
排名:
pick ticker       name           snr    rs_20      close
*    2357.TW      華碩          0.4254   0.2443     838.00
QUEUE BUY 2357.TW 華碩 snr=0.4254 rs=0.2443 close=838.00 → 下一根開盤成交
收盤: cash=404253 MV=1623241 equity=2027495 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=buy:2357.TW/breakout

## 2026-08-06
開始: cash=404253 持倉=3 pending=1 equity=2027495
PENDING_BUY 買不起1張，現金留存: 2357.TW alloc=404253 open=830.00
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1582433 equity=1986686 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-08-07
開始: cash=404253 持倉=3 pending=0 equity=1986686
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1601239 equity=2005492 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-08-10
開始: cash=404253 持倉=3 pending=0 equity=2005492
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1617506 equity=2021759 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-08-11
開始: cash=404253 持倉=3 pending=0 equity=2021759
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1595024 equity=1999277 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-08-12
開始: cash=404253 持倉=3 pending=0 equity=1999277
流動性篩選通過 30/30 檔（失敗下載 0）
訊號 0 檔，空槽 2，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1583350 equity=1987603 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-08-13
開始: cash=404253 持倉=3 pending=0 equity=1987603
流動性篩選通過 30/30 檔（失敗下載 0）
風險判定 allow_new=False news=34 twii_d1=0.0088 twii_d3=0.0292｜新聞風險分數 34 ≥ 4
風險開關：今日暫停開新倉（舊倉照停利停損）
訊號 0 檔，空槽 0，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1581650 equity=1985903 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-08-14
開始: cash=404253 持倉=3 pending=0 equity=1985903
流動性篩選通過 30/30 檔（失敗下載 0）
風險判定 allow_new=False news=35 twii_d1=-0.0046 twii_d3=0.0153｜新聞風險分數 35 ≥ 4
風險開關：今日暫停開新倉（舊倉照停利停損）
訊號 0 檔，空槽 0，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1609150 equity=2013403 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-08-17
開始: cash=404253 持倉=3 pending=0 equity=2013403
流動性篩選通過 30/30 檔（失敗下載 0）
風險判定 allow_new=False news=35 twii_d1=0.001 twii_d3=0.0075｜今08:30分數 35 ≥ 4（尚無昨21:30）
風險開關：今日暫停開新倉（舊倉照停利停損）
訊號 0 檔，空槽 0，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1564800 equity=1969053 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-08-18
開始: cash=404253 持倉=3 pending=0 equity=1969053
流動性篩選通過 30/30 檔（失敗下載 0）
風險判定 allow_new=False news=35 twii_d1=-0.011 twii_d3=-0.0046｜今08:30分數 35 ≥ 4（尚無昨21:30）
風險開關：今日暫停開新倉（舊倉照停利停損）
訊號 0 檔，空槽 0，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1595900 equity=2000153 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-08-19
開始: cash=404253 持倉=3 pending=0 equity=2000153
流動性篩選通過 30/30 檔（失敗下載 0）
風險判定 allow_new=False news=40 twii_d1=-0.013 twii_d3=-0.0238｜今早熱度 40 ≥ 嚴重線 12(昨21:30=44,Δ-4)仍關
風險開關：今日暫停開新倉（舊倉照停利停損）
訊號 0 檔，空槽 0，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1587650 equity=1991903 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

## 2026-08-20
開始: cash=404253 持倉=3 pending=0 equity=1991903
流動性篩選通過 30/30 檔（失敗下載 0）
風險判定 allow_new=False news=39 twii_d1=0.0048 twii_d3=-0.0201｜今早熱度 39 ≥ 嚴重線 12(昨21:30=36,Δ+3)仍關
風險開關：今日暫停開新倉（舊倉照停利停損）
訊號 0 檔，空槽 0，新排隊 0
排名:
(no signals)
收盤: cash=404253 MV=1576400 equity=1980653 持倉=2881.TW 6000@111.7, 2882.TW 4000@98.5, 2886.TW 9000@41.9 pending=(無)

