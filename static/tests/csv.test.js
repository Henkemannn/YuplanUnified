import { describe, it, expect } from 'vitest'

// Load the page script to populate window.__YU
import '../demo.js'

const api = global.window.__YU

describe('CSV parser basics', () => {
  it('strips BOM and detects semicolon', () => {
    const txt = '\uFEFFa;b\n1;2\n'
    const clean = api.stripBom(txt)
    expect(clean.startsWith('\uFEFF')).toBe(false)
    expect(api.autodetectDelimiter(clean)).toBe(';')
    const res = api.parseCsv(clean, api.autodetectDelimiter(clean))
    expect(res.headers).toEqual(['a','b'])
    expect(res.rows[0]).toEqual({ a: '1', b: '2' })
  })

  it('parses comma CSV with quotes and escaped quotes', () => {
    const txt = 'day,lunch,evening\n"Mon","Fish, ""n"" Chips","Pasta"\n'
    const res = api.parseCsv(txt, ',')
    expect(res.rows[0].day).toBe('Mon')
    expect(res.rows[0].lunch).toBe('Fish, "n" Chips')
    expect(res.rows[0].evening).toBe('Pasta')
  })

  it('handles åäö in headers and values', () => {
    const txt = 'Dag;LUnch;Kväll\nMån;Ärtsoppa;Pannkakor\n'
    const res = api.parseCsv(txt, ';')
    expect(Object.keys(res.rows[0])).toEqual(['Dag','LUnch','Kväll'])
    expect(res.rows[0]['LUnch']).toBe('Ärtsoppa')
  })
})

describe('Day normalization and summary', () => {
  it('normalizes variety of day strings', () => {
    expect(api.normalizeDay('mån')).toBe(1)
    expect(api.normalizeDay('Mon')).toBe(1)
    expect(api.normalizeDay('ti')).toBe(2)
    expect(api.normalizeDay('ons')).toBe(3)
    expect(api.normalizeDay('Thu')).toBe(4)
    expect(api.normalizeDay('Fre')).toBe(5)
    expect(api.normalizeDay('lör')).toBe(6)
    expect(api.normalizeDay('Sun')).toBe(7)
  })

  it('builds summary per day', () => {
    const rows = [
      { Dag: 'Mån', Lunch: 'Soppa', Kväll: 'Pasta' },
      { Dag: 'Tis', Lunch: 'Fisk', Kväll: '' }
    ]
    const sum = api.summarizeMenu({ dayCol:'Dag', lunchCol:'Lunch', eveCol:'Kväll' }, rows)
    expect(sum['1']).toEqual({ lunch: 'Soppa', eve: 'Pasta' })
    expect(sum['2']).toEqual({ lunch: 'Fisk', eve: '' })
  })
})
