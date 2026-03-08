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
                if ticker == "GC=F": price_str = f"${close:,.2f}"
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
    
    DATA CONTEXT:
    - Market Numbers: {market_summary}
    - Recent Headlines: {news_headlines}
    
    INSTRUCTIONS:
    1. Summarize only the MOST IMPORTANT stories. Don't be vague. Mention specific data points (e.g., 'CPI rose 3.1%', 'Fed's Powell said...').
    2. Focus on Macro and Geopolitics. 
    3. Investment Implications must be logical and specific to the Thai context (Trade balance, Baht volatility, specific Thai sectors).
    4. TONE: Formal, professional, high-signal, NO DRAMA.
    5. CONSTRAINT: NO investment advice. Use Thai language.
    
    Provide the output in JSON format:
    {{
      "moverStory": "A concise but detailed paragraph summarizing the key move of the night.",
      "macroFocus": ["Bullet 1 with data", "Bullet 2 with data", "Bullet 3 with data"],
      "implications": ["Specific risk 1", "Specific risk 2", "Specific risk 3"]
    }}
    """
    
    try:
        print("Generating deep analysis with OpenAI GPT-4o-mini...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional financial analyst at KKP Research. Your output is data-driven and objective."},
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
    msg['From'] = f"KKP Research Bot <{sender}>"
    msg['To'] = ", ".join(receivers)
    rows = "".join([f"<tr><td style='padding:12px;border-bottom:1px solid #e2e8f0;'>{item['name']}</td><td style='padding:12px;border-bottom:1px solid #e2e8f0;'>{item['price']}</td><td style='padding:12px;border-bottom:1px solid #e2e8f0;color:{'#059669' if item['status'] == 'up' else '#dc2626'};font-weight:bold;'>{item['change']}</td></tr>" for item in data['marketData']])
    macro_items = "".join([f"<p style='margin-bottom:8px;'>• {item}</p>" for item in data['macroFocus']])
    risk_items = "".join([f"<p style='margin-bottom:8px;'>• {item}</p>" for item in data['implications']])
    html = f"""<html><body style="font-family:Arial,sans-serif;background-color:#f8fafc;padding:20px;color:#1e293b;"><div style="max-width:600px;margin:0 auto;background:#ffffff;padding:30px;border-radius:12px;border:1px solid #e2e8f0;border-top:8px solid #512D6D;"><h1 style="color:#512D6D;font-size:22px;">KKP Research Recap</h1><p style="color:#64748b;font-size:14px;">{data['lastUpdated']} (เวลาประเทศไทย)</p><hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;"><h2 style="color:#512D6D;font-size:16px;">📊 สรุปตลาดและราคาสินทรัพย์</h2><table style="width:100%;border-collapse:collapse;"><tr style="background:#f3f0f7;"><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">สินทรัพย์</th><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">ล่าสุด</th><th style="text-align:left;padding:10px;font-size:11px;color:#512D6D;">เปลี่ยนแปลง</th></tr>{rows}</table><h2 style="color:#512D6D;font-size:16px;margin-top:25px;">MARKET FOCUS</h2><p style="font-size:15px;line-height:1.6;">{data['moverStory']}</p><h2 style="color:#512D6D;font-size:16px;margin-top:25px;">🧠 MACRO FOCUS</h2><div style="font-size:14px;line-height:1.6;">{macro_items}</div><h2 style="color:#512D6D;font-size:16px;margin-top:25px;">⚠️ RISK WATCH</h2><div style="font-size:14px;line-height:1.6;">{risk_items}</div><hr style="border:none;border-top:1px solid #e2e8f0;margin:30px 0;"><p style="font-size:11px;color:#94a3b8;line-height:1.6;">เนื้อหาข้างต้นจัดทำขึ้นโดย KKP Research เพื่อวัตถุประสงค์ในการรายงานข้อมูลข่าวสารเศรษฐกิจและตลาดทุนเท่านั้น มิใช่การให้คำแนะนำการลงทุน</p></div></body></html>"""
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
