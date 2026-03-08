import { Globe, TrendingDown, TrendingUp, AlertCircle, BarChart3, Info, PieChart } from 'lucide-react';
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
        <div style={{fontSize: '0.75rem', color: '#707070', marginTop: '1rem'}}>
          * ดัชนีตลาดเอเชียเป็นระดับปิด ณ วันศุกร์ที่ผ่านมา | ราคาทองคำเป็น Spot Price
        </div>
      </section>

      {/* 2. ประเด็นหลัก */}
      <section className="section">
        <h2 className="section-title">
          <Globe size={24} />
          ประเด็นหลักที่ขับเคลื่อนตลาด
        </h2>
        <div className="story-content">
          <span className="market-tag">Market Focus</span>
          <p>{data.moverStory}</p>
        </div>
      </section>

      {/* 3. ข้อมูลมหภาค */}
      <section className="section">
        <h2 className="section-title">
          <PieChart size={24} />
          ข้อมูลมหภาคที่สำคัญ (Macro Focus)
        </h2>
        <div className="story-content">
          {data.macroFocus.map((item, index) => (
            <p key={index}>• {item}</p>
          ))}
        </div>
      </section>

      {/* 4. ปัจจัยที่ต้องระมัดระวัง */}
      <section className="section">
        <h2 className="section-title">
          <AlertCircle size={24} />
          สิ่งที่อาจเกิดขึ้นและปัจจัยที่ต้องระมัดระวัง
        </h2>
        <div className="implication-content">
          {data.implications.map((item, index) => (
            <p key={index}>• {item}</p>
          ))}
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
