import { expect, test } from "@playwright/test";

for (const mode of ["admin", "line"] as const) test(`${mode}: prepare then explicitly send a replacement invitation and finalize one person`,async({page})=>{
  await page.setViewportSize({width:mode === "line" ? 390 : 1280,height:900});
  const date="2026-10-29";
  let item:null|{id:string;revision:number;status:string;date:string;worker_name:string;project_name:string;is_test:boolean;reason:string;recruitment_version_id:string|null}=null;
  let sent=0,decisions=0;
  const people=["候補の方A","候補の方B","候補の方C"].map((name,i)=>({id:`w${i}`,name,availability:"available_all_day",line_linked:true}));
  const profile={id:"test",username:"test",name:"試験運営",display_name:"試験運営",role:"admin",is_active:true,permissions:mode === "line" ? {wake:true,orders:true,availability:true,staffing:true} : ["wake_status_read","order_read","order_write"]};
  if(mode === "admin") await page.addInitScript(()=>localStorage.setItem("vanzai.admin.access_token","mock-admin-token"));
  await page.route("https://static.line-scdn.net/liff/edge/2/sdk.js",r=>r.fulfill({contentType:"application/javascript",body:"window.liff={init:async()=>{},isLoggedIn:()=>true,login:()=>{},getIDToken:()=> 'proof'};"}));
  await page.route("**/api/**",async route=>{
    let path=new URL(route.request().url()).pathname;
    if(!path.startsWith("/api/")) return route.continue();
    const respond=(json:unknown)=>route.fulfill({json});
    if(path.endsWith("/operator-registration/entry")) return respond({enabled:true,liff_id:"2011980694-test"});
    if(path.endsWith("/operator/session")) return respond({token:"operator-token"});
    if(path.endsWith("/auth/me") || path.endsWith("/operator/me")) return respond(profile);
    if(path.endsWith("/auth/session")) return respond({access_token:"mock-admin-token",token_type:"bearer"});
    if(path.endsWith("/wake-status")) return respond({date,is_today:true,total:item?0:1,reported:0,items:item?[]:[{worker_id:"original",worker_name:"元の担当者",first_start:"09:00",wake_reported_at:null,next_action:{step:"call",label:"電話する",priority:2},handler:null,last_result:null,contacts:[],entries:[{id:"entry1",document_id:"d1",project_name:"駅前イベント",site_name:"会場",start_time:"09:00",end_time:"18:00",status:"active",is_test:false}]}]});
    if(path.includes("staffing-replacements") || path.includes("order-staffing")) {
      if(mode === "line") expect(route.request().headers().authorization).toBe("Bearer operator-token");
      path=path.replace("/api/line/operator/","/api/");
    }
    if(path === "/api/staffing-replacements/entries/entry1") return respond({entry_id:"entry1",date,worker_name:"元の担当者",project_name:"駅前イベント",is_test:false,guard:"1".repeat(64)});
    if(path === "/api/staffing-replacements" && route.request().method() === "POST") {
      item={id:"vacancy1",revision:0,status:"open",date,worker_name:"元の担当者",project_name:"駅前イベント",is_test:false,reason:"欠勤を確認",recruitment_version_id:null}; return respond(item);
    }
    if(path === "/api/staffing-replacements") return respond({items:item?[item]:[]});
    if(path === "/api/staffing-replacements/vacancy1") return respond(item);
    if(path.endsWith("/vacancy1/candidates")) return respond({items:people});
    if(path.endsWith("/vacancy1/recruit")) {item={...item!,revision:1,status:"recruiting",recruitment_version_id:"recruit1"};return respond(item);}
    if(path.endsWith("/vacancy1/invitation")) return respond({body:"駅前イベント\n2026/10/29 09:00〜18:00\n参加可否をご回答ください。",notifications_enabled:true,recipients:people.map(p=>({name:p.name,send_status:sent?"accepted":"unsent",ack_status:"unacked"}))});
    if(path.endsWith("/vacancy1/send")) {sent+=1;return respond({sent:3,remaining:0,unknown:0,vacancy:item});}
    if(path === "/api/order-staffing/recruit1") return respond({enabled:true,revision:0,is_test:false,is_replacement:true,days:[{date,capacity:1,confirmed:decisions?1:0,confirmed_ids:decisions?["w0"]:[],closed:!!decisions}],people:people.map(p=>({...p,worker_id:p.id,available:true,offered_dates:[date],accepted_dates:sent?[date]:[],ack_status:sent?"acked":"unacked",send_status:sent?"accepted":"unsent"})),notices:decisions?[{status:"sent"},{status:"sent"},{status:"sent"}]:[]});
    if(path.endsWith("/recruit1/decisions")) {expect(route.request().postDataJSON().selected).toEqual({[date]:["w0"]});decisions+=1;item={...item!,status:"filled"};return respond({});}
    return respond({items:[],total:0});
  });
  await page.goto(mode === "line" ? "/public/line-operator-registration?m=wake" : "/operations/wake-status");
  await page.getByRole("button",{name:"別人員を確保する",exact:true}).click();
  const dialog=page.getByRole("dialog",{name:"欠員・代替人員の手配"});
  await dialog.getByLabel("欠員にする理由",{exact:true}).fill("欠勤を確認");
  await dialog.getByRole("button",{name:"欠員として、この日の予定から外す"}).click();
  await expect(dialog.getByText("候補の方A",{exact:false})).toBeVisible();
  for(const name of people.map(p=>p.name)) await dialog.getByRole("checkbox",{name:new RegExp(name)}).check();
  await dialog.getByRole("button",{name:"打診する内容を確認"}).click();
  await page.screenshot({path:`../../.work/replacement-${mode}-review.png`,fullPage:true});
  await dialog.getByRole("button",{name:"この内容で募集を作成"}).click();
  expect(sent).toBe(0);
  await dialog.getByRole("button",{name:"募集の内容・送付先を確認"}).click();
  await expect(dialog.getByText("送付先：",{exact:false})).toBeVisible();
  expect(sent).toBe(0);
  await dialog.getByRole("button",{name:"この内容で募集のLINEを送る"}).click();
  await expect(dialog.getByRole("status")).toContainText("送信済み 3件");
  await dialog.getByRole("button",{name:"参加者・日別人数を確認"}).click();
  const selection=page.getByRole("dialog",{name:"参加者の最終確定"});
  await selection.getByRole("checkbox",{name:/候補の方A/}).check();
  await selection.getByRole("button",{name:"確定内容を確認",exact:true}).click();
  await selection.getByRole("button",{name:"この内容で確定・通知する"}).click();
  await expect(selection.getByText("参加者を確定しました。通知結果を下で確認してください。",{exact:true})).toContainText("参加者を確定しました");
  expect(decisions).toBe(1);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
