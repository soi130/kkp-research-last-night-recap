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

# VERSION: 1.4 - Deep Analysis + Live News
print("Starting script Version 1.4 (Deep Analysis)...")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def get_latest_headlines():
    print("Fetching latest market news headlines...")
    urls = [
        "https://finance.yahoo.com/news/rss",
        "https://www.reuters.com/tools/rssfeed/us/marketnews"
    ]
    headlines = []
    for url in urls:
        try:
            resp = requests.get(url, timeout=10)
            root = ET.fromstring(resp.content)
            for item in root.findall('./channel/item')[:10]:
                title = item.find('title').text
                headlines.append(title)
        except:
            continue
    return list(set(headlines))[:15]

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
            hist = t.history(period="5d")
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

def generate_ai_content(market_summary, news_headlines):
    prompt = f"""
    You are a professional Senior Macro Strategist at KKP Research. 
    Your task is to provide a deep, insightful recap of the global market for Thai investors.
    
    หน้าที่ของคุณคือสรุปว่า "เมื่อคืนเกิดอะไรขึ้นบ้าง" (What happened), "เกิดขึ้นเพราะอะไร" (Why), 
    และ "ส่งผลต่อการลงทุนของผู้อ่านอย่างไร" (How it affects the reader's investment).
    
    **เน้นที่เนื้อหาข่าวและบทวิเคราะห์เชิงกลยุทธ์เป็นหลัก** 
    
    THEMATIC PRIORITIES (ลำดับความสำคัญของเนื้อหา):
    1. Geopolitics & Energy: หากมีความตึงเครียดทางการเมือง/สงคราม (War) และราคาน้ำมัน (Oil Price) ผันผวน ต้องวิเคราะห์เจาะลึกถึงสาเหตุและผลกระทบต่อต้นทุนพลังงานและอัตราเงินเฟ้อ
    2. Key Economic Indicators: หากเป็นช่วงต้นเดือน ต้องให้ความสำคัญกับตัวเลขจ้างงาน (Non-farm payrolls) และอัตราว่างงานของสหรัฐฯ โดยเปรียบเทียบกับคาดการณ์อย่างชัดเจน
    3. Monetary Policy: ท่าทีของ Fed และธนาคารกลางสำคัญต่อทิศทางดอกเบี้ย
    4. Market Sentiment: การเคลื่อนไหวของ Bond Yield และ Dollar Index ที่สะท้อนความกังวลหรือความเชื่อมั่นของนักลงทุน
    
    DATA CONTEXT:
    - Market Numbers: {market_summary}
    - Recent Headlines: {news_headlines}
    
    INSTRUCTIONS:
    1. Summarize only the MOST IMPORTANT stories. NEVER be vague. 
    2. สำหรับส่วน Mover Story: เขียนเป็น Narrative ที่ร้อยเรียงเหตุการณ์เข้าด้วยกัน (เช่น ข่าวสงคราม -> ดันราคาน้ำมัน -> กระทบคาดการณ์เงินเฟ้อ -> Yield พุ่ง)
    3. สำหรับส่วน Macro Focus: ต้องมีตัวเลขเศรษฐกิจที่สำคัญ (Actual vs Expected) โดยเฉพาะ NFP หากอยู่ในช่วงสัปดาห์แรกของเดือน
    4. สำหรับส่วน Implications: วิเคราะห์เจาะลึกถึง Asset Allocation หรือ Sector ที่ได้ประโยชน์/เสียประโยชน์ในตลาดหุ้นไทย (SET Index)
    5. TONE: Senior Macro Strategist, formal, high-signal, professional.
    6. CONSTRAINT: NO investment advice. Use Thai language.
    
    Provide the output in JSON format:
    {{
      "moverStory": "สรุปประเด็นหลักที่ขับเคลื่อนตลาดเมื่อคืนแบบร้อยเรียงเหตุผล (What & Why)",
      "macroFocus": ["ประเด็นเศรษฐกิจสำคัญ 1 (พร้อมตัวเลข)", "ประเด็นเศรษฐกิจสำคัญ 2 (พร้อมตัวเลข)", "ประเด็นเศรษฐกิจสำคัญ 3 (พร้อมตัวเลข)"],
      "implications": ["กลยุทธ์/ผลกระทบต่อพอร์ตลงทุน 1", "กลยุทธ์/ผลกระทบต่อพอร์ตลงทุน 2", "กลยุทธ์/ผลกระทบต่อพอร์ตลงทุน 3"]
    }}
    """
    
    try:
        print("Generating deep analysis with OpenAI GPT-4o-mini...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional financial analyst at KKP Research. Your output is data-driven and objective. You focus on 'What, Why, and Impact'."},
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
    html = f"""<html><body style="font-family:Arial,sans-serif;background-color:#f8fafc;padding:20px;color:#1e293b;"><div style="max-width:600px;margin:0 auto;background:#ffffff;padding:30px;border-radius:12px;border:1px solid #e2e8f0;border-top:8px solid #512D6D;"><h1 style="color:#512D6D;font-size:22px;">KKP Research Recap</h1><p style="color:#64748b;font-size:14px;">{data['lastUpdated']} (เวลาประเทศไทย)</p><hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;"><h2 style="color:#512D6D;font-size:16px;">📊 สรุปตลาดและราคาสินทรัพย์</h2><table style="width:100%;border-collapse:collapse;"><tr style="background:#f3f0f7;"><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">สินทรัพย์</th><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">ล่าสุด</th><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">เปลี่ยนแปลง</th></tr>{rows}</table><p style='font-size:11px;color:#94a3b8;margin-top:8px;'>แหล่งข้อมูล: Yahoo Finance, Reuters</p><h2 style="color:#512D6D;font-size:16px;margin-top:25px;">MARKET FOCUS (WHAT & WHY)</h2><p style="font-size:15px;line-height:1.6;">{data['moverStory']}</p><h2 style="color:#512D6D;font-size:16px;margin-top:25px;">🧠 MACRO FOCUS</h2><div style="font-size:14px;line-height:1.6;">{macro_items}</div><h2 style="color:#512D6D;font-size:16px;margin-top:25px;">💡 INVESTMENT IMPLICATIONS</h2><div style="font-size:14px;line-height:1.6;">{risk_items}</div><hr style="border:none;border-top:1px solid #e2e8f0;margin:30px 0;"><p style="font-size:11px;color:#94a3b8;line-height:1.6;">เนื้อหาข้างต้นจัดทำขึ้นโดย KKP Research เพื่อวัตถุประสงค์ในการรายงานข้อมูลข่าวสารเศรษฐกิจและตลาดทุนเท่านั้น มิใช่การให้คำแนะนำการลงทุน</p></div></body></html>"""
    msg.attach(MIMEText(html, 'html'))
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            print("SUCCESS: Email sent.")
    except Exception as e: print(f"ERROR: Email failed: {e}")

def main():
    print("Main execution started (Deep Analysis Version).")
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.now(tz)
    months_th = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    date_str = f"{now.day} {months_th[now.month]} {now.year + 543}, {now.strftime('%H:%M')} น."
    
    market_data = get_market_data_v2()
    headlines = get_latest_headlines()
    print(f"Fetched {len(headlines)} headlines for context.")
    
    ai_content = generate_ai_content(str(market_data), str(headlines))
    
    if ai_content:
        final_data = {"lastUpdated": date_str, "marketData": market_data, "moverStory": ai_content['moverStory'], "macroFocus": ai_content['macroFocus'], "implications": ai_content['implications']}
        with open('src/data.json', 'w', encoding='utf-8') as f: json.dump(final_data, f, ensure_ascii=False, indent=2)
        send_recap_email(final_data)
        print("Workflow finished successfully.")
    else: print("Workflow failed at AI generation.")

if __name__ == "__main__": main()
