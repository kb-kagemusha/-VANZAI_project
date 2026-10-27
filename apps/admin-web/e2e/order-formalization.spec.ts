import { expect,test,type Page } from '@playwright/test';

async function mock(page:Page,existing=false) {
  await page.addInitScript(()=>localStorage.setItem('vanzai.admin.access_token','local-test'));
  const writes:any[]=[];
  const conditions=JSON.stringify({format:'additional-request-v1',project_name:'会場案内イベント',content:'来場者の受付と誘導',notes:'集合時間を確認してください',schedule:{version:1,work_groups:[{id:'g1',date_mode:'single',from:'2026-11-01',to:'2026-11-01',start_time:'09:00',end_time:'18:00'}],rates_follow_work:true,rate_groups:[{id:'r1',work_group_id:'g1',date_mode:'single',from:'2026-11-01',to:'2026-11-01',amount:'15000',unit:'day'}]}});
  const relation={source_document_number:'TEST-001',source_version_id:'v1',formal_document_number:'ORD-002',formal_version_id:'v2',formal_status:'draft',formal_hidden:false};
  const formal={id:'v2',document_id:'d2',document_number:'ORD-002',version_no:1,kind:'formal',status:'draft',draft_worker_ids:['w2'],draft_recipient_absences:{},deliveries:[],notes:[],change_documents:[],request_conditions:conditions,body:'',site_name:'会場A',contact_name:'運営担当',work_date_label:'2026-11-01',internal_source:{client_id:'c1',client_staff_id:null,client_name:'正式な発注元'},follow_up_due_on:'2026-10-31',follow_up_due_time:'21:00',requires_operator_confirmation:true,formalization:relation};
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(!path.startsWith('/api/')) return route.continue();
    const reply=(json:any)=>route.fulfill({json});
    if(path.endsWith('/auth/me')) return reply({id:'admin',username:'admin',role:'admin',is_active:true,permissions:['order_read','order_write']});
    if(path.endsWith('/auth/session')) return reply({access_token:'local-test',token_type:'bearer'});
    if(path==='/api/workers')return reply({items:[{id:'w1',name:'テスト時の候補'},{id:'w2',name:'正式な候補'}],total:2});
    if(path==='/api/clients') return reply({items:[{id:'c1',name:'正式な発注元'}],total:1});
    if(path.endsWith('/formalization')){
      if(route.request().method()==='POST'){writes.push(route.request().postDataJSON());return reply(formal);}
      return reply(existing?{existing:relation}:{existing:null,source_digest:'a'.repeat(64),document_number:'TEST-001',work_date_label:'2026-11-01',request_conditions:conditions,body:'',site_name:'会場A',contact_name:'運営担当',capacities:{'2026-11-01':2},source_candidates:[{id:'w1',name:'テスト時の候補',active:true}]});
    }
    if(path==='/api/order-requests/versions/v2')return reply(formal);
    if(path==='/api/order-requests')return reply({items:[{document_id:'d1',version_id:'v1',document_number:'TEST-001',version_no:1,kind:'test',status:'confirmed',project_name:'会場案内イベント',work_date_label:'2026-11-01',created_by_name:'運営',recipient_count:1,change_documents:[]}],total:1});
    return reply({items:[],total:0});
  });return writes;
}

test('formal draft requires explicit client, candidates, deadline and review, without sending',async({page})=>{
  await page.setViewportSize({width:1440,height:1100});
  const writes=await mock(page);
  await page.goto('/operations/order-requests');
  await page.getByRole('button',{name:'正式版を作成・確認',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'テスト案件から正式版を作成',exact:true});
  await expect(dialog.getByRole('checkbox',{name:'テスト時の候補',exact:true})).not.toBeChecked();
  await expect(dialog.getByRole('combobox',{name:'発注元',exact:true})).toHaveValue('');
  const create=dialog.getByRole('button',{name:'確認して正式な下書きを作成',exact:true});
  await expect(create).toBeDisabled();
  await dialog.getByRole('combobox',{name:'発注元',exact:true}).selectOption('c1');
  await dialog.getByRole('checkbox',{name:'正式な候補',exact:true}).check();
  await dialog.getByLabel('正式版の回答期限（21:00）',{exact:true}).fill('2026-10-31');
  await dialog.getByLabel('案件内容・正式な発注元・候補者・募集上限を確認しました',{exact:true}).check();
  expect(writes).toHaveLength(0);
  await page.screenshot({path:'.work/order-formalization-review.png',fullPage:true});
  await create.click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('dialog',{name:'第1版',exact:true})).toBeVisible();
  expect(writes).toEqual([{source_digest:'a'.repeat(64),internal_source:{client_id:'c1',client_staff_id:null},worker_ids:['w2'],capacities:{'2026-11-01':2},masters_reviewed:true,follow_up_due_on:'2026-10-31'}]);
});

test('existing formal draft opens instead of creating another',async({page})=>{
  const writes=await mock(page,true);
  await page.goto('/operations/order-requests');
  await page.getByRole('button',{name:'正式版を作成・確認',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'テスト案件から正式版を作成',exact:true});
  await expect(dialog).toContainText('正式版 ORD-002 は作成済み');
  await dialog.getByRole('button',{name:'作成済みの正式版を開く',exact:true}).click();
  expect(writes).toHaveLength(0);
  await expect(dialog).toHaveCount(0);
});
