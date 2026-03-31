(function(){
  'use strict';
  var CONFIG={"cards":[{"label":"請求書","description":"請求書の発行/確認","env_key":"KINTONE_APP_INVOICES","category":"billing","allow_add":true,"add_label":"新規追加","app_id":"171","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/171/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/171/edit"},{"label":"支払明細","description":"稼働者への支払明細","env_key":"KINTONE_APP_PAYOUTS","category":"billing","allow_add":true,"add_label":"新規追加","app_id":"173","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/173/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/173/edit"},{"label":"支払明細送信","description":"送信履歴/状況","env_key":"KINTONE_APP_PAYOUT_DELIVERIES","category":"billing","allow_add":false,"add_label":"新規追加","app_id":"","enabled":false,"href":"#","add_href":""},{"label":"銀行振込","description":"全銀フォーマット作成","env_key":"KINTONE_APP_BANK_TRANSFERS","category":"billing","allow_add":false,"add_label":"新規追加","app_id":"","enabled":false,"href":"#","add_href":""},{"label":"稼働者マスタ","description":"稼働者の登録/更新","env_key":"KINTONE_APP_WORKERS","category":"master","allow_add":true,"add_label":"新規追加","app_id":"165","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/165/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/165/edit"},{"label":"クライアント職員","description":"クライアント先の職員（責任者/担当者など）","env_key":"KINTONE_APP_STAFF_MANAGERS","category":"master","allow_add":true,"add_label":"新規追加","app_id":"309","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/309/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/309/edit"},{"label":"VANZAI職員","description":"自社職員の登録/更新","env_key":"KINTONE_APP_VANZAI_STAFF","category":"internal","allow_add":true,"add_label":"職員を登録","app_id":"313","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/313/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/313/edit"},{"label":"クライアント","description":"クライアント情報の管理","env_key":"KINTONE_APP_CLIENTS","category":"master","allow_add":true,"add_label":"新規追加","app_id":"167","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/167/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/167/edit"},{"label":"案件種別","description":"案件種別マスタ","env_key":"KINTONE_APP_PROJECT_TYPES","category":"master","allow_add":true,"add_label":"新規追加","app_id":"164","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/164/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/164/edit"},{"label":"下請け（紹介者）","description":"suppliersマスタ","env_key":"KINTONE_APP_SUPPLIERS","category":"master","allow_add":true,"add_label":"新規追加","app_id":"199","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/199/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/199/edit"},{"label":"単価管理","description":"売上単価・外注単価・単価ルール","env_key":"KINTONE_APP_PRICE_RULES","category":"master","allow_add":false,"add_label":"新規追加","app_id":"157","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/157/","add_href":""},{"label":"現場","description":"現場/サイト情報","env_key":"KINTONE_APP_SITES","category":"field","allow_add":true,"add_label":"新規追加","app_id":"166","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/166/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/166/edit"},{"label":"案件","description":"案件マスタ","env_key":"KINTONE_APP_PROJECTS","category":"field","allow_add":true,"add_label":"新規追加","app_id":"160","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/160/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/160/edit"},{"label":"案件登録（カテゴリ分け）","description":"案件登録・担当/スタッフ登録の起点","env_key":"KINTONE_APP_PROJECT_ASSIGNMENTS","category":"field","allow_add":true,"add_label":"新規追加","app_id":"307","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/307/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/307/edit"},{"label":"シフト管理","description":"シフト枠/アサイン","env_key":"KINTONE_APP_SHIFT_SLOTS","category":"field","allow_add":true,"add_label":"新規追加","app_id":"159","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/159/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/159/edit"},{"label":"実績管理","description":"CSV取り込み/実績確認","env_key":"KINTONE_APP_ACTUALS","category":"field","allow_add":true,"add_label":"新規追加","app_id":"168","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/168/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/168/edit"},{"label":"登録ダッシュボード","description":"フロント（登録/確認）","env_key":"KINTONE_APP_FRONT_DASHBOARD","category":"field","allow_add":false,"add_label":"","app_id":"174","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/174/","add_href":""},{"label":"経費精算","description":"経費申請/承認","env_key":"KINTONE_APP_EXPENSES","category":"other","allow_add":true,"add_label":"新規追加","app_id":"151","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/151/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/151/edit"},{"label":"インセンティブ","description":"インセンティブ支給","env_key":"KINTONE_APP_INCENTIVES","category":"other","allow_add":true,"add_label":"新規追加","app_id":"150","enabled":true,"href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/150/","add_href":"https://xtf5wpxp3gk2.cybozu.com/k/guest/3/150/edit"},{"label":"タスク進捗","description":"案件タスクとアラート","env_key":"KINTONE_APP_TASKS","category":"other","allow_add":true,"add_label":"新規追加","app_id":"","enabled":false,"href":"#","add_href":""},{"label":"案件資料","description":"案件説明資料","env_key":"KINTONE_APP_PROJECT_DOCUMENTS","category":"other","allow_add":true,"add_label":"新規追加","app_id":"","enabled":false,"href":"#","add_href":""},{"label":"貸出備品","description":"備品マスタ/貸出","env_key":"KINTONE_APP_EQUIPMENT","category":"other","allow_add":true,"add_label":"新規追加","app_id":"","enabled":false,"href":"#","add_href":""},{"label":"貸出備品（貸出）","description":"備品貸出履歴","env_key":"KINTONE_APP_EQUIPMENT_LOANS","category":"other","allow_add":true,"add_label":"新規追加","app_id":"","enabled":false,"href":"#","add_href":""}]};

  function el(tag, attrs, children){
    var node=document.createElement(tag);
    if(attrs){
      Object.keys(attrs).forEach(function(k){
        if(k==='class') node.className=attrs[k];
        else if(k==='text') node.textContent=attrs[k];
        else if(k==='html') node.innerHTML=attrs[k];
        else node.setAttribute(k, attrs[k]);
      });
    }
    if(children){
      children.forEach(function(c){
        if(c==null) return;
        node.appendChild(typeof c==='string'?document.createTextNode(c):c);
      });
    }
    return node;
  }

  function buildCard(card){
    var cardClass='vf-card vf-cat-'+card.category + (card.enabled?'':' vf-disabled');
    var title=el('div',{class:'vf-card-title',text:card.label});
    var desc=el('div',{class:'vf-card-desc',text:card.description});

    var actions=el('div',{class:'vf-card-actions'});
    var listBtn=el('a',{class:'vf-btn',href:card.enabled?card.href:'#',text:'一覧を開く'});
    listBtn.style.display='inline-flex';
    listBtn.style.alignItems='center';
    listBtn.style.gap='6px';
    listBtn.style.padding='6px 10px';
    listBtn.style.borderRadius='999px';
    listBtn.style.background='#2a5bd7';
    listBtn.style.color='#fff';
    listBtn.style.textDecoration='none';
    listBtn.style.fontSize='12px';
    if(!card.enabled){ listBtn.setAttribute('aria-disabled','true'); }
    actions.appendChild(listBtn);

    if(card.add_href){
      var addBtn=el('a',{class:'vf-btn vf-secondary',href:card.add_href,text:card.add_label||'新規追加'});
      addBtn.style.display='inline-flex';
      addBtn.style.alignItems='center';
      addBtn.style.gap='6px';
      addBtn.style.padding='6px 10px';
      addBtn.style.borderRadius='999px';
      addBtn.style.background='#0f766e';
      addBtn.style.color='#fff';
      addBtn.style.textDecoration='none';
      addBtn.style.fontSize='12px';
      actions.appendChild(addBtn);
    }else if(card.allow_add){
      var disabledBtn=el('a',{class:'vf-btn vf-secondary vf-disabled',href:'#',text:'未設定'});
      disabledBtn.style.display='inline-flex';
      disabledBtn.style.alignItems='center';
      disabledBtn.style.gap='6px';
      disabledBtn.style.padding='6px 10px';
      disabledBtn.style.borderRadius='999px';
      disabledBtn.style.background='#cbd5e1';
      disabledBtn.style.color='#fff';
      disabledBtn.style.textDecoration='none';
      disabledBtn.style.fontSize='12px';
      actions.appendChild(disabledBtn);
    }

    var badge=el('div',{class:'vf-card-badge',text:card.enabled?'Open':'未設定'});
    return el('div',{class:cardClass},[title,desc,actions,badge]);
  }

  function init(){
    var root=document.getElementById('vanzai-front-root');
    if(!root){
      var mount=document.querySelector('.gaia-argoui-app-index')||document.querySelector('.contents-gaia')||document.body;
      root=el('div',{id:'vanzai-front-root'});
      mount.appendChild(root);
    }
    if(root.dataset.vanzaiFrontInitialized==='1') return;
    root.dataset.vanzaiFrontInitialized='1';

    var container=el('div',{class:'vanzai-front'});
    var header=el('div',{class:'vf-header'});
    header.appendChild(el('h1',{class:'vf-h1',html:'VANZAI Portal Page <span style="font-size:14px;font-weight:500;color:#bfdbfe;">- 仮運用開始日：2026年2月～</span>'}));

    var main=el('div',{class:'vf-main'});
    var grid=el('div',{class:'vf-grid'});
    (CONFIG.cards||[]).forEach(function(c){ grid.appendChild(buildCard(c)); });

    main.appendChild(grid);

    container.appendChild(header);
    container.appendChild(main);
    root.appendChild(container);
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init);
  else init();
  try{ if(window.kintone && kintone.events && kintone.events.on) kintone.events.on('portal.show', init); }catch(e){}
})();
