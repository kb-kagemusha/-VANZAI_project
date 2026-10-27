import { expect, test, type Page } from '@playwright/test';

async function mock(page:Page, stale=false) {
  await page.addInitScript(()=>localStorage.setItem('vanzai.admin.access_token','local-test'));
  const writes:any[]=[];let setting:any=null;
  const order={version_id:'v1',series_id:'s1',document_number:'ORD-001',version_no:1,project_name:'秋のイベント',work_date_label:'10月22日～24日',categories:[],client_id:'c1',client_name:'依頼元会社',revision:0,amount_id:null,amount:null,billing_month:null,invoice_id:null,status:'missing',incentive_enabled:true,incentive_note:'当日の追加分は運営が確認',incentive_amount:null,total_amount:null,billing_ready:false,client_mismatch:false};
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(!path.startsWith('/api/')) return route.continue();
    const method=route.request().method();
    const reply=(value:any,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(value)});
    if(path.endsWith('/auth/me')) return reply({id:'admin',username:'admin',role:'admin',is_active:true,permissions:['invoice_read','invoice_generate','order_read']});
    if(path.endsWith('/auth/session')) return reply({access_token:'local-test',token_type:'bearer'});
    if(path.endsWith('/daily/rates')) {setting={...route.request().postDataJSON(),revision:1};writes.push({path,body:setting});return reply({setting,dates:[],projects:[],previous_days:[]});}
    if(path.endsWith('/daily/preview')) return reply({project_name:'実績案件',source_digest:'a'.repeat(64),rates_revision:1,excluded_count:1,needs_review:0,days:[{date:'2026-10-22',weekday:3,quantity:2,unit_price:'20000.01',subtotal:'40000.02',workers:[{worker_id:'w1',name:'真島さん',minutes:480,actual_ids:['a1','a2']},{worker_id:'w2',name:'田中さん',minutes:480,actual_ids:['a3']}]},{date:'2026-10-23',weekday:4,quantity:3,unit_price:'20000.01',subtotal:'60000.03',workers:[]},{date:'2026-10-24',weekday:5,quantity:1,unit_price:'25000',subtotal:'25000',workers:[]}]});
    if(path.endsWith('/daily/confirm')) {writes.push({path,body:route.request().postDataJSON()});return stale?reply({detail:'実績または単価が変わりました。人数と明細を読み直して確認してください'},409):reply({id:'a1',revision:1});}
    if(path.endsWith('/daily')) return reply({setting,dates:[],is_test:false,client_id:'c1',projects:[{id:'p1',name:'実績案件',code:'P001'}]});
    if(path.endsWith('/order-billing/orders')) return reply({items:[order],total:1});
    if(path.endsWith('/order-billing/summary')) return reply({missing_count:1,total:1});
    if(path.endsWith('/order-billing/clients')) return reply({items:[{id:'c1',name:'依頼元会社'}]});
    return reply({items:[],total:0});
  });return writes;
}

async function open(page:Page) {
  await page.goto('/billing/order-amounts');
  await page.getByRole('button',{name:'1人日単価で計算',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'1人日単価で請求金額を確認',exact:true});
  await dialog.getByLabel('人数を確認する実績の案件').selectOption('p1');
  await dialog.getByLabel('基本の1人日単価（税抜・円）',{exact:true}).fill('20000.01');
  await dialog.getByRole('button',{name:'曜日別に設定する',exact:true}).click();
  await dialog.getByLabel('土曜日（税抜・円）',{exact:true}).fill('25000');
  await dialog.getByRole('button',{name:'単価設定を保存して実績を確認',exact:true}).click();
  await expect(dialog.getByText('真島さん',{exact:true})).toBeVisible();
  return dialog;
}

test('review actual people, weekday rate and signed adjustment before saving exact totals',async({page})=>{
  await page.setViewportSize({width:1440,height:1100});
  const writes=await mock(page);const dialog=await open(page);
  await expect(dialog.locator('.daily-billing-total')).toHaveText('通常請求額（税抜） ¥125,000.05');
  await dialog.getByLabel('2026-10-23の調整額',{exact:true}).fill('-10000');
  const review=dialog.getByRole('button',{name:'日別明細と金額を最終確認',exact:true});
  await expect(review).toBeDisabled();
  await dialog.getByLabel('2026-10-23の調整理由',{exact:true}).fill('半日分を運営で確認');
  await dialog.getByLabel('インセンティブ額（税抜・円、未確定は空欄）',{exact:true}).fill('5000');
  await dialog.getByLabel('請求月',{exact:true}).fill('2026-11');
  await dialog.getByLabel('日別人数・単価・調整額を運営で確認しました',{exact:true}).check();
  await review.click();expect(writes).toHaveLength(1);
  await expect(dialog.locator('.daily-billing-review')).toContainText('合計（税抜） ¥120,000.05');
  await page.screenshot({path:'.work/daily-billing-review.png',fullPage:true});
  await dialog.getByRole('button',{name:'この明細で請求金額を確定',exact:true}).click();
  await expect(dialog).toHaveCount(0);
  expect(writes[1].body).toMatchObject({billing_month:'202611',expected_revision:0,incentive_amount:'5000',adjustments:{'2026-10-23':{amount:'-10000',reason:'半日分を運営で確認'}}});
  expect(writes[1].body).not.toHaveProperty('amount');
  expect(writes[1].body).not.toHaveProperty('quantity');
});

test('changed actuals preserve entered adjustment and ask for another review',async({page})=>{
  await mock(page,true);const dialog=await open(page);
  await dialog.getByLabel('2026-10-23の調整額',{exact:true}).fill('-10000');
  await dialog.getByLabel('2026-10-23の調整理由',{exact:true}).fill('半日分を確認');
  await dialog.getByLabel('日別人数・単価・調整額を運営で確認しました',{exact:true}).check();
  await dialog.getByRole('button',{name:'日別明細と金額を最終確認',exact:true}).click();
  await dialog.getByRole('button',{name:'この明細で請求金額を確定',exact:true}).click();
  await expect(dialog.getByRole('alert')).toContainText('実績または単価が変わりました');
  await expect(dialog.getByLabel('2026-10-23の調整額',{exact:true})).toHaveValue('-10,000');
  await dialog.getByRole('button',{name:'実績を読み直す',exact:true}).click();
  await expect(dialog.getByRole('button',{name:'日別明細と金額を最終確認',exact:true})).toBeDisabled();
});
