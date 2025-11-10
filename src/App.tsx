import React from 'react';
import DepartmentsPage from './pages/admin/DepartmentsPage';
import DietDefaultsPage from './pages/admin/DietDefaultsPage';
import Alt2BulkPage from './pages/admin/Alt2BulkPage';

function useQueryParam(name:string){
  const sp = new URLSearchParams(window.location.search);
  return sp.get(name) ?? '';
}

export default function App(){
  const path = window.location.pathname;
  if (path.startsWith('/admin/departments')) {
    const siteId = useQueryParam('site') || 's1';
    return <DepartmentsPage siteId={siteId} />;
  }
  if (path.startsWith('/admin/diet-defaults')) {
    const depId = useQueryParam('department') || 'd1';
    return <DietDefaultsPage departmentId={depId} />;
  }
  if (path.startsWith('/admin/alt2')) {
    const siteId = useQueryParam('site') || 's1';
    // week handled inside page state but we pass site
    return <Alt2BulkPage siteId={siteId} />;
  }
  return (
    <div style={{padding:16}}>
      <h1>Admin UI</h1>
      <p>Routes:</p>
      <ul>
        <li><a href="/admin/departments?site=s1">/admin/departments?site=s1</a></li>
        <li><a href="/admin/diet-defaults?department=d1">/admin/diet-defaults?department=d1</a></li>
        <li><a href="/admin/alt2?site=s1&week=1">/admin/alt2?site=s1&week=1</a></li>
      </ul>
    </div>
  );
}
