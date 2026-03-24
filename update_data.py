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

# VERSION: 1.9.1 - Strict Geopolitical Grounding
print("Starting script Version 1.9.1 (Strict Grounding)...")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def get_latest_news_context():
    print("Fetching deep market news context (Verified BBC, NPR, The Hill)...")
    feeds = [
        {"name": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
        {"name": "NPR World", "url": "https://feeds.npr.org/1004/rss.xml"},
        {"name": "The Hill (US Politics)", "url": "https://thehill.com/feed/"},
        {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rss"},
        {"name": "CNBC Markets", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=401&id=15839069"},
        {"name": "CNBC Economy", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=401&id=10000063"}
    ]
    news_items = []
    
    # Headers to avoid 403 Forbidden
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # Keywords to prioritize (Crisis/Politics focus)
    keywords = ["Fed", "Rate", "Inflation", "CPI", "NFP", "Unemployment", "GDP", "Yield", "War", "Conflict", "Oil", "Geopolitical", "Trump", "Election", "Tariff", "Iran", "Strike"]
    
    for feed in feeds:
        try:
            resp = requests.get(feed['url'], headers=headers, timeout=10)
            root = ET.fromstring(resp.content)
            for item in root.findall('./channel/item')[:30]:
                title = item.find('title').text
                desc = item.find('description').text if item.find('description') is not None else ""
                
                # Simple HTML cleaning
                if desc and '<' in desc:
                    try: desc = ET.fromstring(f"<div>{desc}</div>").text
                    except: pass
                
                content = f"Source: {feed['name']} | Headline: {title} | Summary: {desc}"
                
                # Prioritize: Add high-impact news to the front
                if any(kw.lower() in content.lower() for kw in keywords):
                    news_items.insert(0, content + "\n---")
                else:
                    news_items.append(content + "\n---")
                    
        except Exception as e:
            print(f"Error fetching {feed['name']}: {e}")
            continue
            
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
  "headline": "Trump เลื่อนการโจมตีอิหร่าน + yield ดิ่ง ดันหุ้นสหรัฐฯ พุ่ง — แต่เอเชียเจ็บหนักจาก margin call และขาย cyclicals",
  "keyStory": {
    "narrative": "คืนนี้ตลาดสหรัฐฯ ฟื้นตัวได้จากแรงสองทาง: ประธานาธิบดี Trump ประกาศเลื่อนการโจมตีโรงไฟฟ้าอิหร่านออกไป 5 วันเพื่อเจรจา ขณะที่อัตราผลตอบแทนพันธบัตร 10 ปีร่วงลงสู่ 4.33% — ทั้งสองปัจจัยนี้ช่วยลดแรงกดดันด้านความเสี่ยงภูมิรัฐศาสตร์และดึงเงินกลับเข้าหุ้น growth ฝั่งสหรัฐฯ ทันที"
  },
  "topNews": [
    "Trump เลื่อนการโจมตีโรงไฟฟ้าอิหร่าน 5 วัน เพื่อเปิดช่องเจรจา (ที่มา: NPR)",
    "Yield 10 ปีสหรัฐฯ ร่วงแตะ 4.33% หลังนักลงทุนคลายกังวลชั่วคราว",
    "หุ้นกลุ่ม Tech พุ่งแรงรับกระแส De-escalation และ AI Optimism",
    "ราคาน้ำมัน WTI ดิ่งแรงหลังคลายกังวลเรื่องอุปทานน้ำมันในตะวันออกกลาง"
  ],
  "whyItMatters": "การที่ความเสี่ยงสงครามถูกเลื่อนออกไปพร้อม yield ลงในวันเดียวกันเป็นสัญญาณ risk-on ชัดเจน แต่ต้องระวังว่านี่อาจเป็นเพียงความสงบชั่วคราว",
  "closingTakeaway": "Mental model วันนี้: ตลาดกำลังเล่นกับ 'News Baseline' — เมื่อข่าวร้าย (สงคราม) ไม่เกิดตามกำหนด ตลาดจะพุ่งสวนทันที"
}
"""

    prompt = f"""คุณคือนักวิเคราะห์มหภาคอาวุโสที่เล่าสรุปตลาดให้เพื่อนฟัง
    วันนี้คือ {current_day_info}

    ข้อมูลตลาด (Market Summary):
    {market_summary}

    บริบทข่าว (News Context - ข้อมูลจริงเท่านั้น):
    {news_context}

    กฎเหล็กป้องกันการมโน (Strict Grounding Rules):
    - **Source-Only Logic**: ต้องใช้ข้อมูลจาก "บริบทข่าว" ที่ให้ไปเท่านั้น **ห้ามนำข้อมูลภายนอกหรือความรู้รอบตัวอื่นมาเขียนเด็ดขาด** (Zero-Out-of-Context)
    - **No Geopolitical Hallucination**: หากใน "บริบทข่าว" ไม่มีการเอ่ยถึงสงคราม, Trump, หรือความขัดแย้งภูมิรัฐศาสตร์ **ห้ามเขียนเรื่องพวกนี้เด็ดขาด** ให้เขียนสรุปเฉพาะตัวเลขเศรษฐกิจ (Econ Data) และข้อมูลตลาดที่มี
    - **Fact-Check Headers**: ข่าวใน "Top News" ต้องมาจาก Headline ในบริบทข่าวเท่านั้น
    - **Connect the Dots**: เชื่อมโยงเหตุการณ์ในข่าวเข้ากับตัวเลขตลาด **เฉพาะในกรณีที่มีข่าวรองรับจริง**

    {few_shot_example}

    ตอบเป็น JSON เท่านั้น ตาม schema นี้:
    {{
    "headline": "string — สรุปเหตุการณ์ข่าว (จาก context) และผลต่อตลาด",
    "keyStory": {{
      "narrative": "string — 2-3 ประโยค เล่าสิ่งที่เกิดขึ้นจากข่าวและตัวเลข (ต้องมีที่มาจาก context)"
    }},
    "topNews": ["string 1", "string 2", "string 3", "string 4"],
    "whyItMatters": "string — ความสำคัญของสถานการณ์ต่อโครงสร้างตลาด",
    "closingTakeaway": "string — mental model สรุปภาพรวมจากข้อมูลที่มีจริง"
    }}"""

    try:
        print("Generating narrative market recap with Strict Grounding...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": "คุณเล่าเรื่องตลาดเป็นภาษาไทยแบบนักวิเคราะห์เล่าให้เพื่อนฟัง ห้ามนำข้อมูลภายนอกที่ไม่ได้อยู่ใน context มาใช้เด็ดขาด ถ้าไม่มีข่าวการเมืองให้เขียนเฉพาะเรื่องเศรษฐกิจ"
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
    print("Main execution started (Version 1.9.1).")
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
