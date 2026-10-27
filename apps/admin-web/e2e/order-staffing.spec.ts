import { expect, test } from "@playwright/test";

test("operator reviews daily selection before confirming; Escape closes the top dialog only", async ({page}) => {
  await page.setViewportSize({width: 1280,height: 900});
  await page.addInitScript(() => localStorage.setItem("vanzai.admin.access_token","mock-admin-token"));
  const people = ["真島 達也", "候補の方", "未回答の方"].map((name,i) => ({worker_id:`w${i}`,name,offered_dates:["2026-10-29"],accepted_dates:i<2?["2026-10-29"]:[],available:true,ack_status:i<2?"acked":"unacked"}));
  let state = {enabled:true,revision:1,is_test:true,days:[{date:"2026-10-29",capacity:1,confirmed:0,confirmed_ids:[] as string[],closed:false}],people,notices:[] as {status:string}[]};
  const writes: unknown[]=[];
  await page.route("**/api/**",async route => {
    const path=new URL(route.request().url()).pathname;
    if(!path.startsWith("/api/")) return route.continue();
    const respond=(json:unknown) => route.fulfill({json});
    if(path.endsWith("/auth/me")) return respond({id:"test",username:"test",display_name:"試験運営",role:"admin",is_active:true,permissions:["order_read","order_write"]});
    if(path.endsWith("/auth/session")) return respond({access_token:"mock-admin-token",token_type:"bearer"});
    if(path === "/api/order-requests/participation-calendar") return respond({days:[{date:"2026-10-29",events:[{series_id:"s1",version_id:"v1",document_id:"d1",document_number:"TEST-STAFFING",project_name:"会場運営テスト",is_test:true,ok:[],changing:[],unanswered:[{worker_id:"w2",name:"未回答の方"}],unavailable:[],pending:people.slice(0,2)}]}],workers:people.map(p=>({...p,line_linked:true}))});
    if(path === "/api/order-requests/versions/v1") return respond({id:"v1",kind:"test",document_number:"TEST-STAFFING",version_no:1,status:"confirmed",requires_operator_confirmation:true,work_date_label:"2026-10-29",body:"会場運営テスト",deliveries:[]});
    if(path === "/api/order-staffing/v1/decisions") {
      writes.push(route.request().postDataJSON());
      state={...state,revision:2,days:[{...state.days[0],confirmed:1,confirmed_ids:["w0"],closed:true}],notices:[{status:"skipped"},{status:"skipped"},{status:"skipped"}]};
      return respond(state);
    }
    if(path === "/api/order-staffing/v1") return respond(state);
    return respond({items:[],total:0});
  });
  await page.goto("/operations/calendar?view=event&month=2026-10&test=1");
  await page.getByRole("button",{name:"TEST-STAFFING",exact:true}).click();
  await page.getByRole("button",{name:"参加者・日別人数を確認"}).click();
  const dialog=page.getByRole("dialog",{name:"参加者の最終確定"});
  await expect(dialog).toBeVisible();
  await dialog.getByRole("checkbox",{name:/真島 達也/}).check();
  await expect(dialog.getByRole("checkbox",{name:/未回答の方/})).toBeDisabled();
  await dialog.getByRole("button",{name:"確定内容を確認",exact:true}).click();
  expect(writes).toHaveLength(0);
  await page.screenshot({path:"../../.work/staffing-selection-review.png",fullPage:true});
  await dialog.getByRole("button",{name:"この内容で確定・通知する",exact:true}).click();
  await expect(dialog.getByText("参加者を確定しました。",{exact:false})).toBeVisible();
  expect(writes).toEqual([{selected:{"2026-10-29":["w0"]},close_dates:[],reason:"",revision:1}]);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("dialog",{name:/発注依頼書 TEST-STAFFING/})).toBeVisible();
});
