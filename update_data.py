import os
import json
import yfinance as yf
from openai import OpenAI
from datetime import datetime
import pytz
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# VERSION: 1.3 - Switch to OpenAI
print("Starting script Version 1.3 (OpenAI)...")

# Setup OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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
    - moverStory: (A concise paragraph about the main market driver, focus on macro/geopolitics)
    - macroFocus: (An array of 3 bullet points about key macro data like Fed, Inflation, Jobs)
    - implications: (An array of 3 bullet points about what COULD happen and risks to watch, focusing on TH economy/markets)
    """
    
    try:
        print("Generating content with OpenAI GPT-4o-mini...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"OpenAI AI Generation Error: {e}")
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
            <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; font-size: 14px;">{item['name']}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; font-size: 14px;">{item['price']}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; font-size: 14px; color: {'#059669' if item['status'] == 'up' else '#dc2626'}; font-weight: bold;">{item['change']}</td>
        </tr>
    """ for item in data['marketData']])

    macro_items = "".join([f"<p style='margin-bottom: 8px;'>• {item}</p>" for item in data['macroFocus']])
    risk_items = "".join([f"<p style='margin-bottom: 8px;'>• {item}</p>" for item in data['implications']])

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f8fafc; padding: 20px; color: #1e293b;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 12px; border: 1px solid #e2e8f0; border-top: 8px solid #512D6D;">
            <h1 style="color: #512D6D; font-size: 22px;">KKP Research - Last Night Recap</h1>
            <p style="color: #64748b; font-size: 14px;">{data['lastUpdated']} (เวลาประเทศไทย)</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
            <h2 style="color: #512D6D; font-size: 16px;">📊 สรุปตลาดและราคาสินทรัพย์</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background: #f3f0f7;">
                    <th style="text-align: left; padding: 10px; font-size: 11px; color: #512D6D;">สินทรัพย์</th>
                    <th style="text-align: left; padding: 10px; font-size: 11px; color: #512D6D;">ล่าสุด</th>
                    <th style="text-align: left; padding: 10px; font-size: 11px; color: #512D6D;">เปลี่ยนแปลง</th>
                </tr>
                {rows}
            </table>
            <h2 style="color: #512D6D; font-size: 16px; margin-top: 25px;">MARKET FOCUS</h2>
            <p style="font-size: 15px; line-height: 1.6;">{data['moverStory']}</p>
            <h2 style="color: #512D6D; font-size: 16px; margin-top: 25px;">🧠 MACRO FOCUS</h2>
            <div style="font-size: 14px; line-height: 1.6;">{macro_items}</div>
            <h2 style="color: #512D6D; font-size: 16px; margin-top: 25px;">⚠️ RISK WATCH</h2>
            <div style="font-size: 14px; line-height: 1.6;">{risk_items}</div>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;">
            <p style="font-size: 11px; color: #94a3b8; line-height: 1.6;">
                เนื้อหาข้างต้นจัดทำขึ้นโดย KKP Research เพื่อวัตถุประสงค์ในการรายงานข้อมูลข่าวสารเศรษฐกิจและตลาดทุนเท่านั้น 
                มิใช่การให้คำแนะนำการลงทุนหรือการชี้ชวนซื้อขายหลักทรัพย์
            </p>
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
            print(f"SUCCESS: Email sent to recipients.")
    except Exception as e:
        print(f"ERROR: Email failed: {e}")

def main():
    print("Main execution started (OpenAI Version).")
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.now(tz)
    
    months_th = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    date_str = f"{now.day} {months_th[now.month]} {now.year + 543}, {now.strftime('%H:%M')} น."
    
    market_data = get_market_data_v2()
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
