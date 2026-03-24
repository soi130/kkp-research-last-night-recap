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

# VERSION: 1.9.3 - Reliable News Mapping
print("Starting script Version 1.9.3 (Reliable News Mapping)...")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def get_latest_news_context():
    print("Fetching news feeds...")
    feeds = [
        {"name": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
        {"name": "NPR World", "url": "https://feeds.npr.org/1004/rss.xml"},
        {"name": "The Hill", "url": "https://thehill.com/feed/"},
        {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rss"},
        {"name": "CNBC Economy", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=401&id=10000063"}
    ]
    
    news_items = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    keywords = ["Fed", "Rate", "Inflation", "CPI", "NFP", "Unemployment", "GDP", "Yield", "War", "Conflict", "Oil", "Geopolitical", "Trump", "Election", "Tariff", "Iran", "Strike"]
    
    id_counter = 1
    news_map = {} # To link IDs back to URLs
    
    for feed in feeds:
        try:
            resp = requests.get(feed['url'], headers=headers, timeout=10)
            root = ET.fromstring(resp.content)
            for item in root.findall('./channel/item')[:20]:
                title = item.find('title').text
                link = item.find('link').text if item.find('link') is not None else ""
                
                content = f"[ID: {id_counter}] Source: {feed['name']} | Headline: {title}"
                news_map[str(id_counter)] = {"text": title, "url": link}
                
                if any(kw.lower() in title.lower() for kw in keywords):
                    news_items.insert(0, content)
                else:
                    news_items.append(content)
                id_counter += 1
                    
        except Exception as e:
            print(f"Error fetching {feed['name']}: {e}")
            continue
            
    return "\n".join(news_items[:150]), news_map

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
  "headline": "ความตึงเครียดลดลง + yield ดิ่ง ดันหุ้นสหรัฐฯ พุ่งสวนทองคำและน้ำมัน",
  "keyStory": {
    "narrative": "คืนนี้ตลาดหุ้นสหรัฐฯ ปิดบวกแรงหลัง Trump ประกาศเลื่อนแผนโจมตีอิหร่าน ช่วยลดความเสี่ยงภูมิรัฐศาสตร์ ประกอบกับ yield 10 ปีที่ร่วงแตะ 4.33% ช่วยหนุนกลุ่มเทคโนโลยี"
  },
  "selectedNewsIDs": ["1", "5", "12", "18"],
  "whyItMatters": "การที่ Crisis คลี่คลาย (De-escalation) เป็นบวกต่อหุ้น แต่เป็นลบต่อทองคำ/น้ำมัน ต้องระบุทิศทางให้ถูก",
  "closingTakeaway": "Mental model: ตลาดเล่นตามข่าวสงคราม — หากไม่รุนแรง หุ้นไปต่อ"
}
"""

    prompt = f"""คุณคือนักวิเคราะห์มหภาคอาวุโสที่เล่าสรุปตลาดให้เพื่อนฟัง
    วันนี้คือ {current_day_info}

    ข้อมูลตลาด (Market Summary):
    {market_summary}

    บริบทข่าว (News Context พร้อม ID):
    {news_context}

    กฎเหล็ก:
    - **Logic Check**: ตรรกะเหตุและผลต้องถูกต้อง (เช่น สงครามคลี่คลาย = หุ้นขึ้น/น้ำมันลง, สงครามดุเดือด = หุ้นลง/น้ำมันขึ้น)
    - **News Selection**: เลือกข่าวที่ขับเคลื่อนตลาดที่สุด 4 ข่าว โดยระบุเป็น "selectedNewsIDs" จาก ID ที่ให้ไปเท่านั้น
    - **Zero Hallucination**: ห้ามมโนข่าวเองเด็ดขาด ถ้าไม่มีข่าวสงครามใน Context ห้ามเขียนเรื่องสงคราม

    ตอบเป็น JSON เท่านั้น ตาม schema นี้:
    {{
    "headline": "string",
    "keyStory": {{"narrative": "string"}},
    "selectedNewsIDs": ["string id 1", "string id 2", "string id 3", "string id 4"],
    "whyItMatters": "string",
    "closingTakeaway": "string"
    }}"""

    try:
        print("Generating narrative market recap...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "คุณเล่าเรื่องตลาดเป็นภาษาไทยแบบนักวิเคราะห์ ตรรกะภูมิรัฐศาสตร์ต้องเป๊ะ และเลือกข่าวตาม ID ที่ให้ไปเท่านั้น"},
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
    print("Main execution started (Version 1.9.3).")
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.now(tz)
    
    months_th = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    date_str = f"{now.day} {months_th[now.month]} {now.year + 543}, {now.strftime('%H:%M')} น."
    
    market_data = get_market_data_v2()
    news_context, news_map = get_latest_news_context()
    
    days_th = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]
    current_day_info = f"วัน{days_th[now.weekday()]}ที่ {now.day}/{now.month}/{now.year}"
    
    ai_content = generate_ai_content(str(market_data), news_context, current_day_info)
    
    if ai_content:
        # Re-map selected IDs to actual text and URLs
        top_news = []
        for nid in ai_content.get('selectedNewsIDs', []):
            if nid in news_map:
                top_news.append(news_map[nid])
        
        # Fallback if AI didn't select news
        if not top_news:
            top_news = list(news_map.values())[:4]

        mover_story = f"**{ai_content.get('headline', '')}**\n\n{ai_content.get('keyStory', {}).get('narrative', '')}"

        final_data = {
            "lastUpdated": date_str, 
            "marketData": market_data, 
            "moverStory": mover_story, 
            "topNews": top_news,
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
