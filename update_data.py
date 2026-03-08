import os
import json
import yfinance as yf
import google.generativeai as genai
from datetime import datetime
import pytz
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Setup Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

def get_market_data():
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
        except:
            continue
    return results

def generate_content(market_summary):
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
    
    response = model.generate_content(prompt)
    try:
        content = response.text.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        return json.loads(content)
    except:
        return None

def send_email(data):
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD") # Use App Password
    receiver = "thanak.ratt@kkpfg.com"
    
    if not sender or not password:
        print("Email credentials missing. Skipping email.")
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"KKP Research Recap - {data['lastUpdated'].split(',')[0]}"
    msg['From'] = f"KKP Research Bot <{sender}>"
    msg['To'] = receiver

    # Generate HTML rows for market data
    rows = ""
    for item in data['marketData']:
        color = "#059669" if item['status'] == 'up' else "#dc2626"
        rows += f"""
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; font-size: 14px;">{item['name']}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; font-size: 14px;">{item['price']}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; font-size: 14px; color: {color}; font-weight: bold;">{item['change']}</td>
            </tr>
        """

    macro_items = "".join([f"<p style='margin-bottom: 8px;'>• {item}</p>" for item in data['macroFocus']])
    risk_items = "".join([f"<p style='margin-bottom: 8px;'>• {item}</p>" for item in data['implications']])

    html = f"""
    <html>
    <body style="font-family: 'Helvetica', Arial, sans-serif; background-color: #f8fafc; padding: 20px; color: #1e293b;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 12px; border: 1px solid #e2e8f0; border-top: 8px solid #512D6D;">
            <div style="margin-bottom: 30px;">
                <h1 style="color: #512D6D; margin: 0; font-size: 22px; font-weight: bold;">KKP Research - Last Night Recap</h1>
                <p style="color: #64748b; font-size: 14px; margin-top: 5px;">{data['lastUpdated']}</p>
            </div>
            
            <div style="margin-bottom: 25px;">
                <h2 style="color: #512D6D; font-size: 16px; border-bottom: 2px solid #f3f0f7; padding-bottom: 8px; text-transform: uppercase;">📊 สรุปตลาดและราคาสินทรัพย์</h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background: #f3f0f7;">
                        <th style="text-align: left; padding: 10px; font-size: 11px; color: #512D6D;">สินทรัพย์</th>
                        <th style="text-align: left; padding: 10px; font-size: 11px; color: #512D6D;">ล่าสุด</th>
                        <th style="text-align: left; padding: 10px; font-size: 11px; color: #512D6D;">เปลี่ยนแปลง</th>
                    </tr>
                    {rows}
                </table>
            </div>

            <div style="margin-bottom: 25px;">
                <div style="display: inline-block; background: #f3f0f7; color: #512D6D; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; margin-bottom: 10px;">MARKET FOCUS</div>
                <p style="font-size: 15px; line-height: 1.6;">{data['moverStory']}</p>
            </div>

            <div style="margin-bottom: 25px;">
                <h2 style="color: #512D6D; font-size: 16px; border-bottom: 2px solid #f3f0f7; padding-bottom: 8px; text-transform: uppercase;">🧠 MACRO FOCUS</h2>
                <div style="font-size: 14px; line-height: 1.6;">{macro_items}</div>
            </div>

            <div style="margin-bottom: 25px;">
                <h2 style="color: #512D6D; font-size: 16px; border-bottom: 2px solid #f3f0f7; padding-bottom: 8px; text-transform: uppercase;">⚠️ RISK WATCH</h2>
                <div style="font-size: 14px; line-height: 1.6;">{risk_items}</div>
            </div>

            <div style="font-size: 11px; color: #94a3b8; margin-top: 40px; border-top: 1px solid #e2e8f0; padding-top: 20px; line-height: 1.6;">
                เนื้อหาข้างต้นจัดทำขึ้นโดย KKP Research เพื่อวัตถุประสงค์ในการรายงานข้อมูลข่าวสารเศรษฐกิจและตลาดทุนเท่านั้น มิใช่การให้คำแนะนำการลงทุนหรือการชี้ชวนซื้อขายหลักทรัพย์
            </div>
        </div>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(html, 'html'))

    try:
        # Use Gmail/Google SMTP as a free standard
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

def main():
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.now(tz)
    date_str = now.strftime("%d %B %Y, %H:%M น.")
    
    months = {
        "January": "มกราคม", "February": "กุมภาพันธ์", "March": "มีนาคม",
        "April": "เมษายน", "May": "พฤษภาคม", "June": "มิถุนายน",
        "July": "กรกฎาคม", "August": "สิงหาคม", "September": "กันยายน",
        "October": "ตุลาคม", "November": "พฤศจิกายน", "December": "ธันวาคม"
    }
    for eng, thai in months.items():
        date_str = date_str.replace(eng, thai)

    market_data = get_market_data()
    ai_content = generate_content(str(market_data))
    
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
        
        # Send Email
        send_email(final_data)
        print("Process completed.")

if __name__ == "__main__":
    main()
