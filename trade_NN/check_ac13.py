"""AC-13 檢查：名目 NT$5,000 的買單手續費 NT$20，賣單 NT$20 加 0.3% 稅，都經由 broker.py 計算。
"""
import sys
sys.path.insert(0, "../snr_backtest")
from broker import commission_on, sell_fill, buy_cost

def test_ac13():
    notional = 5000.0
    rate = 0.001425
    min_comm = 20.0
    tax_rate = 0.003
    # 買單
    buy_comm = commission_on(notional, rate, min_comm)
    assert buy_comm == 20.0, f"買單手續費應為 20，實際 {buy_comm}"
    buy_total = buy_cost(1, 5000.0, rate, min_comm)
    assert abs(buy_total - (5000.0 + 20.0)) < 1e-6
    # 賣單
    sf = sell_fill(1, 5000.0, rate, min_comm, tax_rate)
    assert sf.commission == 20.0, f"賣單手續費應為 20，實際 {sf.commission}"
    assert abs(sf.tax - 5000.0 * 0.003) < 1e-6, f"賣單稅應為 15，實際 {sf.tax}"
    print("AC-13 通過：買單手續費 20，賣單手續費 20 + 稅 15")

if __name__ == "__main__":
    test_ac13()
