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

# VERSION: 1.9.2 - News URLs + Logical Consistency
print("Starting script Version 1.9.2 (News URLs)...")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def get_latest_news_context():
    print("Fetching deep market news context with URLs...")
    feeds = [
        {"name": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
        {"name": "NPR World", "url": "https://feeds.npr.org/1004/rss.xml"},
        {"name": "The Hill (US Politics)", "url": "https://thehill.com/feed/"},
        {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rss"},
        {"name": "CNBC Markets", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=401&id=15839069"},
        {"name": "CNBC Economy", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=401&id=10000063"}
    ]
    news_items = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    keywords = ["Fed", "Rate", "Inflation", "CPI", "NFP", "Unemployment", "GDP", "Yield", "War", "Conflict", "Oil", "Geopolitical", "Trump", "Election", "Tariff", "Iran", "Strike"]
    
    for feed in feeds:
        try:
            resp = requests.get(feed['url'], headers=headers, timeout=10)
            root = ET.fromstring(resp.content)
            for item in root.findall('./channel/item')[:30]:
                title = item.find('title').text
                link = item.find('link').text if item.find('link') is not None else ""
                desc = item.find('description').text if item.find('description') is not None else ""
                
                if desc and '<' in desc:
                    try: desc = ET.fromstring(f"<div>{desc}</div>").text
                    except: pass
                
                content = f"Source: {feed['name']} | Headline: {title} | Summary: {desc} | URL: {link}"
                
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
EXAMPLE OUTPUT:
{
  "headline": "ความตึงเครียดในตะวันออกกลางลดลง + yield ดิ่ง ดันหุ้นสหรัฐฯ พุ่ง — แต่เอเชียเจ็บหนักจาก margin call",
  "keyStory": {
    "narrative": "คืนนี้ตลาดสหรัฐฯ ฟื้นตัวได้จากแรงสองทาง: ความกังวลเรื่องสงครามที่คลี่คลายลงหลัง Trump ประกาศเลื่อนแผนโจมตีอิหร่าน ประกอบกับอัตราผลตอบแทนพันธบัตร 10 ปีที่ร่วงลงสู่ 4.33% — ทั้งสองปัจจัยนี้ช่วยลดต้นทุนทางการเงินและดึงเงินกลับเข้าสินทรัพย์เสี่ยง"
  },
  "topNews": [
    {
      "text": "Trump เลื่อนการโจมตีโรงไฟฟ้าอิหร่าน 5 วัน เพื่อเปิดช่องเจรจา",
      "url": "https://www.npr.org/xyz"
    },
    {
      "text": "Yield 10 ปีสหรัฐฯ ร่วงแตะ 4.33% หลังนักลงทุนคลายกังวลชั่วคราว",
      "url": "https://www.cnbc.com/abc"
    }
  ],
  "whyItMatters": "การที่ความเสี่ยงภูมิรัฐศาสตร์ 'ลดลง' เป็นบวกต่อหุ้นและเป็นลบต่อทองคำ/น้ำมัน ต้องแยกแยะทิศทางให้ถูกต้อง",
  "closingTakeaway": "Mental model: ตลาดตอบรับเชิงบวกต่อการ De-escalation — หากสถานการณ์นิ่ง หุ้นมีโอกาสไปต่อ"
}
"""

    prompt = f"""คุณคือนักวิเคราะห์มหภาคอาวุโสที่เล่าสรุปตลาดให้เพื่อนฟัง
    วันนี้คือ {current_day_info}

    ข้อมูลตลาด (Market Summary):
    {market_summary}

    บริบทข่าว (News Context พร้อม URL):
    {news_context}

    กฎเหล็ก (Strict Rules):
    - **News URLs**: ในส่วน "topNews" ต้องแนบ URL ของข่าวนั้นๆ มาด้วยทุกครั้งจากบริบทข่าว
    - **Logical Consistency**: ตรวจสอบความสมเหตุสมผลของเหตุและผล เช่น ความตึงเครียด 'ลดลง' (De-escalation) ถึงจะส่งผลให้หุ้น 'ขึ้น' และน้ำมัน 'ลง' หากความตึงเครียด 'เพิ่มขึ้น' หุ้นต้อง 'ลง' และน้ำมัน 'ขึ้น' ห้ามเขียนสลับกันเด็ดขาด
    - **Strict Grounding**: ห้ามมโนข่าวเอง ทุกข่าวต้องมี URL อ้างอิงใน context เท่านั้น
    - **No Direct Advice**: ห้ามบอกให้ซื้อหรือขาย

    {few_shot_example}

    ตอบเป็น JSON เท่านั้น ตาม schema นี้:
    {{
    "headline": "string — สรุปเหตุการณ์ที่เกิดขึ้นและผลต่อตลาด (ตรวจสอบตรรกะให้ถูกต้อง)",
    "keyStory": {{
      "narrative": "string — 2-3 ประโยค เล่าเรื่องราวจากข่าวและตัวเลข (ตรรกะต้องเป๊ะ)"
    }},
    "topNews": [
      {{"text": "string headline สั้นๆ", "url": "string url จริงจาก context"}}
    ],
    "whyItMatters": "string — ความสำคัญต่อโครงสร้างตลาด",
    "closingTakeaway": "string — mental model สรุปภาพรวม"
    }}"""

    try:
        print("Generating narrative market recap with URLs and Logical Check...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": "คุณเล่าเรื่องตลาดแบบมืออาชีพ ตรรกะเหตุและผลเรื่องภูมิรัฐศาสตร์ต้องถูกต้อง ห้ามเขียนสลับทิศทาง และต้องแนบ URL ข่าวเสมอ"
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
    
    # Updated news items with links for email
    news_items = "".join([f"<p style='margin-bottom:8px;'>• {item['text']} <a href='{item['url']}' style='color:#512D6D;font-size:12px;text-decoration:none;'>[อ่านต่อ]</a></p>" for item in data['topNews']])
    
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
    print("Main execution started (Version 1.9.2).")
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
