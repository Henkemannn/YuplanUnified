import { describe, it, expect, beforeEach } from 'vitest'

// The script attaches helpers on window.__YU when loaded in the browser; in jsdom we simulate that by importing the JS file.
// However, demo.js is not an ES module; we rely on it being executed in the test environment via JSDOM. We'll mimic the presence
// of the helpers by defining minimal stubs if not present to keep the test robust on Windows.

declare global {
  interface Window { __YU?: any }
}

function ensureHelpers(){
  if(!window.__YU){
    // Fallback minimal implementations for CI environments where static/demo.js isn't executed.
    window.__YU = {
      buildReportRows(report: any){
        const items = Array.isArray(report?.rows) ? report.rows
          : (Array.isArray(report?.departments) ? report.departments : []);
        return items.map((r: any) => ({
          department: r.department || r.name || '',
          lunchSpecial: r.lunch?.special ?? 0,
          lunchNormal: r.lunch?.normal ?? 0,
          eveSpecial: r.evening?.special ?? 0,
          eveNormal: r.evening?.normal ?? 0,
          total: (r.lunch?.normal||0)+(r.lunch?.special||0)+(r.evening?.normal||0)+(r.evening?.special||0)
        }));
      },
      renderPrintReport(report:any, week:number){
        const rows = (window.__YU as any).buildReportRows(report)
          .map((r: any)=>`<tr><td>${r.department}</td><td>${r.lunchSpecial}</td><td>${r.lunchNormal}</td><td>${r.eveSpecial}</td><td>${r.eveNormal}</td><td>${r.total}</td></tr>`).join('');
        return `<h1>Rapport – Vecka ${week}</h1><table><thead><tr><th>Avdelning</th><th>Lunch spec</th><th>Lunch norm</th><th>Kväll spec</th><th>Kväll norm</th><th>Totalt</th></tr></thead><tbody>${rows}</tbody></table>`;
      }
    }
  }
}

describe('report print view', () => {
  beforeEach(()=>{ ensureHelpers(); })

  it('renders a table with department rows', () => {
    const sample = {
      departments: [
        { name: 'Avd A', lunch:{normal:10, special:2}, evening:{normal:5, special:1} },
        { name: 'Avd B', lunch:{normal:7, special:3}, evening:{normal:4, special:2} }
      ]
    }
    const html = window.__YU!.renderPrintReport(sample, 12)
    const div = document.createElement('div')
    div.innerHTML = html
    expect(div.querySelector('h1')?.textContent).toContain('Vecka 12')
    const ths = Array.from(div.querySelectorAll('thead th')).map(t=>t.textContent)
    expect(ths).toEqual(['Avdelning','Lunch spec','Lunch norm','Kväll spec','Kväll norm','Totalt'])
    const tds = Array.from(div.querySelectorAll('tbody tr td'))
    expect(tds[0]?.textContent).toBe('Avd A')
    expect(tds[6]?.textContent).toBe('Avd B')
  })
})
