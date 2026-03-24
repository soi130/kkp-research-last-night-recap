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
    print("Fetching deep market news context (50 items per feed)...")
    feeds = [
        {"name": "Reuters Markets", "url": "https://www.reuters.com/tools/rssfeed/us/marketnews"},
        {"name": "Reuters Business", "url": "https://www.reuters.com/tools/rssfeed/us/businessnews"},
        {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rss"},
        {"name": "CNBC Markets", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=401&id=15839069"},
        {"name": "CNBC Economy", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=401&id=10000063"}
    ]
    news_items = []
    for feed in feeds:
        try:
            resp = requests.get(feed['url'], timeout=10)
            root = ET.fromstring(resp.content)
            for item in root.findall('./channel/item')[:50]:
                title = item.find('title').text
                desc = item.find('description').text if item.find('description') is not None else ""
                if desc:
                    if '<' in desc:
                        try:
                            desc = ET.fromstring(f"<div>{desc}</div>").text
                        except:
                            pass
                news_items.append(f"Source: {feed['name']} | Headline: {title} | Summary: {desc}\n---")
        except Exception as e:
            print(f"Error fetching {feed['name']}: {e}")
            continue
    return "\n".join(news_items[:150])

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
    "narrative": "คืนนี้ตลาดสหรัฐฯ ฟื้นตัวได้จากแรงสองทาง: อัตราผลตอบแทนพันธบัตร 10 ปีร่วงลงสู่ 4.33% ขณะที่ดัชนีดอลลาร์อ่อนแตะ 99.15 — ทั้งสองปัจจัยนี้ลดต้นทุนทางการเงินและดึงเงินกลับเข้าหุ้น growth สหรัฐฯ ฝั่งเอเชียกลับเป็นภาพตรงข้าม KOSPI ดิ่ง 6.49% และ Nikkei ร่วง 3.48% สะท้อน position unwind และแรงขาย sector พลังงาน/วัตถุดิบที่กระจายออกทั่วภูมิภาค",
    "dataPoints": [
      {"label": "US 10Y Yield", "value": "4.33%", "change": "-1.30%"},
      {"label": "DXY", "value": "99.15", "change": "-0.50%"},
      {"label": "WTI Oil", "value": "$89.19", "change": "-9.29%"},
      {"label": "KOSPI", "value": "5,405.75", "change": "-6.49%"}
    ],
    "whyItMatters": "การที่ yield ลงพร้อมดอลลาร์อ่อนในวันเดียวกันเป็นสัญญาณ risk-on ชัดเจนสำหรับสหรัฐฯ แต่การที่เอเชียไม่ตาม บ่งชี้ว่ามีปัจจัยเฉพาะภูมิภาค (ราคาโภคภัณฑ์ร่วง, ค่าเงิน) กดดันอยู่"
  },
  "implications": [
    {
      "audience": "ผู้ถือหุ้นพลังงาน/ปิโตรเคมี",
      "action": "ทบทวนสัดส่วน PTT, PTTEP, IRPC",
      "reason": "WTI ร่วง 9.3% คืนเดียว — กำไร Q2 ของกลุ่มนี้มีความเสี่ยงถูกปรับลดจาก consensus"
    },
    {
      "audience": "นักลงทุนที่มีหุ้นส่งออกไทย",
      "action": "ตรวจสอบ FX hedge ratio",
      "reason": "USD/THB อ่อนที่ 32.44 กดรายได้เมื่อแปลงกลับ โดยเฉพาะส่งออกที่ต้นทุนเป็นบาทแต่รายได้เป็นดอลลาร์"
    },
    {
      "audience": "นักลงทุนที่กำลังพิจารณาเพิ่มหุ้นเอเชีย",
      "action": "รอดูทิศทางอีก 1–2 วัน",
      "reason": "KOSPI ดิ่ง 6.49% อาจมีแรง technical rebound — แต่ถ้าไม่มีข่าวดีรองรับ อาจเป็นแค่ dead cat bounce"
    }
  ],
  "closingTakeaway": "Mental model วันนี้: ตลาดกำลังแยก 'สหรัฐฯ soft landing' ออกจาก 'เอเชีย commodity shock' — portfolio ที่กระจุกในพลังงานหรือส่งออกเอเชียต้องระวังเป็นพิเศษจนกว่าราคาน้ำมันจะนิ่ง"
}
"""

    prompt = f"""คุณคือนักวิเคราะห์มหภาคอาวุโสที่กำลังเล่าสรุปตลาดให้เพื่อนนักลงทุนรายย่อยฟังในช่วงเช้า
ไม่ใช่เขียน research report — เล่าเป็นเรื่องราว มีตัวเลขเป็น anchor ไม่ใช่เป็นหัวข้อ

วันนี้คือ {current_day_info}

ข้อมูลตลาด:
{market_summary}

ข่าวและบริบท:
{news_context}

กฎเหล็ก:
- ต้องใส่ตัวเลขจริง (NFP, อัตราว่างงาน, อัตราดอกเบี้ย ฯลฯ) เมื่อมีในข้อมูล
- ห้ามขึ้นประโยคด้วย "ราคา X ลดลง Y%" โดยไม่บอกว่าทำไม
- ห้ามใช้ภาษาทางการแบบ report ("ทั้งนี้", "อย่างไรก็ตาม", "กล่าวคือ")
- implications ต้องระบุ audience ชัดเจน ไม่ใช่คำแนะนำกว้าง ๆ

{few_shot_example}

ตอบเป็น JSON เท่านั้น ตาม schema นี้:
{{
  "headline": "string — ประโยคเดียว ≤15 คำ บอกเหตุและผลรวมกัน",
  "keyStory": {{
    "narrative": "string — 2-3 ประโยค เล่าสิ่งที่เกิดขึ้นแบบ story มีตัวเลขแทรก",
    "dataPoints": [
      {{"label": "ชื่อตัวชี้วัด", "value": "ค่าปัจจุบัน", "change": "การเปลี่ยนแปลง"}}
    ],
    "whyItMatters": "string — 1-2 ประโยค ความสำคัญต่อภาพรวม"
  }},
  "implications": [
    {{
      "audience": "กลุ่มนักลงทุนที่ได้รับผลกระทบโดยตรง",
      "action": "สิ่งที่ควรทำหรือตรวจสอบ",
      "reason": "เพราะ... (อ้างตัวเลขจริง)"
    }}
  ],
  "closingTakeaway": "string — mental model 1-2 ประโยค ที่ติดมือกลับไปได้"
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
    macro_items = "".join([f"<p style='margin-bottom:8px;'>• {item}</p>" for item in data['macroFocus']])
    risk_items = "".join([f"<p style='margin-bottom:8px;'>• {item}</p>" for item in data['implications']])
    html = f"""<html><body style="font-family:Arial,sans-serif;background-color:#f8fafc;padding:20px;color:#1e293b;"><div style="max-width:600px;margin:0 auto;background:#ffffff;padding:30px;border-radius:12px;border:1px solid #e2e8f0;border-top:8px solid #512D6D;"><h1 style="color:#512D6D;font-size:22px;">KKP Research Recap</h1><p style="color:#64748b;font-size:14px;">{data['lastUpdated']} (เวลาประเทศไทย)</p><hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;"><h2 style="color:#512D6D;font-size:16px;">📊 สรุปตลาดและราคาสินทรัพย์</h2><table style="width:100%;border-collapse:collapse;"><tr style="background:#f3f0f7;"><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">สินทรัพย์</th><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">ล่าสุด</th><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">เปลี่ยนแปลง</th></tr>{rows}</table><p style='font-size:11px;color:#94a3b8;margin-top:8px;'>แหล่งข้อมูล: Yahoo Finance, Reuters, CNBC</p><h2 style="color:#512D6D;font-size:16px;margin-top:25px;">MARKET FOCUS (WHAT & WHY)</h2><p style="font-size:15px;line-height:1.6;">{data['moverStory']}</p><h2 style="color:#512D6D;font-size:16px;margin-top:25px;">🧠 สรุปประเด็นเศรษฐกิจสำคัญ</h2><div style="font-size:14px;line-height:1.6;">{macro_items}</div><h2 style="color:#512D6D;font-size:16px;margin-top:25px;">⚠️ ข้อควรระวังสำหรับนักลงทุนไทย</h2><div style="font-size:14px;line-height:1.6;">{risk_items}</div><hr style="border:none;border-top:1px solid #e2e8f0;margin:30px 0;"><p style="font-size:11px;color:#94a3b8;line-height:1.6;">เนื้อหาข้างต้นจัดทำขึ้นโดย KKP Research เพื่อวัตถุประสงค์ในการรายงานข้อมูลข่าวสารเศรษฐกิจและตลาดทุนเท่านั้น มิใช่การให้คำแนะนำการลงทุน</p></div></body></html>"""
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
        # Map new schema to existing keys for frontend compatibility
        mover_story = f"**{ai_content.get('headline', '')}**\n\n{ai_content.get('keyStory', {}).get('narrative', '')}"
        
        macro_focus = []
        key_story = ai_content.get('keyStory', {})
        for dp in key_story.get('dataPoints', []):
            macro_focus.append(f"{dp['label']}: {dp['value']} ({dp['change']})")
        if key_story.get('whyItMatters'):
            macro_focus.append(f"Why it matters: {key_story['whyItMatters']}")
        if ai_content.get('closingTakeaway'):
            macro_focus.append(f"Closing Takeaway: {ai_content['closingTakeaway']}")
            
        implications = []
        for imp in ai_content.get('implications', []):
            implications.append(f"[{imp['audience']}] {imp['action']} — {imp['reason']}")

        final_data = {
            "lastUpdated": date_str, 
            "marketData": market_data, 
            "moverStory": mover_story, 
            "macroFocus": macro_focus, 
            "implications": implications
        }
        
        with open('src/data.json', 'w', encoding='utf-8') as f: 
            json.dump(final_data, f, ensure_ascii=False, indent=2)
        
        send_recap_email(final_data)
        print("Workflow finished successfully.")
    else: 
        print("Workflow failed at AI generation.")

if __name__ == "__main__": main()
