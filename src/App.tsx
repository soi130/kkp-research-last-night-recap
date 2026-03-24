import { Globe, TrendingDown, TrendingUp, BarChart3, Info, PieChart, Newspaper, ExternalLink } from 'lucide-react';
import './App.css';
import data from './data.json';

function App() {
  return (
    <div className="container">
      <header>
        <h1>KKP Research - Last Night Recap</h1>
        <div className="timestamp" style={{background: '#512D6D', color: '#fff', padding: '4px 12px', borderRadius: '4px', display: 'inline-block'}}>
          อัปเดตล่าสุด: {data.lastUpdated} (เวลาประเทศไทย)
        </div>
      </header>

      {/* 1. สรุปดัชนีสำคัญ */}
      <section className="section">
        <h2 className="section-title">
          <BarChart3 size={24} />
          สรุปดัชนีและราคาสินทรัพย์สำคัญ
        </h2>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>สินทรัพย์ / ดัชนี</th>
                <th>ระดับล่าสุด</th>
                <th>เปลี่ยนแปลง</th>
              </tr>
            </thead>
            <tbody>
              {data.marketData.map((item, index) => (
                <tr key={index}>
                  <td>{item.name}</td>
                  <td>{item.price}</td>
                  <td className={item.status === 'up' ? 'change-up' : 'change-down'}>
                    {item.status === 'up' ? <TrendingUp size={16} style={{marginRight: '4px'}} /> : <TrendingDown size={16} style={{marginRight: '4px'}} />}
                    {item.change}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{fontSize: '0.75rem', color: '#707070', marginTop: '1rem', lineHeight: '1.5'}}>
          * ดัชนีตลาดเอเชียเป็นระดับปิด ณ วันทำการล่าสุด | ราคาทองคำเป็น Spot Price<br />
          แหล่งข้อมูล: Yahoo Finance, Reuters, CNBC
        </div>
      </section>

      {/* 2. ประเด็นหลัก */}
      <section className="section">
        <h2 className="section-title">
          <Globe size={24} />
          เมื่อคืนเกิดอะไรขึ้นและทำไม (Market Focus)
        </h2>
        <div className="story-content">
          <p>{data.moverStory}</p>
        </div>
      </section>

      {/* 3. สรุปข่าวสำคัญ */}
      <section className="section">
        <h2 className="section-title">
          <Newspaper size={24} />
          ข่าวสำคัญ
        </h2>
        <div className="story-content">
          {data.topNews.map((item: any, index: number) => (
            <div key={index} style={{marginBottom: '1rem', display: 'flex', alignItems: 'flex-start'}}>
              <span style={{marginRight: '8px', color: '#512D6D'}}>•</span>
              <div>
                <span>[{item.source}] <strong>{item.text}</strong></span>
                {item.url && (
                  <a 
                    href={item.url} 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    style={{
                      marginLeft: '8px', 
                      color: '#512D6D', 
                      textDecoration: 'none', 
                      fontSize: '0.85rem',
                      display: 'inline-flex',
                      alignItems: 'center'
                    }}
                  >
                    [อ่านต่อ <ExternalLink size={12} style={{marginLeft: '2px'}} />]
                  </a>
                )}
              </div>
            </div>
          ))}
          
          <div style={{
            marginTop: '1.5rem', 
            padding: '1.25rem', 
            background: '#f3f0f7', 
            borderRadius: '8px',
            borderLeft: '4px solid #512D6D'
          }}>
            <p style={{marginBottom: 0}}>
              <PieChart size={18} style={{verticalAlign: 'middle', marginRight: '8px', color: '#512D6D'}} />
              <strong>Why these matters:</strong> {data.whyItMatters}
            </p>
          </div>

          <div style={{
            marginTop: '1rem', 
            padding: '1.25rem', 
            background: '#f3f0f7', 
            borderRadius: '8px',
            borderLeft: '4px solid #512D6D'
          }}>
            <p style={{marginBottom: 0}}>
              <strong>Takeaways:</strong> {data.closingTakeaway}
            </p>
          </div>
        </div>
      </section>

      <footer className="disclaimer">
        <Info size={14} style={{verticalAlign: 'middle', marginRight: '4px'}} />
        เนื้อหาข้างต้นจัดทำขึ้นโดย KKP Research เพื่อวัตถุประสงค์ในการรายงานข้อมูลข่าวสารเศรษฐกิจและตลาดทุนเท่านั้น 
        มิใช่การให้คำแนะนำการลงทุนหรือการชี้ชวนซื้อขายหลักทรัพย์ ผู้ใช้งานควรศึกษาข้อมูลเพิ่มเติมและใช้วิจารณญาณในการตัดสินใจ
      </footer>
    </div>
  );
}

export default App;
