import os
import json
import yfinance as yf
import google.generativeai as genai
from datetime import datetime
import pytz

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
        # Extract JSON from response
        content = response.text.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        return json.loads(content)
    except:
        return None

def main():
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.now(tz)
    date_str = now.strftime("%d %B %Y, %H:%M น.")
    
    # Map English month to Thai
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
        print("Data updated successfully.")

if __name__ == "__main__":
    main()
