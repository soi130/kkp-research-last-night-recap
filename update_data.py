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

# VERSION: 1.9 - Precise Macro Data (NFP/Rates/Unemployment)
print("Starting script Version 1.9 (Precise Macro Data)...")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def get_latest_news_context():
    print("Fetching deep market news context (Geopolitics + US Economy focus)...")
    feeds = [
        {"name": "Reuters Markets", "url": "https://www.reuters.com/tools/rssfeed/us/marketnews"},
        {"name": "Reuters Business", "url": "https://www.reuters.com/tools/rssfeed/us/businessnews"},
        {"name": "Reuters World (Geopolitics)", "url": "https://www.reuters.com/tools/rssfeed/us/worldnews"},
        {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rss"},
        {"name": "CNBC Markets", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=401&id=15839069"},
        {"name": "CNBC Economy", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=401&id=10000063"},
        {"name": "CNBC Politics (US Indicators)", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=401&id=10000113"}
    ]
    news_items = []
    
    # Keywords to prioritize for filtering (Market Movers)
    keywords = ["Fed", "Rate", "Inflation", "CPI", "NFP", "Unemployment", "GDP", "Yield", "War", "Conflict", "Oil", "Geopolitical", "Treasury", "Election", "Tariff"]
    
    for feed in feeds:
        try:
            resp = requests.get(feed['url'], timeout=10)
            root = ET.fromstring(resp.content)
            for item in root.findall('./channel/item')[:50]:
                title = item.find('title').text
                desc = item.find('description').text if item.find('description') is not None else ""
                
                # Simple HTML cleaning
                if desc and '<' in desc:
                    try: desc = ET.fromstring(f"<div>{desc}</div>").text
                    except: pass
                
                content = f"Source: {feed['name']} | Headline: {title} | Summary: {desc}"
                
                # Prioritization: Add high-impact news to the front of the list
                if any(kw.lower() in content.lower() for kw in keywords):
                    news_items.insert(0, content + "\n---")
                else:
                    news_items.append(content + "\n---")
                    
        except Exception as e:
            print(f"Error fetching {feed['name']}: {e}")
            continue
            
    # Return top 200 items (after prioritization) to give AI a rich context
    return "\n".join(news_items[:200])

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

def generate_ai_content(market_summary, news_context, current_day_info):
    
    few_shot_example = """
EXAMPLE OUTPUT (tone & structure ที่ต้องการ):
{
  "headline": "ดอลลาร์อ่อน + yield ดิ่ง ดันหุ้นสหรัฐฯ พุ่ง — แต่เอเชียเจ็บหนักจาก margin call และขาย cyclicals",
  "keyStory": {
    "narrative": "คืนนี้ตลาดสหรัฐฯ ฟื้นตัวได้จากแรงสองทาง: อัตราผลตอบแทนพันธบัตร 10 ปีร่วงลงสู่ 4.33% ขณะที่ดัชนีดอลลาร์อ่อนแตะ 99.15 — ทั้งสองปัจจัยนี้ลดต้นทุนทางการเงินและดึงเงินกลับเข้าหุ้น growth สหรัฐฯ ฝั่งเอเชียกลับเป็นภาพตรงข้าม KOSPI ดิ่ง 6.49% และ Nikkei ร่วง 3.48% สะท้อน position unwind และแรงขาย sector พลังงาน/วัตถุดิบที่กระจายออกทั่วภูมิภาค"
  },
  "topNews": [
    "Yield 10 ปีสหรัฐฯ ร่วงแตะ 4.33% หลังเงินเฟ้อเริ่มส่งสัญญาณชะลอตัว",
    "หุ้นกลุ่ม Tech พุ่งแรงนำโดย Nvidia และ Microsoft รับกระแส AI Optimism",
    "ราคาน้ำมัน WTI ดิ่ง 7% จากความกังวลอุปสงค์โลกชะลอตัวมากกว่าคาด",
    "ดัชนีดอลลาร์ (DXY) หลุด 100 จุดเป็นครั้งแรกในปีนี้ กดดันทองคำถูกขายทำกำไร"
  ],
  "whyItMatters": "การที่ yield ลงพร้อมดอลลาร์อ่อนในวันเดียวกันเป็นสัญญาณ risk-on ชัดเจนสำหรับสหรัฐฯ แต่การที่เอเชียไม่ตาม บ่งชี้ว่ามีปัจจัยเฉพาะภูมิภาคกดดันอยู่",
  "closingTakeaway": "Mental model วันนี้: ตลาดกำลังแยก 'สหรัฐฯ soft landing' ออกจาก 'เอเชีย commodity shock' — portfolio ที่กระจุกในพลังงานหรือส่งออกเอเชียต้องระวังเป็นพิเศษ"
}
"""

    prompt = f"""คุณคือนักวิเคราะห์มหภาคอาวุโสที่กำลังเล่าสรุปตลาดให้เพื่อนนักลงทุนรายย่อยฟังในช่วงเช้า
    ไม่ใช่เขียน research report — เล่าเป็นเรื่องราว โดยมีตัวเลขตลาดเป็น anchor แต่ต้องมี "สาเหตุเชิงมหภาค" (Geopolitics/Policy/Macro) เป็นหัวใจของเรื่อง

    วันนี้คือ {current_day_info}

    ข้อมูลตลาด:
    {market_summary}

    ข่าวและบริบท (สำคัญ: ค้นหาสัญญาณสงคราม, นโยบาย Trump, หรือความขัดแย้งทางภูมิรัฐศาสตร์):
    {news_context}

    กฎเหล็ก (Strict Rules):
    - **Connect the Dots**: ต้องเชื่อมโยงเหตุการณ์ใหญ่ (เช่น สงคราม, คำสั่งจาก Trump, ความขัดแย้งภูมิรัฐศาสตร์) เข้ากับตัวเลขตลาดโดยตรง ห้ามรายงานแต่ตัวเลขเศรษฐกิจ (Econ Data) เพียงอย่างเดียว
    - **Primary Drivers**: หากมีข่าว Crisis หรือข่าวการเมืองระดับโลกที่ขับเคลื่อนตลาด (Market Driver) ต้องยกมาเป็นประเด็นหลักใน headline และ narrative
    - **Top News**: เลือกข่าวที่สำคัญที่สุด 4 ข่าว (เน้น Geopolitics/US Policy ที่ drive ตลาด) สรุปสั้นๆ (One-liner)
    - **No Direct Advice**: ห้ามให้คำแนะนำการลงทุนโดยตรง ("ซื้อ", "ขาย") เนื่องจากไม่มีใบอนุญาต
    - **Closing Takeaway**: สรุปภาพรวมที่รวมทั้งตัวเลขตลาดและสถานการณ์โลก (Crisis/Politics) เข้าด้วยกัน

    {few_shot_example}

    ตอบเป็น JSON เท่านั้น ตาม schema นี้:
    {{
    "headline": "string — ประโยคเดียว บอกเหตุ (Crisis/News) และผล (Market) รวมกัน",
    "keyStory": {{
      "narrative": "string — 2-3 ประโยค เล่าเรื่องราวที่ Crisis หรือข่าวใหญ่ขับเคลื่อนราคาในคืนที่ผ่านมา"
    }},
    "topNews": ["string 1", "string 2", "string 3", "string 4"],
    "whyItMatters": "string — ความสำคัญของสถานการณ์ Crisis/Policy ต่อโครงสร้างตลาดในระยะถัดไป",
    "closingTakeaway": "string — mental model ที่รวมภาพ Crisis และ Econ เข้าด้วยกัน"
    }}"""

    try:
        print("Generating narrative market recap...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": "คุณเล่าเรื่องตลาดเป็นภาษาไทยแบบนักวิเคราะห์เล่าให้เพื่อนฟัง ไม่ใช่เขียน report ตัวเลขต้องอยู่ในประโยค ไม่ใช่หัวข้อ"
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return None

def send_recap_email(data):
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD") 
    receivers = ["thanak.ratt@kkpfg.com"]
    if not sender or not password: return
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"KKP Research Recap - {data['lastUpdated'].split(',')[0]}"
    msg['From'] = f"KKP Research <thanak.ratt@kkpfg.com>"
    msg['To'] = ", ".join(receivers)
    rows = "".join([f"<tr><td style='padding:12px;border-bottom:1px solid #e2e8f0;'>{item['name']}</td><td style='padding:12px;border-bottom:1px solid #e2e8f0;'>{item['price']}</td><td style='padding:12px;border-bottom:1px solid #e2e8f0;color:{'#059669' if item['status'] == 'up' else '#dc2626'};font-weight:bold;'>{item['change']}</td></tr>" for item in data['marketData']])
    news_items = "".join([f"<p style='margin-bottom:8px;'>• {item}</p>" for item in data['topNews']])
    html = f"""<html><body style="font-family:Arial,sans-serif;background-color:#f8fafc;padding:20px;color:#1e293b;"><div style="max-width:600px;margin:0 auto;background:#ffffff;padding:30px;border-radius:12px;border:1px solid #e2e8f0;border-top:8px solid #512D6D;"><h1 style="color:#512D6D;font-size:22px;">KKP Research Recap</h1><p style="color:#64748b;font-size:14px;">{data['lastUpdated']} (เวลาประเทศไทย)</p><hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;"><h2 style="color:#512D6D;font-size:16px;">📊 สรุปตลาดและราคาสินทรัพย์</h2><table style="width:100%;border-collapse:collapse;"><tr style="background:#f3f0f7;"><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">สินทรัพย์</th><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">ล่าสุด</th><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">เปลี่ยนแปลง</th></tr>{rows}</table><p style='font-size:11px;color:#94a3b8;margin-top:8px;'>แหล่งข้อมูล: Yahoo Finance, Reuters, CNBC</p><h2 style="color:#512D6D;font-size:16px;margin-top:25px;">MARKET FOCUS (WHAT & WHY)</h2><p style="font-size:15px;line-height:1.6;">{data['moverStory']}</p><h2 style="color:#512D6D;font-size:16px;margin-top:25px;">🧠 สรุปข่าวสำคัญ</h2><div style="font-size:14px;line-height:1.6;">{news_items}<hr style="border:none;border-top:1px solid #e2e8f0;margin:15px 0;"><p><strong>Why it matters:</strong> {data['whyItMatters']}</p><p><strong>Closing Takeaway:</strong> {data['closingTakeaway']}</p></div><hr style="border:none;border-top:1px solid #e2e8f0;margin:30px 0;"><p style="font-size:11px;color:#94a3b8;line-height:1.6;">เนื้อหาข้างต้นจัดทำขึ้นโดย KKP Research เพื่อวัตถุประสงค์ในการรายงานข้อมูลข่าวสารเศรษฐกิจและตลาดทุนเท่านั้น มิใช่การให้คำแนะนำการลงทุน</p></div></body></html>"""
    msg.attach(MIMEText(html, 'html'))
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            print("SUCCESS: Email sent.")
    except Exception as e: print(f"ERROR: Email failed: {e}")

def main():
    print("Main execution started (Version 1.9).")
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.now(tz)
    
    days_th = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]
    current_day_info = f"วัน{days_th[now.weekday()]}ที่ {now.day}/{now.month}/{now.year}"
    
    months_th = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    date_str = f"{now.day} {months_th[now.month]} {now.year + 543}, {now.strftime('%H:%M')} น."
    
    market_data = get_market_data_v2()
    news_context = get_latest_news_context()
    
    ai_content = generate_ai_content(str(market_data), news_context, current_day_info)
    
    if ai_content:
        # Map new schema for frontend compatibility
        mover_story = f"**{ai_content.get('headline', '')}**\n\n{ai_content.get('keyStory', {}).get('narrative', '')}"

        final_data = {
            "lastUpdated": date_str, 
            "marketData": market_data, 
            "moverStory": mover_story, 
            "topNews": ai_content.get('topNews', []),
            "whyItMatters": ai_content.get('whyItMatters', ''),
            "closingTakeaway": ai_content.get('closingTakeaway', '')
        }
        
        with open('src/data.json', 'w', encoding='utf-8') as f: 
            json.dump(final_data, f, ensure_ascii=False, indent=2)
        
        send_recap_email(final_data)
        print("Workflow finished successfully.")
    else: 
        print("Workflow failed at AI generation.")

if __name__ == "__main__": main()
