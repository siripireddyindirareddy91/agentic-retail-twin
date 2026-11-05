import axios from 'axios';
import { sandboxRequest } from './sandbox';
export const API_BASE = (import.meta as any).env.VITE_API_BASE_URL || '';
// Production uses the same-origin FastAPI function by default. Browser demo
// mode must be explicitly enabled; missing configuration must never disable auth.
export const SANDBOX = (import.meta as any).env.VITE_SANDBOX === 'true';
const http = axios.create({baseURL:API_BASE,timeout:30000});
http.interceptors.request.use(config=>{const token=sessionStorage.getItem('st-token')||localStorage.getItem('st-token');if(token)config.headers.Authorization=`Bearer ${token}`;return config;});
export async function api(path:string,method='GET',data?:any):Promise<any>{
  if(SANDBOX)return sandboxRequest(path,method,data);
  try{return (await http.request({url:'/api'+path,method,data})).data;}catch(e:any){
    if(e.response?.status===401&&!path.startsWith('/auth/')){sessionStorage.removeItem('st-token');localStorage.removeItem('st-token');window.dispatchEvent(new Event('st-signout'));}
    const detail=e.response?.data?.detail;
    throw new Error(typeof detail==='string'?detail:Array.isArray(detail)?detail.map((x:any)=>x.msg).join(', '):'Cannot reach the API. Check the backend URL and connection.');
  }
}
export async function downloadReport(kind:string,format:string,start='',end=''){
  if(SANDBOX){
    const rows=await sandboxRequest('/reports/'+kind,'GET');
    if(format==='pdf'){window.print();return;}
    const keys=Object.keys(rows[0]||{id:''});
    const escape=(v:any)=>'"'+String(v??'').replaceAll('"','""')+'"';
    const csv=[keys.join(','),...rows.map((r:any)=>keys.map(k=>escape(r[k])).join(','))].join('\n');
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download=`supplytwin-${kind}.csv`;a.click();URL.revokeObjectURL(url);return;
  }
  const response=await http.get(`/api/reports/${kind}?format=${format}&start=${start}&end=${end}`,{responseType:'blob'});
  const url=URL.createObjectURL(response.data);const a=document.createElement('a');a.href=url;a.download=`supplytwin-${kind}.${format}`;a.click();URL.revokeObjectURL(url);
}
