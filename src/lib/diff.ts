export type Row = { id:string; amount:number };
export function diffRows(prev:Row[], next:Row[]) {
  const map = new Map(prev.map(r=>[r.id, r.amount]));
  return next.filter(r=> map.get(r.id) !== r.amount);
}
