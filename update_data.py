import os
import json
import yfinance as yf
from google import genai
from datetime import datetime
import pytz
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# VERSION: 1.2 - Explicit Function Check
print("Starting script Version 1.2...")

# Setup Gemini
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
MODELS_TO_TRY = ['gemini-2.0-flash', 'gemini-2.5-flash']

def get_market_data_v2():
    print("Fetching market data...")
    tickers = {
        "^GSPC": "S&P 500 (US)",
        "^IXIC": "Nasdaq (US)",
        "^N225": "Nikkei 225 (JP)*",
        "^KS11": "KOSPI (KR)*",
        "GC=F": "Gold (Spot)",
        "^TNX": "US 10Y Yield"
    }
    
    results = []
    for ticker, name in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")
            if len(hist) >= 2:
                close = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                change_pct = ((close - prev_close) / prev_close) * 100
                
                price_str = f"{close:,.2f}"
                if ticker == "GC=F": price_str = f"${close:,.2f}"
                if ticker == "^TNX": price_str = f"{close:.2f}%"
                
                results.append({
                    "name": name,
                    "price": price_str,
                    "change": f"{'+' if change_pct >= 0 else ''}{change_pct:.2f}%",
                    "status": "up" if change_pct >= 0 else "down"
                })
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            continue
    return results

def generate_ai_content(market_summary):
    prompt = f"""
    You are a professional researcher at KKP Research. 
    Summarize the global market events from last night for Thai investors.
    Tone: Formal, professional, concise, NOT dramatized. 
    Constraint: DO NOT give investment advice. Use Thai language.
    
    Market Data Context: {market_summary}
    
    Provide the output in JSON format with these exact keys:
    - moverStory: (A concise paragraph)
    - macroFocus: (An array of 3 strings)
    - implications: (An array of 3 strings)
    """
    
    for model_name in MODELS_TO_TRY:
        try:
            print(f"Generating content with model: {model_name}")
            response = client.models.generate_content(model=model_name, contents=prompt)
            content = response.text.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            return json.loads(content)
        except Exception as e:
            print(f"AI Error with {model_name}: {e}")
            continue
    return None

def send_recap_email(data):
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD") 
    receivers = ["thanak.ratt@kkpfg.com", "mynameisnak@gmail.com"]
    
    if not sender or not password:
        print("Email credentials missing.")
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"KKP Research Recap - {data['lastUpdated'].split(',')[0]}"
    msg['From'] = f"KKP Research Bot <{sender}>"
    msg['To'] = ", ".join(receivers)

    rows = "".join([f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">{item['name']}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">{item['price']}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; color: {'#059669' if item['status'] == 'up' else '#dc2626'}; font-weight: bold;">{item['change']}</td>
        </tr>
    """ for item in data['marketData']])

    macro_items = "".join([f"<li>{item}</li>" for item in data['macroFocus']])
    risk_items = "".join([f"<li>{item}</li>" for item in data['implications']])

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #1e293b;">
        <div style="max-width: 600px; margin: 0 auto; border-top: 8px solid #512D6D; padding: 20px; border: 1px solid #e2e8f0;">
            <h1 style="color: #512D6D;">KKP Research Recap</h1>
            <p>{data['lastUpdated']}</p>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background: #f3f0f7;">
                    <th style="text-align: left; padding: 10px;">สินทรัพย์</th>
                    <th style="text-align: left; padding: 10px;">ล่าสุด</th>
                    <th style="text-align: left; padding: 10px;">เปลี่ยนแปลง</th>
                </tr>
                {rows}
            </table>
            <h3>MARKET FOCUS</h3>
            <p>{data['moverStory']}</p>
            <h3>MACRO FOCUS</h3>
            <ul>{macro_items}</ul>
            <h3>RISK WATCH</h3>
            <ul>{risk_items}</ul>
            <hr>
            <p style="font-size: 11px; color: #94a3b8;">มิใช่การให้คำแนะนำการลงทุน</p>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(html, 'html'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            print(f"SUCCESS: Email sent to {', '.join(receivers)}")
    except Exception as e:
        print(f"ERROR: Email failed: {e}")

def main():
    print("Main execution started.")
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.now(tz)
    
    # Format Thai date and time
    months_th = [
        "", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
        "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
    ]
    day = now.day
    month = months_th[now.month]
    year = now.year + 543
    time_str = now.strftime("%H:%M")
    date_str = f"{day} {month} {year}, {time_str} น."
    
    # Simple market fetch
    market_data = get_market_data_v2()
    print(f"Data fetched: {len(market_data)} indices.")
    
    # AI Summary
    ai_content = generate_ai_content(str(market_data))
    
    if ai_content:
        final_data = {
            "lastUpdated": date_str,
            "marketData": market_data,
            "moverStory": ai_content['moverStory'],
            "macroFocus": ai_content['macroFocus'],
            "implications": ai_content['implications']
        }
        
        with open('src/data.json', 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)
        
        send_recap_email(final_data)
        print("Workflow finished successfully.")
    else:
        print("Workflow failed at AI generation.")

if __name__ == "__main__":
    main()
