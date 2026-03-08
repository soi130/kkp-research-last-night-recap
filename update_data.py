import os
import json
import yfinance as yf
from openai import OpenAI
from datetime import datetime
import pytz
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
import xml.etree.ElementTree as ET

# VERSION: 1.5 - Real News Content + Risk Focus
print("Starting script Version 1.5 (Real News Content)...")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def get_latest_news_context():
    print("Fetching latest market news with context...")
    feeds = [
        {"name": "Reuters Markets", "url": "https://www.reuters.com/tools/rssfeed/us/marketnews"},
        {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rss"},
        {"name": "CNBC Markets", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=401&id=15839069"}
    ]
    news_items = []
    for feed in feeds:
        try:
            resp = requests.get(feed['url'], timeout=10)
            root = ET.fromstring(resp.content)
            for item in root.findall('./channel/item')[:8]:
                title = item.find('title').text
                desc = item.find('description').text if item.find('description') is not None else ""
                # Clean up description (remove HTML tags if any)
                if desc:
                    desc = ET.fromstring(f"<div>{desc}</div>").text if '<' in desc else desc
                news_items.append(f"Source: {feed['name']}\nHeadline: {title}\nSummary: {desc}\n---")
        except Exception as e:
            print(f"Error fetching {feed['name']}: {e}")
            continue
    return "\n".join(news_items[:20])

def get_market_data_v2():
    print("Fetching market data...")
    tickers = {
        "^GSPC": "S&P 500 (US)",
        "^DJI": "Dow Jones (US)",
        "^IXIC": "Nasdaq (US)",
        "^N225": "Nikkei 225 (JP)*",
        "^TPX": "TOPIX (JP)*",
        "^KS11": "KOSPI (KR)*",
        "GC=F": "Gold (Spot)",
        "CL=F": "Crude Oil (WTI)",
        "BZ=F": "Crude Oil (Brent)",
        "BTC-USD": "Bitcoin (BTC)",
        "THB=X": "USD/THB",
        "DX-Y.NYB": "Dollar Index (DXY)",
        "^TNX": "US 10Y Yield"
    }
    results = []
    for ticker, name in tickers.items():
        try:
            t = yf.Ticker(ticker)
            # Increased period to 10d to cover long weekends/holidays
            hist = t.history(period="10d")
            if len(hist) >= 2:
                close = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                change_pct = ((close - prev_close) / prev_close) * 100
                if ticker in ["GC=F", "CL=F", "BZ=F"]: price_str = f"${close:,.2f}"
                elif ticker == "BTC-USD": price_str = f"${close:,.0f}"
                elif ticker == "THB=X": price_str = f"{close:.2f} บาท"
                elif ticker == "^TNX": price_str = f"{close:.2f}%"
                else: price_str = f"{close:,.2f}"
                results.append({"name": name, "price": price_str, "change": f"{'+' if change_pct >= 0 else ''}{change_pct:.2f}%", "status": "up" if change_pct >= 0 else "down"})
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            continue
    return results

def generate_ai_content(market_summary, news_context):
    prompt = f"""
    You are a professional Senior Macro Strategist at KKP Research. 
    Your task is to analyze real market-moving news and data for Thai investors.
    
    หน้าที่ของคุณคือวิเคราะห์ "เหตุการณ์สำคัญที่เกิดขึ้นตั้งแต่ปิดตลาดครั้งล่าสุดจนถึงปัจจุบัน" (โดยเฉพาะหากเป็นหลังวันหยุดเสาร์-อาทิตย์ หรือวันหยุดยาว ให้รวบรวมประเด็นตั้งแต่คืนวันศุกร์หรือวันก่อนหยุด)
    
    DATA CONTEXT:
    - Market Numbers: {market_summary}
    - News Headlines & Summaries (ตั้งแต่ปิดตลาดครั้งก่อนถึงปัจจุบัน): 
    {news_context}
    
    INSTRUCTIONS:
    1. **HOLIDAY/WEEKEND COVERAGE**: หากวันนี้เป็นวันจันทร์ หรือวันแรกหลังวันหยุดยาว ให้สรุปภาพรวมข่าวสำคัญทั้งหมดที่เกิดขึ้นตลอดช่วงวันหยุด (Weekend Wrap-up) โดยเน้นประเด็นที่จะส่งผลต่อการเปิดตลาดในเช้านี้
    2. **FOCUS ON NEWS, NOT NUMBERS**: ไม่ต้องบรรยายการเปลี่ยนแปลงของตัวเลขราคาในตาราง ให้เน้นที่ "ข่าว" หรือ "เหตุการณ์" (Market Movers) ที่เป็นสาเหตุของการเคลื่อนไหวนั้นๆ
    3. **WHAT HAPPENED?**: เจาะจงไปที่เหตุการณ์หรือข่าวสำคัญที่เกิดขึ้นจริงจาก News Context โดยต้องระบุชื่อข่าว (Headline) หรือแหล่งข่าว (Source) ให้ชัดเจนเพื่อให้ผู้อ่านทราบว่านี่คือเหตุการณ์จริง
    4. **STRATEGIC IMPLICATIONS**: วิเคราะห์นัยสำคัญต่อกลยุทธ์การลงทุน หรือปัจจัยเสี่ยงที่นักลงทุนไทยต้องเตรียมรับมือในวันนี้
    5. **BE HONEST**: หากช่วงวันหยุดที่ผ่านมาไม่มีข่าวใหญ่จริงๆ ให้ระบุตามตรงว่าบรรยากาศการลงทุนเงียบเหงา
    6. TONE: Professional, Data-driven, Objective, Cautious.
    7. CONSTRAINT: Use Thai language. Output must be JSON.
    
    Provide the output in JSON format:
    {{
      "moverStory": "สรุปเหตุการณ์สำคัญที่เกิดขึ้นจริง (เน้นเนื้อหาข่าวจาก Context ตลอดช่วงวันหยุด/วันก่อนหน้า)",
      "macroFocus": ["วิเคราะห์นัยสำคัญของเหตุการณ์ 1", "วิเคราะห์นัยสำคัญของเหตุการณ์ 2", "วิเคราะห์นัยสำคัญของเหตุการณ์ 3"],
      "implications": ["ปัจจัยเสี่ยงที่ต้องจับตา 1", "ปัจจัยเสี่ยงที่ต้องจับตา 2", "ปัจจัยเสี่ยงที่ต้องจับตา 3"]
    }}
    """
    
    try:
        print("Generating deep analysis with OpenAI GPT-5-mini...")
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a professional Senior Macro Strategist. You focus on real news events and their implications since the last closed session. You value news accuracy and context over hype."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return None

def send_recap_email(data):
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD") 
    receivers = ["thanak.ratt@kkpfg.com", "mynameisnak@gmail.com"]
    if not sender or not password: return
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"KKP Research Recap - {data['lastUpdated'].split(',')[0]}"
    msg['From'] = f"KKP Research <thanak.ratt@kkpfg.com>"
    msg['To'] = ", ".join(receivers)
    rows = "".join([f"<tr><td style='padding:12px;border-bottom:1px solid #e2e8f0;'>{item['name']}</td><td style='padding:12px;border-bottom:1px solid #e2e8f0;'>{item['price']}</td><td style='padding:12px;border-bottom:1px solid #e2e8f0;color:{'#059669' if item['status'] == 'up' else '#dc2626'};font-weight:bold;'>{item['change']}</td></tr>" for item in data['marketData']])
    macro_items = "".join([f"<p style='margin-bottom:8px;'>• {item}</p>" for item in data['macroFocus']])
    risk_items = "".join([f"<p style='margin-bottom:8px;'>• {item}</p>" for item in data['implications']])
    html = f"""<html><body style="font-family:Arial,sans-serif;background-color:#f8fafc;padding:20px;color:#1e293b;"><div style="max-width:600px;margin:0 auto;background:#ffffff;padding:30px;border-radius:12px;border:1px solid #e2e8f0;border-top:8px solid #512D6D;"><h1 style="color:#512D6D;font-size:22px;">KKP Research Recap</h1><p style="color:#64748b;font-size:14px;">{data['lastUpdated']} (เวลาประเทศไทย)</p><hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;"><h2 style="color:#512D6D;font-size:16px;">📊 สรุปตลาดและราคาสินทรัพย์</h2><table style="width:100%;border-collapse:collapse;"><tr style="background:#f3f0f7;"><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">สินทรัพย์</th><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">ล่าสุด</th><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">เปลี่ยนแปลง</th></tr>{rows}</table><p style='font-size:11px;color:#94a3b8;margin-top:8px;'>แหล่งข้อมูล: Yahoo Finance, Reuters, CNBC</p><h2 style="color:#512D6D;font-size:16px;margin-top:25px;">MARKET FOCUS (WHAT & WHY)</h2><p style="font-size:15px;line-height:1.6;">{data['moverStory']}</p><h2 style="color:#512D6D;font-size:16px;margin-top:25px;">🧠 MACRO FOCUS</h2><div style="font-size:14px;line-height:1.6;">{macro_items}</div><h2 style="color:#512D6D;font-size:16px;margin-top:25px;">⚠️ RISKS & FACTORS TO WATCH</h2><div style="font-size:14px;line-height:1.6;">{risk_items}</div><hr style="border:none;border-top:1px solid #e2e8f0;margin:30px 0;"><p style="font-size:11px;color:#94a3b8;line-height:1.6;">เนื้อหาข้างต้นจัดทำขึ้นโดย KKP Research เพื่อวัตถุประสงค์ในการรายงานข้อมูลข่าวสารเศรษฐกิจและตลาดทุนเท่านั้น มิใช่การให้คำแนะนำการลงทุน</p></div></body></html>"""
    msg.attach(MIMEText(html, 'html'))
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            print("SUCCESS: Email sent.")
    except Exception as e: print(f"ERROR: Email failed: {e}")

def main():
    print("Main execution started (Version 1.5).")
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.now(tz)
    months_th = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    date_str = f"{now.day} {months_th[now.month]} {now.year + 543}, {now.strftime('%H:%M')} น."
    
    market_data = get_market_data_v2()
    news_context = get_latest_news_context()
    print(f"Fetched news context for analysis.")
    
    ai_content = generate_ai_content(str(market_data), news_context)
    
    if ai_content:
        final_data = {"lastUpdated": date_str, "marketData": market_data, "moverStory": ai_content['moverStory'], "macroFocus": ai_content['macroFocus'], "implications": ai_content['implications']}
        with open('src/data.json', 'w', encoding='utf-8') as f: json.dump(final_data, f, ensure_ascii=False, indent=2)
        send_recap_email(final_data)
        print("Workflow finished successfully.")
    else: print("Workflow failed at AI generation.")

if __name__ == "__main__": main()
